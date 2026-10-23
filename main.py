from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from core import runner  # noqa: E402
from ui import theme  # noqa: E402
from ui.window import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Nucleo")
    app.setApplicationDisplayName("Núcleo")
    app.setOrganizationName("Nucleo")
    app.setDesktopFileName("nucleo")
    icon_path = theme.ASSETS / "icon.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    theme.apply(app)
    window = MainWindow()
    window.show()
    app.aboutToQuit.connect(runner.shutdown_all)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
