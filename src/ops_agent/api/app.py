"""The HTTP surface. Three endpoints, nothing clever.

The caller's identity comes from the API key, never from the body. A request
that could name its own customer_id is a request that can refund someone
else's order.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections.abc import MutableMapping
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from sqlalchemy import text

from ops_agent.agent.agent import USAGE_LIMITS, Deps, build_agent, load_prompt
from ops_agent.api.auth import resolve_key
from ops_agent.api.limits import enforce, redis_ok
from ops_agent.config import settings
from ops_agent.db.session import session_scope
from ops_agent.domain.contract import Decision
from ops_agent.obs.errors import install_sentry
from ops_agent.obs.metrics import COST, LATENCY, REFUND_VALUE, STEPS, cost_inr
from ops_agent.obs.metrics import RUNS as RUNS_TOTAL
from ops_agent.obs.redact import install, redact
from ops_agent.obs.tracing import install_tracing, tracer
from ops_agent.tools.context import ToolContext


def _skip_telemetry(scope: MutableMapping[str, Any]) -> bool:
    """Health and metrics are polled forever by machines. Tracing them
    buries the handful of traces a person will actually read."""
    return scope.get("path") in {"/metrics", "/health"}


app = FastAPI(
    title="OpsAgent",
    telemetry={
        "tracing": True,
        # Our own "chat" span is the story. FastAPI's dependency and
        # serialization spans are plumbing nobody debugs from Langfuse.
        "operation_spans": False,
        "exclude": _skip_telemetry,
    },
)
install()
install_tracing()
install_sentry()
log = logging.getLogger("ops_agent.api")

# Not durable. Replaced when run records get a home in the database.
RUNS: dict[str, dict[str, Any]] = {}

# The prompt that ships. Hashed once at import, so every trace can say
# exactly which text produced it. Rule 2: a change is a new file, never
# an edit, so this sha is stable for the life of the process.
PROMPT_VERSION = "v2"
PROMPT_SHA = hashlib.sha256(load_prompt(PROMPT_VERSION).encode()).hexdigest()[:16]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _postgres_ok() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@app.get("/health")
def health(response: Response) -> dict[str, Any]:
    """Honest about its dependencies.

    A health check that always says ok is worse than no health check, because
    something upstream will keep routing traffic to a service that cannot
    serve it. Each dependency is named, so the answer says what is wrong.
    """
    checks = {"postgres": _postgres_ok(), "redis": redis_ok()}

    if not all(checks.values()):
        response.status_code = 503
        return {"status": "degraded", "checks": checks}

    return {"status": "ok", "checks": checks}


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus scrapes this. Deliberately unauthenticated: the scraper
    is inside the deployment, and these are counts, not customer data."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/chat")
def chat(
    request: ChatRequest, x_api_key: str | None = Header(default=None)
) -> dict[str, Any]:
    started = time.perf_counter()
    caller = resolve_key(x_api_key)
    enforce(
        x_api_key or "",
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    log.info(
        "chat customer=%s scope=%s message=%s",
        caller.customer_id,
        caller.scope,
        redact(request.message),
    )

    # Two independent switches. The scope is what this caller is allowed to
    # do, the kill switch is what anyone is allowed to do right now. Both
    # must say yes, and the kill switch always wins.
    may_write = caller.may_write and settings.write_tools_enabled

    run_id = "run_" + uuid.uuid4().hex[:16]

    with tracer().start_as_current_span("chat") as span:
        span.set_attribute("ops.run_id", run_id)
        span.set_attribute("ops.customer_id", caller.customer_id)
        span.set_attribute("ops.scope", caller.scope)
        span.set_attribute("ops.may_write", may_write)
        # Redacted, because a trace is a place data goes to stay.
        span.set_attribute("ops.message", redact(request.message))
        span.set_attribute("ops.prompt_version", PROMPT_VERSION)
        span.set_attribute("ops.prompt_sha", PROMPT_SHA)

        agent = build_agent(PROMPT_VERSION, may_write=may_write)
        tool_ctx = ToolContext(customer_id=caller.customer_id, write_enabled=may_write)

        # One Session, and SQLAlchemy Sessions are not thread safe. Parallel
        # tool calls would hand the same Session to several threads, which
        # fails with IllegalStateChangeError rather than anything readable.
        with (
            agent.parallel_tool_call_execution_mode("sequential"),
            session_scope() as session,
        ):
            result = agent.run_sync(
                request.message,
                deps=Deps(tool_ctx=tool_ctx, session=session),
                usage_limits=USAGE_LIMITS,
            )

        outcome = result.output
        span.set_attribute("ops.decision", str(outcome.decision))
        span.set_attribute("ops.escalated", outcome.decision is Decision.ESCALATE)
        span.set_attribute("ops.reason_code", outcome.reason_code)
        span.set_attribute("ops.confidence", outcome.confidence)

    usage = result.usage
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    steps = int(getattr(usage, "requests", 0) or 0)

    RUNS_TOTAL.labels(decision=str(outcome.decision)).inc()
    STEPS.observe(steps)
    COST.inc(cost_inr(input_tokens, output_tokens))
    LATENCY.observe(time.perf_counter() - started)

    # Only money that actually moved. A refund decision the tool refused is
    # not a refund, and counting it would make the alert lie.
    if outcome.decision is Decision.REFUND and outcome.amount_minor:
        REFUND_VALUE.inc(outcome.amount_minor)

    RUNS[run_id] = {
        "run_id": run_id,
        "customer_id": caller.customer_id,
        "scope": caller.scope,
        "outcome": outcome.model_dump(),
    }
    return RUNS[run_id]


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="No such run.")
    return RUNS[run_id]
