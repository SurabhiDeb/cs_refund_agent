# Runbook

OpsAgent looks up orders and issues refunds. It is the only service here
that moves money, so every procedure below is written around one question:
how fast can the write path be stopped, and how do you know it stopped.

Read the first section before you need it. The rest is reference.

## Kill the write path

Three levers. The fastest one is not the one named "kill switch".

### 1. Revoke write scope, no restart, seconds

The caller's scope is read from Postgres on every single request, so this
takes effect on the next call with no deploy and no restart.

    docker compose exec postgres psql -U opsagent -d opsagent \
      -c "UPDATE customers SET scope = 'read';"

The refund tool is registered per request and only when the caller may
write, so after this the model is not refusing refunds, it has no refund
tool to call. Escalation keeps working.

Confirm:

    docker compose exec postgres psql -U opsagent -d opsagent \
      -c "SELECT id, scope FROM customers;"

To restore, set the scope back to `write` for the keys that should have it.
Do not blanket-restore: check which keys were meant to write.

### 2. The kill switch, needs a restart, about a minute

    WRITE_TOOLS_ENABLED=false

Settings are read from the environment once at import, so this needs the
process restarted to take effect. On Fly.io, `fly secrets set` triggers a
rolling restart by itself. Locally, stop Granian and start it again.

This is the broader lever: it disables writes for every caller regardless
of scope, and the check lives inside `issue_refund` as well as at the
edge, so it holds even if the agent is somehow handed the tool.

### 3. Stop the Temporal worker, only when DURABLE_REFUNDS is on

    # find and stop the worker process
    pkill -f "ops_agent.workflows.worker"

Refund workflows then queue in Temporal rather than execute. Nothing is
lost and nothing is paid. Starting the worker again drains the queue, so
this pauses the money, it does not cancel it. If you need the queued
refunds not to happen, terminate the workflows in Temporal before
restarting the worker.

### What none of these stop

Refunds already committed. The database write is the point of no return;
there is no reversal path in this service. Compensation exists only for a
processor rejection inside a running workflow.

## Confirm the money stopped

    curl -s localhost:8000/metrics | grep ops_agent_refund_value_minor_total

Watch it for a minute. If it is still climbing, the lever did not take.

Beware: counters are per process and two workers each keep their own, so
a scrape reaches one of them. A flat reading from one worker does not
prove the other is flat. Check the database instead when it matters:

    docker compose exec postgres psql -U opsagent -d opsagent \
      -c "SELECT count(*), sum(amount_minor) FROM refunds
          WHERE created_at > now() - interval '15 minutes';"

## When RefundValuePerHourHigh fires

Threshold is 50000 minor units in an hour, which is at least ten refunds
at the cap or a burst of smaller ones.

1. Look at the refunds table for the last hour, query above. Decide
   whether this is one bad actor, one bad case, or the agent misbehaving
   across many cases.
2. If it is the agent, revoke write scope first and investigate second.
   Lever 1 takes seconds and is reversible.
3. Read the traces in Langfuse for the runs involved. Every trace carries
   `ops.prompt_version` and `ops.prompt_sha`, so you can tell exactly
   which text produced the decisions.
4. Check `audit_log` for refused attempts around the same window. A spike
   of refusals beside a spike of refunds is someone probing.

There is no Alertmanager, so this alert fires in Prometheus and reaches
nobody. In practice you are reading this because a person noticed.

## Health

    curl -s localhost:8000/health

`200` with `{"status": "ok"}` means Postgres and Redis both answered.
`503` with `{"status": "degraded"}` names which one did not. A degraded
service can still answer `/chat` for anything that does not need the dead
dependency, but it is not fit to serve.

Also check `fake_model` in that payload. If it is `true` in a real
environment, the service is answering from a canned model and every
response is fiction. Stop it immediately.

## Common failures

**503, "The service is at capacity."** Load shedding, working as designed.
Five concurrent requests per worker. Beyond that callers are refused at the
door rather than queued, because queueing turned a busy minute into sixty
second hangs. If this is constant rather than bursty, add workers.

**429, "Rate limit reached."** Per API key, ten requests a minute by
default. It is a fixed window, so twenty requests across a window boundary
are allowed in quick succession. Raise `RATE_LIMIT_REQUESTS` if a
legitimate caller is being throttled.

**Requests hanging for seconds, then 500s.** Database pool exhaustion.
Ten connections plus twenty overflow per worker, five second checkout
timeout. Check `SELECT count(*) FROM pg_stat_activity;` against
`SHOW max_connections;`. Every refund takes two connections, not one,
because the audit row is written in its own transaction.

**Refunds accepted but nothing in the refunds table.** With
`DURABLE_REFUNDS=true`, check the Temporal worker is running and the task
queue is draining. Without a worker, workflows queue silently.

**Traces missing.** Langfuse runs in a separate compose stack. If it is
down, the service works and records nothing. Not an outage, but you are
flying blind until it is back.

## Settings that change behaviour

| Variable | Default | What it does |
|---|---|---|
| `WRITE_TOOLS_ENABLED` | false | The kill switch. False means no refunds for anyone. |
| `DURABLE_REFUNDS` | false | Route refunds through Temporal instead of writing in process. |
| `FAKE_MODEL` | false | Serve a canned model. Load testing only. Never in a real environment. |
| `REFUND_CAP_MINOR_UNITS` | 5000 | Per order, not per refund. Above it the agent escalates. |
| `MAX_CONCURRENT_CHATS` | 5 | Per worker. Over this, 503 at the door. |
| `RATE_LIMIT_REQUESTS` | 10 | Per key, per window. |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 10 / 20 | Per worker. The real concurrency ceiling. |

All of them are read once at import. Changing any of them means a restart.

## What this runbook cannot help you with yet

- **Nobody gets paged.** The alert evaluates in Prometheus and stops
  there. No Alertmanager, no rota.
- **Escalations go nowhere.** `escalate_to_human` returns a ticket id and
  writes an audit row. There is no tickets table and no queue a person
  works from.
- **Run records vanish on restart.** They live in a dict in memory, and
  two workers disagree about what exists. `/runs/{id}` is a demo.
- **The durable path is unproved end to end.** `DURABLE_REFUNDS=true` has
  never been run against a live worker from an HTTP call.
