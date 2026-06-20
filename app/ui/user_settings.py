"""Persisted desktop-UI preferences: theme choice and the Mangle Keywords
list (app/config.py::Settings.known_terms front-end).

Stored under the per-user config dir, not a path derived from `__file__` or
`sys._MEIPASS` — that pattern is what made run_ui.py's debug-log path land
somewhere meaningless once frozen/packaged (a known, already-documented
issue). `%APPDATA%` resolves identically whether running from source or from
the built exe.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_SETTINGS_FILENAME = "settings.json"


class UserSettings(BaseModel):
    theme_name: str = "Light Blue"  # "Light Blue" | "Dark" | "Light Gray" | "Custom"
    custom_base_color: str | None = None  # hex, only meaningful when theme_name == "Custom"
    keywords: list[str] = []


def settings_file_path() -> Path:
    base = os.getenv("APPDATA") or str(Path.home())
    return Path(base) / "CodeMangler" / _SETTINGS_FILENAME


def load_user_settings() -> UserSettings:
    path = settings_file_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return UserSettings()
    try:
        return UserSettings.model_validate_json(raw)
    except ValueError:
        logger.warning("load_user_settings: %s is corrupt, using defaults", path)
        return UserSettings()


def save_user_settings(settings: UserSettings) -> None:
    path = settings_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    logger.info("save_user_settings: wrote %s", path)
