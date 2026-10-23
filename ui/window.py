from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import auth, system
from core.util import human_duration
from ui import theme
from ui.components.toast import ToastManager
from ui.components.widgets import Badge, Divider, repolish
from ui.icons import pixmap
from ui.responsive import ElidedLabel
from ui.pages.cache import CachePage
from ui.pages.cleanup import CleanupPage
from ui.pages.dashboard import DashboardPage
from ui.pages.history import HistoryPage
from ui.pages.mirrors import MirrorsPage
from ui.pages.orphans import OrphansPage
from ui.pages.packages import PackagesPage
from ui.pages.snapshots import SnapshotsPage
from ui.pages.update import UpdatePage

NAV_SECTIONS = [
    ("PRINCIPAL", [("dashboard", "Panel general", "grid"), ("update", "Actualizar", "refresh")]),
    (
        "PAQUETES",
        [
            ("packages", "Paquetes", "box"),
            ("orphans", "Huérfanas", "unlink"),
            ("cache", "Caché", "database"),
        ],
    ),
    (
        "SISTEMA",
        [
            ("cleanup", "Limpieza", "broom"),
            ("snapshots", "Snapshots", "layers"),
            ("mirrors", "Espejos", "globe"),
        ],
    ),
    ("ACTIVIDAD", [("history", "Historial", "clock")]),
]

PAGES = {
    "dashboard": DashboardPage,
    "update": UpdatePage,
    "packages": PackagesPage,
    "orphans": OrphansPage,
    "cache": CachePage,
    "cleanup": CleanupPage,
    "snapshots": SnapshotsPage,
    "mirrors": MirrorsPage,
    "history": HistoryPage,
}


class NavButton(QPushButton):
    def __init__(self, key, label, icon_name, parent=None):
        super().__init__(label, parent)
        self.setObjectName("Nav")
        self.key = key
        self._icon_name = icon_name
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(QIcon(pixmap(icon_name, theme.C["MUTED"], 17)))
        self.setIconSize(pixmap(icon_name, theme.C["MUTED"], 17).size())
        self.setProperty("active", "false")
        self.setToolTip(f"Ir a {label}")

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        color = theme.C["ACCENT2"] if active else theme.C["MUTED"]
        self.setIcon(QIcon(pixmap(self._icon_name, color, 17)))
        repolish(self)


class Sidebar(QFrame):
    COMPACT_WIDTH = 76
    FULL_WIDTH = 236

    def __init__(self, window):
        super().__init__(window)
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.FULL_WIDTH)
        self._compact = False
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 14, 16)
        root.setSpacing(6)

        self.brand = QLabel("NÚCLEO")
        self.brand.setObjectName("AppName")
        self.tagline = QLabel("CENTRO DE SISTEMA")
        self.tagline.setObjectName("AppTag")
        root.addWidget(self.brand)
        root.addWidget(self.tagline)
        root.addSpacing(14)

        self.buttons = {}
        self._labels = {}
        self._section_labels = []
        for section, items in NAV_SECTIONS:
            label = QLabel(section)
            label.setObjectName("NavSection")
            root.addSpacing(6)
            root.addWidget(label)
            self._section_labels.append(label)
            for key, text, icon_name in items:
                button = NavButton(key, text, icon_name)
                button.clicked.connect(lambda _=False, k=key: window.navigate(k))
                root.addWidget(button)
                self.buttons[key] = button
                self._labels[key] = text

        root.addStretch()
        root.addWidget(Divider())
        root.addSpacing(8)
        status_row = QHBoxLayout()
        self.sudo_badge = Badge("sudo", "neutral")
        status_row.addWidget(self.sudo_badge)
        status_row.addStretch()
        root.addLayout(status_row)
        self.env = ElidedLabel("")
        self.env.setObjectName("Faint")
        root.addWidget(self.env)
        self.uptime = ElidedLabel("")
        self.uptime.setObjectName("Faint")
        root.addWidget(self.uptime)

        self._timer = QTimer(self)
        self._timer.setInterval(15000)
        self._timer.timeout.connect(self.update_status)
        self._timer.start()
        self.update_status()

    def set_compact(self, compact: bool) -> None:
        if compact == self._compact:
            return
        self._compact = compact
        self.setFixedWidth(self.COMPACT_WIDTH if compact else self.FULL_WIDTH)
        self.setProperty("compact", "true" if compact else "false")
        for key, button in self.buttons.items():
            label = self._labels[key]
            if compact:
                button.setText("")
            else:
                button.setText(label)
            button.setToolTip(f"Ir a {label}")
        for label in self._section_labels:
            label.setVisible(not compact)
        self.tagline.setVisible(not compact)
        self.env.setVisible(not compact)
        self.uptime.setVisible(not compact)
        self.sudo_badge.setVisible(not compact)
        self.brand.setText("N" if compact else "NÚCLEO")
        repolish(self)

    def update_status(self) -> None:
        if auth.is_root():
            self.sudo_badge.setText("root")
            self.sudo_badge.set_kind("danger")
            self.sudo_badge.setToolTip("La aplicación se está ejecutando como root.")
        elif auth.sudo_cached():
            self.sudo_badge.setText("sudo activo")
            self.sudo_badge.set_kind("success")
            self.sudo_badge.setToolTip(
                "La contraseña de sudo está cacheada; no se volverá a pedir por un tiempo."
            )
        else:
            self.sudo_badge.setText("sudo requerido")
            self.sudo_badge.set_kind("neutral")
            self.sudo_badge.setToolTip(
                "Se pedirá la contraseña la próxima vez que una acción necesite permisos."
            )
        self.env.setText(f"{system.os_name()} · {system.desktop()}")
        self.uptime.setText(
            f"kernel {system.kernel()} · {human_duration(system.uptime_seconds())}"
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Núcleo · Centro de sistema")
        self.setMinimumSize(680, 500)
        self.resize(1240, 820)

        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toast = ToastManager(self)
        self.sidebar = Sidebar(self)
        layout.addWidget(self.sidebar)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(22, 22, 22, 22)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        layout.addWidget(self.content, 1)

        self.pages = {}
        for key, factory in PAGES.items():
            page = factory(self)
            self.pages[key] = page
            self.stack.addWidget(page)

        self._anim: QPropertyAnimation | None = None
        self._current = ""
        for sequence in ("Ctrl+R", "F5"):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(self._refresh_current)
        self._update_layout_mode()
        self.navigate("dashboard")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_layout_mode()

    def _update_layout_mode(self) -> None:
        compact = self.width() < 900
        self.sidebar.set_compact(compact)
        margin = 14 if self.width() < 760 else 22
        self.content.setContentsMargins(margin, margin, margin, margin)

    def navigate(self, key: str) -> None:
        page = self.pages[key]
        first = self._current != key
        self._current = key
        self.stack.setCurrentWidget(page)
        for nav_key, button in self.sidebar.buttons.items():
            button.set_active(nav_key == key)
        page.on_show()
        if first:
            self._animate(page)

    def _refresh_current(self) -> None:
        page = self.pages.get(self._current)
        if page is not None:
            page.refresh()
            self.toast.show("Actualizado", "Se recargó la página actual.", "info", 2200)

    def _animate(self, widget) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def finish():
            try:
                widget.setGraphicsEffect(None)
            except RuntimeError:
                pass

        anim.finished.connect(finish)
        self._anim = anim
        anim.start()
