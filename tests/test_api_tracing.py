"""Beat 10.2. The trace says which prompt produced the decision.

Free. The endpoint runs against TestModel and the spans go to an in-memory
exporter, so neither the gateway nor Langfuse is touched.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from ops_agent.agent.agent import build_agent as real_build_agent
from ops_agent.api import app as app_module
from ops_agent.api.app import app

client = TestClient(app)

HEADERS = {"X-API-Key": "dev-key-owner"}
ASK = {"message": "My order ord_C1_01 arrived damaged, I would like a refund."}


@pytest.fixture
def spans(monkeypatch: pytest.MonkeyPatch) -> Generator[InMemorySpanExporter]:
    """Capture spans in memory instead of shipping them to Langfuse."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = provider.get_tracer("test")

    monkeypatch.setattr(app_module, "tracer", lambda: test_tracer)
    yield exporter


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every agent the endpoint builds answers from TestModel.

    The override is entered and left inside the request's own thread.
    Entering it here and closing it in the fixture would try to reset a
    context variable belonging to a thread that no longer exists.
    """

    def build(version: str, *, may_write: bool = True) -> Any:
        agent = real_build_agent(version, may_write=may_write)
        original: Any = agent.run_sync

        def run_sync(*args: Any, **kwargs: Any) -> Any:
            with agent.override(model=TestModel()):
                return original(*args, **kwargs)

        agent.run_sync = run_sync  # type: ignore[method-assign]
        return agent

    monkeypatch.setattr(app_module, "build_agent", build)


def _chat_span(exporter: InMemorySpanExporter) -> dict[str, object]:
    finished = exporter.get_finished_spans()
    chat = [s for s in finished if s.name == "chat"]
    assert chat, f"no chat span, got {[s.name for s in finished]}"
    return dict(chat[0].attributes or {})


def test_chat_span_names_the_prompt(
    db: Session, spans: InMemorySpanExporter, fake_model: None
) -> None:
    """Rule 3. A run that cannot say which prompt produced it is not a
    record, it is an anecdote."""
    assert client.post("/chat", json=ASK, headers=HEADERS).status_code == 200

    attrs = _chat_span(spans)
    assert attrs["ops.prompt_version"] == "v2"
    assert isinstance(attrs["ops.prompt_sha"], str)
    assert len(str(attrs["ops.prompt_sha"])) == 16


def test_chat_span_records_the_decision(
    db: Session, spans: InMemorySpanExporter, fake_model: None
) -> None:
    client.post("/chat", json=ASK, headers=HEADERS)

    attrs = _chat_span(spans)
    assert attrs["ops.decision"] in {"refund", "refuse", "escalate"}
    assert attrs["ops.reason_code"]
    assert "ops.run_id" in attrs


def test_chat_span_identifies_the_caller(
    db: Session, spans: InMemorySpanExporter, fake_model: None
) -> None:
    client.post("/chat", json=ASK, headers=HEADERS)

    attrs = _chat_span(spans)
    assert attrs["ops.customer_id"] == "cus_001"
    assert attrs["ops.scope"] in {"read", "write"}


def test_the_span_carries_no_raw_customer_text(
    db: Session, spans: InMemorySpanExporter, fake_model: None
) -> None:
    """9.5, the trace half. The message is on the span, redacted."""
    client.post(
        "/chat",
        json={"message": "refund ord_C1_01, my card is 4111 1111 1111 1111"},
        headers=HEADERS,
    )

    attrs = _chat_span(spans)
    assert "4111" not in str(attrs["ops.message"])
    assert "[CARD]" in str(attrs["ops.message"])


def test_metrics_move_when_a_run_completes(
    db: Session, spans: InMemorySpanExporter, fake_model: None
) -> None:
    """A counter nobody increments is a dashboard that always looks calm."""
    from prometheus_client import REGISTRY

    def total() -> float:
        return sum(
            sample.value
            for metric in REGISTRY.collect()
            if metric.name == "ops_agent_runs"
            for sample in metric.samples
            if sample.name == "ops_agent_runs_total"
        )

    before = total()
    assert client.post("/chat", json=ASK, headers=HEADERS).status_code == 200
    assert total() == before + 1

    assert client.get("/metrics").status_code == 200
