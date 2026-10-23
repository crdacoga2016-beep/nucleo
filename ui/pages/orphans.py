from __future__ import annotations

from core import proc, queries, runner
from core.util import human_bytes
from ui.components.dialogs import confirm
from ui.components.widgets import (
    Card,
    DangerButton,
    EmptyState,
    GhostButton,
    Hero,
    PrimaryButton,
)
from ui.pages.common import Page, add_row, console_view, make_table, selected_data


class OrphansPage(Page):
    key = "orphans"
    title = "Dependencias huérfanas"
    subtitle = (
        "Paquetes instalados como dependencia que ya nadie necesita "
        "(equivalente a: sudo pacman -Rs $(pacman -Qdtq))."
    )

    def __init__(self, window):
        super().__init__(window)
        self._items: list = []
        self._loaded = False

        self.hero = Hero(
            "Analizando el sistema…",
            "Buscando dependencias que ya no son necesarias.",
            icon_name="unlink",
        )
        self.btn_remove_all = DangerButton("Eliminar todas")
        self.btn_remove_all.setToolTip(
            "Elimina todos los paquetes huérfanos con 'pacman -Rns', "
            "incluyendo sus dependencias no usadas."
        )
        refresh = GhostButton("Actualizar lista")
        refresh.setToolTip("Vuelve a buscar paquetes que ya no necesita nadie.")
        self.hero.add_action(refresh)
        self.hero.add_action(self.btn_remove_all)
        self.content.addWidget(self.hero)

        self.empty = EmptyState(
            "check",
            "No hay paquetes huérfanos",
            "Tu sistema está limpio: todas las dependencias instaladas se usan.",
        )

        self.table = make_table(
            ["Paquete", "Versión", "Tamaño", "Descripción"],
            widths=[200, 150, 100, 0],
            stretch=(3,),
            min_height=220,
        )
        self.btn_remove_sel = DangerButton("Eliminar seleccionadas")
        self.btn_remove_sel.setToolTip(
            "Elimina solo las filas seleccionadas y sus dependencias no usadas."
        )
        self.btn_select_all = GhostButton("Seleccionar todo")
        self.btn_select_all.setToolTip("Marca todas las filas de la tabla.")
        self.card = Card(title="Paquetes huérfanos", icon_name="unlink")
        self.card.add_header_widget(self.btn_select_all)
        self.card.add_header_widget(self.btn_remove_sel)
        self.table.setToolTip(
            "Paquetes instalados como dependencia que ningún paquete requiere ya."
        )
        self.card.body.addWidget(self.empty)
        self.card.body.addWidget(self.table)
        self.content.addWidget(self.card, 1)

        self.console = console_view("Salida de pacman")
        self.content.addWidget(self.console)

        self.runner = runner.CommandRunner(self, label="huérfanas")
        self.runner.output.connect(lambda s, t: self.console.append(t, s))
        self.runner.runningChanged.connect(self.console.set_running)
        self.runner.finishedSignal.connect(self._on_finished)

        refresh.clicked.connect(self.load)
        self.btn_remove_all.clicked.connect(lambda: self._remove(all_items=True))
        self.btn_remove_sel.clicked.connect(lambda: self._remove(all_items=False))
        self.btn_select_all.clicked.connect(self.table.selectAll)
        self.console.stop_btn.clicked.connect(lambda: self.runner.cancel())

    def on_show(self) -> None:
        if not self._loaded:
            self._loaded = True
            self.load()

    def load(self) -> None:
        proc.async_call(queries.orphan_details, self._on_data, owner=self)

    def _on_data(self, items) -> None:
        if isinstance(items, proc.QueryError):
            self.hero.title.setText("No se pudo analizar")
            self.hero.text.setText(str(items))
            return
        self._items = items
        self.table.setRowCount(0)
        total = 0
        for item in items:
            total += item["size"]
            add_row(
                self.table,
                [
                    item["name"],
                    item["version"] or "—",
                    human_bytes(item["size"]),
                    item["description"] or "—",
                ],
                data=item["name"],
            )
        has_items = bool(items)
        self.table.setVisible(has_items)
        self.empty.setVisible(not has_items)
        self.btn_remove_all.setEnabled(has_items)
        self.btn_remove_sel.setEnabled(has_items)
        self.btn_select_all.setEnabled(has_items)
        if has_items:
            self.hero.title.setText(f"{len(items)} paquetes huérfanos")
            self.hero.text.setText(
                f"Se pueden liberar {human_bytes(total)} eliminándolos."
            )
        else:
            self.hero.title.setText("Sistema limpio")
            self.hero.text.setText("No se encontraron dependencias huérfanas.")

    def _remove(self, all_items: bool) -> None:
        if all_items:
            names = [item["name"] for item in self._items]
        else:
            names = selected_data(self.table)
        if not names:
            self.notify("Sin selección", "Selecciona al menos un paquete.", "warn")
            return
        size = sum(
            item["size"] for item in self._items if item["name"] in set(names)
        )
        if not confirm(
            self,
            "Eliminar paquetes huérfanos",
            f"Se eliminarán {len(names)} paquetes y se liberarán ~{human_bytes(size)}.",
            items=names,
            detail="Comando: sudo pacman -Rns --noconfirm <paquetes>",
            confirm_text="Eliminar",
        ):
            return
        self.runner.run(["pacman", "-Rns", "--noconfirm", *names], privileged=True)

    def _on_finished(self, result) -> None:
        if result.ok:
            self.notify("Huérfanas eliminadas", f"{len(self._items)} analizadas.", "success")
            self.load()
        elif not result.cancelled:
            self.notify("No se pudo completar", f"Código {result.code}", "danger")
