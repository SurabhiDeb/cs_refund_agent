"""The one way a tool says no.

Every refusal carries a code from SPEC.md, so failures can be counted
per mode instead of blurring into aggregate.
"""

from __future__ import annotations


class ToolRefusal(Exception):
    """The tool declined. Not a crash, an answer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
