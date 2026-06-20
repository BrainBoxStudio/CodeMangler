"""Resolves bundled UI resources (app/resources/CodeMangler.png,
app/resources/code_mangler_app_icon.ico) so the same lookup works whether
running from source (run_ui.bat) or from the PyInstaller --onefile exe —
build_exe.bat's --add-data flag extracts app/resources/ into sys._MEIPASS
under the same relative path used here.
"""
from __future__ import annotations

import sys
from pathlib import Path

_RESOURCES_DIR_NAME = "resources"


def resource_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS) / "app" / _RESOURCES_DIR_NAME  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent / _RESOURCES_DIR_NAME  # app/resources
    return base / name
