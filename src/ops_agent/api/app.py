"""The HTTP surface. Three endpoints, nothing clever.

The caller's identity comes from the API key, never from the body. A request
that could name its own customer_id is a request that can refund someone
else's order.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from ops_agent.agent.agent import USAGE_LIMITS, Deps, build_agent
from ops_agent.api.auth import resolve_key
from ops_agent.api.limits import enforce
from ops_agent.config import settings
from ops_agent.db.session import session_scope
from ops_agent.tools.context import ToolContext

app = FastAPI(title="OpsAgent")

# Not durable. Replaced when run records get a home in the database.
RUNS: dict[str, dict[str, Any]] = {}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
def chat(
    request: ChatRequest, x_api_key: str | None = Header(default=None)
) -> dict[str, Any]:
    caller = resolve_key(x_api_key)
    enforce(
        x_api_key or "",
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )

    # Two independent switches. The scope is what this caller is allowed to
    # do, the kill switch is what anyone is allowed to do right now. Both
    # must say yes, and the kill switch always wins.
    may_write = caller.may_write and settings.write_tools_enabled

    agent = build_agent("v2", may_write=may_write)
    tool_ctx = ToolContext(customer_id=caller.customer_id, write_enabled=may_write)

    with session_scope() as session:
        result = agent.run_sync(
            request.message,
            deps=Deps(tool_ctx=tool_ctx, session=session),
            usage_limits=USAGE_LIMITS,
        )

    run_id = "run_" + uuid.uuid4().hex[:16]
    RUNS[run_id] = {
        "run_id": run_id,
        "customer_id": caller.customer_id,
        "scope": caller.scope,
        "outcome": result.output.model_dump(),
    }
    return RUNS[run_id]


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="No such run.")
    return RUNS[run_id]
