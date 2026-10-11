"""Run the evaluation and write a run record.

You choose how many cases to spend on. Nothing here runs the full set
unless you ask for it.

    uv run python evals/run.py --cases 3
    uv run python evals/run.py --cases 70 --max-cost-inr 15

The spend guard stops the run once cumulative cost passes --max-cost-inr,
so a mistake costs a few paise rather than the whole balance.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ops_agent.agent.runner import Provenance, run_case
from ops_agent.db.seed import seed
from ops_agent.db.session import session_scope

ROOT = Path(__file__).resolve().parents[1]
GOALS = ROOT / "evals" / "goal_states.json"
RUNS = ROOT / "evals" / "runs"

# Front loaded with different outcomes on purpose, so a three case run
# exercises a refund, an escalation, and an authorisation refusal rather
# than three variations of the same path.
ARCHETYPE_ORDER = [
    "C1",
    "C9",
    "C12",
    "C5",
    "C7",
    "C11",
    "C14",
    "C15",
    "C16",
    "C2",
    "C3",
    "C4",
    "C6",
    "C8",
    "C10",
    "C13",
]


def select(goals: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Small runs take one case per archetype. Large runs take everything."""
    first_of_each: dict[str, dict[str, Any]] = {}
    for goal in goals:
        first_of_each.setdefault(goal["case"], goal)
    spread = [first_of_each[case] for case in ARCHETYPE_ORDER if case in first_of_each]
    if count <= len(spread):
        return spread[:count]
    return goals[:count]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OpsAgent evaluation.")
    parser.add_argument("--cases", type=int, default=3, help="how many cases to run")
    parser.add_argument("--prompt", default="v1", help="prompt version, e.g. v1")
    parser.add_argument(
        "--max-cost-inr",
        type=float,
        default=5.0,
        help="stop the run once this much has been spent",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="ignore cached runs and pay again"
    )
    parser.add_argument(
        "--no-write", action="store_true", help="throw the kill switch, no refunds"
    )
    args = parser.parse_args()

    goals: list[dict[str, Any]] = json.loads(GOALS.read_text())
    chosen = select(goals, args.cases)

    print(
        f"Reseeding, then running {len(chosen)} cases "
        f"on prompt {args.prompt}, guard INR {args.max_cost_inr}"
    )
    seed()

    provenance = Provenance.build(args.prompt)
    records: list[dict[str, Any]] = []
    spent = 0.0
    stopped_early = False

    for goal in chosen:
        # A session per case, so each case commits on its own.
        with session_scope() as session:
            record = run_case(
                goal,
                prompt_version=args.prompt,
                session=session,
                write_enabled=not args.no_write,
                provenance=provenance,
                use_cache=not args.no_cache,
            )

        records.append(record)
        spent += float(record["cost_inr"])
        tag = (
            "cached"
            if record["replayed_from_cache"]
            else f"INR {record['cost_inr']:.4f}"
        )

        wrote = record["refund_written_minor"]
        print(
            f"  {record['case']:>4} {record['order_id']:<14} "
            f"want {record['expected_decision']:<9} got {record['decision']:<9} "
            f"steps {record['step_count']:<2} wrote {wrote:<5} {tag}"
        )

        if spent > args.max_cost_inr:
            stopped_early = True
            print(f"  STOPPED. Spend guard of INR {args.max_cost_inr} reached.")
            break

    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    path = RUNS / f"{stamp}-{args.prompt}.json"
    path.write_text(
        json.dumps(
            {
                "provenance": asdict(provenance),
                "stopped_early": stopped_early,
                "cases": records,
            },
            indent=2,
        )
        + "\n"
    )

    paid = [r for r in records if not r["replayed_from_cache"]]
    matched = sum(1 for r in records if r["decision"] == r["expected_decision"])

    print()
    print(f"cases run        {len(records)}")
    print(f"paid for         {len(paid)}")
    print(f"total cost       INR {spent:.4f}")
    if paid:
        print(f"cost per case    INR {spent / len(paid):.4f}")
        print(f"all 70 would be  INR {spent / len(paid) * 70:.2f}")
    print(f"decision matches {matched} of {len(records)}")
    print()
    print("Decision match is a rough signal, not the score. The real grading")
    print("compares the final database state, and arrives at Beat 6.")
    print(f"record written to {path}")


if __name__ == "__main__":
    main()
