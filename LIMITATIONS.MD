# Known limitations

Accepted deliberately, not forgotten. Written for whoever operates this
or reads its numbers, not for whoever built it.

Detail lives in `evals/runs/v1-notes.md`, `evals/runs/v2-notes.md`,
`evals/runs/redteam-notes.md`, `evals/runs/grooming-notes.md` and
`ops/k6/load-notes.md`. This file is the index to what is wrong.

## Money and safety

- **A committed refund cannot be reversed.** The database write is the
  point of no return. Compensation exists only for a processor rejection
  inside a running workflow, and there is no processor.

- **The durable write path has never been proved end to end.** `/chat`
  calls whichever executor `DURABLE_REFUNDS` selects, and tests prove the
  selection, the kill switch and R5 at the workflow boundary. No refund
  has travelled that path from a real HTTP call with a worker running.

- **The audit row is still written in its own transaction.** Beat 8 was
  supposed to replace this with Temporal and did not: `_audit()` opens a
  separate session, including inside the activity. A crash between the
  audit write and the refund write leaves an "allowed" row with no refund
  beside it. Deliberate in origin, since a refusal must survive its own
  rollback, but the window is real.

- **Malformed arguments are audited on one path only.** The model facing
  wrapper catches `ValidationError`, writes X9 and refuses. A caller that
  builds `IssueRefundArgs` itself, the Temporal activity or a test, still
  raises before any audit row exists.

- **Escalations go nowhere.** `escalate_to_human` returns a derived ticket
  id and writes an audit row. There is no tickets table and no queue a
  person works from, so every escalation is a dead end today.

## Operation

- **Load shedding is tuned to a laptop.** Five concurrent requests per
  worker, then a 503. At forty callers this turned a 58 second hang into a
  one second refusal and raised throughput fivefold, but the number was
  chosen from one machine's knee and is per process, so the real ceiling
  is five times however many workers run.

- **The rate limit is a fixed window and per key.** Ten calls at 59
  seconds and ten more at 61 is twenty in two seconds. Ten keys at ten
  calls each pass it entirely. One Redis round trip bought that
  imprecision on purpose.

- **Every setting is read once at import.** Changing the kill switch, the
  cap or the concurrency bound needs a restart. The fast kill is a
  database update to the caller's scope, which takes effect on the next
  request. See RUNBOOK.md.

- **Run records live in memory.** A module level dict in `api/app.py`, so
  a restart loses them and two workers disagree about what exists.
  `/runs/{id}` is a demo.

- **The health check tests fake the outage.** They monkeypatch the probe
  rather than stopping Postgres or Redis, so they test the handling and
  not the detection. A probe that wrongly returned True would still pass.

- **The image secret scan reports, it does not gate.** Trivy would not
  have caught our own `.env`: `LLM_API_KEY=...` matches none of its rules.
  "No secrets in the image" rests on `.dockerignore` and gitleaks.

- **The crash test's sleeps are tuned to one machine.** A slow runner
  could kill the worker before the row is written. The `after_crash != 1`
  check makes that a visible failure rather than a silent pass, but it
  will flake eventually.

## Observability

- **Nothing pages anyone.** `RefundValuePerHourHigh` evaluates in
  Prometheus and was proved to fire. There is no Alertmanager, so firing
  means a red row on a page nobody is watching at 3am.

- **Metrics are per process, and this is measured, not suspected.** A load
  test shed roughly 777 requests; `/metrics` reported 278, because the
  scrape reached one of two workers. Every counter has this flaw,
  including the refund value the alert watches.

- **Refunds issued by the Temporal worker are not counted at all.** The
  counters are incremented in `/chat` only, so money moved by the workflow
  is invisible to the dashboard and to the alert.

- **A failed run records zero cost.** `/chat` reads `result.usage`, which
  does not exist when a run raises. A run that loops and dies is the most
  expensive kind and currently costs nothing on the dashboard.
  `runner.py` does this correctly by reading the messages instead.

- **`cost_inr` exists twice**, in `obs/metrics.py` and `agent/runner.py`.
  Two copies of a pricing calculation disagree the first time rates move.

- **Tracing depends on another project.** Langfuse runs in a separate
  compose stack. If it is down the service works and records nothing.

- **Run records store raw customer text.** `runner.py` writes the full
  trajectory, user turn included, to `evals/runs/`. Nothing redacts that
  path. Fine for seeded fixtures, a leak the moment a real conversation is
  recorded.

## Evidence and evaluation

- **The red team's zero is weaker than it looks.** 19 of 30 attacks ended
  in X7 and three of five controls under-paid. No injection moved money,
  on a run where the agent mostly moved nothing.

- **The multi-turn suite tests two conversations, not eight.** Six still
  die on turn 1 even on v3. The headline is "2 of 8 got past turn 1", not
  "0 breaches".

- **Grooming is graded as a ceiling, so a wrong answer can pass.** The
  suite can say money did not escape. It cannot say the agent was right.

- **The attacker is the same model as the defender**, same temperature, so
  it shares the agent's blind spots and is probably too polite.

- **Nothing checks the simulator stayed in character.** If it breaks
  persona or ends early, the conversation still records as a pass.

- **The CI graders validate writes, not conversation.** They replay tool
  calls. An agent that said something disastrous but wrote nothing passes
  every assertion.

- **No external benchmark has been run.** tau2-bench retail would cost
  roughly INR 250 to 450 against INR 6 for the whole red team, and a ten
  task subset would be quoted as a leaderboard score it is not. Beat 12.1,
  12.2 and 12.4 are open on cost, deliberately.

- **The eval harness shares one Session across parallel tool calls.**
  `runner.py` passes a single SQLAlchemy Session into the agent and
  pydantic-ai runs tool calls in parallel threads. The API path is guarded
  with `parallel_tool_call_execution_mode("sequential")`; `runner.py` is
  not. The 70 case run has been lucky, not safe. **Unfixed.**

- **The eval hands the agent a pinned date.** `runner.py` puts 2026-10-10
  into the user turn so the 30 day window is reproducible. The agent has
  never been tested against a date it was not given.

- **The order id is injected by the harness, not carried by the fixture**,
  so `goal_states.json` does not show what the agent was actually asked.

- **A replayed run reports stale database numbers.** The cache returns the
  original record's `refunds_before_minor` and `refunds_after_minor`
  without re-checking the database.

- **v2 changed more than one variable**, so a gain cannot be attributed to
  a single change. The per archetype breakdown gives partial attribution.

- **v3 is a candidate, not shipped.** It was probed on three main cases
  and run on eight conversations. The 70 case set has not been re-run, so
  it could be better at multi-turn and worse at the day job.

- **The API tests read a private pydantic-ai attribute**,
  `_function_toolset.tools`. An upgrade can rename it. It would fail
  loudly, which is the acceptable direction.

## Deliberate deviations from CLAUDE.md

- **promptfoo is not used, though the stack lists it.** The red team is
  two layers in this repo's own harness. promptfoo would keep a second
  cache and a second set of run records that can disagree with the first,
  and its generated suites run 300 to 1000 cases for numbers this harness
  already produces.

## Resolved, kept so the record is honest

- The database pool used SQLAlchemy's defaults and produced 49 second
  requests under load. Sized at Beat 13.1.
- The service collapsed above ten concurrent callers with no shedding.
  Fixed at Beat 13.1 with a bounded semaphore.
- The refund cap was per refund, so two conversations moved 6000 under a
  5000 cap. Made per order at Beat 11.
- `/chat` wrote refunds directly, outside everything Beat 8 built. One
  executor now, selected at the edge.
- Rate limit state leaked between tests and looked like a flake. Cleared
  per test at Beat 13.
