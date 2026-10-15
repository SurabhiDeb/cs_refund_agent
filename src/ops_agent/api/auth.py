"""Who is calling, decided by the key alone.

Rule 12. The body never names a customer. The hash is compared, never the
key itself, so the database holds nothing worth stealing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select

from ops_agent.db.models import Customer
from ops_agent.db.session import session_scope


@dataclass(frozen=True)
class Caller:
    customer_id: str
    scope: str

    @property
    def may_write(self) -> bool:
        return self.scope == "write"


def resolve_key(api_key: str | None) -> Caller:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key.")

    digest = hashlib.sha256(api_key.encode()).hexdigest()
    with session_scope() as session:
        customer = session.scalar(
            select(Customer).where(Customer.api_key_hash == digest)
        )
        if customer is None:
            raise HTTPException(status_code=401, detail="Unknown API key.")
        return Caller(customer_id=customer.id, scope=customer.scope)
