from __future__ import annotations

import os

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QSizePolicy

from core import proc, queries, runner
from core.util import human_bytes, human_duration
from ui.components.dialogs import confirm, info
from ui.components.widgets import (
    Card,
    DangerButton,
    GhostButton,
    Hero,
    PrimaryButton,
    StatTile,
)
from ui.pages.common import Page, add_row, console_view, make_table, selected_data
from ui.responsive import ResponsiveGrid, WrapRow

CACHE_DIR = "/var/cache/pacman/pkg"


class CachePage(Page):
    key = "cache"
    title = "Caché de pacman"
    subtitle = "Revisa cuánto ocupa la caché de paquetes y decide qué conservar."

    def __init__(self, window):
        super().__init__(window, scroll=True)
        self._stats = {"total": 0, "count": 0, "files": []}
        self._loaded = False

        self.hero = Hero(
            "Analizando la caché…",
            f"Leyendo {CACHE_DIR}",
            icon_name="database",
        )
        self.btn_refresh = GhostButton("Actualizar")
        self.btn_refresh.setToolTip("Vuelve a calcular el tamaño y los archivos de la caché.")
        self.btn_scc = DangerButton("Borrado total (pacman -Scc)")
        self.btn_scc.setToolTip(
            "Elimina TODOS los paquetes descargados. No afecta a lo instalado, "
            "pero no podrás reinstalar sin conexión."
        )
        self.hero.add_action(self.btn_refresh)
        self.hero.add_action(self.btn_scc)
        self.content.addWidget(self.hero)

        tiles = ResponsiveGrid(min_column=170, spacing=12)
        self.tile_total = StatTile("Espacio en caché", "database")
        self.tile_count = StatTile("Paquetes descargados", "box")
        self.tile_newest = StatTile("Descarga más reciente", "clock")
        self.tile_oldest = StatTile("Descarga más antigua", "clock")
        for tile in (self.tile_total, self.tile_count, self.tile_newest, self.tile_oldest):
            tiles.addWidget(tile)
        self.tile_total.setToolTip("Espacio total ocupado por los archivos de la caché")
        self.tile_count.setToolTip("Número de paquetes descargados en la caché")
        self.tile_newest.setToolTip("Fecha de la descarga más reciente")
        self.tile_oldest.setToolTip("Fecha de la descarga más antigua")
        self.content.addWidget(tiles)

        smart = Card(
            title="Limpieza inteligente con paccache",
            subtitle="Conserva las últimas versiones de los paquetes instalados y elimina el resto.",
            icon_name="sparkles",
        )
        row = WrapRow(spacing=10)
        keep_label = QLabel("Conservar versiones:")
        keep_label.setObjectName("Soft")
        keep_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row.addWidget(keep_label)
        self.combo_keep = QComboBox()
        self.combo_keep.addItems(["0 (todas)", "1", "2", "3", "5"])
        self.combo_keep.setCurrentIndex(2)
        self.combo_keep.setFixedWidth(120)
        self.combo_keep.setToolTip(
            "Número de versiones recientes que se conservarán por paquete instalado."
        )
        row.addWidget(self.combo_keep)
        self.btn_paccache = PrimaryButton("Aplicar paccache -rk N")
        self.btn_paccache.setToolTip(
            "Conserva las N versiones más recientes de los paquetes instalados "
            "y elimina las demás (paccache -rk N)."
        )
        row.addWidget(self.btn_paccache)
        self.btn_uninstalled = GhostButton("Caché de no instalados")
        self.btn_uninstalled.setToolTip(
            "Elimina de la caché los paquetes que ya no están instalados "
            "(paccache -ruk0)."
        )
        row.addWidget(self.btn_uninstalled)
        smart.body.addWidget(row)

        note = QLabel(
            "· -rk N conserva las N versiones más recientes de los paquetes instalados.\n"
            "· -ruk0 elimina todo lo que no está instalado actualmente."
        )
        note.setObjectName("Faint")
        smart.body.addWidget(note)
        self.content.addWidget(smart)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filtrar archivos…")
        self.filter.setToolTip("Filtra por nombre de archivo dentro de la tabla.")
        self.btn_select_all = GhostButton("Seleccionar todo")
        self.btn_select_all.setToolTip("Marca todos los archivos visibles de la tabla.")
        self.btn_delete = DangerButton("Eliminar seleccionados")
        self.btn_delete.setToolTip(
            "Elimina solo los archivos seleccionados de /var/cache/pacman/pkg."
        )
        card = Card(title="Archivos en la caché", icon_name="database")
        card.add_header_widget(self.btn_select_all)
        card.add_header_widget(self.btn_delete)
        card.body.addWidget(self.filter)
        self.table = make_table(
            ["Archivo", "Tamaño", "Fecha"],
            widths=[0, 110, 150],
            stretch=(0,),
            min_height=240,
        )
        card.body.addWidget(self.table)
        self.content.addWidget(card, 1)

        self.console = console_view("Salida")
        self.content.addWidget(self.console)
        self.content.addStretch()

        self.runner = runner.CommandRunner(self, label="caché")
        self.runner.output.connect(lambda s, t: self.console.append(t, s))
        self.runner.runningChanged.connect(self.console.set_running)
        self.runner.finishedSignal.connect(self._on_finished)

        self.btn_refresh.clicked.connect(self.load)
        self.btn_scc.clicked.connect(self._clean_all)
        self.btn_paccache.clicked.connect(self._paccache)
        self.btn_uninstalled.clicked.connect(self._paccache_uninstalled)
        self.btn_select_all.clicked.connect(self.table.selectAll)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.filter.textChanged.connect(self._apply_filter)
        self.console.stop_btn.clicked.connect(lambda: self.runner.cancel())

    def on_show(self) -> None:
        if not self._loaded:
            self._loaded = True
            self.load()

    def load(self) -> None:
        proc.async_call(queries.cache_stats, self._on_stats, owner=self)

    def _on_stats(self, stats) -> None:
        if isinstance(stats, proc.QueryError):
            self.hero.title.setText("No se pudo leer la caché")
            self.hero.text.setText(str(stats))
            return
        self._stats = stats
        self.tile_total.set_value(human_bytes(stats["total"]))
        self.tile_count.set_value(str(stats["count"]))
        newest = QDateTime.fromSecsSinceEpoch(int(stats["newest"] or 0))
        oldest = QDateTime.fromSecsSinceEpoch(int(stats["oldest"] or 0))
        self.tile_newest.set_value(
            newest.toString("dd/MM/yy") if stats["newest"] else "—"
        )
        self.tile_oldest.set_value(
            oldest.toString("dd/MM/yy") if stats["oldest"] else "—"
        )
        self.hero.title.setText(f"{human_bytes(stats['total'])} en caché")
        self.hero.text.setText(
            f"{stats['count']} paquetes descargados en {CACHE_DIR}. "
            "Los paquetes ya instalados se pueden volver a descargar si hicieran falta."
        )
        files = stats["files"][:300]
        self.table.setRowCount(0)
        for item in files:
            dt = QDateTime.fromSecsSinceEpoch(int(item["mtime"]))
            add_row(
                self.table,
                [item["name"], human_bytes(item["size"]), dt.toString("dd/MM/yy HH:mm")],
                data=item["path"],
            )

    def _apply_filter(self, text) -> None:
        needle = text.lower()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            hidden = bool(needle) and needle not in (item.text() if item else "").lower()
            self.table.setRowHidden(row, hidden)

    @staticmethod
    def _valid_path(path: str) -> bool:
        return (
            isinstance(path, str)
            and path.startswith(CACHE_DIR + "/")
            and ("pkg.tar" in os.path.basename(path) or path.endswith(".sig"))
        )

    def _delete_selected(self) -> None:
        paths = [p for p in selected_data(self.table) if self._valid_path(p)]
        if not paths:
            self.notify("Sin selección", "Selecciona archivos de la caché.", "warn")
            return
        sizes = {item["path"]: item["size"] for item in self._stats.get("files", [])}
        total = sum(sizes.get(p, 0) for p in paths)
        preview = [os.path.basename(p) for p in paths[:14]]
        if len(paths) > 14:
            preview.append(f"… y {len(paths) - 14} más")
        if not confirm(
            self,
            "Eliminar archivos de la caché",
            f"Se eliminarán {len(paths)} archivos y se liberarán ~{human_bytes(total)}.",
            items=preview,
            confirm_text="Eliminar",
        ):
            return
        self.runner.run(["rm", "-f", "--", *paths], privileged=True)

    def _paccache(self) -> None:
        keep = self.combo_keep.currentText().split()[0]
        if keep == "0" and not confirm(
            self,
            "Eliminar todas las versiones en caché",
            "Se eliminará TODA la caché de paquetes (paccache -rk0). "
            "No afecta a los paquetes instalados, pero perderás las copias locales.",
            confirm_text="Eliminar todo",
        ):
            return
        self.runner.run(["paccache", f"-rk{keep}"], privileged=True)

    def _paccache_uninstalled(self) -> None:
        if not confirm(
            self,
            "Eliminar caché de paquetes no instalados",
            "Se eliminarán de la caché los paquetes que ya no están instalados. "
            "No afecta a ningún paquete del sistema.",
            confirm_text="Eliminar",
        ):
            return
        self.runner.run(["paccache", "-ruk0"], privileged=True)

    def _clean_all(self) -> None:
        if not confirm(
            self,
            "Borrado total de la caché",
            "Se ejecutará 'pacman -Scc': se eliminarán TODOS los paquetes de la caché, "
            "incluidos los que aún podrían reinstalarse sin conexión.",
            items=[
                f"Tamaño actual: {human_bytes(self._stats['total'])}",
                f"Archivos: {len(self._stats.get('files', []))}",
            ],
            confirm_text="Borrar todo",
        ):
            return
        self.runner.run(["pacman", "-Scc", "--noconfirm"], privileged=True)

    def _on_finished(self, result) -> None:
        if result.ok:
            self.notify("Caché actualizada", "Operación completada.", "success")
            self.load()
        elif not result.cancelled:
            self.notify("No se pudo completar", f"Código {result.code}", "danger")
