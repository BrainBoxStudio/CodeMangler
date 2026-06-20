"""app/input/loader.py — non-UTF-8 source file handling.

Regression for a real crash: a legacy MSVC C++ file containing a cp1252-
encoded byte (0xF1, accented author name in a comment) made `load_file` raise
UnicodeDecodeError and crash the whole sanitize run instead of degrading
gracefully.
"""
from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.input.loader import load_file, load_folder


def test_load_file_falls_back_to_cp1252_for_non_utf8_bytes(tmp_path: Path):
    path = tmp_path / "legacy.cpp"
    path.write_bytes(b"// author: Mu\xf1oz\nint main() { return 0; }\n")

    sources = load_file(path)

    assert len(sources) == 1
    assert sources[0].used_fallback_encoding is True
    assert "Muñoz" in sources[0].content  # decoded as 'n with tilde', not U+FFFD


def test_load_file_plain_utf8_is_unaffected(tmp_path: Path):
    path = tmp_path / "plain.cpp"
    path.write_bytes("// café\nint main() { return 0; }\n".encode("utf-8"))

    sources = load_file(path)

    assert sources[0].used_fallback_encoding is False
    assert "café" in sources[0].content


def test_load_folder_includes_non_utf8_files_instead_of_silently_dropping_them(tmp_path: Path):
    (tmp_path / "legacy.cpp").write_bytes(b"// Mu\xf1oz\nint x;\n")
    (tmp_path / "plain.cpp").write_bytes(b"int y;\n")

    sources = load_folder(tmp_path, Settings())

    names = {s.relative_path.as_posix() for s in sources}
    assert names == {"legacy.cpp", "plain.cpp"}
