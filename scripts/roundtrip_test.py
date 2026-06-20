"""Automated end-to-end round-trip proof for CodeMangler.

1. Reads Test/Original
2. Detects language per file
3. Sanitizes ("mangles") each file
4. Writes sanitized output to Test/Mangled
5. Writes the change map to Test/Mangled/mangler.json
6. Reads Test/Mangled
7. Applies Test/Mangled/mangler.json
8. Restores original values ("demangles")
9. Writes restored output to Test/Unmangled
10. Compares Test/Original against Test/Unmangled byte-for-byte

Usage: python scripts/roundtrip_test.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DIR = PROJECT_ROOT / "Test" / "Original"
MANGLED_DIR = PROJECT_ROOT / "Test" / "Mangled"
UNMANGLED_DIR = PROJECT_ROOT / "Test" / "Unmangled"
MAP_FILENAME = "mangler.json"
MAP_PATH = MANGLED_DIR / MAP_FILENAME


def _clean(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def sanitize_step() -> dict[str, tuple[str, list]]:
    from app.anonymization.code_anonymizer import anonymize_text
    from app.anonymization.fake_value_generator import FakeValueGenerator
    from app.code.identifier_extractor import build_identifier_catalog
    from app.config import Settings
    from app.detection.language_detector import detect_language
    from app.input.loader import load_input
    from app.mapping.map_writer import build_map, write_map

    settings = Settings()
    generator = FakeValueGenerator()

    sources = load_input(input_path=ORIGINAL_DIR, text=None, settings=settings)
    if not sources:
        print(f"No files found under {ORIGINAL_DIR}")
        sys.exit(1)

    print(f"[1/5] Read {len(sources)} file(s) from {ORIGINAL_DIR}")

    # Project-wide identifier catalog: a class/function/variable defined in
    # one file (e.g. a header) is renamed consistently in every other file
    # that only references it (e.g. `Class::method` in the matching .cpp).
    languages = {src.relative_path: detect_language(src.relative_path, src.content) for src in sources}
    catalog = build_identifier_catalog([(languages[src.relative_path], src.content) for src in sources])
    print(f"      Project-wide identifier catalog: {len(catalog.definitions)} eligible name(s)")

    MANGLED_DIR.mkdir(parents=True, exist_ok=True)
    per_file_changes: dict[str, tuple[str, list]] = {}
    for src in sources:
        rel = src.relative_path.as_posix()
        language = languages[src.relative_path]
        sanitized, changes = anonymize_text(
            src.content, settings, generator, language=language, catalog=catalog
        )
        per_file_changes[rel] = (language, changes)

        out_path = MANGLED_DIR / src.relative_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(sanitized, encoding="utf-8", newline="")
        print(f"      {rel:<28} language={language:<10} changes={len(changes)}")

    print("[2/5] Writing change map")
    sanitization_map = build_map(per_file_changes)
    write_map(sanitization_map, MAP_PATH)
    total = sum(len(c) for _, c in per_file_changes.values())
    print(f"      Total replacements : {total}")
    print(f"      Map written        : {MAP_PATH}")
    return per_file_changes


def restore_step() -> dict[str, str]:
    from app.config import Settings
    from app.input.loader import load_input
    from app.mapping.map_reader import read_map
    from app.mapping.restore_engine import restore_files

    settings = Settings()
    print(f"[3/5] Read mangled files from {MANGLED_DIR}")
    sources = load_input(input_path=MANGLED_DIR, text=None, settings=settings)
    sanitized_files = {
        src.relative_path.as_posix(): src.content
        for src in sources
        if src.relative_path.name != MAP_FILENAME
    }
    print(f"      ({len(sanitized_files)} file(s), excluding {MAP_FILENAME})")

    print(f"[4/5] Applying {MAP_PATH} to restore originals")
    sanitization_map = read_map(MAP_PATH)
    restored_files = restore_files(sanitized_files, sanitization_map)

    UNMANGLED_DIR.mkdir(parents=True, exist_ok=True)
    for rel, content in restored_files.items():
        out_path = UNMANGLED_DIR / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8", newline="")
    print(f"      Restored {len(restored_files)} file(s) to {UNMANGLED_DIR}")
    return restored_files


def compare_step() -> bool:
    print(f"[5/5] Comparing {ORIGINAL_DIR} vs {UNMANGLED_DIR}")
    original_files = sorted(
        p.relative_to(ORIGINAL_DIR).as_posix() for p in ORIGINAL_DIR.rglob("*") if p.is_file()
    )
    unmangled_files = sorted(
        p.relative_to(UNMANGLED_DIR).as_posix() for p in UNMANGLED_DIR.rglob("*") if p.is_file()
    )

    if original_files != unmangled_files:
        print("      FAIL: file sets differ")
        print("        only in Original :", sorted(set(original_files) - set(unmangled_files)))
        print("        only in Unmangled:", sorted(set(unmangled_files) - set(original_files)))
        return False

    all_match = True
    for rel in original_files:
        orig_bytes = (ORIGINAL_DIR / rel).read_bytes()
        restored_bytes = (UNMANGLED_DIR / rel).read_bytes()
        match = orig_bytes == restored_bytes
        status = "OK" if match else "MISMATCH"
        print(f"      [{status}] {rel}  ({len(orig_bytes)} bytes)")
        if not match:
            all_match = False
    return all_match


def main() -> None:
    _clean(MANGLED_DIR)
    _clean(UNMANGLED_DIR)

    sanitize_step()
    restore_step()
    ok = compare_step()

    print()
    if ok:
        print("RESULT: PASS - Test/Original and Test/Unmangled are byte-for-byte identical.")
        sys.exit(0)
    else:
        print("RESULT: FAIL - differences found between Test/Original and Test/Unmangled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
