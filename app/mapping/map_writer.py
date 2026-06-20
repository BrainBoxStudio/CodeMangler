"""Builds and writes sanitization_map.json (CLAUDE.md section 7)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import orjson

from app.anonymization.text_anonymizer import TextChange
from app.mapping.schema import ChangeEntry, FileEntry, SanitizationMap
from app.security.map_encryption import encrypt_map_bytes

MAP_FILENAME = "sanitization_map.json"


def build_map(
    per_file_changes: dict[str, tuple[str, list[TextChange]]],
) -> SanitizationMap:
    """per_file_changes: relative POSIX path -> (language, changes for that file)."""
    files: list[FileEntry] = []
    changes: list[ChangeEntry] = []
    counter = 0
    for relative_path, (language, file_changes) in per_file_changes.items():
        files.append(FileEntry(path=relative_path, language=language))
        for change in file_changes:
            counter += 1
            changes.append(
                ChangeEntry(
                    id=f"chg_{counter:06d}",
                    file=relative_path,
                    type=change.type,
                    category=change.category,
                    language=language,
                    original=change.original,
                    replacement=change.replacement,
                    start_line=change.start_line,
                    start_col=change.start_col,
                    end_line=change.end_line,
                    end_col=change.end_col,
                    scope="text",
                    confidence=change.confidence,
                    detector=change.detector,
                    reversible=True,
                )
            )
    return SanitizationMap(
        created_at=datetime.now(timezone.utc).isoformat(),
        session_id=str(uuid.uuid4()),
        mode="sanitize",
        files=files,
        changes=changes,
    )


def write_map(sanitization_map: SanitizationMap, path: Path, password: str | None = None) -> None:
    data = orjson.dumps(sanitization_map.model_dump(), option=orjson.OPT_INDENT_2)
    if password:
        data = encrypt_map_bytes(data, password)
    Path(path).write_bytes(data)
