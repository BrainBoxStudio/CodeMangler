"""About tab: author/version on the left, a scalable logo on the right."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app import __author__, __version__
from app.ui.resource_paths import resource_path

logger = logging.getLogger(__name__)


class _ScalableImageLabel(QLabel):
    """A QLabel that keeps its pixmap proportionally scaled to its own size."""

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._original = pixmap
        self.setMinimumSize(1, 1)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rescale()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._original.isNull():
            return
        scaled = self._original.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


class AboutPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(24)

        # ── Left: author / version ───────────────────────────────────────────
        left_shell = QVBoxLayout()
        left_shell.addStretch()

        text_frame = QFrame()
        text_frame.setObjectName("aboutTextFrame")
        text_frame.setStyleSheet(
            """
            QFrame#aboutTextFrame {
                border: 1.5px solid #7FB3D3;
                border-radius: 10px;
                background: transparent;
            }
            """
        )

        left = QVBoxLayout(text_frame)
        left.setContentsMargins(18, 18, 18, 18)
        left.setSpacing(10)

        title = QLabel("CodeMangler")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1A5276;")
        left.addWidget(title)

        description = QLabel(
            "CodeMangler is a smart sanitization tool designed to help developers, "
            "teams, and technical users safely share code or text online without "
            "exposing sensitive information.\n\n"
            "Code, logs, configuration files, and plain text often contain confidential "
            "details such as usernames, passwords, API keys, server names, internal "
            "function names, customer data, or organization-specific identifiers. "
            "Sharing such content publicly can create security and privacy risks.\n\n"
            "CodeMangler scans your input and replaces sensitive information with safe, "
            "arbitrary values while preserving the overall structure and readability of "
            "the content. The sanitized output can then be used confidently in public "
            "forums, documentation, AI tools, issue trackers, or support discussions.\n\n"
            "Once your public editing, review, or troubleshooting work is complete, "
            "CodeMangler allows you to restore the sanitized content back to its "
            "original form with just a few simple clicks. This makes it easy to protect "
            "sensitive data without losing the ability to recover the original text "
            "when needed.\n\n"
            "With CodeMangler, you can share smarter, collaborate safely, and keep "
            "confidential information protected."
        )
        description.setWordWrap(True)
        description.setMaximumWidth(520)
        description.setStyleSheet("font-size: 13px; color: #1A3550;")
        left.addWidget(description)
        left.addSpacing(8)

        author = QLabel(f"Author: {__author__}")
        author.setStyleSheet("font-size: 13px; color: #1A3550;")
        left.addWidget(author)

        version = QLabel(f"Version: {__version__}")
        version.setStyleSheet("font-size: 13px; color: #1A3550;")
        left.addWidget(version)

        left_shell.addWidget(text_frame)
        left_shell.addStretch()
        root.addLayout(left_shell, stretch=1)

        # ── Right: scalable logo, vertically centred ─────────────────────────
        image_path = resource_path("code_mangler_app_icon_1024.png")
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            logger.warning("AboutPanel: could not load image at %s", image_path)
        self.image_label = _ScalableImageLabel(pixmap)
        root.addWidget(self.image_label, stretch=1)
