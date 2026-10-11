# Progress

Last updated: 10 October 2026

## Where we are right now

Nothing built. Folder scaffolded, docs written. Beat 0 not started.

## NEXT STEP TO BEGIN

**Beat 4, the agent v1.**

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
- [ ] 4.5 Cache keyed on the whole message array plus tool schemas
- [ ] 4.6 All fixtures run, one run record with full provenance

### Beat 5, error analysis
- [ ] 5.1 Every trajectory read by hand
- [ ] 5.2 Failure modes named
- [ ] 5.3 Each failure classified as agent wrong, label wrong, or spec gap
- [ ] 5.4 evals/runs/v1-notes.md with counts and named case ids

### Beat 6, the eval harness
- [ ] 6.1 pytest plus testcontainers, fresh Postgres per case
- [ ] 6.2 Grading by final state against the goal state
- [ ] 6.3 Zero tolerance checks wired and passing
- [ ] 6.4 Scored metrics implemented
- [ ] 6.5 Wilson intervals on every rate
- [ ] 6.6 Per failure mode breakdown
- [ ] 6.7 Targets set in SPEC.md from the baseline

### Beat 7, v2 and the gate
- [ ] 7.1 prompts/v2.md, one failure mode, one variable
- [ ] 7.2 Case level flip list reported
- [ ] 7.3 gate.py pinned to the shipping configuration
- [ ] 7.4 Gate in CI, proved to block a broken run

### Beat 8, durable money
- [ ] 8.1 Temporal workflow wrapping issue_refund
- [ ] 8.2 Idempotency key derived, not random
- [ ] 8.3 Crash test, worker killed mid refund, exactly one refund row
- [ ] 8.4 Compensation path for a rejected refund
- [ ] 8.5 Crash test in CI

### Beat 9, the service
- [ ] 9.1 FastAPI on Granian, three endpoints
- [ ] 9.2 API key auth, scope decides which tools are registered
- [ ] 9.3 Redis rate limiting per key
- [ ] 9.4 422 on bad input, 503 from health when degraded
- [ ] 9.5 PII redaction in logs and traces
- [ ] 9.6 Docker multi stage, non root, no secrets in image
- [ ] 9.7 Test proving an unauthenticated call cannot reach a tool
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

## Known limitations

Nothing to record yet. Accepted deliberately, not forgotten.

## Open questions

Which model to pin at Beat 4. Decide after the matrix at Beat 7, not before.
Whether the refund cap is a single number or tiered by customer history.
