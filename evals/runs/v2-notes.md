# v2 result

Prompt v2 against prompt v1, same 70 cases, same dataset, same grading code.
v1 record 20261011-161141Z-v1.json, score 20261014-153144Z-v1-score.json.
v2 record 20261014-152051Z-v2.json, score 20261014-153153Z-v2-score.json.

## Headline

| Metric | v1 | v2 |
|---|---|---|
| State match | 47 of 70, 67.1%, CI 55.5 to 77.0 | 59 of 70, 84.3%, CI 74.0 to 91.0 |
| Decision match | 32 of 70 | 41 of 70 |
| No outcome, X7 | 31 of 70 | 29 of 70 |
| Repeated issue_refund | 11 of 70 | 17 of 70 |
| Money overpaid | 33200 | 8400 |
| Money underpaid | 28299 | 19599 |
| Steps p50, p95 | 12 and 25 | 10 and 23 |
| Cost per case | INR 0.1714 | INR 0.1836 |

The two intervals overlap between 74.0 and 77.0, so comparing them is the
weak reading. The same 70 cases ran twice, so the pairing carries the
information. McNemar exact, two sided, 15 fixed against 3 broken, p = 0.0075.

## Not one variable

Three things changed together, for budget reasons rather than design.

1. prompts/v2.md, which adds facts from tools, the eligibility list, the
   distress rule, and the instruction to finish.
2. runner.py now puts the pinned date into the user turn.
3. R5 and R8 are enforced in code, landed before the run.

So no single sentence can be credited. The archetype breakdown gives partial
attribution because the modes live in different archetypes.

## Fixed, 15 cases

| Case | Order | Before | After | Wanted |
|---|---|---|---|---|
| C1 | ord_C1_10 | 0 | 3200 | 3200 |
| C2 | ord_C2_01 | 2800 | 0 | 0 |
| C2 | ord_C2_02 | 2800 | 0 | 0 |
| C2 | ord_C2_05 | 2800 | 0 | 0 |
| C3 | ord_C3_01 | 4100 | 0 | 0 |
| C3 | ord_C3_02 | 4100 | 0 | 0 |
| C3 | ord_C3_04 | 4100 | 0 | 0 |
| C3 | ord_C3_06 | 4100 | 0 | 0 |
| C6 | ord_C6_03 | 0 | 2500 | 2500 |
| C6 | ord_C6_04 | 0 | 2500 | 2500 |
| C7 | ord_C7_03 | 0 | 500 | 500 |
| C7 | ord_C7_04 | 0 | 500 | 500 |
| C14 | ord_C14_01 | 0 | 2600 | 2600 |
| C14 | ord_C14_02 | 0 | 2600 | 2600 |
| C15 | ord_C15_03 | 0 | 2900 | 2900 |

Three mechanisms, each traceable to a change.

- C2 and C3, seven cases, stopped paying and started refusing. That is M3.
  The agent now reads status and delivered_at and lets the record win over
  the customer's sentence.
- C14, two cases, could not be fixed by wording at all. The 30 day window
  needs today's date, and the date only reached the agent in this run.
- C1_10, C6, C7 and C15_03 moved from talking about a refund to writing one.
  That is the finish rule plus R8.

## Broken, 3 cases

| Case | Order | Before | After | Wanted |
|---|---|---|---|---|
| C1 | ord_C1_03 | 3200 | 0 | 3200 |
| C6 | ord_C6_01 | 2500 | 0 | 2500 |
| C15 | ord_C15_02 | 2900 | 0 | 2900 |

All three are X7, the step limit, not a wrong refusal. The new eligibility
wording is not being read too strictly. These are the old loop.

There is a cost hidden here. In v1 the loop cycled one policy topic. In v2
C1_03 and C15_02 cycle `damaged` and `window`, because the eligibility list
gave the agent a second thing to check. The rule that fixed seven cases also
gave the loop more to chew on. M1 is now the dominant mode and the clear v3
candidate.

Underpaying a customer is a smaller harm than overpaying one, but it is a
harm. Three customers would be told to wait for a human who should have been
paid on the spot.

## Against the targets set at Beat 6

| Target | Result |
|---|---|
| Task success point estimate above 80% | hit, 84.3% |
| No outcome below 10% | missed, 41.4% |
| Repeated issue_refund zero | missed, 17 of 70, but no money escaped |
| Money overpaid below 5000 | missed, 8400 |
| Steps p95 below 15 | missed, 23 |
| Cost per case no worse than INR 0.20 | hit, INR 0.1836 |
| Latency p95 below 15s | hit, 13.48s |
| Unauthorised writes, over cap, over remainder | all zero |

One of four quality targets hit. Say that out loud rather than quoting only
the task success number.

## The line worth keeping

Repeated `issue_refund` attempts went up, 11 to 17, and money overpaid fell
from 33200 to 8400. The agent tries to double pay more often than it used
to, and it fails, because R5 is enforced in `issue_refund` rather than asked
for in the prompt.

That is rule 9 demonstrated on real data. A prompt is advice. A guard is a
rule.

## v3 candidate, one variable

M1, the loop. 29 of 70 runs still end at the step limit with no answer, and
it is now the only mode costing double digits. Nothing else should change in
the same run.
