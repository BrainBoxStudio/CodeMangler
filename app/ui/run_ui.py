"""Entry point for the CodeMangler desktop UI."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.resource_paths import resource_path

_LOG_FILE = Path(__file__).resolve().parents[2] / "codemangler_ui.log"
_FMT = "%(asctime)s %(levelname)-8s %(name)-40s %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler — INFO and above so the terminal isn't flooded
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(_FMT, _DATE))
    root.addHandler(ch)

    # File handler — DEBUG and above for full detail
    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FMT, _DATE))
    root.addHandler(fh)

    logger.debug("Logging initialised — file: %s", _LOG_FILE)


def main() -> None:
    _setup_logging()
    logger.info("CodeMangler UI starting")

    app = QApplication(sys.argv)
    app.setApplicationName("CodeMangler")
    app.setApplicationDisplayName("CodeMangler")
    icon_path = resource_path("code_mangler_app_icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        logger.warning("App icon not found at %s", icon_path)

    logger.debug("QApplication created, building MainWindow")
    window = MainWindow()
    window.show()
    logger.info("MainWindow shown — entering event loop")
    code = app.exec()
    logger.info("Event loop exited with code %d", code)
    sys.exit(code)


if __name__ == "__main__":
    main()
