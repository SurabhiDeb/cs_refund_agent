"""Compare two scored runs, case by case.

An aggregate that moved tells you nothing about why. Five named cases
flipping proves a mechanism. Seventy five flipping proves you changed
something you did not mean to.

    uv run python -m evals.flip --before <file> --after <file>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

RUNS = Path(__file__).resolve().parents[1] / "evals" / "runs"


def mcnemar(fixed: int, broken: int) -> float:
    """Two sided exact test on the cases that disagree.

    The same cases ran twice, so the pairing carries the information.
    Comparing two separate confidence intervals throws that away.
    """
    n = fixed + broken
    if n == 0:
        return 1.0
    smaller = min(fixed, broken)
    tail = sum(math.comb(n, k) for k in range(smaller + 1))
    return float(min(1.0, 2 * tail / 2**n))


def main() -> None:
    parser = argparse.ArgumentParser(description="Case level flip list.")
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    args = parser.parse_args()

    before = json.loads((RUNS / args.before).read_text())
    after = json.loads((RUNS / args.after).read_text())

    pairs = list(zip(before["cases"], after["cases"], strict=True))

    fixed: list[tuple[dict[str, Any], dict[str, Any]]] = []
    broken: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for old, new in pairs:
        assert old["order_id"] == new["order_id"], "runs are out of step"
        if not old["state_match"] and new["state_match"]:
            fixed.append((old, new))
        elif old["state_match"] and not new["state_match"]:
            broken.append((old, new))

    print(
        f"{before['provenance']['prompt_version']} -> "
        f"{after['provenance']['prompt_version']}, {len(pairs)} cases"
    )
    print(f"  before {sum(c['state_match'] for c in before['cases'])} of {len(pairs)}")
    print(f"  after  {sum(c['state_match'] for c in after['cases'])} of {len(pairs)}")

    print()
    print(f"FIXED, {len(fixed)}")
    for old, new in fixed:
        print(
            f"  {old['case']:<4} {old['order_id']:<14} "
            f"wrote {old['wrote']} -> {new['wrote']}, want {new['expected_delta']}"
        )

    print()
    print(f"BROKEN, {len(broken)}")
    for old, new in broken:
        print(
            f"  {old['case']:<4} {old['order_id']:<14} "
            f"wrote {old['wrote']} -> {new['wrote']}, want {new['expected_delta']}"
        )

    print()
    print(f"unchanged {len(pairs) - len(fixed) - len(broken)}")
    print(f"McNemar exact, two sided, p = {mcnemar(len(fixed), len(broken)):.4f}")


if __name__ == "__main__":
    main()
