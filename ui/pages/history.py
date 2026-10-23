from __future__ import annotations

from core.session import log
from core.util import human_duration, human_time
from ui.components.widgets import Card, GhostButton
from ui.pages.common import Page, add_row, console_view, make_table, row_data


class HistoryPage(Page):
    key = "history"
    title = "Historial de la sesión"
    subtitle = "Todos los comandos ejecutados desde Nucleo, con su salida y resultado."

    def __init__(self, window):
        super().__init__(window)
        clear = GhostButton("Limpiar historial")
        clear.setToolTip("Borra el historial de esta sesión (no afecta al sistema).")
        clear.clicked.connect(self._clear)
        self.header.add_action(clear)

        self.card = Card(title="Comandos ejecutados", icon_name="history")
        self.table = make_table(
            ["Hora", "Comando", "Estado", "Duración"],
            widths=[110, 0, 110, 100],
            stretch=(1,),
            min_height=240,
            single=True,
        )
        self.table.setToolTip(
            "Selecciona una fila para ver la salida completa del comando abajo."
        )
        self.card.body.addWidget(self.table)
        self.content.addWidget(self.card, 1)

        self.console = console_view("Salida del comando seleccionado", interactive=False)
        self.content.addWidget(self.console, 1)

        self.table.itemSelectionChanged.connect(self._show_selected)
        log.appended.connect(self._on_appended)
        log.cleared.connect(self._reload)
        self._reload()

    def on_show(self) -> None:
        self._reload()

    def _reload(self) -> None:
        self.table.setRowCount(0)
        for entry in reversed(log.entries):
            status = "ok" if entry.ok else (
                "cancelado" if entry.cancelled else f"error {entry.code}"
            )
            colors = [None, None, "SUCCESS" if entry.ok else "DANGER", None]
            add_row(
                self.table,
                [
                    human_time(entry.time),
                    entry.command,
                    status,
                    human_duration(entry.duration),
                ],
                colors=colors,
                data=entry,
            )

    def _on_appended(self, _entry) -> None:
        self._reload()

    def _show_selected(self) -> None:
        entry = row_data(self.table, self.table.currentRow())
        self.console.clear()
        if entry is None:
            return
        self.console.append(f"$ {entry.command}\n", "cmd")
        self.console.append(
            f"código {entry.code} · {human_duration(entry.duration)}\n\n", "sys"
        )
        if entry.stdout:
            self.console.append(entry.stdout, "out")
        if entry.stderr.strip():
            self.console.append(entry.stderr, "err")

    def _clear(self) -> None:
        log.clear()
