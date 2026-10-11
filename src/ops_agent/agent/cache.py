"""Disk cache for whole runs.

Credits are a real cost, so a repeat run must be free. Scores must also be
reproducible, which they cannot be if the model is asked again.

The key covers every input that could change the answer. Getting a cache key
wrong is worse than having no cache, because the numbers still look fine.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).resolve().parents[3] / "cache" / "runs"


def run_key(
    *,
    prompt_sha: str,
    dataset_sha: str,
    model: str,
    request: str,
    order_id: str,
    write_enabled: bool,
) -> str:
    """A fingerprint of everything that could change the outcome."""
    payload = json.dumps(
        {
            "prompt_sha": prompt_sha,
            "dataset_sha": dataset_sha,
            "model": model,
            "request": request,
            "order_id": order_id,
            "write_enabled": write_enabled,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def load(key: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    record: dict[str, Any] = json.loads(path.read_text())
    record["replayed_from_cache"] = True
    return record


def save(key: str, record: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(record, indent=2) + "\n")
