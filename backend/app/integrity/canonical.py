import json
from typing import Any

SCHEMA_VERSION = 1


def canonical_json(obj: Any) -> str:
    """Deterministic serialization: sorted keys, no whitespace, UTF-8 safe ASCII escaping."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
