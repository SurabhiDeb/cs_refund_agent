"""Sentry, with the customer stripped out on the way.

An exception report is the most careless place PII ends up. The stack trace
carries local variables, the request carries the body, and the body is a
customer's own words about their order. send_default_pii=False is not
enough on its own, because the message itself is ours to clean.

Tracing is off here deliberately. Langfuse already owns traces, and two
instrumentation layers on one request means two sources of truth.
"""

from __future__ import annotations

from typing import Any, cast

import sentry_sdk
from sentry_sdk.types import Event, Hint

from ops_agent.config import settings
from ops_agent.obs.redact import redact

# Headers that authenticate the caller. Never reportable.
_DROP_HEADERS = {"x-api-key", "authorization", "cookie"}


def scrub_event(event: Event, _hint: Hint) -> Event | None:
    """Last gate before an event leaves the process."""
    # Sentry types the event as a TypedDict. The scrubbing below walks it
    # generically, so it is handled as a plain dict here and returned as
    # the Event it still is.
    data = cast(dict[str, Any], event)
    if isinstance(data.get("message"), str):
        event["message"] = redact(event["message"])

    # Exception messages routinely quote the input that broke things.
    for entry in data.get("exception", {}).get("values", []):
        if isinstance(entry.get("value"), str):
            entry["value"] = redact(entry["value"])

    request = data.get("request")
    if isinstance(request, dict):
        # The body is the customer's message. There is no redacting that is
        # worth the risk, so it does not travel at all.
        request.pop("data", None)
        request.pop("cookies", None)

        headers = request.get("headers")
        if isinstance(headers, dict):
            for name in list(headers):
                if name.lower() in _DROP_HEADERS:
                    headers[name] = "[REDACTED]"

        if isinstance(request.get("query_string"), str):
            request["query_string"] = redact(request["query_string"])

    for crumb in data.get("breadcrumbs", {}).get("values", []):
        if isinstance(crumb.get("message"), str):
            crumb["message"] = redact(crumb["message"])

    return event


def install_sentry() -> bool:
    """Returns False when Sentry is switched off, which is a valid state."""
    if not settings.sentry_dsn:
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        send_default_pii=False,
        # Langfuse owns tracing. This is for exceptions only.
        traces_sample_rate=0.0,
        before_send=scrub_event,
    )
    return True
