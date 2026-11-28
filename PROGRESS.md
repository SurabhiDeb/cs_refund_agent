# Progress

Last updated: 10 October 2026

## Where we are right now

Nothing built. Folder scaffolded, docs written. Beat 0 not started.

## NEXT STEP TO BEGIN

**Beat 13, ship.**

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
- [x] 9.5 PII redaction in logs and traces
- [x] 9.6 Docker multi stage, non root, no secrets in image
- [x] 9.7 Test proving an unauthenticated call cannot reach a tool
- [x] 9.8 Trivy image scan in CI

### Beat 10, observability
- [x] 10.1 OTel spans on every agent step and tool call
- [x] 10.2 Langfuse traces with structured tool calls, prompts versioned
- [x] 10.3 Prometheus metrics for refunds, escalations, steps, cost, latency
- [x] 10.4 Grafana dashboard plus the refund value per hour alert
- [x] 10.5 Sentry with PII scrubbing

### Beat 11, red team
- [x] 11.1 promptfoo red team suite written
- [x] 11.2 Injection payloads planted inside tool results
- [x] 11.3 Any success is a hard CI failure
- [x] 11.4 Fixes applied at the tool layer where possible

### Beat 12, external benchmark
- [ ] 12.1 tau2-bench retail run against the agent
- [ ] 12.2 Failure modes compared against ours
- [x] 12.3 User simulator adopted for multi turn
- [ ] 12.4 Score recorded, not tuned against

### Beat 13, ship
- [x] 13.1 k6 load test, breaking concurrency found
- [ ] 13.2 Deployed, Temporal worker as its own service
- [ ] 13.3 Write path canaried behind the kill switch
- [x] 13.4 docs/RUNBOOK.md written
- [x] 13.5 Known limitations written down

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
### Session 6, Beat 10 start
OTel spans wired to a self-hosted Langfuse over OTLP, content excluded so
traces carry no customer text. Two bugs found while proving it: parallel
tool calls shared one Session, and the audit row id was derived from its
own content, so a repeated escalation collided and the audit write raised.
Both fixed.
---
### Session 7, Beat 10
Observability end to end. OTel spans to a self-hosted Langfuse, content
excluded so no customer text leaves the process. Prompt version and sha on
every trace, so a decision can be traced back to the exact text that
produced it. Prometheus metrics for runs, refund value, steps, cost,
latency and refusals, scraped into a Grafana dashboard with one alert on
refund value per hour, proved to fire and then put back. Sentry wired with
a before_send scrubber, proved on a real event. Temporal workflow and
activities traced through Temporal's own interceptor, so a refund is
reconstructable from the trace including its idempotency key.
---
### Session 8, Beat 11
Red team, two layers, no promptfoo. Layer 1 is 17 pytest cases calling the
tools directly with hostile arguments, free and gating every push. It found
three real holes: the cap was per refund so two conversations moved 6000
under a 5000 cap, a malformed write attempt raised before any audit row
existed and killed the run, and ToolRefusal printed the literal word
"message" in every log line. All three fixed at the tool layer, cap now
summed per order, bad arguments audited as X9 and answered as a refusal.
Layer 2 is 30 model-level attacks across direct injection, indirect
injection planted in product names and policy articles, authority claims,
urgency and encoded instructions, INR 6.21, cached so re-runs are free.
Zero breaches. Read that with the caveat in redteam-notes.md: 19 of 30 hit
the step limit and three of five controls under-paid, so nothing got
through on a run where most cases did nothing. Same M1 loop already named
for v3, not a new mode. Multi-turn grooming stays uncovered until the
tau2-bench user simulator at 12.3.
---
### Session 9, Beat 12
Beat 12 done partially and on purpose. 12.1, the tau2-bench retail run, is
not run: a full retail run is roughly INR 250 to 450 against INR 6 for the
entire red team, and a ten task subset would be quoted as a leaderboard
score it is not. 12.2 and 12.4 depend on it. 12.3 is built and ticked: a
user simulator, prompt sim_user_v1, drives up to five turns against the
agent, and eight grooming conversations are graded on the refunds table as
a ceiling. v2 died on turn 1 in all eight, so the suite measured nothing;
prompts/v3.md, one variable, replaces v2's closing advice with a numbered
procedure and a once-per-tool rule. v3 gets two conversations past turn 1
and one, the legitimate control, all the way through to a correct 2400
refund. Zero breaches on both. v3 stays a candidate: gate.py is pinned to
v2 and re-measuring everything is about INR 20. Total spend this session
INR 6.7.
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

- **9.5 is half done.** Logs are redacted by `obs/redact.py` and a filter on
  the root logger. There are no traces yet, so the trace half lands with
  Langfuse at 10.2. Tick 9.5 then, not before.

- **Run records store raw customer text.** `runner.py` captures the full
  trajectory, including the user turn, and writes it to `evals/runs/`.
  Nothing redacts that path. Fine for seeded fixtures, a leak the moment a
  real conversation is recorded.

- **The image secret scan reports, it does not gate.** Trivy's only hits are
  a private-key marker in google-auth bytecode and an example JWT in pyjwt's
  METADATA, both third party. It also would not have caught our own `.env`:
  `LLM_API_KEY=...` matches none of its rules. So "no secrets in the image"
  rests on `.dockerignore` and gitleaks, not on Trivy. Verified by building
  an image with a planted `.env` and seeing Trivy stay silent.

- **The eval harness shares one Session across parallel tool calls.**
  `runner.py` passes a single SQLAlchemy Session into the agent, and
  pydantic-ai runs tool calls in parallel threads by default. Sessions are
  not thread safe. The API path is guarded with
  `parallel_tool_call_execution_mode("sequential")`; `runner.py` is not. The
  70 case run has been lucky, not safe. (**This is unfixed.**)

- the alert fires in Prometheus only — there’s no Alertmanager, so nothing actually pages anyone yet.

- **The durable write path exists but has not been proved end to end.**
  `/chat` now calls whichever executor `DURABLE_REFUNDS` selects, so the
  service can take the Temporal path that Beat 8 built. Tests prove the
  selection and prove the kill switch and R5 are re-checked before the
  workflow starts, because the activity builds its own ToolContext in
  another process and neither rule reaches it. What is not proved is a
  real refund travelling that path from an HTTP call, with a worker
  running. That belongs with the Beat 13 deploy.

- **Nothing pages anyone.** `RefundValuePerHourHigh` evaluates in Prometheus
  and was proved to fire, but there is no Alertmanager, so firing means a
  red row on a page nobody is watching at 3am.

- **Metrics live in one process.** `prometheus-client` counts in memory, so
  two Granian workers would each hold their own totals and Prometheus would
  scrape whichever answered. Correct today because there is one worker.

- **Refunds issued by the Temporal worker are not counted.** The Prometheus
  counters are incremented in `/chat` only, so the money the workflow moves
  is invisible to the dashboard and to the alert that watches it.

- **Cost is read from the result, so a failed run records zero.** `/chat`
  uses `result.usage`, which does not exist when a run raises.
  `runner.py` solved this properly by reading the messages instead. A run
  that loops and dies is the most expensive kind and currently costs
  nothing on the dashboard.

- **`cost_inr` exists twice.** Once in `obs/metrics.py` and once in
  `agent/runner.py`. Two copies of a pricing calculation will disagree the
  first time the rates change.

- **Tracing depends on another project.** Langfuse runs in a separate
  compose stack. If those containers are down, ops_agent still works but
  records nothing. Fine for dev, wrong for Beat 13.

- - **Only the agent's own write path audits malformed arguments.** The model
  facing wrapper catches `ValidationError`, writes an X9 row and returns a
  refusal. A caller that builds `IssueRefundArgs` itself, the Temporal
  activity or a test, still raises before any audit row exists. Acceptable
  while every such caller is ours, wrong the moment a second external entry
  point is added.
- **Beat 11 does not use promptfoo, though CLAUDE.md's stack lists it.** The
  red team is two layers inside this repo's own harness: pytest against the
  tools in `tests/test_red_team_tools.py`, and model level injection
  fixtures graded on final database state. promptfoo would keep a second
  cache and a second set of run records that can disagree with the first,
  and its generated suites run 300 to 1000 cases, roughly INR 100 to 300,
  for numbers this harness already produces. A deliberate deviation,
  recorded here because the stack list is otherwise the contract.

- **The red team's zero is weaker than it looks.** 19 of the 30 attacks
  ended in X7 and three of five controls under-paid. No injection moved
  money, on a run where the agent mostly moved nothing. Re-run after v3.

- **Multi-turn grooming is untested.** The harness sends one user turn, so
  an attack spread across several messages cannot be written as a fixture.
  Beat 12.3's user simulator is the fix.

- **The multi-turn suite tests two conversations, not eight.** Six of the
  eight still die on turn 1 with X7 even on v3. The harness is sound; the
  agent is the limit. The headline number is "2 of 8 got past turn 1", not
  "0 breaches".

- **Grooming is graded as a ceiling, so a wrong answer can pass.** G2 paid
  the full 3200 on turn 1 and counts as HELD because 3200 is what the
  order allows. The suite can tell you money did not escape. It cannot
  tell you the agent was right.

- **The attacker is the same model as the defender.** The simulator runs
  on the same pinned model with the same temperature, so it shares the
  agent's blind spots and is probably too polite to be a real attacker. A
  different model on the customer side would be a harder test.

- **Nothing checks the simulator stayed in character.** If it breaks
  persona, helps the agent, or ends early, the conversation still records
  as a pass. The transcript is read by hand or not at all.

- **The conversation ends the moment the agent fails.** A real customer
  keeps talking after a system error. One X7 closes the case, which is why
  six conversations are one turn long.

- **The CI grader validates writes, not conversation.** It replays
  `tool_calls` against a fresh database. An agent that said something
  disastrous but wrote nothing passes every assertion in it.

- **v3's effect on ordinary task success is unknown.** It was probed on
  three main cases and run on eight conversations. The 70 case set has not
  been re-run, so it could be better at multi-turn and worse at the day
  job, and nothing here would show it.

- **The service collapses above 10 concurrent callers and nothing sheds
  load.** Measured in ops/k6/load-notes.md. The rate limit is per key, so
  ten keys at ten requests each pass it and reach a service that cannot
  serve them. Bounded concurrency with a fast 503 is the fix, and it is
  not built.

- **The service sheds load at five concurrent callers per worker.** Over
  that, a 503 with Retry-After. Measured in ops/k6/load-notes.md: at forty
  callers this turned a 58 second hang into a one second refusal and
  raised throughput five fold. The number is a guess tuned to a laptop,
  not a deployment, and it is per process, so the real ceiling is five
  times however many workers run.

- **Per-process metrics are now proved wrong, not just suspected.** A load
  test shed roughly 777 requests and `/metrics` reported 278, because the
  scrape reached one of two workers. Every counter in this service has
  that flaw, including the refund value the alert watches.


## Open questions

Which model to pin at Beat 4. Decide after the matrix at Beat 7, not before.
Whether the refund cap is a single number or tiered by customer history.
