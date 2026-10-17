"""Beat 13.1's finding, enforced.

Past ten concurrent callers the service did less work as load rose, and
excess requests died on a pool timeout five seconds later. A caller that
cannot be served should learn so at the door.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from ops_agent.api import limits


def test_a_full_service_refuses_at_the_door(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two slots, two callers in, the third is shed rather than queued."""
    import threading

    monkeypatch.setattr(limits, "_inflight", threading.BoundedSemaphore(2))

    with (
        limits.bounded_concurrency(),
        limits.bounded_concurrency(),
        pytest.raises(HTTPException) as caught,
        limits.bounded_concurrency(),
    ):
        pass

    assert caught.value.status_code == 503
    assert caught.value.headers == {"Retry-After": "1"}


def test_slots_come_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """A released slot is reusable. A semaphore that leaks on the way out
    turns a busy minute into a permanently dead process."""
    import threading

    monkeypatch.setattr(limits, "_inflight", threading.BoundedSemaphore(1))

    for _ in range(3):
        with limits.bounded_concurrency():
            pass
