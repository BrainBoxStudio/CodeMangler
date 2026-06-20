"""Unifies file, folder, and raw-text inputs into a common list of SourceFile."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.input.file_walker import walk_files

DEFAULT_ENCODING = "utf-8"
# Legacy Windows/MSVC source files are frequently saved in the system codepage
# rather than UTF-8 (accented author names, degree symbols, etc. in comments).
# cp1252 never raises UnicodeDecodeError for byte values 0x00-0xFF except a
# handful of unassigned C1 control codes, so errors="replace" is the only
# remaining safety net, not the common case.
_FALLBACK_ENCODING = "cp1252"


@dataclass
class SourceFile:
    relative_path: Path
    content: str
    source_path: Path | None = None
    used_fallback_encoding: bool = False


def _decode_bytes(raw: bytes) -> tuple[str, bool]:
    # No newline translation is applied here (matching the previous
    # `read_text(newline="")` behaviour) — original line endings are
    # preserved verbatim for an exact restore.
    try:
        return raw.decode(DEFAULT_ENCODING), False
    except UnicodeDecodeError:
        return raw.decode(_FALLBACK_ENCODING, errors="replace"), True


def load_text(text: str) -> list[SourceFile]:
    return [SourceFile(relative_path=Path("input.txt"), content=text, source_path=None)]


def load_file(path: Path) -> list[SourceFile]:
    path = Path(path)
    content, used_fallback = _decode_bytes(path.read_bytes())
    return [
        SourceFile(
            relative_path=Path(path.name),
            content=content,
            source_path=path,
            used_fallback_encoding=used_fallback,
        )
    ]


def load_folder(root: Path, settings: Settings) -> list[SourceFile]:
    root = Path(root).resolve()
    sources: list[SourceFile] = []
    for path in walk_files(root, settings):
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        content, used_fallback = _decode_bytes(raw)
        sources.append(
            SourceFile(
                relative_path=path.relative_to(root),
                content=content,
                source_path=path,
                used_fallback_encoding=used_fallback,
            )
        )
    return sources


def load_input(
    *, input_path: Path | None, text: str | None, settings: Settings
) -> list[SourceFile]:
    if text is not None:
        return load_text(text)
    if input_path is None:
        raise ValueError("Either input_path or text must be provided")
    input_path = Path(input_path)
    if input_path.is_dir():
        return load_folder(input_path, settings)
    return load_file(input_path)
