"""Hybrid restore algorithm (CLAUDE.md section 8).

Pass 1 is position-anchored: per file, process changes bottom-to-top by the
recorded start position (recorded against the sanitized output - see
text_anonymizer.apply_findings) so an earlier splice never invalidates the
offset of a change still waiting to be processed, and only restore if the
text at that exact span still equals `replacement` (i.e. the user didn't
touch that span).

Pass 2 is a fallback for any change whose position drifted because the user
edited elsewhere in the file: whole-document substitution, longest
`replacement` string first, word-boundary-aware for identifier-like tokens so
it doesn't match inside unrelated new text the user added.
"""
from __future__ import annotations

import re

from app.mapping.schema import ChangeEntry, SanitizationMap

_WORD_TOKEN = re.compile(r"^\w+$")


def _line_col_to_offset(text: str, line: int, col: int) -> int | None:
    lines = text.split("\n")
    if line < 1 or line > len(lines):
        return None
    offset = sum(len(l) + 1 for l in lines[: line - 1]) + (col - 1)
    if offset < 0 or offset > len(text):
        return None
    return offset


def _restore_by_position(text: str, changes: list[ChangeEntry]) -> tuple[str, list[ChangeEntry]]:
    ordered = sorted(changes, key=lambda c: (c.start_line, c.start_col), reverse=True)
    remaining: list[ChangeEntry] = []
    for change in ordered:
        start = _line_col_to_offset(text, change.start_line, change.start_col)
        end = _line_col_to_offset(text, change.end_line, change.end_col)
        if start is None or end is None or text[start:end] != change.replacement:
            remaining.append(change)
            continue
        text = text[:start] + change.original + text[end:]
    return text, remaining


def _restore_by_text_fallback(text: str, changes: list[ChangeEntry]) -> str:
    for change in sorted(changes, key=lambda c: len(c.replacement), reverse=True):
        if _WORD_TOKEN.match(change.replacement):
            pattern = re.compile(rf"\b{re.escape(change.replacement)}\b")
        else:
            pattern = re.compile(re.escape(change.replacement))
        text = pattern.sub(change.original.replace("\\", "\\\\"), text)
    return text


def restore_text(text: str, changes: list[ChangeEntry]) -> str:
    text, remaining = _restore_by_position(text, changes)
    if remaining:
        text = _restore_by_text_fallback(text, remaining)
    return text


def restore_files(
    sanitized_files: dict[str, str], sanitization_map: SanitizationMap
) -> dict[str, str]:
    changes_by_file: dict[str, list[ChangeEntry]] = {}
    for change in sanitization_map.changes:
        changes_by_file.setdefault(change.file, []).append(change)

    restored: dict[str, str] = {}
    for relative_path, text in sanitized_files.items():
        file_changes = changes_by_file.get(relative_path, [])
        restored[relative_path] = restore_text(text, file_changes) if file_changes else text
    return restored
