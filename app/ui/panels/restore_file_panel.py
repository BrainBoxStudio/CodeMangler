"""DeMangler File / Folder mode panel: source + dest pickers, Restore button, live log.

The mangle map is supplied via the DeMangler tab's [Reset Mangle] button (loaded
once, shared across all sub-modes) rather than a per-panel field.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

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

from app.ui.workers import RestoreWorker

logger = logging.getLogger(__name__)

_LOG_COLORS = {
    "[ERROR]": "#E74C3C",
    "[WARN]":  "#F39C12",
    "⚠":       "#F39C12",
    "Done.":   "#2ECC71",
    "[OK]":    "#2ECC71",
}


class RestoreFilePanel(QWidget):
    """Shared panel for both File and Folder restore modes."""

    def __init__(
        self,
        folder_mode: bool,
        set_status: Callable[[str], None],
        get_map_path: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.folder_mode = folder_mode
        self._set_status = set_status
        self._get_map_path = get_map_path
        self._worker: RestoreWorker | None = None
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
        self.src_edit.setPlaceholderText(f"Select sanitized {hint}…")
        src_row.addWidget(self.src_edit, stretch=1)
        src_browse = QPushButton("…")
        src_browse.setFixedWidth(32)
        src_browse.setToolTip("Browse for sanitized source")
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

        # ── Restore button ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.process_btn = QPushButton("  Restore  ")
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
        if self.folder_mode:
            path = QFileDialog.getExistingDirectory(self, "Select Sanitized Folder")
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Sanitized File", filter="All files (*.*)"
            )
        if not path:
            return
        logger.info("_browse_source: selected path=%s", path)
        self.src_edit.setText(path)

        if not self.dst_edit.text():
            self.dst_edit.setText(str(Path(path).parent / "restored"))

    def _browse_destination(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if path:
            self.dst_edit.setText(path)

    # ── processing ────────────────────────────────────────────────────────────

    def _on_process(self) -> None:
        source = self.src_edit.text().strip()
        dest = self.dst_edit.text().strip()
        map_path = self._get_map_path().strip()

        if not source:
            logger.warning("_on_process: source path is empty")
            self._log("  Source path is required.", error=True)
            return
        if not dest:
            logger.warning("_on_process: destination path is empty")
            self._log("  Destination path is required.", error=True)
            return
        if not map_path:
            logger.warning("_on_process: no mangle map loaded")
            self._log("  Load a mangle map first (Reset Mangle).", error=True)
            return

        mode = "folder" if self.folder_mode else "file"
        logger.info(
            "_on_process: launching restore worker  mode=%s  source=%s  map=%s  dest=%s",
            mode, source, map_path, dest,
        )

        self.process_btn.setEnabled(False)
        self.log_edit.clear()
        self._set_status("Restoring…")
        self._log(f"Source      : {source}")
        self._log(f"Map file    : {map_path}")
        self._log(f"Destination : {dest}")
        self._log("")

        self._worker = RestoreWorker(
            mode=mode,
            source=source,
            destination=dest,
            map_path=map_path,
            parent=self,
        )
        self._worker.log_line.connect(self._log)
        self._worker.finished.connect(self._on_done)
        self._worker.start()
        logger.debug("_on_process: worker thread started")

    def _on_done(self, code: int) -> None:
        logger.info("_on_done: worker finished  exit_code=%d", code)
        self.process_btn.setEnabled(True)
        if code == 0:
            self._set_status("Restore complete.")
        else:
            self._set_status("Error during restore.")
            self._log("[ERROR] Restore failed — see log above.", error=True)

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
        logger.debug("clear: resetting restore file panel  folder_mode=%s", self.folder_mode)
        self.src_edit.clear()
        self.dst_edit.clear()
        self.log_edit.clear()
        self.process_btn.setEnabled(True)
