from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLabel

from core import auth, proc, queries, runner
from ui.components.dialogs import ask_text, confirm
from ui.components.widgets import (
    Card,
    DangerButton,
    EmptyState,
    GhostButton,
    Hero,
    PrimaryButton,
)
from ui.pages.common import Page, add_row, console_view, make_table, selected_data


class SnapshotsPage(Page):
    key = "snapshots"
    title = "Snapshots (snapper)"
    subtitle = "Crea y gestiona instantáneas del sistema de archivos (configuración 'root')."

    def __init__(self, window):
        super().__init__(window)
        self._loaded = False
        self._rows: list = []

        self.hero = Hero(
            "Instantáneas del sistema",
            "Los snapshots permiten volver atrás si una actualización sale mal.",
            icon_name="layers",
        )
        self.btn_refresh = GhostButton("Actualizar")
        self.btn_refresh.setToolTip("Vuelve a leer la lista de snapshots de snapper.")
        self.btn_create = PrimaryButton("Crear snapshot")
        self.btn_create.setToolTip(
            "Crea una instantánea manual del sistema con una descripción."
        )
        self.hero.add_action(self.btn_refresh)
        self.hero.add_action(self.btn_create)
        self.content.addWidget(self.hero)

        self.empty = EmptyState(
            "layers",
            "No hay snapshots",
            "Crea uno antes de una actualización importante para poder revertir cambios.",
        )
        self.card = Card(title="Snapshots disponibles", icon_name="layers")
        self.btn_status = GhostButton("Ver cambios (status)")
        self.btn_status.setToolTip(
            "Compara los snapshots entre sí y muestra qué archivos cambiaron."
        )
        self.btn_cleanup = GhostButton("Limpiar antiguos")
        self.btn_cleanup.setToolTip(
            "Aplica las políticas de limpieza configuradas en snapper "
            "(número y antigüedad de snapshots)."
        )
        self.btn_delete = DangerButton("Eliminar seleccionados")
        self.btn_delete.setToolTip(
            "Elimina las instantáneas seleccionadas. No se puede deshacer."
        )
        self.card.add_header_widget(self.btn_status)
        self.card.add_header_widget(self.btn_cleanup)
        self.card.add_header_widget(self.btn_delete)
        self.table = make_table(
            ["#", "Tipo", "Fecha", "Descripción", "Usuario"],
            widths=[70, 110, 190, 0, 110],
            stretch=(3,),
            min_height=230,
        )
        self.table.setToolTip(
            "Snapshots del sistema. Puedes seleccionar varios con Ctrl o Mayús."
        )
        self.card.body.addWidget(self.empty)
        self.card.body.addWidget(self.table)
        self.content.addWidget(self.card, 1)

        self.console = console_view("Salida de snapper", interactive=False)
        self.content.addWidget(self.console)

        self.runner = runner.CommandRunner(self, label="snapper")
        self.runner.output.connect(lambda s, t: self.console.append(t, s))
        self.runner.runningChanged.connect(self.console.set_running)
        self.runner.finishedSignal.connect(self._on_finished)

        self.btn_refresh.clicked.connect(self._refresh_with_auth)
        self.btn_create.clicked.connect(self._create)
        self.btn_delete.clicked.connect(self._delete)
        self.btn_status.clicked.connect(self._status)
        self.btn_cleanup.clicked.connect(self._cleanup)
        self.console.stop_btn.clicked.connect(lambda: self.runner.cancel())

    def on_show(self) -> None:
        if not self._loaded:
            self._loaded = True
            self.load()

    def refresh(self) -> None:
        self._refresh_with_auth()

    def _refresh_with_auth(self) -> None:
        if auth.ensure_sudo(
            self, "snapper necesita permisos de administrador para leer los snapshots."
        ):
            self.load()

    def load(self) -> None:
        proc.async_call(queries.snapshots, self._on_rows, "root", owner=self)

    def _on_rows(self, payload) -> None:
        if isinstance(payload, proc.QueryError):
            self.hero.text.setText(str(payload))
            return
        if not payload["ok"]:
            self.hero.title.setText("Snapshots no disponibles")
            self.hero.text.setText(
                f"{payload['error']}. Pulsa 'Actualizar' para solicitar permisos."
            )
            self.table.setRowCount(0)
            self.table.hide()
            self.empty.show()
            return
        self._rows = payload["rows"]
        self.table.setRowCount(0)
        for item in self._rows:
            add_row(
                self.table,
                [
                    item["number"],
                    item["type"] or "—",
                    item["date"] or "—",
                    item["description"] or "—",
                    item["user"] or "—",
                ],
                data=item["number"],
            )
        has_rows = bool(self._rows)
        self.table.setVisible(has_rows)
        self.empty.setVisible(not has_rows)
        self.btn_delete.setEnabled(has_rows)
        self.btn_status.setEnabled(has_rows)
        self.hero.title.setText(f"{len(self._rows)} snapshots disponibles")
        if self._rows:
            last = self._rows[0]
            self.hero.text.setText(
                f"Último: #{last['number']} ({last['date']}) · {last['description'] or 'sin descripción'}"
            )

    def _authorize_then(self, action) -> None:
        if auth.ensure_sudo(self):
            action()
        else:
            self.notify("Permisos necesarios", "Autenticación cancelada.", "warn")

    def _create(self) -> None:
        description = ask_text(
            self,
            "Crear snapshot",
            "Describe el snapshot para poder identificarlo más tarde.",
            placeholder="Antes de actualizar el sistema",
            text="Snapshot manual desde Nucleo",
        )
        if description is None:
            return
        self._authorize_then(
            lambda: self.runner.run(
                [
                    "snapper",
                    "-c",
                    "root",
                    "create",
                    "--description",
                    description or "Snapshot manual",
                ],
                privileged=True,
            )
        )

    def _delete(self) -> None:
        numbers = selected_data(self.table)
        if not numbers:
            self.notify("Sin selección", "Selecciona snapshots a eliminar.", "warn")
            return
        labels = [
            f"#{item['number']} · {item['date']} · {item['description'] or 'sin descripción'}"
            for item in self._rows
            if item["number"] in numbers
        ]
        if not confirm(
            self,
            "Eliminar snapshots",
            f"Se eliminarán {len(numbers)} snapshots. Esta acción no se puede deshacer.",
            items=labels,
            confirm_text="Eliminar",
        ):
            return
        self.runner.run(
            ["snapper", "-c", "root", "delete", *[str(n) for n in numbers]],
            privileged=True,
        )

    def _status(self) -> None:
        self.runner.run(["snapper", "-c", "root", "status"], privileged=True)

    def _cleanup(self) -> None:
        if not confirm(
            self,
            "Limpiar snapshots antiguos",
            "Se aplicarán las políticas de limpieza configuradas en snapper "
            "(número y antigüedad).",
            confirm_text="Limpiar",
            danger=False,
        ):
            return
        self.runner.run(["snapper", "-c", "root", "cleanup", "number"], privileged=True)

    def _on_finished(self, result) -> None:
        if result.ok:
            self.notify("snapper", "Operación completada.", "success")
            self.load()
        elif not result.cancelled:
            self.notify("snapper falló", f"Código {result.code}", "danger")
