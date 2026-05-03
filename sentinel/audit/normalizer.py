from __future__ import annotations

import json
from typing import Any


class NormalizationError(Exception):
    pass


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        # Deterministic key ordering.
        return {k: _normalize_value(value[k]) for k in sorted(value.keys())}
    raise NormalizationError(f"unsupported type for normalization: {type(value)!r}")


def normalize_for_hash(value: Any) -> str:
    """Return deterministic JSON string for hashing using fixed ordering rules."""
    normalized = _normalize_value(value)
    return json.dumps(normalized, separators=(",", ":"), sort_keys=False)

