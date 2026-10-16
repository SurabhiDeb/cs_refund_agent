"""Beat 10.5. Nothing sensitive leaves in an exception report.

scrub_event is tested directly. Sending real events to Sentry to find out
what they contain is the wrong way round.
"""

from __future__ import annotations

from typing import Any, cast

from sentry_sdk.types import Event

from ops_agent.obs.errors import scrub_event


def _scrubbed(**kwargs: Any) -> dict[str, Any]:
    """Build an event, scrub it, hand back a plain dict to assert on."""
    base: dict[str, Any] = {"message": "ok"}
    base.update(kwargs)

    out = scrub_event(cast(Event, base), {})
    assert out is not None
    return cast(dict[str, Any], out)


def test_message_is_redacted() -> None:
    out = _scrubbed(message="card 4111 1111 1111 1111 failed")
    assert "4111" not in out["message"]


def test_exception_value_is_redacted() -> None:
    out = _scrubbed(exception={"values": [{"value": "bad input: surabhi@example.com"}]})
    assert "example.com" not in out["exception"]["values"][0]["value"]


def test_request_body_never_travels() -> None:
    """The body is the customer's own words. It does not leave at all."""
    out = _scrubbed(request={"data": {"message": "my card is 4111111111111111"}})
    assert "data" not in out["request"]


def test_api_key_header_is_replaced() -> None:
    out = _scrubbed(request={"headers": {"X-API-Key": "dev-key-owner"}})
    assert out["request"]["headers"]["X-API-Key"] == "[REDACTED]"


def test_breadcrumbs_are_redacted() -> None:
    out = _scrubbed(breadcrumbs={"values": [{"message": "saw 4111 1111 1111 1111"}]})
    assert "4111" not in out["breadcrumbs"]["values"][0]["message"]


def test_an_ordinary_event_survives() -> None:
    out = _scrubbed(message="refund ord_C1_01 refused, code E4")
    assert out["message"] == "refund ord_C1_01 refused, code E4"
