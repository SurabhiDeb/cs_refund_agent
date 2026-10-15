"""Beat 9.5. Nothing sensitive survives into a log line.

No model calls anywhere here. Redaction is string handling.
"""

from __future__ import annotations

import logging

import pytest

from ops_agent.obs.redact import RedactingFilter, redact


def test_card_number_is_removed() -> None:
    out = redact("my card is 4111 1111 1111 1111 please refund")
    assert "4111" not in out
    assert "[CARD]" in out


def test_card_number_without_spaces_is_removed() -> None:
    assert "[CARD]" in redact("4111111111111111")


def test_email_is_removed() -> None:
    out = redact("contact me at surabhi@example.com")
    assert "example.com" not in out
    assert "[EMAIL]" in out


def test_api_key_is_removed() -> None:
    assert "[KEY]" in redact("here is my key sk-abcdef123456789")


def test_phone_number_is_removed() -> None:
    out = redact("call me on +91 98765 43210")
    assert "98765" not in out


def test_ordinary_text_is_left_alone() -> None:
    """Over-redaction is its own bug. An unreadable log is not a safe log."""
    message = "refund order ord_C1_01, it arrived damaged"
    assert redact(message) == message


def test_amounts_are_not_redacted() -> None:
    assert redact("refund me 3200") == "refund me 3200"


def test_the_filter_scrubs_a_log_record(caplog: pytest.LogCaptureFixture) -> None:
    """The filter is the real defence, because it does not depend on the
    person writing the log call remembering to redact."""
    logger = logging.getLogger("ops_agent.test")
    logger.addFilter(RedactingFilter())

    with caplog.at_level(logging.INFO):
        logger.info("leak 4111 1111 1111 1111")

    assert "4111" not in caplog.text
