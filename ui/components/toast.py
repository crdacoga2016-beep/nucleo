from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from ui import theme
from ui.components.widgets import IconBox, IconButton, repolish
from PySide6.QtWidgets import QFrame

KIND_ICON = {
    "info": ("info", "INFO"),
    "success": ("check", "SUCCESS"),
    "danger": ("warning", "DANGER"),
    "warn": ("warning", "WARN"),
    "accent": ("sparkles", "ACCENT"),
}


class Toast(QFrame):
    def __init__(self, parent, title, text="", kind="info"):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("kind", kind)
        repolish(self)
        self.setFixedWidth(330)
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 12, 12)
        root.setSpacing(12)
        icon_name, color_key = KIND_ICON.get(kind, KIND_ICON["info"])
        root.addWidget(IconBox(icon_name, color=theme.C[color_key], size=36))
        texts = QVBoxLayout()
        texts.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("ToastTitle")
        title_label.setWordWrap(True)
        texts.addWidget(title_label)
        if text:
            text_label = QLabel(text)
            text_label.setObjectName("ToastText")
            text_label.setWordWrap(True)
            texts.addWidget(text_label)
        root.addLayout(texts, 1)
        close = IconButton("close", "Cerrar", size=24)
        root.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._fade: QPropertyAnimation | None = None
        close.clicked.connect(self._request_close)
        self.on_close = None

    def _request_close(self):
        if self.on_close:
            self.on_close(self)

    def fade_in(self):
        anim = QPropertyAnimation(self._effect, b"opacity", self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._fade = anim

    def fade_out(self, on_done):
        anim = QPropertyAnimation(self._effect, b"opacity", self)
        anim.setStartValue(self._effect.opacity())
        anim.setEndValue(0.0)
        anim.setDuration(160)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(on_done)
        anim.start()
        self._fade = anim


class ToastManager(QObject):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.toasts: list = []
        host.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.host and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self._layout()
        return False

    def show(self, title, text="", kind="info", duration=4600):
        toast = Toast(self.host, title, text, kind)
        toast.adjustSize()
        toast.on_close = self._dismiss
        self.toasts.append(toast)
        toast.show()
        toast.raise_()
        self._layout()
        toast.fade_in()
        if duration:
            QTimer.singleShot(duration, lambda t=toast: self._dismiss(t))

    def _dismiss(self, toast):
        if toast not in self.toasts:
            return
        self.toasts.remove(toast)

        def done():
            toast.hide()
            toast.deleteLater()
            self._layout()

        toast.fade_out(done)

    def _layout(self):
        margin = 26
        y = self.host.height() - margin
        for toast in reversed(self.toasts):
            toast.adjustSize()
            y -= toast.height()
            toast.move(self.host.width() - toast.width() - margin, y)
            y -= 10
