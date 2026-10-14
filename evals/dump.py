"""Read a run record into something a person can actually read."""

import json
import pathlib

RUNS = pathlib.Path("evals/runs")
path = sorted(RUNS.glob("*-v1.json"))[-1]
data = json.loads(path.read_text())

lines = []
for case in data["cases"]:
    lines.append(f"=== {case['case']}  {case['order_id']}")
    lines.append(f"    ask      {case['request']}")
    lines.append(
        f"    want     {case['expected_decision']} / "
        f"{case['expected_reason']} / refund {case['expected_refund_minor']}"
    )
    lines.append(
        f"    got      {case['decision']} / "
        f"{case['reason_code']} / wrote {case['refund_written_minor']}"
    )
    lines.append(f"    failure  {case['failure']}")
    for i, call in enumerate(case["tool_calls"], 1):
        lines.append(f"      {i:>2}. {call['tool']}  {str(call['args'])[:200]}")
    lines.append("")

out = RUNS / "v1-trajectories.txt"
out.write_text("\n".join(lines))
print(f"read {path.name}, {len(data['cases'])} cases")
print(f"wrote {out}")
