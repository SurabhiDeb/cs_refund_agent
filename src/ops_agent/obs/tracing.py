"""OpenTelemetry spans, exported to Langfuse.

Beat 10 asks that any refund be reconstructable from traces alone. That
means the tool calls and their arguments, not the chat transcript.

include_content is off deliberately. The raw conversation is the biggest
PII surface in the system, and 9.5 says traces are redacted too. What goes
in instead is a redacted copy of the message, attached by us, so a trace is
still readable without carrying a customer's card number into Langfuse.
"""

from __future__ import annotations

import base64

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic_ai import Agent, InstrumentationSettings

from ops_agent.config import settings

_installed = False


def install_tracing() -> bool:
    """Wire OTel to Langfuse. Returns False when tracing is switched off.

    Switched off is a supported state, not a failure. CI has no Langfuse,
    and a missing trace backend must never stop a refund.
    """
    global _installed
    if _installed:
        return True

    if not (
        settings.langfuse_host
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    ):
        return False

    token = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()

    exporter = OTLPSpanExporter(
        endpoint=f"{settings.langfuse_host.rstrip('/')}/api/public/otel/v1/traces",
        headers={"Authorization": f"Basic {token}"},
        timeout=30,
    )

    provider = TracerProvider(
        resource=Resource.create({"service.name": "ops-agent"}),
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Every agent run and every tool call now emits a span, without a
    # decorator on any of them.
    Agent.instrument_all(
        InstrumentationSettings(tracer_provider=provider, include_content=False)
    )

    _installed = True
    return True


def tracer() -> trace.Tracer:
    return trace.get_tracer("ops_agent")
