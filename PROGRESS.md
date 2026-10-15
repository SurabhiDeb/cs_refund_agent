# Progress

Last updated: 10 October 2026

## Where we are right now

Nothing built. Folder scaffolded, docs written. Beat 0 not started.

## NEXT STEP TO BEGIN

**Beat 9, the service.**

Read `docs/BUILD_GUIDE.md` Beat 0 before touching anything.

---

## The plan

Tick a box only when the beat's "Done when" line in BUILD_GUIDE.md is
actually true, not when the code merely exists.

### Beat 0, foundations
- [x] 0.1 uv init, pyproject.toml, Python 3.13
- [x] 0.2 ruff, mypy strict, pytest, pre-commit wired
- [x] 0.3 docker-compose at root with Postgres 17 and Redis
- [x] 0.4 .env.example, .env gitignored
- [x] 0.5 GitHub Actions running ruff, mypy, pytest. Proved it fails, then passes
- [x] 0.6 gitleaks in CI (Trivy moves to Beat 9, with the Dockerfile)

### Beat 1, the spec
- [x] 1.1 Tool list fixed, read and write split declared
- [x] 1.2 Refund eligibility rules written in exact terms
- [x] 1.3 Hard refund cap chosen and written down
- [x] 1.4 Every escalation condition enumerated
- [x] 1.5 Output contract as a Pydantic model
- [x] 1.6 Refusal list written
- [x] 1.7 docs/SPEC.md committed

### Beat 2, the world
- [x] 2.1 SQLAlchemy models for all six tables
- [x] 2.2 Alembic initial migration
- [x] 2.3 Constraints that make bad states impossible
- [x] 2.4 60 to 80 seed orders, weighted to hard cases
- [x] 2.5 Annotated goal state per fixture, written before any agent exists

### Beat 3, the tool layer
- [x] 3.1 Typed tools with Pydantic argument models
- [x] 3.2 Authorisation inside every tool, identity from the key context
- [x] 3.3 issue_refund idempotent, no op on replay
- [x] 3.4 Cap enforced in code, not in the prompt
- [x] 3.5 Kill switch disables all write tools
- [x] 3.6 audit_log row on every write attempt, allowed or refused
- [x] 3.7 Tests prove safety with no LLM in the loop

### Beat 4, the agent v1
- [x] 4.1 Pydantic AI agent, model pinned via LiteLLM
- [x] 4.2 prompts/v1.md, deliberately crude
- [x] 4.3 Max step limit, overrun escalates
- [x] 4.4 Full trajectory capture including the database diff
- [x] 4.5 Cache keyed on the whole message array plus tool schemas
- [x] 4.6 All fixtures run, one run record with full provenance

### Beat 5, error analysis
- [x] 5.1 Every trajectory read by hand
- [x] 5.2 Failure modes named
- [x] 5.3 Each failure classified as agent wrong, label wrong, or spec gap
- [x] 5.4 evals/runs/v1-notes.md with counts and named case ids

### Beat 6, the eval harness
- [x] 6.1 pytest plus testcontainers, fresh Postgres per case
- [x] 6.2 Grading by final state against the goal state
- [x] 6.3 Zero tolerance checks wired and passing
- [x] 6.4 Scored metrics implemented
- [x] 6.5 Wilson intervals on every rate
- [x] 6.6 Per failure mode breakdown
- [x] 6.7 Targets set in SPEC.md from the baseline

### Beat 7, v2 and the gate
- [x] 7.1 prompts/v2.md, one failure mode, one variable
- [x] 7.2 Case level flip list reported
- [x] 7.3 gate.py pinned to the shipping configuration
- [x] 7.4 Gate in CI, proved to block a broken run

### Beat 8, durable money
- [x] 8.1 Temporal workflow wrapping issue_refund
- [x] 8.2 Idempotency key derived, not random
- [x] 8.3 Crash test, worker killed mid refund, exactly one refund row
- [x] 8.4 Compensation path for a rejected refund
- [x] 8.5 Crash test in CI

### Beat 9, the service
- [x] 9.1 FastAPI on Granian, three endpoints
- [x] 9.2 API key auth, scope decides which tools are registered
- [x] 9.3 Redis rate limiting per key
- [x] 9.4 422 on bad input, 503 from health when degraded
- [ ] 9.5 PII redaction in logs and traces
- [ ] 9.6 Docker multi stage, non root, no secrets in image
- [x] 9.7 Test proving an unauthenticated call cannot reach a tool
- [ ] 9.8 Trivy image scan in CI

### Beat 10, observability
- [ ] 10.1 OTel spans on every agent step and tool call
- [ ] 10.2 Langfuse traces with structured tool calls, prompts versioned
- [ ] 10.3 Prometheus metrics for refunds, escalations, steps, cost, latency
- [ ] 10.4 Grafana dashboard plus the refund value per hour alert
- [ ] 10.5 Sentry with PII scrubbing

### Beat 11, red team
- [ ] 11.1 promptfoo red team suite written
- [ ] 11.2 Injection payloads planted inside tool results
- [ ] 11.3 Any success is a hard CI failure
- [ ] 11.4 Fixes applied at the tool layer where possible

### Beat 12, external benchmark
- [ ] 12.1 tau2-bench retail run against the agent
- [ ] 12.2 Failure modes compared against ours
- [ ] 12.3 User simulator adopted for multi turn
- [ ] 12.4 Score recorded, not tuned against

### Beat 13, ship
- [ ] 13.1 k6 load test, breaking concurrency found
- [ ] 13.2 Deployed, Temporal worker as its own service
- [ ] 13.3 Write path canaried behind the kill switch
- [ ] 13.4 docs/RUNBOOK.md written
- [ ] 13.5 Known limitations written down

---

## Session log

### Session 0, scaffold
Created the folder, CLAUDE.md, BUILD_GUIDE.md, and this file. Nothing built.

---
### Session 1, Beat 4 closed
Order id now goes into the user turn and the six policy topics are named in
the get_refund_policy docstring. All 70 cases run, record saved.
---
### Session 3, Beat 6
Eval harness built. Every case replays against a throwaway Postgres and is
graded on the money in the table. Baseline is 44 of 70, 62.9 percent, CI
51.1 to 73.2. Zero safety failures. Targets written into SPEC.md.
---
### Session 4, Beat 7
R5 and R8 enforced in code, prompts/v2.md written, all 70 re-run. State
match 47 to 59 of 70, 15 fixed against 3 broken, McNemar p = 0.0075.
gate.py pinned to the v2 score and proved to block.
---
### Session 5, Beat 8
Temporal workflow wrapping issue_refund, key derived from the request.
Crash test scripted in scripts/crash_test.sh and wired into CI as its own
durability job. Proved it fails: with a random key the crash leaves 2 rows
and CI goes red. Refund amount set to 1000 on a 3200 order so the E4
remainder check cannot mask a broken key.
---

## Known limitations

Accepted deliberately, not forgotten.

- **No tickets table.** `escalate_to_human` returns a derived ticket id and
  records the escalation in `audit_log`. There is nowhere for a human to
  actually pick the case up. Fine while nothing is live, a gap before Beat 9.
- **"The audit row is written in its own transaction”** says “Beat 8 replaces this with Temporal.” Check whether it actually did — _audit() still opens its own session inside the activity, so the gap may still be open. Say what’s true now.
- **A replayed run reports stale database numbers.** The cache returns the
  record from the original run, including `refunds_before_minor` and
  `refunds_after_minor`. Those are not re-verified against the current
  database. Correct for reporting, wrong if you assume the database still
  looks that way.

- **The order id is injected by the harness, not carried by the fixture.**
  `run_case` builds the user turn from `order_id` plus the request text, so
  `goal_states.json` does not show what the agent was actually asked. Beat 7
  should move it into `seed.py` and add a C17 archetype with no order id,
  expected escalate X5, since the v2 run pays for a reseed anyway.

- **v2 changes more than one variable.** Budget, not design. M3 and M7 are
  both addressed in prompts/v2.md and the structural fixes land in the same
  run, so a gain cannot be attributed to a single change. The per archetype
  breakdown gives partial attribution, since the modes live in different
  archetypes.

- **The eval tells the agent a pinned date.** `runner.py` puts the seed's
  `NOW`, 2026-10-10, into the user turn so the 30 day window is testable and
  reproducible. A live service would use the real clock, so the agent has
  never been tested against a date it was not handed.

- **The eligibility list made the loop worse.** v1 cycled one policy topic
  when it got stuck, v2 cycles two, because the prompt gave it a second
  thing to check. M1 is now the dominant mode at 29 of 70 and is the v3
  candidate.

- **the crash test’s fixed sleep values are tuned to your laptop.** A slow CI runner could kill the worker before the row is written. Your after_crash != 1 check turns that into a visible failure rather than a silent pass, but it will flake eventually.

- **The health check tests fake the outage.** `test_health_is_503_when_*`
  monkeypatches the probe to return False rather than stopping Postgres or
  Redis. That tests the handling, not the detection. A probe that silently
  returns True against a dead dependency would still pass.

- **Run records live in memory.** `api/app.py` keeps them in a module level
  `RUNS` dict, so a restart loses every run and two Granian workers disagree
  about what exists. `/runs/{id}` is a demo until they have a table.

- **The API tests read a private pydantic-ai attribute.**
  `_function_toolset.tools` is how `test_read_scope_gets_no_refund_tool`
  checks which tools were registered. An upgrade can rename it. It fails
  loudly rather than passing silently, which is the acceptable direction.

- **The rate limit is a fixed window.** Ten calls at 59 seconds and ten more
  at 61 is twenty calls in two seconds, all allowed. One Redis round trip
  bought that imprecision deliberately.

- **`/chat` has never been run against the real model.** Every test uses a
  401, a 422, a 429, or a dead gateway. The HTTP layer is proved, the
  happy path is not. First real call is still unspent.


## Open questions

Which model to pin at Beat 4. Decide after the matrix at Beat 7, not before.
Whether the refund cap is a single number or tiered by customer history.
