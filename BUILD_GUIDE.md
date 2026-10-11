# OpsAgent Build Guide

Fourteen beats, Beat 0 to Beat 13. Each beat ends with something that runs
and something you can show. Do not skip ahead. Tick off in PROGRESS.md.

---

## Beat 0, foundations

Goal: an empty project that already enforces quality.

1. `uv init`, Python 3.13, `pyproject.toml`.
2. Add ruff, mypy strict, pytest, pre-commit. Wire pre-commit hooks.
3. `docker-compose.yml` at the root with Postgres 17 and Redis.
   Temporal is added at Beat 8, Langfuse at Beat 10.
4. `.env.example` with every variable named, no values. `.env` gitignored.
5. GitHub Actions workflow that runs ruff, mypy, pytest. Prove it fails on
   purpose, then make it pass.
6. Add gitleaks in CI (Trivy moves to Beat 9, with the Dockerfile)

Done when: `docker compose up` gives you all four services, CI is green, and
a deliberately bad commit is blocked.

---

## Beat 1, the spec

Goal: `docs/SPEC.md`. Nothing downstream is allowed to contradict it.

Write down, in exact terms:
- The tool list. `get_order`, `get_order_items`, `get_customer`,
  `get_refund_policy`, `issue_refund`, `escalate_to_human`.
- Which tools read and which tools write. Keep the split visible in the
  module layout, not just in your head.
- Refund eligibility rules. Window in days, condition of goods, payment
  method, prior refunds on the same order, partial versus full.
- The hard refund cap. The amount above which the agent may not act.
- Every escalation condition. Distress, fraud signals, ambiguity, missing
  data, over cap, policy conflict.
- The output contract as a Pydantic model. Decision, amount, reason,
  policy article cited, escalated flag, confidence.
- What the agent must refuse. Acting on a customer's claim about their own
  order status. Guessing an order id. Refunding a different customer's order.

Done when: a second person could tell, from SPEC.md alone, whether any given
refund decision was right.

---

## Beat 2, the world

Goal: a real database with hard cases in it.

1. SQLAlchemy 2.0 models. `customers`, `orders`, `order_items`, `refunds`,
   `policies`, `audit_log`.
2. Alembic migration. Never hand edit the schema.
3. Constraints that make bad states impossible. A unique index on
   `(order_id, idempotency_key)`. A check that refund amount is never above
   the order total minus refunds already issued.
4. Seed fixtures, 60 to 80 orders, weighted to the hard cases. Already fully
   refunded. Partially refunded. Outside the window. Wrong customer asking.
   Item missing from the order. Order id that does not exist. Amount just
   under and just over the cap.
5. For each fixture, an annotated goal state. What the database should look
   like after a correct run.

Done when: the goal states are written down before any agent exists.

---

## Beat 3, the tool layer

Goal: tools that are safe even with no model attached.

1. Each tool is a plain typed Python function with a Pydantic argument model.
2. Authorisation inside every tool. The caller's customer id comes from the
   API key context, never from an argument.
3. `issue_refund` takes an idempotency key and is a no op on replay.
4. The cap is enforced in `issue_refund` itself, not in the prompt. Over cap
   raises and returns an escalation.
5. A kill switch. One flag disables every write tool and the agent degrades
   to read plus escalate.
6. `audit_log` row written on every write attempt, allowed or refused.

Done when: pytest can prove, with no LLM in the loop, that the tools cannot
double-refund, cannot exceed the cap, and cannot touch another customer.

This is the most important beat in the project.

---

## Beat 4, the agent, v1

Goal: a deliberately crude agent that fails in ways worth studying.

1. Pydantic AI agent, tools registered, model pinned via AICredits gateway. LiteLLM arrives at Beat 7.
2. `prompts/v1.md`, intentionally thin. No worked examples, minimal policy.
3. Max step limit. A loop that hits it escalates.
4. Capture the full trajectory per run. Every message, tool name, arguments,
   tool result, tokens, cost, latency, and the final database diff.
5. Caching keyed on the whole message array plus tool schemas, never on the
   user string alone. Getting this wrong silently serves step 3 of an old
   run and your scores become fiction.
6. Run all fixtures. Save one run record with full provenance.

Done when: you have a run file you can read case by case.

---

## Beat 5, error analysis

Goal: a failure taxonomy, written by hand, before any eval code exists.

1. Read every trajectory. Not the summaries, the trajectories.
2. Name each distinct failure mode. Wrong tool. Right tool wrong arguments.
   Refund without checking policy. Policy checked and ignored. Accepted the
   customer's claim as fact. Looped. Escalated when it could have acted.
   Acted when it should have escalated.
3. For each failure, decide whether the agent is wrong, the fixture label is
   wrong, or the spec never decided. Most will be spec gaps.
4. Write `evals/runs/v1-notes.md` with counts per mode and named case ids.

Done when: you can say which mode costs the most, and why.

---

## Beat 6, the eval harness

Goal: numbers you are allowed to quote.

1. pytest plus testcontainers. A fresh Postgres per case, seeded, torn down.
2. Grade by comparing final database state to the annotated goal state.
3. Deterministic assertions first. Unauthorised writes, over cap refunds,
   double refunds, wrong customer. All must be zero.
4. Then the scored metrics. Task success, tool choice accuracy, wrong tool
   rate, steps per task, cost per task, latency p50 and p95.
5. Wilson confidence intervals on every rate. Quote the interval, not the
   point.
6. A per-failure-mode breakdown, never a bare aggregate.
7. Set the targets in SPEC.md now that you know the baseline.

Done when: the baseline is recorded and the zero-tolerance checks are wired.

---

## Beat 7, v2 and the gate

Goal: one improvement, attributed, and a CI gate that blocks regressions.

1. `prompts/v2.md` fixes exactly one failure mode. One variable.
2. Re-run. Report the case level flip list, not just the aggregate. Five
   named cases flipping proves a mechanism. Seventy five to eighty proves
   nothing.
3. `gate.py` reads the run file for the shipping configuration, not the
   newest file. Pin the configuration explicitly. An experiment that ran
   last must not become what CI gates on.
4. Wire the gate into CI. Prove it blocks by breaking a run file on purpose.

Done when: CI rejects a deliberately regressed run.

---

## Beat 8, durable money

Goal: a refund that survives a crash without paying twice.

1. Temporal workflow wrapping `issue_refund`. Activities retry, the workflow
   does not duplicate.
2. The idempotency key is derived from the order and the request, not random.
3. Kill the worker mid-refund on purpose. Restart. Prove exactly one refund
   row exists.
4. Add a compensation path for a refund that the downstream system rejects.

Done when: the crash test is in CI, not just in your memory.

---

## Beat 9, the service

Goal: something a client can call.

1. FastAPI on Granian. `POST /chat`, `GET /health`, `GET /runs/{id}`.
2. API key auth. The key maps to a customer id and a scope. Scope decides
   whether write tools are even registered for that caller.
3. Redis rate limiting, per key.
4. 422 on bad input, 503 from health when a dependency is down.
5. PII redaction in logs and in traces, both.
6. Docker multi stage, non root, no secrets in the image.
7. Trivy image scan in CI

Done when: an unauthenticated call cannot reach a tool, proved by a test.

---

## Beat 10, observability

Goal: you can answer "what did it do" after the fact.

1. OpenTelemetry spans around every agent step and every tool call.
2. Langfuse receiving traces with tool calls as structured fields, prompt
   versions registered.
3. Prometheus metrics. Refund count, refund value, escalation rate, step
   count, cost, latency, tool error rate.
4. A Grafana dashboard with one alert that matters. Refund value per hour
   above a threshold.
5. Sentry for exceptions, with PII scrubbing on.

Done when: you can reconstruct any single refund from traces alone.

---

## Beat 11, red team

Goal: prove the agent cannot be talked into spending money.

1. promptfoo red team suite. Direct injection, indirect injection via order
   notes and product names, authority claims, urgency pressure, encoded
   instructions, multi turn grooming.
2. Plant injection payloads inside tool results, not only in user messages.
   This is the realistic attack.
3. Every success is a hard CI failure.
4. Fix at the tool layer where possible. A prompt fix for an injection is a
   weaker fix than a constraint.

Done when: the suite runs in CI and the pass bar is zero successes.

---

## Beat 12, external benchmark

Goal: a number that is not self-marked.

1. Run tau2-bench retail against your agent.
2. Compare its failure modes to yours. Where they disagree, one of you is
   measuring the wrong thing.
3. Adopt its user simulator for multi-turn cases. This is also most of
   Product 4.
4. Record the score. Do not tune against it.

Done when: the benchmark score sits next to your own, both quoted.

---

## Beat 13, ship

Goal: it runs somewhere other than your laptop.

1. k6 load test. Find the concurrency where latency breaks the budget.
2. Deploy. Fly.io or ECS, with the Temporal worker as a separate service.
3. Canary the write path. Read only for the first window, writes behind the
   kill switch, then on.
4. Write `docs/RUNBOOK.md`. How to kill the write path in under a minute.
5. Write the known limitations section. Accepted deliberately, not forgotten.

Done when: someone else could operate it from the runbook.

---

## Possible extensions, not in the plan

### LangGraph human in the loop

Over-cap refunds currently escalate and the run ends. An alternative is to
**pause** the run and wait for a supervisor, then resume from that exact
step once approved. That needs checkpointing, which is what LangGraph's
`interrupt` exists for, and Pydantic AI does not do.

Would be a product change first, not a framework swap:

- SPEC change: over-cap refunds pause for approval rather than escalate
- Rebuild the decision flow as a LangGraph graph
- Postgres checkpointer so a paused run survives a process restart
- `interrupt()` at the approval node, resume with the supervisor's decision
- Proof: pause a run, kill the process, restart, resume, exactly one refund
- Compare against the Pydantic AI path and record which you would ship

Rejected for now because escalation already satisfies the spec, and swapping
frameworks to learn one teaches less than using it where it earns its place.
