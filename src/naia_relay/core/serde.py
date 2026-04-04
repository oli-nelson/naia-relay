from __future__ import annotations

import json
from typing import Any


def to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, separators=(",", ":"), sort_keys=True)


def from_json(text: str) -> dict[str, Any]:
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("JSON payload must decode to an object")
    return loaded
