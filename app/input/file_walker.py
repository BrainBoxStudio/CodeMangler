"""Recursive directory walker with directory pruning, file-glob ignoring, and
a pure-Python binary-file heuristic (no libmagic — see CLAUDE.md feasibility
notes: python-magic's Windows packaging is unreliable).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from app.config import Settings
from app.input.ignore_rules import build_ignore_spec, is_ignored_file

BINARY_PROBE_BYTES = 8192


def is_probably_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(BINARY_PROBE_BYTES)
    except OSError:
        return True
    if b"\x00" in chunk:
        return True
    try:
        chunk.decode("utf-8")
        return False
    except UnicodeDecodeError:
        pass
    # Legacy Windows/MSVC source is often saved in the system codepage rather
    # than UTF-8 (accented names/symbols in comments) — without this check
    # such files are misclassified as binary and silently skipped during
    # folder walks. Mirrors the same cp1252 fallback in
    # app/input/loader.py::_decode_bytes.
    try:
        chunk.decode("cp1252")
        return False
    except UnicodeDecodeError:
        return True


def walk_files(root: Path, settings: Settings) -> Iterator[Path]:
    root = Path(root).resolve()
    spec = build_ignore_spec(settings)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in settings.ignored_dirs)
        current_dir = Path(dirpath)
        for filename in sorted(filenames):
            path = current_dir / filename
            relative = path.relative_to(root)
            if is_ignored_file(relative.as_posix(), spec):
                continue
            if is_probably_binary(path):
                continue
            yield path
