"""Project-wide identifier consistency across files (Folder mode).

Regression for a real gap: a class defined in one file (e.g. a header) but
only *used* via `Class::method` in another (e.g. the matching .cpp) was
renamed in the header but left completely untouched in the .cpp, because
app/code/identifier_extractor.py's eligibility check only ever looked at one
file's occurrences at a time. build_identifier_catalog() pre-scans every file
in a run so eligibility is "defined anywhere in this run," not "defined in
this exact file."
"""
from __future__ import annotations

from typer.testing import CliRunner

from app.anonymization.code_anonymizer import anonymize_text
from app.anonymization.fake_value_generator import FakeValueGenerator
from app.cli import app
from app.code.identifier_extractor import build_identifier_catalog
from app.config import Settings

runner = CliRunner()

_HEADER = "class Foo {\npublic:\n    void bar();\n    int count;\n};\n"
_SOURCE = "void Foo::bar() {\n    count = count + 1;\n}\n"


def test_build_identifier_catalog_finds_definitions_across_files():
    catalog = build_identifier_catalog([("cpp", _HEADER), ("cpp", _SOURCE)])

    assert catalog.definitions["Foo"] == "class"
    assert catalog.definitions["bar"] == "method"
    assert catalog.definitions["count"] == "variable"


def test_with_catalog_class_renamed_consistently_in_usage_only_file():
    settings = Settings()
    generator = FakeValueGenerator()
    catalog = build_identifier_catalog([("cpp", _HEADER), ("cpp", _SOURCE)])

    header_out, header_changes = anonymize_text(_HEADER, settings, generator, language="cpp", catalog=catalog)
    source_out, source_changes = anonymize_text(_SOURCE, settings, generator, language="cpp", catalog=catalog)

    assert "Foo" not in source_out  # previously left untouched
    assert {c.original for c in source_changes} >= {"Foo", "bar", "count"}
    # Same fake name used in both files.
    header_fake = next(c.replacement for c in header_changes if c.original == "Foo")
    source_fake = next(c.replacement for c in source_changes if c.original == "Foo")
    assert header_fake == source_fake
    assert header_fake in header_out
    assert source_fake in source_out


def test_without_catalog_usage_only_file_leaves_class_untouched():
    # Documents the pre-existing single-file behavior is unchanged when no
    # catalog is supplied (Text mode / single File mode).
    settings = Settings()
    generator = FakeValueGenerator()

    header_out, header_changes = anonymize_text(_HEADER, settings, generator, language="cpp")
    source_out, source_changes = anonymize_text(_SOURCE, settings, generator, language="cpp")

    assert "Foo" in {c.original for c in header_changes}
    assert "Foo" not in {c.original for c in source_changes}
    assert "Foo" in source_out  # left exactly as-is, no local definition in this file


def test_cli_sanitize_folder_renames_class_consistently_across_header_and_source(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "foo.h").write_text(_HEADER, encoding="utf-8", newline="")
    (src_dir / "foo.cpp").write_text(_SOURCE, encoding="utf-8", newline="")

    sanitized_dir = tmp_path / "sanitized"
    map_path = tmp_path / "sanitization_map.json"
    result = runner.invoke(
        app,
        ["sanitize", "--input", str(src_dir), "--output", str(sanitized_dir), "--map", str(map_path)],
    )
    assert result.exit_code == 0, result.output

    header_out = (sanitized_dir / "foo.h").read_text(encoding="utf-8", newline="")
    source_out = (sanitized_dir / "foo.cpp").read_text(encoding="utf-8", newline="")
    assert "Foo" not in header_out
    assert "Foo" not in source_out

    restored_dir = tmp_path / "restored"
    result = runner.invoke(
        app,
        ["restore", "--input", str(sanitized_dir), "--output", str(restored_dir), "--map", str(map_path)],
    )
    assert result.exit_code == 0, result.output

    assert (restored_dir / "foo.h").read_text(encoding="utf-8", newline="") == _HEADER
    assert (restored_dir / "foo.cpp").read_text(encoding="utf-8", newline="") == _SOURCE
