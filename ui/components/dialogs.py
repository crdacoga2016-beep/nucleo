from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from ui import theme
from ui.components.widgets import DangerButton, GhostButton, IconBox, PrimaryButton


class ShellDialog(QDialog):
    def __init__(self, parent=None, width=460):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.setModal(True)
        self.setFixedWidth(width)
        self.setStyleSheet(
            f"QDialog {{ background: {theme.C['CARD']}; "
            f"border: 1px solid {theme.C['BORDER2']}; border-radius: 16px; }}"
        )
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 18, 20, 18)
        self._root.setSpacing(12)


class ConfirmDialog(ShellDialog):
    def __init__(
        self,
        parent,
        title,
        message="",
        items=None,
        detail="",
        confirm_text="Continuar",
        danger=True,
    ):
        super().__init__(parent, width=500)
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(IconBox("warning", color=theme.C["DANGER"] if danger else theme.C["ACCENT"], size=42))
        texts = QVBoxLayout()
        texts.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        texts.addWidget(title_label)
        if message:
            msg = QLabel(message)
            msg.setObjectName("PageSub")
            msg.setWordWrap(True)
            texts.addWidget(msg)
        header.addLayout(texts)
        header.addStretch()
        self._root.addLayout(header)

        if items:
            listing = QListWidget()
            rows = [str(item) for item in items][:400]
            listing.addItems(rows)
            listing.setFixedHeight(min(190, max(64, len(rows) * 32 + 8)))
            self._root.addWidget(listing)

        if detail:
            detail_label = QLabel(detail)
            detail_label.setObjectName("Faint")
            detail_label.setWordWrap(True)
            self._root.addWidget(detail_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = GhostButton("Cancelar")
        confirm = DangerButton(confirm_text) if danger else PrimaryButton(confirm_text)
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        self._root.addLayout(buttons)
        confirm.setDefault(True)
        confirm.setFocus()


def confirm(parent, title, message="", items=None, detail="", confirm_text="Continuar", danger=True) -> bool:
    dialog = ConfirmDialog(parent, title, message, items, detail, confirm_text, danger)
    return dialog.exec() == QDialog.DialogCode.Accepted


class InfoDialog(ShellDialog):
    def __init__(self, parent, title, message="", detail="", items=None, danger=False):
        super().__init__(parent, width=500)
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(
            IconBox(
                "warning" if danger else "info",
                color=theme.C["DANGER"] if danger else theme.C["INFO"],
                size=42,
            )
        )
        texts = QVBoxLayout()
        texts.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        texts.addWidget(title_label)
        if message:
            msg = QLabel(message)
            msg.setObjectName("PageSub")
            msg.setWordWrap(True)
            texts.addWidget(msg)
        header.addLayout(texts)
        header.addStretch()
        self._root.addLayout(header)
        if items:
            listing = QListWidget()
            rows = [str(item) for item in items][:400]
            listing.addItems(rows)
            listing.setFixedHeight(min(220, max(64, len(rows) * 32 + 8)))
            self._root.addWidget(listing)
        if detail:
            detail_label = QLabel(detail)
            detail_label.setObjectName("Faint")
            detail_label.setWordWrap(True)
            self._root.addWidget(detail_label)
        buttons = QHBoxLayout()
        buttons.addStretch()
        ok = PrimaryButton("Entendido")
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        self._root.addLayout(buttons)


def info(parent, title, message="", detail="", items=None, danger=False) -> None:
    InfoDialog(parent, title, message, detail, items, danger).exec()


class PromptDialog(ShellDialog):
    def __init__(self, parent, title, label="", placeholder="", text=""):
        super().__init__(parent, width=460)
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(IconBox("sparkles", color=theme.C["ACCENT"], size=42))
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        header.addWidget(title_label)
        header.addStretch()
        self._root.addLayout(header)
        if label:
            label_widget = QLabel(label)
            label_widget.setObjectName("PageSub")
            label_widget.setWordWrap(True)
            self._root.addWidget(label_widget)
        self.field = QLineEdit(text)
        self.field.setPlaceholderText(placeholder)
        self.field.setMinimumHeight(34)
        self._root.addWidget(self.field)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = GhostButton("Cancelar")
        ok = PrimaryButton("Aceptar")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        self._root.addLayout(buttons)
        self.field.returnPressed.connect(self.accept)
        self.field.setFocus()

    def value(self) -> str:
        return self.field.text().strip()


def ask_text(parent, title, label="", placeholder="", text="") -> str | None:
    dialog = PromptDialog(parent, title, label, placeholder, text)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.value()
    return None


class PasswordDialog(ShellDialog):
    def __init__(self, parent, reason="", error=""):
        super().__init__(parent, width=440)
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(IconBox("shield", color=theme.C["ACCENT"], size=42))
        title_label = QLabel("Autenticación de administrador")
        title_label.setObjectName("CardTitle")
        header.addWidget(title_label)
        header.addStretch()
        self._root.addLayout(header)

        message = QLabel(
            reason
            or "'sudo' solicita tu contraseña para aplicar esta acción en el sistema."
        )
        message.setObjectName("PageSub")
        message.setWordWrap(True)
        self._root.addWidget(message)

        if error:
            error_label = QLabel(error)
            error_label.setStyleSheet(f"color: {theme.C['DANGER']};")
            error_label.setWordWrap(True)
            self._root.addWidget(error_label)

        self.field = QLineEdit()
        self.field.setObjectName("Password")
        self.field.setEchoMode(QLineEdit.EchoMode.Password)
        self.field.setPlaceholderText("Contraseña de sudo")
        self.field.setMinimumHeight(36)
        self._root.addWidget(self.field)

        self.remember = QCheckBox("Recordar durante esta sesión")
        self.remember.setChecked(True)
        self._root.addWidget(self.remember)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = GhostButton("Cancelar")
        ok = PrimaryButton("Autenticar")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        self._root.addLayout(buttons)
        self.field.returnPressed.connect(self.accept)
        self.field.setFocus()

    def values(self) -> tuple[str, bool]:
        return self.field.text(), self.remember.isChecked()


def password_dialog(parent, reason="", error=""):
    dialog = PasswordDialog(parent, reason, error)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.values()
