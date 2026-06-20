"""Text mode panel: split input/output editors with an animated sanitize button."""
from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets import AnimatedArrowButton
from app.ui.workers import SanitizeWorker

logger = logging.getLogger(__name__)

_FRAMES = ("▷▷", "▶▷", "▶▶", "▷▶", "▷▷")

# Internal language name -> display label mapping (inverse of main_window.LANG_MAP)
_INTERNAL_TO_DISPLAY: dict[str, str] = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "c": "C",
    "cpp": "C++",
    "csharp": "C#",
    "go": "Go",
    "rust": "Rust",
    "sql": "SQL",
    "shell": "Shell",
    "json": "JSON",
    "yaml": "YAML",
    "xml": "XML",
    "markdown": "Markdown",
    "text": "Plain Text",
}
_DISPLAY_TO_INTERNAL: dict[str, str] = {v: k for k, v in _INTERNAL_TO_DISPLAY.items()}


class TextPanel(QWidget):
    """Split-view panel: left = raw input, right = sanitized output."""

    def __init__(
        self,
        get_language: Callable[[], str],
        set_language: Callable[[str], None],
        set_status: Callable[[str], None],
        on_changes_ready: Callable[[object], None],
        get_mangle_options: Callable[[], object],
        get_known_terms: Callable[[], dict[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_language = get_language
        self._set_language = set_language
        self._set_status = set_status
        self._on_changes_ready = on_changes_ready
        self._get_mangle_options = get_mangle_options
        self._get_known_terms = get_known_terms
        self._worker: SanitizeWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ── Left: input ──────────────────────────────────────────────────────
        left = QVBoxLayout()
        lbl_in = QLabel("Input")
        lbl_in.setStyleSheet("font-weight: bold; color: #1A5276;")
        left.addWidget(lbl_in)
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Paste your code or text here…")
        self.input_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        left.addWidget(self.input_edit)
        root.addLayout(left, stretch=1)

        # ── Centre: arrow ─────────────────────────────────────────────────────
        centre = QVBoxLayout()
        centre.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.arrow_btn = AnimatedArrowButton(_FRAMES, tooltip="Sanitize  (Ctrl+Enter)", parent=self)
        self.arrow_btn.clicked.connect(self._on_process)
        centre.addWidget(self.arrow_btn)
        root.addLayout(centre)

        # ── Right: output ─────────────────────────────────────────────────────
        right = QVBoxLayout()
        lbl_out = QLabel("Sanitized Output")
        lbl_out.setStyleSheet("font-weight: bold; color: #1A5276;")
        right.addWidget(lbl_out)
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText("Sanitized output will appear here…")
        self.output_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        right.addWidget(self.output_edit)
        root.addLayout(right, stretch=1)

    # ── keyboard shortcut ─────────────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self._on_process()
        else:
            super().keyPressEvent(event)

    # ── processing ────────────────────────────────────────────────────────────

    def _on_process(self) -> None:
        text = self.input_edit.toPlainText()
        if not text.strip():
            logger.debug("_on_process: empty input, ignoring click")
            return

        display_lang = self._get_language()
        language_override = _DISPLAY_TO_INTERNAL.get(display_lang)
        logger.info(
            "_on_process: starting sanitization  input_len=%d  language_override=%r",
            len(text), language_override,
        )
        self.arrow_btn.start_animation()
        self.output_edit.clear()
        self._set_status("Processing…")
        self._on_changes_ready(None)

        self._worker = SanitizeWorker(
            mode="text",
            input_text=text,
            language=language_override,
            mangle_options=self._get_mangle_options(),
            known_terms=self._get_known_terms(),
            parent=self,
        )
        self._worker.text_result.connect(self._on_result)
        self._worker.changes_ready.connect(self._on_changes_ready)
        self._worker.finished.connect(self._on_done)
        self._worker.start()
        logger.debug("_on_process: worker thread started")

    def _on_result(self, sanitized: str) -> None:
        logger.debug("_on_result: received sanitized text  len=%d", len(sanitized))
        self.output_edit.setPlainText(sanitized)
        self._auto_detect_language()

    def _on_done(self, code: int) -> None:
        logger.info("_on_done: worker finished  exit_code=%d", code)
        self.arrow_btn.stop_animation()
        self._set_status("Done." if code == 0 else "Error — check output.")

    # ── Clear All ─────────────────────────────────────────────────────────────

    def clear(self) -> None:
        logger.debug("clear: resetting text panel")
        self.input_edit.clear()
        self.output_edit.clear()
        self.arrow_btn.stop_animation()

    def _auto_detect_language(self) -> None:
        current = self._get_language()
        logger.debug("_auto_detect_language: current combo value=%r", current)
        if current != "Auto-detect":
            logger.debug("_auto_detect_language: user override in place, skipping detection")
            return
        from app.detection.language_detector import detect_language
        from pathlib import Path

        lang_internal = detect_language(
            Path("input.txt"), self.input_edit.toPlainText()
        )
        display = _INTERNAL_TO_DISPLAY.get(lang_internal, "Plain Text")
        logger.info("_auto_detect_language: detected=%s  display=%s", lang_internal, display)
        self._set_language(display)
