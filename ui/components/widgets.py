from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QVariantAnimation,
    QTimer,
    Signal,
)
from PySide6.QtGui import QPainter, QPen, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui import theme
from ui.icons import icon, pixmap
from ui.responsive import ElidedLabel, FlowLayout


def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class Spinner(QWidget):
    def __init__(self, parent=None, size=16, color=None):
        super().__init__(parent)
        self._size = size
        self._angle = 0
        self._color = color or theme.C["ACCENT"]
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 7) % 360
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(2, 2, -2, -2)
        pen = QPen(theme.color("ACCENT"), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, int(-self._angle * 16), int(270 * 16))
        painter.end()


class IconBox(QFrame):
    def __init__(self, name, color=None, size=38, parent=None):
        super().__init__(parent)
        self.setObjectName("IconBox")
        self.setFixedSize(size, size)
        self._color = color or theme.C["ACCENT"]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setPixmap(pixmap(name, self._color, int(size * 0.5)))
        layout.addWidget(label)


class Badge(QLabel):
    def __init__(self, text="", kind="neutral", parent=None):
        super().__init__(text, parent)
        self.setObjectName("Badge")
        self.set_kind(kind)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_kind(self, kind: str) -> None:
        self.setProperty("kind", kind)
        repolish(self)


class Divider(QFrame):
    def __init__(self, horizontal=True, parent=None):
        super().__init__(parent)
        self.setObjectName("Divider")
        if horizontal:
            self.setFixedHeight(1)
        else:
            self.setFixedWidth(1)


class PageHeader(QWidget):
    def __init__(self, title="", subtitle="", parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 0, 2, 0)
        root.setSpacing(2)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(2)
        self._title = ElidedLabel(title)
        self._title.setObjectName("PageTitle")
        self._sub = QLabel(subtitle)
        self._sub.setObjectName("PageSub")
        self._sub.setWordWrap(True)
        left.addWidget(self._title)
        left.addWidget(self._sub)
        row.addLayout(left, 1)
        self.actions = FlowLayout(spacing=8)
        self.actions.setContentsMargins(0, 0, 0, 0)
        row.addLayout(self.actions)
        root.addLayout(row)

    def set_subtitle(self, text: str) -> None:
        self._sub.setText(text)

    def add_action(self, widget: QWidget) -> None:
        self.actions.addWidget(widget)


class Card(QFrame):
    def __init__(self, title="", subtitle="", icon_name=None, parent=None, danger=False):
        super().__init__(parent)
        self.setObjectName("Card")
        if danger:
            self.setProperty("danger", "true")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)
        self._header = QHBoxLayout()
        self._header.setSpacing(12)
        if icon_name:
            self._header.addWidget(IconBox(icon_name, size=34))
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self._title = ElidedLabel(title)
        self._title.setObjectName("CardTitle")
        self._sub = QLabel(subtitle)
        self._sub.setObjectName("CardSub")
        self._sub.setWordWrap(True)
        self._sub.setVisible(bool(subtitle))
        titles.addWidget(self._title)
        titles.addWidget(self._sub)
        self._header.addLayout(titles, 1)
        self._actions = FlowLayout(spacing=8)
        self._actions.setContentsMargins(0, 0, 0, 0)
        self._header.addLayout(self._actions)
        root.addLayout(self._header)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        root.addLayout(self.body)

    def add_header_widget(self, widget: QWidget) -> None:
        self._actions.addWidget(widget)

    def set_subtitle(self, text: str) -> None:
        self._sub.setText(text)
        self._sub.setVisible(bool(text))


class Hero(QFrame):
    def __init__(self, title="", text="", icon_name="sparkles", parent=None):
        super().__init__(parent)
        self.setObjectName("Hero")
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(16)
        self.icon = IconBox(icon_name, size=48)
        self.icon.setStyleSheet(
            "QFrame#IconBox { background: rgba(255,138,61,0.18); border-radius: 14px; }"
        )
        root.addWidget(self.icon)
        texts = QVBoxLayout()
        texts.setSpacing(3)
        self.title = ElidedLabel(title)
        self.title.setObjectName("PageTitle")
        self.text = QLabel(text)
        self.text.setObjectName("PageSub")
        self.text.setWordWrap(True)
        texts.addWidget(self.title)
        texts.addWidget(self.text)
        root.addLayout(texts, 1)
        self.actions = FlowLayout(spacing=8, vspacing=8)
        self.actions.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self.actions)

    def add_action(self, widget: QWidget) -> None:
        self.actions.addWidget(widget)


class StatTile(QFrame):
    clicked = Signal()

    def __init__(self, title="", icon_name="info", accent=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Tile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(96)
        self._accent = accent or theme.C["ACCENT"]
        self._number = 0.0
        self._formatter = str
        self._anim: QVariantAnimation | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 13, 14, 13)
        root.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        self._icon = QLabel()
        self._icon.setPixmap(pixmap(icon_name, self._accent, 18))
        self._title = ElidedLabel(title)
        self._title.setObjectName("StatLabel")
        top.addWidget(self._icon)
        top.addWidget(self._title, 1)
        top.addStretch()
        root.addLayout(top)
        self.value = QLabel("—")
        self.value.setObjectName("StatValue")
        root.addWidget(self.value)
        self.sub = QLabel("")
        self.sub.setObjectName("Faint")
        self.sub.setWordWrap(True)
        root.addWidget(self.sub)
        root.addStretch()

    def set_value(self, text: str) -> None:
        self._cancel_anim()
        self.value.setText(text)

    def set_number(self, number, formatter=None, animate=True) -> None:
        formatter = formatter or self._formatter
        self._formatter = formatter
        if not animate or self._number == number:
            self._number = float(number)
            self.value.setText(formatter(self._number))
            return
        self._cancel_anim()
        anim = QVariantAnimation(self)
        anim.setStartValue(self._number)
        anim.setEndValue(float(number))
        anim.setDuration(650)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: self.value.setText(formatter(v)))
        anim.finished.connect(lambda: self._finish_anim(float(number)))
        self._anim = anim
        anim.start()

    def _finish_anim(self, number):
        self._number = number
        self.value.setText(self._formatter(number))

    def _cancel_anim(self):
        if self._anim is not None:
            self._anim.stop()
            self._anim = None

    def set_sub(self, text: str) -> None:
        self.sub.setText(text)

    def set_accent(self, accent: str) -> None:
        self._accent = accent
        self._icon.setPixmap(pixmap("info", accent, 18))
        self.value.setStyleSheet(f"color: {accent};")

    def set_icon(self, name: str) -> None:
        self._icon.setPixmap(pixmap(name, self._accent, 18))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class PrimaryButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("Primary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(34)


class DangerButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("Danger")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(34)


class GhostButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("Ghost")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(34)


class IconButton(QPushButton):
    def __init__(self, name, tooltip="", color=None, size=30, parent=None):
        super().__init__(parent)
        self.setObjectName("IconBtn")
        self.setFixedSize(size, size)
        self.setIcon(icon(name, color or theme.C["MUTED"], int(size * 0.6)))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)


class Chip(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("Chip")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(30)


class Segmented(QWidget):
    changed = Signal(str)

    def __init__(self, options, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self._chips = {}
        self._value = ""
        for key, label in options:
            chip = Chip(label)
            chip.setCheckable(True)
            chip.setToolTip(f"Ver: {label}")
            chip.clicked.connect(lambda _=False, k=key: self.set_value(k))
            self._chips[key] = chip
            root.addWidget(chip)
        root.addStretch()
        if options:
            self.set_value(options[0][0], emit=False)

    def value(self) -> str:
        return self._value

    def set_value(self, key: str, emit=True) -> None:
        self._value = key
        for chip_key, chip in self._chips.items():
            chip.setChecked(chip_key == key)
        if emit:
            self.changed.emit(key)


class KVList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(8)

    def clear(self) -> None:
        while self._root.count():
            item = self._root.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add(self, key: str, value: str) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        klabel = ElidedLabel(key)
        klabel.setObjectName("Muted")
        klabel.setMinimumWidth(110)
        klabel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        vlabel = QLabel(str(value))
        vlabel.setWordWrap(True)
        vlabel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(klabel, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(vlabel, 1)
        self._root.addWidget(row)


class EmptyState(QWidget):
    def __init__(self, icon_name="check", title="", text="", parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 30, 0, 30)
        root.setSpacing(8)
        box = IconBox(icon_name, color=theme.C["SUCCESS"], size=54)
        box.setStyleSheet(
            "QFrame#IconBox { background: rgba(67,214,160,0.12); border-radius: 16px; }"
        )
        holder = QHBoxLayout()
        holder.addStretch()
        holder.addWidget(box)
        holder.addStretch()
        root.addLayout(holder)
        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text = QLabel(text)
        self.text.setObjectName("PageSub")
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setWordWrap(True)
        root.addWidget(self.title)
        root.addWidget(self.text)
        root.addStretch()


class StepList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(6)
        self._rows: list = []

    def set_steps(self, labels) -> None:
        while self._root.count():
            item = self._root.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []
        for label in labels:
            row = QFrame()
            row.setObjectName("StepRow")
            row.setProperty("state", "pending")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(12, 9, 12, 9)
            layout.setSpacing(10)
            spinner = Spinner(size=14)
            dot = QLabel("•")
            dot.setFixedWidth(12)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(f"color: {theme.C['FAINT']};")
            text = ElidedLabel(label)
            text.setObjectName("Soft")
            layout.addWidget(spinner)
            layout.addWidget(dot)
            layout.addWidget(text, 1)
            self._root.addWidget(row)
            self._rows.append((row, dot, spinner, text))

    def set_state(self, index: int, state: str) -> None:
        if not (0 <= index < len(self._rows)):
            return
        row, dot, spinner, text = self._rows[index]
        row.setProperty("state", state)
        repolish(row)
        if state == "running":
            spinner.start()
            dot.setText("")
        else:
            spinner.stop()
            marks = {
                "ok": ("✓", theme.C["SUCCESS"]),
                "error": ("✕", theme.C["DANGER"]),
                "cancelled": ("—", theme.C["WARN"]),
                "pending": ("•", theme.C["FAINT"]),
            }
            mark, color = marks.get(state, ("•", theme.C["FAINT"]))
            dot.setText(mark)
            dot.setStyleSheet(f"color: {color}; font-weight: 700;")


CONSOLE_COLORS = {
    "cmd": "INFO",
    "out": "TEXT2",
    "err": "DANGER",
    "ok": "SUCCESS",
    "sys": "FAINT",
    "warn": "WARN",
}


def _insert_console_text(edit: QPlainTextEdit, text: str, kind: str) -> None:
    scrollbar = edit.verticalScrollBar()
    at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
    cursor = edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    char_format = QTextCharFormat()
    char_format.setForeground(theme.color(CONSOLE_COLORS.get(kind, "TEXT2")))
    cursor.insertText(text, char_format)
    if at_bottom:
        scrollbar.setValue(scrollbar.maximum())


class ConsoleDialog(QDialog):
    def __init__(self, parent, title="Consola", text=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(1000, 700)
        self.setStyleSheet(
            f"QDialog {{ background: {theme.C['BG']}; }}"
            f"QPlainTextEdit {{ background: {theme.C['CONSOLE']}; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        header = QHBoxLayout()
        header.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("CardTitle")
        header.addWidget(label)
        header.addStretch()
        copy_btn = IconButton("copy", "Copiar toda la salida")
        clear_btn = IconButton("broom", "Limpiar la salida")
        close_btn = IconButton("close", "Cerrar la ventana")
        header.addWidget(copy_btn)
        header.addWidget(clear_btn)
        header.addWidget(close_btn)
        root.addLayout(header)
        self.edit = QPlainTextEdit()
        self.edit.setReadOnly(True)
        self.edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.edit.setCenterOnScroll(False)
        self.edit.setPlainText(text)
        root.addWidget(self.edit, 1)
        copy_btn.clicked.connect(self._copy)
        clear_btn.clicked.connect(self.edit.clear)
        close_btn.clicked.connect(self.close)

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.edit.toPlainText())

    def append(self, text: str, kind: str = "out") -> None:
        if text:
            _insert_console_text(self.edit, text, kind)


class ConsoleView(QFrame):
    submitted = Signal(str)

    COLORS = CONSOLE_COLORS

    def __init__(self, title="Consola", parent=None, interactive=True):
        super().__init__(parent)
        self.setObjectName("Card")
        self._title = title
        self._collapsed = False
        self._running = False
        self._want_input = False
        self._restore_height = 0
        self._restore_min_height = 0
        self._dialog: ConsoleDialog | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        label = ElidedLabel(title)
        label.setObjectName("CardTitle")
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        header.addWidget(label)
        self.spinner = Spinner(size=14)
        header.addWidget(self.spinner)
        self.status = ElidedLabel("Inactivo")
        self.status.setObjectName("Faint")
        self.status.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        header.addWidget(self.status)
        header.addStretch()
        self.copy_btn = IconButton("copy", "Copiar toda la salida al portapapeles")
        self.clear_btn = IconButton(
            "broom", "Limpiar la consola (no detiene el proceso)"
        )
        self.expand_btn = IconButton(
            "restore", "Abrir la salida en una ventana aparte"
        )
        self.collapse_btn = IconButton("minimize", "Contraer la consola")
        self.stop_btn = IconButton(
            "warning", "Detener el proceso en ejecución", color=theme.C["DANGER"]
        )
        self.stop_btn.hide()
        header.addWidget(self.copy_btn)
        header.addWidget(self.clear_btn)
        header.addWidget(self.expand_btn)
        header.addWidget(self.collapse_btn)
        header.addWidget(self.stop_btn)
        root.addLayout(header)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.hide()
        root.addWidget(self.bar)

        self.edit = QPlainTextEdit()
        self.edit.setReadOnly(True)
        self.edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.edit.setMinimumHeight(120)
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.edit.setCenterOnScroll(False)
        self.edit.setToolTip(
            "Salida del proceso. Puedes seleccionar texto, usar Ctrl+C y "
            "desplazarte con la rueda del ratón."
        )
        root.addWidget(self.edit, 1)

        self.input = QLineEdit()
        self.input.setObjectName("TermInput")
        self.input.setPlaceholderText(
            "Escribe una respuesta y pulsa Intro (por ejemplo: s  ·  y  ·  n)"
        )
        self.input.returnPressed.connect(self._send)
        self.input.hide()
        root.addWidget(self.input)
        self._interactive = interactive
        self.copy_btn.clicked.connect(self._copy)
        self.clear_btn.clicked.connect(self.clear)
        self.expand_btn.clicked.connect(self._open_dialog)
        self.collapse_btn.clicked.connect(self._toggle_collapsed)

    def _send(self) -> None:
        text = self.input.text()
        if text.strip() == "":
            text = ""
        self.input.clear()
        self.submitted.emit(text)

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.edit.toPlainText())

    def append(self, text: str, kind: str = "out") -> None:
        if not text:
            return
        _insert_console_text(self.edit, text, kind)
        if self._dialog is not None:
            try:
                self._dialog.append(text, kind)
            except RuntimeError:
                self._dialog = None

    def clear(self) -> None:
        self.edit.clear()
        if self._dialog is not None:
            try:
                self._dialog.edit.clear()
            except RuntimeError:
                self._dialog = None

    def text(self) -> str:
        return self.edit.toPlainText()

    def _open_dialog(self) -> None:
        if self._dialog is not None:
            try:
                self._dialog.show()
                self._dialog.raise_()
                self._dialog.activateWindow()
                return
            except RuntimeError:
                self._dialog = None
        dialog = ConsoleDialog(self.window(), self._title, self.text())
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.finished.connect(self._dialog_closed)
        self._dialog = dialog
        dialog.show()

    def _dialog_closed(self, _result=0) -> None:
        self._dialog = None

    def _toggle_collapsed(self) -> None:
        if not self._collapsed:
            self._restore_height = max(self.height(), 180)
        self._collapsed = not self._collapsed
        self._refresh_visibility()
        if not self._collapsed:
            self._restore_splitter_size()

    def _resize_in_splitter(self, height: int) -> None:
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QSplitter):
            parent = parent.parentWidget()
        if not isinstance(parent, QSplitter):
            return
        index = parent.indexOf(self)
        if index < 0:
            return
        sizes = parent.sizes()
        if index >= len(sizes):
            return
        old = sizes[index]
        delta = old - height
        if delta == 0:
            return
        sizes[index] = height
        others = [pos for pos in range(len(sizes)) if pos != index]
        base = sum(sizes[pos] for pos in others)
        if base > 0:
            for pos in others:
                sizes[pos] += delta * sizes[pos] / base
        parent.setSizes([max(1, int(size)) for size in sizes])

    def _restore_splitter_size(self) -> None:
        if self._restore_height:
            self._resize_in_splitter(self._restore_height)

    def _refresh_visibility(self) -> None:
        self.edit.setVisible(not self._collapsed)
        self.bar.setVisible(self._running and not self._collapsed)
        self.stop_btn.setVisible(self._running)
        self.input.setVisible(self._interactive and self._want_input and not self._collapsed)
        if self._collapsed:
            if self.minimumHeight() > 60:
                self._restore_min_height = self.minimumHeight()
            self.setMinimumHeight(60)
            self.setMaximumHeight(60)
            self._resize_in_splitter(60)
            self.collapse_btn.setIcon(icon("maximize", theme.C["MUTED"], 18))
            self.collapse_btn.setToolTip("Expandir la consola")
        else:
            if self._restore_min_height:
                self.setMinimumHeight(self._restore_min_height)
            self.setMaximumHeight(16777215)
            self.collapse_btn.setIcon(icon("minimize", theme.C["MUTED"], 18))
            self.collapse_btn.setToolTip("Contraer la consola")

    def set_running(self, running: bool, status: str = "") -> None:
        self._running = running
        if running:
            self.spinner.start()
            self.status.setText(status or "En ejecución…")
        else:
            self.spinner.stop()
            self.status.setText(status or "Inactivo")
        self._refresh_visibility()

    def show_input(self, visible: bool) -> None:
        if not self._interactive:
            return
        self._want_input = visible
        self._refresh_visibility()
        if visible and not self._collapsed:
            self.input.setFocus()
