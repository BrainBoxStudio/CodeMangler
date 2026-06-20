"""File / Folder mode panel: source + dest pickers, Process button, live log."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.workers import SanitizeWorker

logger = logging.getLogger(__name__)

_LOG_COLORS = {
    "[ERROR]": "#E74C3C",
    "[WARN]":  "#F39C12",
    "⚠":       "#F39C12",
    "Done.":   "#2ECC71",
    "[OK]":    "#2ECC71",
}


class FilePanel(QWidget):
    """Shared panel for both File and Folder input modes."""

    def __init__(
        self,
        folder_mode: bool,
        set_status: Callable[[str], None],
        on_changes_ready: Callable[[object], None],
        get_mangle_options: Callable[[], object],
        get_known_terms: Callable[[], dict[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.folder_mode = folder_mode
        self._set_status = set_status
        self._on_changes_ready = on_changes_ready
        self._get_mangle_options = get_mangle_options
        self._get_known_terms = get_known_terms
        self._worker: SanitizeWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # ── Source row ────────────────────────────────────────────────────────
        src_row = QHBoxLayout()
        lbl_src = QLabel("Source")
        lbl_src.setFixedWidth(80)
        lbl_src.setStyleSheet("font-weight: bold;")
        src_row.addWidget(lbl_src)
        self.src_edit = QLineEdit()
        hint = "folder" if self.folder_mode else "file or folder"
        self.src_edit.setPlaceholderText(f"Select source {hint}…")
        src_row.addWidget(self.src_edit, stretch=1)
        src_browse = QPushButton("…")
        src_browse.setFixedWidth(32)
        src_browse.setToolTip("Browse for source")
        src_browse.clicked.connect(self._browse_source)
        src_row.addWidget(src_browse)
        root.addLayout(src_row)

        # ── Destination row ───────────────────────────────────────────────────
        dst_row = QHBoxLayout()
        lbl_dst = QLabel("Destination")
        lbl_dst.setFixedWidth(80)
        lbl_dst.setStyleSheet("font-weight: bold;")
        dst_row.addWidget(lbl_dst)
        self.dst_edit = QLineEdit()
        self.dst_edit.setPlaceholderText("Select output folder…")
        dst_row.addWidget(self.dst_edit, stretch=1)
        dst_browse = QPushButton("…")
        dst_browse.setFixedWidth(32)
        dst_browse.setToolTip("Browse for destination folder")
        dst_browse.clicked.connect(self._browse_destination)
        dst_row.addWidget(dst_browse)
        root.addLayout(dst_row)

        # ── Process button ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.process_btn = QPushButton("  Process  ")
        self.process_btn.setObjectName("processBtn")
        self.process_btn.clicked.connect(self._on_process)
        btn_row.addWidget(self.process_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── Live log ──────────────────────────────────────────────────────────
        log_box = QGroupBox("Live Log")
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(6, 6, 6, 6)
        self.log_edit = QTextEdit()
        self.log_edit.setObjectName("logArea")
        self.log_edit.setReadOnly(True)
        log_layout.addWidget(self.log_edit)
        root.addWidget(log_box, stretch=1)

    # ── browse helpers ────────────────────────────────────────────────────────

    def _browse_source(self) -> None:
        logger.debug("_browse_source: opening dialog  folder_mode=%s", self.folder_mode)
        if self.folder_mode:
            path = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Source File",
                filter="All files (*.*)",
            )
        if not path:
            logger.debug("_browse_source: dialog cancelled")
            return
        logger.info("_browse_source: selected path=%s", path)
        self.src_edit.setText(path)
        if not self.dst_edit.text():
            suggested = str(Path(path).parent / "sanitized")
            logger.debug("_browse_source: auto-filled destination=%s", suggested)
            self.dst_edit.setText(suggested)

    def _browse_destination(self) -> None:
        logger.debug("_browse_destination: opening dialog")
        path = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if path:
            logger.info("_browse_destination: selected path=%s", path)
            self.dst_edit.setText(path)
        else:
            logger.debug("_browse_destination: dialog cancelled")

    # ── processing ────────────────────────────────────────────────────────────

    def _on_process(self) -> None:
        source = self.src_edit.text().strip()
        dest = self.dst_edit.text().strip()
        logger.debug("_on_process: source=%r  dest=%r", source, dest)

        if not source:
            logger.warning("_on_process: source path is empty")
            self._log("  Source path is required.", error=True)
            return
        if not dest:
            logger.warning("_on_process: destination path is empty")
            self._log("  Destination path is required.", error=True)
            return

        mode = "folder" if self.folder_mode else "file"
        map_path = str(Path(dest) / "sanitization_map.json")
        logger.info(
            "_on_process: launching worker  mode=%s  source=%s  dest=%s  map=%s",
            mode, source, dest, map_path,
        )

        self.process_btn.setEnabled(False)
        self.log_edit.clear()
        self._set_status("Processing…")
        self._on_changes_ready(None)
        self._log(f"Source      : {source}")
        self._log(f"Destination : {dest}")
        self._log("")

        self._worker = SanitizeWorker(
            mode=mode,
            source=source,
            destination=dest,
            map_path=map_path,
            mangle_options=self._get_mangle_options(),
            known_terms=self._get_known_terms(),
            parent=self,
        )
        self._worker.log_line.connect(self._log)
        self._worker.changes_ready.connect(self._on_changes_ready)
        self._worker.finished.connect(self._on_done)
        self._worker.start()
        logger.debug("_on_process: worker thread started")

    def _on_done(self, code: int) -> None:
        logger.info("_on_done: worker finished  exit_code=%d", code)
        self.process_btn.setEnabled(True)
        if code == 0:
            self._set_status("Sanitization complete.")
        else:
            self._set_status("Error during processing.")
            self._log("[ERROR] Processing failed — see log above.", error=True)

    # ── log helpers ───────────────────────────────────────────────────────────

    def _log(self, line: str, *, error: bool = False) -> None:
        cursor = self.log_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        fmt = QTextCharFormat()
        color = "#E74C3C" if error else self._line_color(line)
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(line + "\n")

        sb = self.log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    @staticmethod
    def _line_color(line: str) -> str:
        for keyword, color in _LOG_COLORS.items():
            if keyword in line:
                return color
        return "#A8D8EA"

    # ── Clear All ─────────────────────────────────────────────────────────────

    def clear(self) -> None:
        logger.debug("clear: resetting file panel  folder_mode=%s", self.folder_mode)
        self.src_edit.clear()
        self.dst_edit.clear()
        self.log_edit.clear()
        self.process_btn.setEnabled(True)
