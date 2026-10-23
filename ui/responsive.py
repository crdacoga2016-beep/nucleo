from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtWidgets import QLabel, QLayout, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    def __init__(
        self,
        text="",
        parent=None,
        elide=Qt.TextElideMode.ElideRight,
        tooltip=True,
    ):
        super().__init__(text, parent)
        self._full = text or ""
        self._elide = elide
        self._tooltip = tooltip
        self._applying = False
        self._hint_width = 0
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._update_hint_width()

    def _update_hint_width(self) -> None:
        self._hint_width = min(
            self.fontMetrics().horizontalAdvance(self._full) + 4, 180
        )

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(max(self._hint_width, 24), hint.height())

    def minimumSizeHint(self):
        return QSize(20, super().minimumSizeHint().height())

    def setText(self, text):
        self._full = "" if text is None else str(text)
        self._update_hint_width()
        QLabel.setText(self, self._compute())
        self.updateGeometry()

    def text(self):
        return self._full

    def set_elide(self, mode) -> None:
        self._elide = mode
        QLabel.setText(self, self._compute())

    def full_text(self) -> str:
        return self._full

    def _compute(self) -> str:
        available = self.width() - self.indent() - 2
        if available <= 20:
            return self._full
        return self.fontMetrics().elidedText(self._full, self._elide, available)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._update_hint_width()
            self._apply()

    def _apply(self) -> None:
        if self._applying:
            return
        self._applying = True
        try:
            elided = self._compute()
            if QLabel.text(self) != elided:
                QLabel.setText(self, elided)
            if self._tooltip:
                tip = self._full if elided != self._full else ""
                if self.toolTip() != tip:
                    self.setToolTip(tip)
        finally:
            self._applying = False


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=8, vspacing=None):
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self._vspacing = spacing if vspacing is None else vspacing

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > effective.right() + 1 and line_height > 0:
                x = effective.x()
                y = y + line_height + self._vspacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x = x + hint.width() + self._spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class WrapRow(QWidget):
    def __init__(self, spacing=8, parent=None):
        super().__init__(parent)
        self._flow = FlowLayout(self, spacing=spacing)
        self._flow.setContentsMargins(0, 0, 0, 0)

    def addWidget(self, widget: QWidget) -> None:
        self._flow.addWidget(widget)

    def isEmpty(self) -> bool:
        return self._flow.count() == 0


class ResponsiveGrid(QWidget):
    def __init__(self, min_column=200, spacing=12, parent=None):
        super().__init__(parent)
        self._items: list[QWidget] = []
        self._min_column = int(min_column)
        self._spacing = int(spacing)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

    def addWidget(self, widget: QWidget) -> None:
        widget.setParent(self)
        widget.show()
        self._items.append(widget)
        self._relayout()

    def widgets(self) -> list:
        return list(self._items)

    def columns_for(self, width: int) -> int:
        if width < self._min_column:
            return 1
        columns = int((width + self._spacing) / (self._min_column + self._spacing))
        return max(1, columns)

    def hasHeightForWidth(self) -> bool:
        return bool(self._items)

    def heightForWidth(self, width: int) -> int:
        return self._layout_height(width)

    def sizeHint(self) -> QSize:
        width = self.width() or (
            self.parentWidget().width() if self.parentWidget() else self._min_column
        )
        width = max(int(width), self._min_column)
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        if not self._items:
            return QSize(self._min_column, 0)
        widest = max(w.minimumSizeHint().width() for w in self._items)
        widest = max(int(widest), 80)
        return QSize(widest, self._layout_height(widest))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _item_height(self, widget: QWidget, width: int) -> int:
        width = max(40, int(width))
        if widget.hasHeightForWidth():
            height = widget.heightForWidth(width)
        else:
            height = widget.sizeHint().height()
        return max(int(height), widget.minimumHeight())

    def _layout_height(self, width: int) -> int:
        if not self._items or width <= 0:
            return 0
        columns = self.columns_for(int(width))
        col_w = (width - self._spacing * (columns - 1)) / columns
        total = 0
        for start in range(0, len(self._items), columns):
            row = self._items[start : start + columns]
            total += max(self._item_height(w, col_w) for w in row) + self._spacing
        return max(0, total - self._spacing)

    def _relayout(self) -> None:
        width = self.width()
        if width < 40 or not self._items:
            return
        columns = self.columns_for(width)
        col_w = (width - self._spacing * (columns - 1)) / columns
        y = 0
        for start in range(0, len(self._items), columns):
            row = self._items[start : start + columns]
            row_h = max(self._item_height(w, col_w) for w in row)
            for column, widget in enumerate(row):
                x = column * (col_w + self._spacing)
                widget.setGeometry(
                    QRect(int(round(x)), int(y), int(col_w), int(row_h))
                )
            y += row_h + self._spacing
        total = max(0, y - self._spacing)
        if abs(self.minimumHeight() - total) > 1:
            self.setMinimumHeight(total)
        self.updateGeometry()
