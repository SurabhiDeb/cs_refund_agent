"""Scrub PII before anything is written down.

The model sees the raw message, because it cannot help without it. Nothing
else does. A card number in a log file outlives the conversation, gets
copied into a ticket, and ends up somewhere nobody is auditing.

Patterns are ordered deliberately. A card number is a long run of digits and
so is a phone number, so cards are matched first.
"""

from __future__ import annotations

import logging
import re
from typing import Any

# Order matters. The first pattern to match a span wins.
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARD]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b(?:sk|key|token|bearer)[-_ ][A-Za-z0-9._-]{8,}\b", re.I), "[KEY]"),
    (re.compile(r"\+?\d[\d\s().-]{8,}\d"), "[PHONE]"),
]


def redact(text: str) -> str:
    """Replace anything that looks like PII with a label."""
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    """Applied to the root logger, so a careless log call cannot leak.

    Redacting at the call site means remembering every call site. Redacting
    at the handler means forgetting is safe.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                scrubbed: tuple[Any, ...] = tuple(
                    redact(a) if isinstance(a, str) else a for a in record.args
                )
                record.args = scrubbed

        return True


def install() -> None:
    """Attach the filter to every handler on the root logger."""
    logging.basicConfig(level=logging.INFO)
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(RedactingFilter())
