"""Main application window: Mangler (sanitize) and DeMangler (restore) tabs."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.panels.about_panel import AboutPanel
from app.ui.panels.file_panel import FilePanel
from app.ui.panels.restore_file_panel import RestoreFilePanel
from app.ui.panels.restore_text_panel import RestoreTextPanel
from app.ui.panels.settings_panel import SettingsPanel
from app.ui.panels.text_panel import TextPanel
from app.ui.resource_paths import resource_path
from app.ui.styles import Palette, PREDEFINED_PALETTES, build_stylesheet, derive_palette_from_base_color
from app.ui.user_settings import UserSettings, load_user_settings
from app.ui.widgets import CheckableTreeDropdown

logger = logging.getLogger(__name__)

# Display label -> internal language name used by detect_language()
LANG_MAP: dict[str, str | None] = {
    "Auto-detect":  None,
    "Python":       "python",
    "JavaScript":   "javascript",
    "TypeScript":   "typescript",
    "C":            "c",
    "C++":          "cpp",
    "C#":           "csharp",
    "Go":           "go",
    "Rust":         "rust",
    "SQL":          "sql",
    "Shell":        "shell",
    "JSON":         "json",
    "YAML":         "yaml",
    "XML":          "xml",
    "Markdown":     "markdown",
    "Plain Text":   "text",
}

_MODES = ["Text", "File", "Folder"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        logger.debug("MainWindow.__init__: building window")
        self.setWindowTitle("CodeMangler")
        self.resize(1200, 720)
        self.setMinimumSize(800, 500)
        self._user_settings: UserSettings = load_user_settings()
        self.setStyleSheet(build_stylesheet(self._resolve_palette(self._user_settings)))
        icon_path = resource_path("code_mangler_app_icon.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            logger.warning("MainWindow.__init__: app icon not found at %s", icon_path)
        self._last_mangle_changes: object | None = None
        self._demangler_map_path: str = ""
        self._build_ui()
        logger.debug("MainWindow.__init__: done")

    @staticmethod
    def _resolve_palette(settings: UserSettings) -> Palette:
        if settings.theme_name == "Custom" and settings.custom_base_color:
            return derive_palette_from_base_color(settings.custom_base_color)
        return PREDEFINED_PALETTES.get(settings.theme_name, PREDEFINED_PALETTES["Light Blue"])

    def _apply_theme(self, palette: Palette) -> None:
        self.setStyleSheet(build_stylesheet(palette))

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(self._build_mangler_tab(), "Mangler")
        tabs.addTab(self._build_demangler_tab(), "DeMangler")
        self.settings_panel = SettingsPanel(
            get_initial_settings=lambda: self._user_settings,
            apply_theme=self._apply_theme,
            set_status=self._set_status,
        )
        tabs.addTab(self.settings_panel, "Settings")
        tabs.addTab(AboutPanel(), "About")
        root.addWidget(tabs, stretch=1)

        self._status_bar = QStatusBar()
        self._status_bar.showMessage("Ready.")
        self.setStatusBar(self._status_bar)

    # ── Mangler tab (sanitize) ───────────────────────────────────────────────

    def _build_mangler_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_mangler_top_bar())
        layout.addWidget(self._build_mangler_stack(), stretch=1)
        return tab

    def _build_mangler_top_bar(self) -> QWidget:
        bar_widget = QWidget()
        bar_widget.setObjectName("topBar")
        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(12, 8, 12, 8)
        bar.setSpacing(6)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        for i, label in enumerate(_MODES):
            btn = QPushButton(label)
            btn.setObjectName("modeBtn")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            self._mode_group.addButton(btn, i)
            bar.addWidget(btn)

        bar.addSpacing(24)

        lang_lbl = QLabel("Language:")
        lang_lbl.setStyleSheet("color: #1A5276; font-weight: bold;")
        bar.addWidget(lang_lbl)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(list(LANG_MAP.keys()))
        self.lang_combo.setToolTip(
            "Auto-detect lets CodeMangler identify the language.\n"
            "Select a language before clicking ▶▶ to override."
        )
        bar.addWidget(self.lang_combo)

        self.mangle_dropdown = CheckableTreeDropdown(self)
        bar.addWidget(self.mangle_dropdown)

        bar.addStretch()

        self.clear_mangle_btn = QPushButton("Clear All")
        self.clear_mangle_btn.setToolTip(
            "Clear all text/file/folder fields, the live log, and any\n"
            "in-memory results from the last run."
        )
        self.clear_mangle_btn.clicked.connect(self._on_clear_mangle)
        bar.addWidget(self.clear_mangle_btn)

        self.save_mangle_btn = QPushButton("Save Mangle")
        self.save_mangle_btn.setEnabled(False)
        self.save_mangle_btn.setToolTip(
            "Save the renamed/modified value map to a JSON file,\n"
            "so it can be restored later in the DeMangler tab."
        )
        self.save_mangle_btn.clicked.connect(self._on_save_mangle)
        bar.addWidget(self.save_mangle_btn)
        return bar_widget

    def _build_mangler_stack(self) -> QStackedWidget:
        self.stack = QStackedWidget()

        self.text_panel = TextPanel(
            get_language=self._get_language,
            set_language=self._set_language_display,
            set_status=self._set_status,
            on_changes_ready=self._on_changes_ready,
            get_mangle_options=self._get_mangle_options,
            get_known_terms=self._get_known_terms,
        )
        self.file_panel = FilePanel(
            folder_mode=False,
            set_status=self._set_status,
            on_changes_ready=self._on_changes_ready,
            get_mangle_options=self._get_mangle_options,
            get_known_terms=self._get_known_terms,
        )
        self.folder_panel = FilePanel(
            folder_mode=True,
            set_status=self._set_status,
            on_changes_ready=self._on_changes_ready,
            get_mangle_options=self._get_mangle_options,
            get_known_terms=self._get_known_terms,
        )

        self.stack.addWidget(self.text_panel)    # index 0 — Text
        self.stack.addWidget(self.file_panel)    # index 1 — File
        self.stack.addWidget(self.folder_panel)  # index 2 — Folder

        self._mode_group.idClicked.connect(self._on_mode_changed)
        return self.stack

    # ── DeMangler tab (restore) ──────────────────────────────────────────────

    def _build_demangler_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_demangler_top_bar())
        layout.addWidget(self._build_demangler_stack(), stretch=1)
        return tab

    def _build_demangler_top_bar(self) -> QWidget:
        bar_widget = QWidget()
        bar_widget.setObjectName("topBar")
        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(12, 8, 12, 8)
        bar.setSpacing(6)

        self._restore_mode_group = QButtonGroup(self)
        self._restore_mode_group.setExclusive(True)
        for i, label in enumerate(_MODES):
            btn = QPushButton(label)
            btn.setObjectName("modeBtn")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            self._restore_mode_group.addButton(btn, i)
            bar.addWidget(btn)

        bar.addStretch()

        self.clear_demangler_btn = QPushButton("Clear All")
        self.clear_demangler_btn.setToolTip(
            "Clear all text/file/folder fields, the live log, the loaded\n"
            "mangle map, and any in-memory results from the last run."
        )
        self.clear_demangler_btn.clicked.connect(self._on_clear_demangler)
        bar.addWidget(self.clear_demangler_btn)

        self.map_label = QLabel("No map loaded")
        self.map_label.setStyleSheet("color: #7F8C8D; font-style: italic; margin-right: 8px;")
        bar.addWidget(self.map_label)

        self.reset_mangle_btn = QPushButton("Reset Mangle")
        self.reset_mangle_btn.setToolTip(
            "Load a previously saved mangle map (JSON) so its renamed/modified\n"
            "values can be restored to their originals."
        )
        self.reset_mangle_btn.clicked.connect(self._on_reset_mangle)
        bar.addWidget(self.reset_mangle_btn)
        return bar_widget

    def _build_demangler_stack(self) -> QStackedWidget:
        self.restore_stack = QStackedWidget()

        self.restore_text_panel = RestoreTextPanel(
            set_status=self._set_status, get_map_path=self._get_demangler_map_path
        )
        self.restore_file_panel = RestoreFilePanel(
            folder_mode=False, set_status=self._set_status, get_map_path=self._get_demangler_map_path
        )
        self.restore_folder_panel = RestoreFilePanel(
            folder_mode=True, set_status=self._set_status, get_map_path=self._get_demangler_map_path
        )

        self.restore_stack.addWidget(self.restore_text_panel)    # index 0 — Text
        self.restore_stack.addWidget(self.restore_file_panel)    # index 1 — File
        self.restore_stack.addWidget(self.restore_folder_panel)  # index 2 — Folder

        self._restore_mode_group.idClicked.connect(self._on_restore_mode_changed)
        return self.restore_stack

    # ── helpers ───────────────────────────────────────────────────────────────

    def _on_mode_changed(self, index: int) -> None:
        mode_name = _MODES[index] if index < len(_MODES) else str(index)
        logger.info("_on_mode_changed: switching to mode=%s (index=%d)", mode_name, index)
        self.stack.setCurrentIndex(index)
        self.lang_combo.setEnabled(index == 0)
        self._set_status("Ready.")

    def _on_restore_mode_changed(self, index: int) -> None:
        mode_name = _MODES[index] if index < len(_MODES) else str(index)
        logger.info("_on_restore_mode_changed: switching to mode=%s (index=%d)", mode_name, index)
        self.restore_stack.setCurrentIndex(index)
        self._set_status("Ready.")

    def _get_mangle_options(self):
        options = self.mangle_dropdown.get_mangle_options()
        logger.debug("_get_mangle_options: %r", options)
        return options

    def _get_known_terms(self) -> dict[str, str]:
        keywords = self.settings_panel.get_saved_keywords()
        logger.debug("_get_known_terms: %d keyword(s)", len(keywords))
        return {term: "org" for term in keywords}

    def _get_language(self) -> str:
        lang = self.lang_combo.currentText()
        logger.debug("_get_language: %r", lang)
        return lang

    def _set_language_display(self, display_name: str) -> None:
        logger.info("_set_language_display: %r", display_name)
        idx = self.lang_combo.findText(
            display_name,
            Qt.MatchFlag.MatchFixedString | Qt.MatchFlag.MatchCaseSensitive,
        )
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        else:
            logger.warning("_set_language_display: %r not found in combo", display_name)

    def _set_status(self, message: str) -> None:
        logger.debug("status: %s", message)
        self._status_bar.showMessage(message)

    def _on_changes_ready(self, per_file_changes: object | None) -> None:
        has_changes = bool(per_file_changes)
        logger.debug("_on_changes_ready: has_changes=%s", has_changes)
        self._last_mangle_changes = per_file_changes if has_changes else None
        self.save_mangle_btn.setEnabled(has_changes)

    def _on_save_mangle(self) -> None:
        if not self._last_mangle_changes:
            logger.warning("_on_save_mangle: clicked with no changes available")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Mangle Map",
            "sanitization_map.json",
            filter="JSON files (*.json);;All files (*.*)",
        )
        if not path:
            logger.debug("_on_save_mangle: dialog cancelled")
            return

        from app.mapping.map_writer import build_map, write_map

        logger.info("_on_save_mangle: writing map to %s", path)
        sanitization_map = build_map(self._last_mangle_changes)
        write_map(sanitization_map, Path(path))
        self._set_status(
            f"Mangle map saved: {path} — contains original values, do not share it publicly."
        )

    def _on_reset_mangle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Mangle Map",
            "",
            filter="JSON files (*.json);;All files (*.*)",
        )
        if not path:
            logger.debug("_on_reset_mangle: dialog cancelled")
            return

        logger.info("_on_reset_mangle: loaded map=%s", path)
        self._demangler_map_path = path
        self.map_label.setText(Path(path).name)
        self.map_label.setToolTip(path)
        self.map_label.setStyleSheet("color: #1A5276; font-style: normal; font-weight: bold; margin-right: 8px;")
        self._set_status(f"Mangle map loaded: {path}")

    def _get_demangler_map_path(self) -> str:
        return self._demangler_map_path

    def _on_clear_mangle(self) -> None:
        logger.info("_on_clear_mangle: clearing Mangler tab")
        self.text_panel.clear()
        self.file_panel.clear()
        self.folder_panel.clear()
        self._last_mangle_changes = None
        self.save_mangle_btn.setEnabled(False)
        self.lang_combo.setCurrentIndex(0)  # Auto-detect
        self._set_status("Cleared.")

    def _on_clear_demangler(self) -> None:
        logger.info("_on_clear_demangler: clearing DeMangler tab")
        self.restore_text_panel.clear()
        self.restore_file_panel.clear()
        self.restore_folder_panel.clear()
        self._demangler_map_path = ""
        self.map_label.setText("No map loaded")
        self.map_label.setToolTip("")
        self.map_label.setStyleSheet("color: #7F8C8D; font-style: italic; margin-right: 8px;")
        self._set_status("Cleared.")
