"""The worker process. It does the work. Kill it and Temporal waits.

uv run python -m ops_agent.workflows.worker
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.worker import Worker

from ops_agent.config import settings
from ops_agent.obs.tracing import install_tracing
from ops_agent.workflows.refund import (
    TASK_QUEUE,
    RefundWorkflow,
    confirm_with_processor,
    issue_refund_activity,
    mark_refund_failed,
)


async def main() -> None:
    # The worker is its own process, so it needs its own exporter. Without
    # this, activity spans are created and dropped.
    install_tracing()

    client = await Client.connect(
        settings.temporal_address,
        interceptors=[TracingInterceptor()],
    )
    # The activity talks to Postgres with a blocking driver, so it runs in a
    # thread rather than on the event loop.
    with ThreadPoolExecutor(max_workers=4) as executor:
        worker = Worker(
            client,
            task_queue=TASK_QUEUE,
            workflows=[RefundWorkflow],
            activities=[
                issue_refund_activity,
                confirm_with_processor,
                mark_refund_failed,
            ],
            activity_executor=executor,
        )
        print(f"worker listening on {TASK_QUEUE}")
        await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("worker stopped")
