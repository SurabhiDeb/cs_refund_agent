"""The cache key changes when any input changes.

A cache key that ignores part of the input is worse than no cache, because
the wrong answer is served silently and the numbers still look plausible.
That is the chatbot-lab failure this test exists to prevent.

Limitation: this tests cache.py directly. The cache inside run_case is not
covered here, because run_case builds its own agent and cannot be handed a
fake model. That path is first exercised for real at Beat 4.6.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ops_agent.agent import cache


def key_for(
    *,
    prompt_sha: str = "aaa111",
    dataset_sha: str = "bbb222",
    model: str = "anthropic/claude-haiku-5.5",
    request: str = "I want a refund.",
    order_id: str = "ord_C1_01",
    write_enabled: bool = True,
) -> str:
    """A key with one field changed at a time, and everything else fixed."""
    return cache.run_key(
        prompt_sha=prompt_sha,
        dataset_sha=dataset_sha,
        model=model,
        request=request,
        order_id=order_id,
        write_enabled=write_enabled,
    )


@pytest.fixture(autouse=True)
def temp_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never touch the real cache directory from a test."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "runs")


def test_a_missing_key_returns_nothing() -> None:
    assert cache.load("never-written") is None


def test_a_saved_record_comes_back_marked_as_replayed() -> None:
    key = key_for()
    cache.save(key, {"decision": "refund", "replayed_from_cache": False})

    loaded = cache.load(key)

    assert loaded is not None
    assert loaded["decision"] == "refund"
    assert loaded["replayed_from_cache"] is True


@pytest.mark.parametrize(
    "changed",
    [
        key_for(prompt_sha="changed"),
        key_for(dataset_sha="changed"),
        key_for(model="anthropic/claude-sonnet-5"),
        key_for(request="Different wording entirely."),
        key_for(order_id="ord_C2_01"),
        key_for(write_enabled=False),
    ],
    ids=[
        "prompt_sha",
        "dataset_sha",
        "model",
        "request",
        "order_id",
        "write_enabled",
    ],
)
def test_every_input_changes_the_key(changed: str) -> None:
    """If a field could change the answer, it must change the key."""
    assert key_for() != changed


def test_the_same_inputs_give_the_same_key() -> None:
    assert key_for() == key_for()
