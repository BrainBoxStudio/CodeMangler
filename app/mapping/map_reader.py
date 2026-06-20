"""Loads and validates sanitization_map.json."""
from __future__ import annotations

from pathlib import Path

import orjson

from app.mapping.schema import SanitizationMap
from app.security.map_encryption import decrypt_map_bytes


def read_map(path: Path, password: str | None = None) -> SanitizationMap:
    blob = Path(path).read_bytes()
    if password:
        blob = decrypt_map_bytes(blob, password)
    data = orjson.loads(blob)
    return SanitizationMap.model_validate(data)
