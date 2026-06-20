"""DeMangler text mode panel: split sanitized/restored editors.

The mangle map is supplied via the DeMangler tab's [Reset Mangle] button
(loaded once, shared across all sub-modes) rather than a per-panel field —
mirroring the Mangler tab's Text mode, which has no extra input rows either.
"""
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
from app.ui.workers import RestoreWorker

logger = logging.getLogger(__name__)

_FRAMES = ("▷▷", "▶▷", "▶▶", "▷▶", "▷▷")


class RestoreTextPanel(QWidget):
    """Split-view panel: left = sanitized text, right = restored output."""

    def __init__(
        self,
        set_status: Callable[[str], None],
        get_map_path: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._set_status = set_status
        self._get_map_path = get_map_path
        self._worker: RestoreWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ── Editors ───────────────────────────────────────────────────────────
        left = QVBoxLayout()
        lbl_in = QLabel("Sanitized Input")
        lbl_in.setStyleSheet("font-weight: bold; color: #1A5276;")
        left.addWidget(lbl_in)
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Paste sanitized text here…")
        self.input_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        left.addWidget(self.input_edit)
        body = QHBoxLayout()
        body.setSpacing(10)
        body.addLayout(left, stretch=1)

        centre = QVBoxLayout()
        centre.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.arrow_btn = AnimatedArrowButton(_FRAMES, tooltip="Restore  (Ctrl+Enter)", parent=self)
        self.arrow_btn.clicked.connect(self._on_process)
        centre.addWidget(self.arrow_btn)
        body.addLayout(centre)

        right = QVBoxLayout()
        lbl_out = QLabel("Restored Output")
        lbl_out.setStyleSheet("font-weight: bold; color: #1A5276;")
        right.addWidget(lbl_out)
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText("Restored output will appear here…")
        self.output_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        right.addWidget(self.output_edit)
        body.addLayout(right, stretch=1)

        root.addLayout(body, stretch=1)

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
        map_path = self._get_map_path().strip()

        if not text.strip():
            logger.debug("_on_process: empty input, ignoring click")
            return
        if not map_path:
            logger.warning("_on_process: no mangle map loaded")
            self._set_status("Load a mangle map first (Reset Mangle).")
            return

        logger.info("_on_process: starting restore  input_len=%d  map=%s", len(text), map_path)
        self.arrow_btn.start_animation()
        self.output_edit.clear()
        self._set_status("Restoring…")

        self._worker = RestoreWorker(
            mode="text",
            input_text=text,
            map_path=map_path,
            parent=self,
        )
        self._worker.log_line.connect(self._on_log)
        self._worker.text_result.connect(self._on_result)
        self._worker.finished.connect(self._on_done)
        self._worker.start()
        logger.debug("_on_process: worker thread started")

    def _on_log(self, line: str) -> None:
        logger.debug("worker log: %s", line)
        if line.startswith("[ERROR]"):
            self._set_status(line)

    def _on_result(self, restored: str) -> None:
        logger.debug("_on_result: received restored text  len=%d", len(restored))
        self.output_edit.setPlainText(restored)

    def _on_done(self, code: int) -> None:
        logger.info("_on_done: worker finished  exit_code=%d", code)
        self.arrow_btn.stop_animation()
        if code == 0:
            self._set_status("Done.")

    # ── Clear All ─────────────────────────────────────────────────────────────

    def clear(self) -> None:
        logger.debug("clear: resetting restore text panel")
        self.input_edit.clear()
        self.output_edit.clear()
        self.arrow_btn.stop_animation()
