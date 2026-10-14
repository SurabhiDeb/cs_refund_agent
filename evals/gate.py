"""The gate. CI fails if the shipping configuration regresses.

The run is pinned here on purpose. Reading the newest file would mean the
last experiment you happened to run becomes the thing you ship, which is
how a gate quietly stops gating.

    uv run python -m evals.gate
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RUNS = Path(__file__).resolve().parents[1] / "evals" / "runs"

# The shipping configuration. Change this line deliberately, never by glob.
SHIPPING_SCORE = "20261014-153153Z-v2-score.json"

# Floors, set from the v2 result at Beat 7. A future run may do better. It
# may not do worse.
MIN_STATE_MATCH = 0.74  # the lower bound of the v2 interval
MAX_OVERPAID_MINOR = 8400
MAX_UNDERPAID_MINOR = 19599


def main() -> int:
    score = json.loads((RUNS / SHIPPING_SCORE).read_text())
    cases = score["cases"]
    total = len(cases)

    passed = sum(1 for c in cases if c["state_match"])
    rate = passed / total
    overpaid = sum(max(0, c["wrote"] - c["expected_delta"]) for c in cases)
    underpaid = sum(max(0, c["expected_delta"] - c["wrote"]) for c in cases)

    failures: list[str] = []
    if rate < MIN_STATE_MATCH:
        failures.append(f"state match {rate:.1%} below floor {MIN_STATE_MATCH:.1%}")
    if overpaid > MAX_OVERPAID_MINOR:
        failures.append(f"overpaid {overpaid} above ceiling {MAX_OVERPAID_MINOR}")
    if underpaid > MAX_UNDERPAID_MINOR:
        failures.append(f"underpaid {underpaid} above ceiling {MAX_UNDERPAID_MINOR}")

    print(f"gating {SHIPPING_SCORE}")
    print(f"  prompt      {score['provenance']['prompt_version']}")
    print(f"  state match {passed} of {total}, {rate:.1%}")
    print(f"  overpaid    {overpaid}")
    print(f"  underpaid   {underpaid}")

    if failures:
        print()
        for line in failures:
            print(f"  BLOCKED, {line}")
        return 1

    print()
    print("  gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
