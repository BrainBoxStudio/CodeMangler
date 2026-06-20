"""Settings tab: theme selection (incl. custom base color) and the Mangle
Keywords list (a UI front-end for Settings.known_terms, app/config.py).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.styles import PREDEFINED_PALETTES, Palette, derive_palette_from_base_color
from app.ui.user_settings import UserSettings, save_user_settings

logger = logging.getLogger(__name__)

_THEME_NAMES = [*PREDEFINED_PALETTES.keys(), "Custom"]
_DEFAULT_CUSTOM_COLOR = "#2E86C1"


class SettingsPanel(QWidget):
    def __init__(
        self,
        get_initial_settings: Callable[[], UserSettings],
        apply_theme: Callable[[Palette], None],
        set_status: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._apply_theme = apply_theme
        self._set_status = set_status
        initial = get_initial_settings()
        self._custom_base_color = initial.custom_base_color or _DEFAULT_CUSTOM_COLOR
        self._saved_keywords: list[str] = list(initial.keywords)
        self._build_ui(initial)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, initial: UserSettings) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addWidget(self._build_theme_group(initial))
        root.addWidget(self._build_keywords_group(initial), stretch=1)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)

    def _build_theme_group(self, initial: UserSettings) -> QGroupBox:
        group = QGroupBox("Theme")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(_THEME_NAMES)
        if initial.theme_name in _THEME_NAMES:
            self.theme_combo.setCurrentText(initial.theme_name)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        layout.addWidget(self.theme_combo)

        self.pick_color_btn = QPushButton("Pick Color...")
        self.pick_color_btn.clicked.connect(self._on_pick_color)
        layout.addWidget(self.pick_color_btn)

        self.color_swatch = QLabel()
        self.color_swatch.setFixedSize(28, 22)
        self._update_swatch()
        layout.addWidget(self.color_swatch)

        layout.addStretch()
        self._update_custom_controls_visibility(initial.theme_name)
        return group

    def _build_keywords_group(self, initial: UserSettings) -> QGroupBox:
        group = QGroupBox("Mangle Keywords")
        layout = QVBoxLayout(group)

        hint = QLabel(
            "Org/project/internal names that should always be mangled, one per line "
            "(e.g. internal product or server names that aren't otherwise detectable)."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.keywords_edit = QTextEdit()
        self.keywords_edit.setPlainText("\n".join(initial.keywords))
        layout.addWidget(self.keywords_edit, stretch=1)

        upload_row = QHBoxLayout()
        upload_row.addStretch()
        self.upload_btn = QPushButton("Upload File...")
        self.upload_btn.clicked.connect(self._on_upload_file)
        upload_row.addWidget(self.upload_btn)
        layout.addLayout(upload_row)

        return group

    # ── helpers ───────────────────────────────────────────────────────────────

    def _update_swatch(self) -> None:
        self.color_swatch.setStyleSheet(
            f"background-color: {self._custom_base_color}; border: 1px solid #888;"
        )

    def _update_custom_controls_visibility(self, theme_name: str) -> None:
        is_custom = theme_name == "Custom"
        self.pick_color_btn.setVisible(is_custom)
        self.color_swatch.setVisible(is_custom)

    def _resolve_palette(self, theme_name: str) -> Palette:
        if theme_name == "Custom":
            return derive_palette_from_base_color(self._custom_base_color)
        return PREDEFINED_PALETTES[theme_name]

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_theme_changed(self, theme_name: str) -> None:
        logger.debug("SettingsPanel: theme changed to %r", theme_name)
        self._update_custom_controls_visibility(theme_name)
        self._apply_theme(self._resolve_palette(theme_name))

    def _on_pick_color(self) -> None:
        from PySide6.QtGui import QColor

        color = QColorDialog.getColor(QColor(self._custom_base_color), self, "Pick Base Color")
        if not color.isValid():
            logger.debug("SettingsPanel: color picker cancelled")
            return
        self._custom_base_color = color.name()
        self._update_swatch()
        self._apply_theme(self._resolve_palette("Custom"))

    def _on_upload_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Upload Keywords File", "", filter="Text files (*.txt);;All files (*.*)"
        )
        if not path:
            logger.debug("SettingsPanel: upload dialog cancelled")
            return
        try:
            # Same UTF-8-then-cp1252 fallback as app/input/loader.py — a
            # plain `open(..., encoding="utf-8")` would raise and crash the
            # UI thread on a non-UTF-8 .txt file (legacy Windows codepage).
            from app.input.loader import _decode_bytes

            content, _used_fallback = _decode_bytes(Path(path).read_bytes())
        except OSError as exc:
            logger.warning("SettingsPanel: could not read %s: %s", path, exc)
            self._set_status(f"Could not read {path}: {exc}")
            return

        existing = self.keywords_edit.toPlainText()
        merged = existing + ("\n" if existing and not existing.endswith("\n") else "") + content
        self.keywords_edit.setPlainText(merged)
        logger.info("SettingsPanel: uploaded keywords from %s", path)
        self._set_status(f"Loaded keywords from {path} — click Save Settings to persist.")

    def _on_save(self) -> None:
        lines = self.keywords_edit.toPlainText().splitlines()
        seen: set[str] = set()
        keywords: list[str] = []
        for line in lines:
            term = line.strip()
            if term and term not in seen:
                seen.add(term)
                keywords.append(term)

        theme_name = self.theme_combo.currentText()
        settings = UserSettings(
            theme_name=theme_name,
            custom_base_color=self._custom_base_color if theme_name == "Custom" else None,
            keywords=keywords,
        )
        save_user_settings(settings)
        self._saved_keywords = keywords
        logger.info("SettingsPanel: saved %d keyword(s), theme=%s", len(keywords), theme_name)
        self._set_status(f"Settings saved ({len(keywords)} keyword(s), theme: {theme_name}).")

    # ── accessor for MainWindow ─────────────────────────────────────────────

    def get_saved_keywords(self) -> list[str]:
        return list(self._saved_keywords)
