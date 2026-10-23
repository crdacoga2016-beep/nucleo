from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui import theme
from ui.components.widgets import ConsoleView, PageHeader


class Page(QWidget):
    key = ""
    title = ""
    subtitle = ""

    def __init__(self, window, scroll=False):
        super().__init__()
        self.window = window
        self.toast = window.toast
        self.header = PageHeader(self.title, self.subtitle)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        root.addWidget(self.header)
        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QScrollArea.Shape.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            container = QWidget()
            self.content = QVBoxLayout(container)
            self.content.setContentsMargins(0, 0, 10, 0)
            self.content.setSpacing(14)
            area.setWidget(container)
            root.addWidget(area, 1)
        else:
            container = QWidget()
            self.content = QVBoxLayout(container)
            self.content.setContentsMargins(0, 0, 0, 0)
            self.content.setSpacing(14)
            root.addWidget(container, 1)

    def on_show(self) -> None:
        pass

    def refresh(self) -> None:
        load = getattr(self, "load", None)
        if callable(load):
            load()

    def notify(self, title, text="", kind="info") -> None:
        self.toast.show(title, text, kind)


def section(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("Section")
    return label


def hrow(*widgets, spacing=8, stretch=True) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    if stretch:
        layout.addStretch()
    return layout


def make_table(
    columns,
    widths=None,
    stretch=(0,),
    min_height=160,
    single=False,
    sortable=False,
) -> QTableWidget:
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
        if single
        else QAbstractItemView.SelectionMode.ExtendedSelection
    )
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setWordWrap(False)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setMinimumHeight(min_height)
    table.setSortingEnabled(sortable)
    table.verticalHeader().setDefaultSectionSize(34)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setMinimumSectionSize(54)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for index in range(len(columns)):
        if index in stretch:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
            if widths and index < len(widths) and widths[index]:
                table.setColumnWidth(index, widths[index])
    return table


def fill_table(table, rows, colors=None) -> None:
    table.setSortingEnabled(False)
    table.setRowCount(0)
    for row_values in rows:
        add_row(table, row_values, colors)
    table.setSortingEnabled(bool(table.isSortingEnabled()))


def add_row(table, values, colors=None, data=None) -> int:
    row = table.rowCount()
    table.insertRow(row)
    for column, value in enumerate(values):
        item = QTableWidgetItem("" if value is None else str(value))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if colors and column < len(colors) and colors[column]:
            item.setForeground(theme.color(colors[column]))
        if column == 0 and data is not None:
            item.setData(Qt.ItemDataRole.UserRole, data)
        table.setItem(row, column, item)
    return row


def row_data(table, row, role=Qt.ItemDataRole.UserRole):
    item = table.item(row, 0)
    if item is None:
        return None
    return item.data(role)


def selected_data(table, role=Qt.ItemDataRole.UserRole) -> list:
    rows = sorted({index.row() for index in table.selectionModel().selectedRows()})
    if not rows and table.currentRow() >= 0:
        rows = [table.currentRow()]
    return [value for value in (row_data(table, r, role) for r in rows) if value is not None]


def console_view(title="Consola", min_height=110, interactive=True) -> ConsoleView:
    console = ConsoleView(title=title, interactive=interactive)
    console.setMinimumHeight(min_height)
    return console
