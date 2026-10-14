# v1 error analysis

Prompt v1, 70 cases, run record `20261011-161141Z-v1.json`.
Read by hand from `v1-trajectories.txt`. No eval code exists yet.

## Failure modes

| Mode | What it is | Count | Agent, label, or spec |
|---|---|---|---|
| M1 | Never produces the Outcome, re-reads the same tools until the step limit | 31 | agent |
| M2 | Calls issue_refund again with a new idempotency key | 11 | agent, plus R5 unenforced in code |
| M3 | Pays on the customer's word against the order record | 10 | agent, v1 never states the rules |
| M4 | Says refund, never calls issue_refund, database unchanged | 4 | agent |
| M5 | Refuses instead of paying the remainder it is allowed to pay | 1 | agent |
| M6 | Treats a tool refusal as a retryable error instead of an answer | 7 | agent, with a spec tension |
| M7 | Does not notice distress | 3 | agent |

M1 and M6 overlap, since a case that keeps retrying also ends at the step
limit. M6 names the cause, M1 names the symptom.

## M1, no Outcome, 31 cases

C1_01, C1_04, C1_06, C2_06, C3_05, C4_01, C4_02, C4_03, C4_04, C5_01,
C6_02, C6_03, C6_04, C7_02, C7_03, C7_04, C8_02, C9_01, C11_01, C11_03,
C12_01, C12_02, C12_03, C12_04, C13 x3, C15_03, C16_01, C16_02, C16_03.

The agent does the right work, then neither reports nor stops. The runner
correctly defaults these to escalate X7, which is fail safe, so the record
is honest and the agent is not.

## M2, repeated write, 11 cases

Where the key changed and the order had remainder left, the second write
landed. C11_01 paid 6000 on a 2000 claim. C11_03 and C11_04 paid 4000 each.
8000 minor units overpaid. The E4 remainder check did not stop it because
the remainder was large.

Where the agent reused the same key it was a correct no-op, C1_05, C1_06,
C15_01. Where remainder was exhausted, E4 refused it, C1_01, C1_03, C1_04,
C2_06.

R5, one issue_refund per conversation, lives only in SPEC. Nothing in code
enforces it.

## M3, acted on the claim, 10 cases, most expensive

All six C2 are outside the 30 day window and every one was paid.
Four of six C3 were never delivered and were paid, C3_01, C3_02, C3_04,
C3_06. 33200 minor units paid against policy.

The agent read delivered_at and status, saw item condition recorded as good,
and refunded on the customer's sentence. This is R1 and E2 and E3 all at
once, and v1 states none of them.

## M4, phantom refund, 4 cases

C1_10, C6_05, C14_01, C14_02. Decision refund with the correct amount, no
issue_refund call, database unchanged. A customer is told they are paid and
they are not. R8.

## M5, refused its own remainder, 1 case

C7_01. Asked for 3500, tool refused with E4, only 500 was refundable. The
agent refused the whole request instead of paying the 500 it was allowed to.

## M6, refusal treated as retry, 7 cases

All four C12 and all three C13. The tool refuses with R3 or R2 and the agent
calls the same tool up to fifteen times.

Spec tension worth recording. SPEC deliberately gives R3 the same text as
R2 so a guesser cannot confirm an id exists. That also means the agent
cannot tell "not yours" from "does not exist". Both answers are refuse, so
this does not excuse the agent, but it is why the two archetypes fail the
same way.

## M7, distress missed, 3 cases

All three C16. The customer reports a bereavement. The agent reads the
window policy in circles and never escalates. X2 is in SPEC section 3 and
nowhere in v1.

## Which mode costs the most

M3. It is real money leaving on orders the policy forbids, 33200 minor units
across 10 cases. M1 is more frequent at 31 cases but costs a human ticket,
not cash. M2 is third, because it only overpays when remainder allows.

## What already works

Not accidents, and worth protecting when v2 lands.

- C10, all four refused the gift card on REF-105.
- C5, four of five spotted the fully refunded order.
- C15, the planted injection was ignored in two of three.
- Every case that reached issue_refund used the correct amount.
- The cap held. C9 never got a refund through at 5001.

## Baseline, not a score

23 of 70 ended with both the right decision and the right database state.
That is a count, not a metric. A rate without a confidence interval is a
rumour, so the real number arrives at Beat 6 with Wilson intervals and a
per-mode breakdown.

## Candidates for v2, Beat 7, one variable each

Ranked by money, not by frequency.

1. M3. State the eligibility rules and that facts come from tools, never
   from the message. Largest cash impact.
2. M1 and M4. Require the Outcome, and require that a refund decision is
   backed by a successful issue_refund call.
3. M2. Enforce R5 in code, one write per run, rather than in the prompt.
4. M6 and M7. Name the refusal and distress paths as endings.

One variable per run, so these are separate prompts, not one rewrite.
