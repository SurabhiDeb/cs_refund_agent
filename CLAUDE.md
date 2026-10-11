# OpsAgent

A customer support agent that acts. It looks up orders and issues refunds.
Products 1 and 2 of chatbot-lab only ever produced text. This one changes
state, so the risk model is not "is it correct" but "what did it do".

Owner: Surabhi. Started October 2026.

## Read this first, every session

1. `PROGRESS.md` tells you where we are and what the next step is. Start there.
2. `docs/BUILD_GUIDE.md` is the full plan, Beat 0 to Beat 13.
3. `docs/SPEC.md` is the product definition. Everything downstream inherits it.
4. `docs/DECISIONS.md` records every choice and why. Append, never rewrite.

Do not start a beat before the one before it is ticked off in PROGRESS.md.

## The rules this repo runs on

1. Pinned model ids. Never an alias containing "latest".
2. Prompts are immutable versioned files. A change creates a new file.
3. Every run records prompt sha, model, dataset sha, git sha, cost, and the
   full trajectory.
4. One variable per run, or you cannot attribute the change.
5. Report per-failure-mode, never a bare aggregate.
6. A pass rate without a confidence interval is a rumour.
7. Fail safe. An unparseable response escalates to a human, never falls silent.
8. Never tune against the split you report on.
9. Money limits live in code, never in the prompt. A prompt is advice. A
   database constraint is a rule.
10. Every write tool is idempotent. A retry must never double-refund.
11. Grade by final database state, not by what the agent said it did.
12. The caller's identity comes from the API key, never from the request body.
13. Credits are a real cost. Build and test with a fake model. Measure cost
    on three cases before running all 70. Cache every response to disk, so a
    re-run is free. Never re-run a full evaluation to fix a reporting bug.

## Grading model

Borrowed from tau2-bench. A case passes when the database at the end of the
run matches the annotated goal state. The agent's prose is not the artifact.
This is why the eval harness runs against a real Postgres and not a mock.

## Metrics that gate CI

| Metric | Target |
|---|---|
| Unauthorised writes | 0, hard fail |
| Refunds over the cap | 0, hard fail |
| Prompt injection successes | 0, hard fail |
| Task success, final state match | set at Beat 6 |
| Tool choice accuracy | set at Beat 6 |
| Steps per task, p50 and p95 | set at Beat 6 |
| Cost per task | set at Beat 6 |
| Latency p50 and p95 | set at Beat 6 |

Zero means zero. A 95% correct and 5% unauthorised agent is unshippable,
where a RAG bot at the same score ships.

## Stack

Core
- Python 3.13, uv for deps and lockfile
- Pydantic AI 2.0 for the agent, Pydantic v2 for tool arg validation
- LiteLLM proxy for model routing, fallback, and per-key cost caps

Money path
- Temporal for durable refund execution
- Postgres 17, SQLAlchemy 2.0, Alembic
- Idempotency keys as a unique constraint
- A kill switch flag on every write tool

Service
- FastAPI and Granian
- Redis for rate limits
- Pydantic Settings for config, Doppler for secrets

Observability
- OpenTelemetry as the one instrumentation layer
- Langfuse for traces, prompt versions, tool call capture
- Prometheus and Grafana for SLOs
- Sentry for exceptions

Evals
- pytest and testcontainers against a real Postgres
- tau2-bench as the external benchmark
- promptfoo for the model matrix and red teaming
- Braintrust for experiment history
- k6 for load

Gates
- ruff, mypy strict, pre-commit
- GitHub Actions, Docker multi stage, non root
- Trivy for images, gitleaks for secrets

## Layout

    docs/            SPEC.md, BUILD_GUIDE.md, DECISIONS.md, GLOSSARY.md
    src/opsagent/
      agent/         the loop, prompts/ versioned
      tools/         read and write tools, split deliberately
      domain/        models, policy rules, eligibility
      db/            SQLAlchemy models and session
      workflows/     Temporal refund workflow
      api/           FastAPI app
      obs/           OTel and Langfuse wiring
    migrations/      Alembic
    tests/           pytest, state based
    evals/           datasets, run records, promptfoo config, tau2 harness
    ops/             docker compose, Grafana dashboards, k6 scripts

## Working style

- Commit per beat, message starts with the beat number.
- Append to DECISIONS.md whenever a choice closes off an alternative.
- Update PROGRESS.md at the end of every session, before you stop.
- Put every new term in GLOSSARY.md in plain English.
- When the agent disagrees with the expected state, three things could be
  true. The agent is wrong, the label is wrong, or the spec never decided.
  Work out which before changing anything.
