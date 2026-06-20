"""CLI commands: sanitize, restore, scan (CLAUDE.md section 10)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from app.anonymization.code_anonymizer import anonymize_text, collect_findings
from app.anonymization.fake_value_generator import FakeValueGenerator
from app.code.identifier_extractor import build_identifier_catalog
from app.config import MangleOptions, Settings
from app.detection.language_detector import detect_language
from app.input.loader import SourceFile, load_input
from app.mapping.map_reader import read_map
from app.mapping.map_writer import MAP_FILENAME, build_map, write_map
from app.mapping.restore_engine import restore_files

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def _build_catalog_if_needed(sources: list[SourceFile], settings: Settings):
    """Builds a project-wide identifier catalog when there's more than one
    file in this run, so a name defined in one file (e.g. a class in a
    header) is recognised as eligible for renaming in every other file that
    only references it (e.g. via `Class::method` in the matching .cpp).
    A single file is already "the whole project," so this is skipped then.
    """
    if not settings.mangle_options.code_identifiers or len(sources) <= 1:
        return None
    return build_identifier_catalog(
        [(detect_language(source.relative_path, source.content), source.content) for source in sources]
    )


def _write_outputs(output_root: Path, files: dict[str, str]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for relative_path, content in files.items():
        destination = output_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        # newline="" matches loader.py's read: write line endings verbatim.
        destination.write_text(content, encoding="utf-8", newline="")


@app.command()
def sanitize(
    input: Optional[Path] = typer.Option(None, "--input", help="File or folder to sanitize."),
    text: Optional[str] = typer.Option(None, "--text", help="Raw text to sanitize."),
    output: Optional[Path] = typer.Option(None, "--output", help="Output directory."),
    map_path: Path = typer.Option(Path(MAP_FILENAME), "--map", help="Mapping JSON file to write."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report findings, write nothing."),
    encrypt_map: bool = typer.Option(False, "--encrypt-map", help="Encrypt the mapping file."),
    password: Optional[str] = typer.Option(None, "--password", help="Password for --encrypt-map."),
    mangle_sensitive_info: bool = typer.Option(
        True, "--mangle-sensitive-info/--no-mangle-sensitive-info",
        help="Replace secrets/PII/network/path/org values.",
    ),
    mangle_code_identifiers: bool = typer.Option(
        True, "--mangle-code-identifiers/--no-mangle-code-identifiers",
        help="Rename locally-defined variables/functions/classes/etc. (requires the '[code]' extra).",
    ),
) -> None:
    if text is None and input is None:
        err_console.print("[red]Provide either --input or --text.[/red]")
        raise typer.Exit(code=1)
    if encrypt_map and not password:
        err_console.print("[red]--encrypt-map requires --password.[/red]")
        raise typer.Exit(code=1)

    settings = Settings(
        mangle_options=MangleOptions(
            sensitive_info=mangle_sensitive_info, code_identifiers=mangle_code_identifiers
        )
    )
    generator = FakeValueGenerator()
    sources: list[SourceFile] = load_input(input_path=input, text=text, settings=settings)
    catalog = _build_catalog_if_needed(sources, settings)

    per_file_changes = {}
    sanitized_files: dict[str, str] = {}
    for source in sources:
        if source.used_fallback_encoding:
            err_console.print(
                f"[yellow]Warning: {source.relative_path} was not valid UTF-8; "
                "decoded with a cp1252 fallback (saved as UTF-8).[/yellow]"
            )
        language = detect_language(source.relative_path, source.content)
        sanitized, changes = anonymize_text(
            source.content, settings, generator, language=language, catalog=catalog
        )
        relative_posix = source.relative_path.as_posix()
        sanitized_files[relative_posix] = sanitized
        per_file_changes[relative_posix] = (language, changes)

    total_changes = sum(len(changes) for _, changes in per_file_changes.values())
    console.print(f"[bold]{total_changes}[/bold] replacement(s) across {len(sources)} file(s).")

    if text is not None:
        console.print(sanitized_files["input.txt"])

    if dry_run:
        console.print("[yellow]Dry run: no files written.[/yellow]")
        return

    if output is not None:
        _write_outputs(output, sanitized_files)
        console.print(f"Sanitized output written to [bold]{output}[/bold]")

    sanitization_map = build_map(per_file_changes)
    write_map(sanitization_map, map_path, password=password if encrypt_map else None)
    console.print(f"Mapping written to [bold]{map_path}[/bold]")
    err_console.print(
        "[red]Warning: the mapping file contains original sensitive values. "
        "Do not share it publicly.[/red]"
    )


@app.command()
def restore(
    input: Path = typer.Option(..., "--input", help="Sanitized file or folder to restore."),
    output: Path = typer.Option(..., "--output", help="Output directory for restored files."),
    map_path: Path = typer.Option(Path(MAP_FILENAME), "--map", help="Mapping JSON file to read."),
    password: Optional[str] = typer.Option(None, "--password", help="Password if the map is encrypted."),
) -> None:
    settings = Settings()
    sources = load_input(input_path=input, text=None, settings=settings)
    sanitized_files = {source.relative_path.as_posix(): source.content for source in sources}

    try:
        sanitization_map = read_map(map_path, password=password)
    except ValueError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        err_console.print(
            f"[red]Could not read mapping file: {exc}[/red]\n"
            "[red]If it was written with --encrypt-map, pass --password.[/red]"
        )
        raise typer.Exit(code=1) from exc
    restored_files = restore_files(sanitized_files, sanitization_map)

    _write_outputs(output, restored_files)
    console.print(f"Restored output written to [bold]{output}[/bold]")


@app.command()
def scan(
    input: Path = typer.Option(..., "--input", help="File or folder to scan."),
) -> None:
    settings = Settings()
    generator = FakeValueGenerator()
    sources = load_input(input_path=input, text=None, settings=settings)
    catalog = _build_catalog_if_needed(sources, settings)

    table = Table(title="CodeMangler scan results")
    table.add_column("File")
    table.add_column("Language")
    table.add_column("Category")
    table.add_column("Count", justify="right")

    total = 0
    for source in sources:
        language = detect_language(source.relative_path, source.content)
        findings = collect_findings(
            source.content, settings, language=language, generator=generator, catalog=catalog
        )
        if not findings:
            continue
        counts: dict[str, int] = {}
        for finding in findings:
            counts[finding.category] = counts.get(finding.category, 0) + 1
        for category, count in sorted(counts.items()):
            table.add_row(source.relative_path.as_posix(), language, category, str(count))
            total += count

    console.print(table)
    console.print(f"[bold]{total}[/bold] potential sensitive value(s) found.")
