"""Who is calling, and what they are allowed to do.

The agent never supplies this. It is built at the edge from the API key, so no prompt,
no tool argument, and no injected instruction can change it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolContext:
    customer_id: str
    write_enabled: bool
    # R5, one refund per conversation. The identity fields above can never
    # change. This list can, because issue_refund appends to it.
    refunds_issued: list[str] = field(default_factory=list)
