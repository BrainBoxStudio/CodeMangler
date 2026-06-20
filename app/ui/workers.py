"""Background QThread workers — keep the UI responsive during sanitization."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class SanitizeWorker(QThread):
    log_line = Signal(str)     # emitted for each progress line
    finished = Signal(int)     # exit code: 0 = success
    text_result = Signal(str)  # text mode only: sanitized output
    changes_ready = Signal(object)  # dict[str, tuple[str, list[TextChange]]]

    def __init__(
        self,
        *,
        mode: str,          # "text" | "file" | "folder"
        source: str = "",
        destination: str = "",
        map_path: str = "",
        input_text: str = "",
        language: str | None = None,  # text mode only: respects a user override
        mangle_options=None,          # MangleOptions | None: None = defaults (everything on)
        known_terms: dict[str, str] | None = None,  # Settings.known_terms front-end (Settings tab)
        parent=None,
    ):
        super().__init__(parent)
        self.mode = mode
        self.source = source
        self.destination = destination
        self.map_path = map_path
        self.input_text = input_text
        self.language = language
        self.mangle_options = mangle_options
        self.known_terms = known_terms
        logger.debug(
            "SanitizeWorker created  mode=%s  source=%r  dest=%r  map=%r  text_len=%d  language=%r",
            mode, source, destination, map_path, len(input_text), language,
        )

    def run(self) -> None:
        logger.debug("Worker thread started  mode=%s", self.mode)
        try:
            if self.mode == "text":
                self._run_text()
            else:
                self._run_files()
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            logger.error("Worker unhandled exception:\n%s", tb)
            self.log_line.emit(f"[ERROR] {exc}")
            self.log_line.emit(tb)
            self.finished.emit(1)

    def _build_settings(self):
        from app.config import Settings

        kwargs = {}
        if self.mangle_options:
            kwargs["mangle_options"] = self.mangle_options
        if self.known_terms:
            kwargs["known_terms"] = self.known_terms
        return Settings(**kwargs)

    # ── text mode ─────────────────────────────────────────────────────────────

    def _run_text(self) -> None:
        from pathlib import Path

        from app.anonymization.code_anonymizer import anonymize_text
        from app.anonymization.fake_value_generator import FakeValueGenerator
        from app.detection.language_detector import detect_language

        logger.debug("_run_text: input length=%d chars", len(self.input_text))
        settings = self._build_settings()
        generator = FakeValueGenerator()

        language = self.language or detect_language(Path("input.txt"), self.input_text)
        logger.debug("_run_text: running anonymize_text  language=%s", language)
        sanitized, changes = anonymize_text(self.input_text, settings, generator, language=language)

        logger.debug(
            "_run_text: done  changes=%d  sanitized_len=%d  language=%s",
            len(changes), len(sanitized), language,
        )
        self.log_line.emit(f"Found {len(changes)} replacement(s).")
        self.text_result.emit(sanitized)
        self.changes_ready.emit({"input.txt": (language, changes)})
        self.finished.emit(0)
        logger.debug("_run_text: signals emitted")

    # ── file / folder mode ────────────────────────────────────────────────────

    def _run_files(self) -> None:
        from app.anonymization.code_anonymizer import anonymize_text
        from app.anonymization.fake_value_generator import FakeValueGenerator
        from app.code.identifier_extractor import build_identifier_catalog
        from app.detection.language_detector import detect_language
        from app.input.loader import load_input
        from app.mapping.map_writer import build_map, write_map

        settings = self._build_settings()
        generator = FakeValueGenerator()
        source_path = Path(self.source)

        logger.info("_run_files: loading source=%s", source_path)
        self.log_line.emit(f"Loading: {source_path}")
        sources = load_input(input_path=source_path, text=None, settings=settings)
        logger.debug("_run_files: loaded %d source file(s)", len(sources))

        if not sources:
            logger.warning("_run_files: no processable files found in %s", source_path)
            self.log_line.emit("No processable files found.")
            self.finished.emit(0)
            return
        self.log_line.emit(f"Found {len(sources)} file(s) to process.")

        out_root = Path(self.destination)
        out_root.mkdir(parents=True, exist_ok=True)
        logger.debug("_run_files: output root=%s", out_root)

        # Project-wide identifier catalog: a class/function/variable defined
        # in one file (e.g. a header) is renamed consistently in every other
        # file that only references it (e.g. `Class::method` in the matching
        # .cpp) — skipped for a single file, which is already "the whole
        # project" on its own.
        catalog = None
        if settings.mangle_options.code_identifiers and len(sources) > 1:
            catalog = build_identifier_catalog(
                [(detect_language(s.relative_path, s.content), s.content) for s in sources]
            )
            logger.debug(
                "_run_files: built project-wide identifier catalog (%d eligible name(s))",
                len(catalog.definitions),
            )

        per_file_changes: dict[str, tuple[str, list]] = {}
        for src in sources:
            rel = src.relative_path.as_posix()
            logger.debug("_run_files: processing %s", rel)
            self.log_line.emit(f"  [{rel}]")
            if src.used_fallback_encoding:
                logger.warning("_run_files: %s was not valid UTF-8; used cp1252 fallback", rel)
                self.log_line.emit(
                    f"      ⚠ Not valid UTF-8 — decoded with a cp1252 fallback (saved as UTF-8)."
                )

            language = detect_language(src.relative_path, src.content)
            logger.debug("_run_files: detected language=%s for %s", language, rel)

            sanitized, changes = anonymize_text(
                src.content, settings, generator, language=language, catalog=catalog
            )
            logger.debug(
                "_run_files: %s  changes=%d  input_len=%d  output_len=%d",
                rel, len(changes), len(src.content), len(sanitized),
            )
            per_file_changes[rel] = (language, changes)

            out_path = out_root / src.relative_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(sanitized, encoding="utf-8", newline="")
            logger.debug("_run_files: written %s", out_path)

            noun = "replacement" if len(changes) == 1 else "replacements"
            self.log_line.emit(f"      {len(changes)} {noun}  →  {out_path}")

        map_out = (
            Path(self.map_path)
            if self.map_path
            else out_root / "sanitization_map.json"
        )
        logger.debug("_run_files: building and writing map to %s", map_out)
        sanitization_map = build_map(per_file_changes)
        write_map(sanitization_map, map_out)
        self.log_line.emit(f"  Map: {map_out}")
        self.log_line.emit(
            "  ⚠  Map contains original values — do NOT share it publicly."
        )

        total = sum(len(ch) for _, ch in per_file_changes.values())
        logger.info(
            "_run_files: complete  total_changes=%d  files=%d", total, len(sources)
        )
        self.log_line.emit(
            f"Done. {total} replacement(s) across {len(sources)} file(s)."
        )
        self.changes_ready.emit(per_file_changes)
        self.finished.emit(0)


class RestoreWorker(QThread):
    log_line = Signal(str)     # emitted for each progress line
    finished = Signal(int)     # exit code: 0 = success
    text_result = Signal(str)  # text mode only: restored output

    def __init__(
        self,
        *,
        mode: str,          # "text" | "file" | "folder"
        source: str = "",
        destination: str = "",
        map_path: str = "",
        input_text: str = "",
        password: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.mode = mode
        self.source = source
        self.destination = destination
        self.map_path = map_path
        self.input_text = input_text
        self.password = password
        logger.debug(
            "RestoreWorker created  mode=%s  source=%r  dest=%r  map=%r  text_len=%d  has_password=%s",
            mode, source, destination, map_path, len(input_text), bool(password),
        )

    def run(self) -> None:
        logger.debug("Worker thread started  mode=%s", self.mode)
        try:
            if self.mode == "text":
                self._run_text()
            else:
                self._run_files()
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            logger.error("Worker unhandled exception:\n%s", tb)
            self.log_line.emit(f"[ERROR] {exc}")
            self.log_line.emit(tb)
            self.finished.emit(1)

    def _read_map(self):
        from app.mapping.map_reader import read_map

        self.log_line.emit(f"Reading map: {self.map_path}")
        try:
            return read_map(Path(self.map_path), password=self.password)
        except ValueError as exc:
            self.log_line.emit(f"[ERROR] {exc}")
            return None
        except Exception as exc:
            self.log_line.emit(f"[ERROR] Could not read mapping file: {exc}")
            self.log_line.emit(
                "[ERROR] If it was written with --encrypt-map, supply the password."
            )
            return None

    # ── text mode ─────────────────────────────────────────────────────────────

    def _run_text(self) -> None:
        from app.mapping.restore_engine import restore_text

        sanitization_map = self._read_map()
        if sanitization_map is None:
            self.finished.emit(1)
            return

        changes = [c for c in sanitization_map.changes if c.file == "input.txt"]
        logger.debug("_run_text: restoring with %d change(s)", len(changes))
        restored = restore_text(self.input_text, changes)
        self.log_line.emit(f"Restored using {len(changes)} change(s).")
        self.text_result.emit(restored)
        self.finished.emit(0)

    # ── file / folder mode ────────────────────────────────────────────────────

    def _run_files(self) -> None:
        from app.config import Settings
        from app.input.loader import load_input
        from app.mapping.restore_engine import restore_files

        settings = Settings()
        source_path = Path(self.source)

        logger.info("_run_files: loading source=%s", source_path)
        self.log_line.emit(f"Loading: {source_path}")
        sources = load_input(input_path=source_path, text=None, settings=settings)
        if not sources:
            logger.warning("_run_files: no processable files found in %s", source_path)
            self.log_line.emit("No processable files found.")
            self.finished.emit(0)
            return
        self.log_line.emit(f"Found {len(sources)} file(s) to process.")

        sanitization_map = self._read_map()
        if sanitization_map is None:
            self.finished.emit(1)
            return

        sanitized_files = {src.relative_path.as_posix(): src.content for src in sources}
        restored_files = restore_files(sanitized_files, sanitization_map)

        out_root = Path(self.destination)
        out_root.mkdir(parents=True, exist_ok=True)
        logger.debug("_run_files: output root=%s", out_root)

        for rel, content in restored_files.items():
            out_path = out_root / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8", newline="")
            logger.debug("_run_files: written %s", out_path)
            self.log_line.emit(f"  [{rel}]  →  {out_path}")

        logger.info("_run_files: complete  files=%d", len(restored_files))
        self.log_line.emit(f"Done. {len(restored_files)} file(s) restored.")
        self.finished.emit(0)
