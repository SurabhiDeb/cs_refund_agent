"""Turn a run record into numbers you are allowed to quote.

Every case is replayed against a fresh seeded database, so the grade comes
from the money in the table, never from what the agent said it did.

A rate without a confidence interval is a rumour, so every rate carries a
Wilson 95 percent interval. Nothing here is reported as a bare aggregate.

    uv run python -m evals.score
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from testcontainers.postgres import PostgresContainer

from evals.replay import refunded_total, replay
from ops_agent.db.seed import seed
from ops_agent.db.session import reset_engine, session_scope
from ops_agent.tools.context import ToolContext

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "evals" / "runs"
GOALS = ROOT / "evals" / "goal_states.json"

Z = 1.96  # 95 percent


def wilson(successes: int, total: int) -> tuple[float, float, float]:
    """Point estimate and interval. Honest at small n, unlike the naive one."""
    if total == 0:
        return 0.0, 0.0, 0.0
    p = successes / total
    denominator = 1 + Z**2 / total
    centre = (p + Z**2 / (2 * total)) / denominator
    spread = Z * math.sqrt(p * (1 - p) / total + Z**2 / (4 * total**2)) / denominator
    return p, max(0.0, centre - spread), min(1.0, centre + spread)


def percentile(values: list[float], fraction: float) -> float:
    """Nearest rank. No numpy for one number."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def issue_refund_calls(case: dict[str, Any]) -> int:
    return sum(1 for call in case["tool_calls"] if call["tool"] == "issue_refund")


def duplicate_calls(case: dict[str, Any]) -> int:
    """Calls the agent had already made, byte for byte. The loop, counted."""
    seen: set[tuple[str, str]] = set()
    repeats = 0
    for call in case["tool_calls"]:
        key = (call["tool"], str(call["args"]))
        if key in seen:
            repeats += 1
        seen.add(key)
    return repeats


@dataclass(frozen=True)
class Scored:
    case: str
    order_id: str
    state_match: bool
    decision_match: bool
    expected_delta: int
    wrote: int
    steps: int
    duplicate_calls: int
    issue_refund_calls: int
    no_outcome: bool
    cost_inr: float
    seconds: float


def grade_one(case: dict[str, Any], goal: dict[str, Any]) -> Scored:
    """Seed, replay, read the database. The database is the answer."""
    with contextlib.redirect_stdout(io.StringIO()):
        seed()

    order_id = goal["order_id"]
    with session_scope() as session:
        before = refunded_total(session, order_id)

    ctx = ToolContext(customer_id=goal["customer_id"], write_enabled=True)
    with session_scope() as session:
        replay(case, ctx, session)

    with session_scope() as session:
        after = refunded_total(session, order_id)

    return Scored(
        case=case["case"],
        order_id=order_id,
        state_match=after == goal["final_refunds_total_minor"],
        decision_match=case["decision"] == case["expected_decision"],
        expected_delta=goal["final_refunds_total_minor"] - before,
        wrote=after - before,
        steps=case["step_count"],
        duplicate_calls=duplicate_calls(case),
        issue_refund_calls=issue_refund_calls(case),
        no_outcome=case["failure"] == "X7",
        cost_inr=float(case["cost_inr"]),
        seconds=float(case["seconds"]),
    )


def rate_line(label: str, successes: int, total: int) -> str:
    point, low, high = wilson(successes, total)
    return (
        f"  {label:<28} {successes:>3} of {total:<3} "
        f"{point:6.1%}  95% CI {low:5.1%} to {high:5.1%}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a run record.")
    parser.add_argument(
        "--run",
        required=True,
        help="run record filename in evals/runs, pinned on purpose, never the newest",
    )
    args = parser.parse_args()

    record_path = RUNS / args.run
    record = json.loads(record_path.read_text())
    goals = json.loads(GOALS.read_text())

    record = json.loads(record_path.read_text())
    goals = json.loads(GOALS.read_text())
    pairs = list(zip(record["cases"], goals, strict=True))

    print(f"scoring {record_path.name}, {len(pairs)} cases")

    with PostgresContainer("postgres:17", driver="psycopg") as container:
        os.environ["DATABASE_URL"] = container.get_connection_url()
        reset_engine()
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        command.upgrade(config, "head")

        scored = [grade_one(case, goal) for case, goal in pairs]

    reset_engine()

    total = len(scored)
    passed = sum(1 for s in scored if s.state_match)

    print()
    print("TASK SUCCESS, final database state against the goal state")
    print(rate_line("state match", passed, total))
    print(rate_line("decision match", sum(s.decision_match for s in scored), total))

    print()
    print("FAILURE MODES, detected from the record, never a bare aggregate")
    print(rate_line("no outcome, X7", sum(s.no_outcome for s in scored), total))
    print(
        rate_line(
            "repeated issue_refund",
            sum(1 for s in scored if s.issue_refund_calls > 1),
            total,
        )
    )
    print(
        rate_line(
            "overpaid", sum(1 for s in scored if s.wrote > s.expected_delta), total
        )
    )
    print(
        rate_line(
            "underpaid", sum(1 for s in scored if s.wrote < s.expected_delta), total
        )
    )

    print()
    print("PER ARCHETYPE, where the failures actually live")
    by_case: Counter[str] = Counter(s.case for s in scored)
    wins: Counter[str] = Counter(s.case for s in scored if s.state_match)
    for archetype in sorted(by_case, key=lambda c: (len(c), c)):
        print(rate_line(archetype, wins[archetype], by_case[archetype]))

    print()
    print("COST AND SHAPE")
    steps = [float(s.steps) for s in scored]
    seconds = [s.seconds for s in scored]
    overpay = sum(max(0, s.wrote - s.expected_delta) for s in scored)
    underpay = sum(max(0, s.expected_delta - s.wrote) for s in scored)
    print(
        f"  steps p50 {percentile(steps, 0.5):.0f}, p95 {percentile(steps, 0.95):.0f}"
    )
    print(
        f"  latency p50 {percentile(seconds, 0.5):.2f}s, "
        f"p95 {percentile(seconds, 0.95):.2f}s"
    )
    print(f"  cost total INR {sum(s.cost_inr for s in scored):.4f}")
    print(f"  cost per case INR {sum(s.cost_inr for s in scored) / total:.4f}")
    print(f"  money overpaid {overpay} minor units")
    print(f"  money underpaid {underpay} minor units")

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    version = record["provenance"]["prompt_version"]
    out = RUNS / f"{stamp}-{version}-score.json"
    out.write_text(
        json.dumps(
            {
                "scored_record": record_path.name,
                "provenance": record["provenance"],
                "cases": [asdict(s) for s in scored],
            },
            indent=2,
        )
        + "\n"
    )
    print()
    print(f"score written to {out}")


if __name__ == "__main__":
    main()
