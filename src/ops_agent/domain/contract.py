"""The output contract from SPEC.md section 4, as real code this time."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Decision(StrEnum):
    REFUND = "refund"
    REFUSE = "refuse"
    ESCALATE = "escalate"


class Outcome(BaseModel):
    """Every run ends as exactly one of these. No free text replaces it."""

    decision: Decision
    amount_minor: int | None = Field(default=None, ge=1)
    reason_code: str = Field(min_length=1, max_length=16)
    reason_text: str = Field(min_length=1, max_length=400)
    policy_article: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
