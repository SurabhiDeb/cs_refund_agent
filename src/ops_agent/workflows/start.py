"""Start one refund workflow by hand.

    uv run python -m ops_agent.workflows.start ord_C1_01 3200

The workflow id is derived from the request too, so starting the same
refund twice is the same workflow rather than a second payment.
"""

from __future__ import annotations

import asyncio
import sys

from temporalio.client import Client

from ops_agent.config import settings
from ops_agent.workflows.refund import (
    TASK_QUEUE,
    RefundRequest,
    RefundWorkflow,
    derive_key,
)


async def main() -> None:
    request = RefundRequest(
        customer_id="cus_001",
        order_id=sys.argv[1],
        amount_minor=int(sys.argv[2]),
        reason="Beat 8 durability test",
    )

    client = await Client.connect(settings.temporal_address)
    result = await client.execute_workflow(
        RefundWorkflow.run,
        request,
        id=f"refund-{derive_key(request)}",
        task_queue=TASK_QUEUE,
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
