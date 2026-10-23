from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import auth, proc, queries, runner
from core.util import human_bytes
from ui.components.dialogs import confirm, info
from ui.components.widgets import (
    Badge,
    Card,
    DangerButton,
    GhostButton,
    KVList,
    PrimaryButton,
    Segmented,
)
from ui.pages.common import Page, add_row, console_view, make_table, selected_data


class PackagesPage(Page):
    key = "packages"
    title = "Paquetes"
    subtitle = "Explora lo instalado, desinstala, marca motivos e instala nuevos paquetes."

    FILTERS = [
        ("all", "Todas"),
        ("explicit", "Explícitas"),
        ("dep", "Dependencias"),
        ("aur", "AUR"),
        ("orphan", "Huérfanas"),
    ]

    def __init__(self, window):
        super().__init__(window)
        self._installed: list = []
        self._orphans: set = set()
        self._filter = "all"
        self._loaded = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(220)
        self._debounce.timeout.connect(self._populate_installed)

        view = Segmented([("installed", "Instalados"), ("install", "Instalar")])
        self.header.add_action(view)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_installed())
        self.stack.addWidget(self._build_install())
        self.content.addWidget(self.stack, 1)

        self.console = console_view("Salida de pacman / paru")
        self.content.addWidget(self.console)

        self.runner = runner.CommandRunner(self, label="paquetes")
        self.runner.output.connect(lambda s, t: self.console.append(t, s))
        self.runner.runningChanged.connect(self.console.set_running)
        self.runner.runningChanged.connect(self._on_running)
        self.runner.finishedSignal.connect(self._on_finished)
        self.console.stop_btn.clicked.connect(lambda: self.runner.cancel())
        self.console.submitted.connect(self.runner.send_input)
        view.changed.connect(self._on_view)

    def on_show(self) -> None:
        if not self._loaded:
            self._loaded = True
            self.load()

    def _on_view(self, key: str) -> None:
        self.stack.setCurrentIndex(0 if key == "installed" else 1)

    def _on_running(self, running: bool) -> None:
        self.btn_install.setEnabled(not running)
        if running:
            self.btn_uninstall.setEnabled(False)
            self.btn_explicit.setEnabled(False)
            self.btn_deps.setEnabled(False)
        else:
            self._show_details(self.table.currentItem())

    def load(self) -> None:
        self.status.setText("Cargando paquetes instalados…")
        proc.async_call(queries.orphans, self._on_orphans, owner=self)
        proc.async_call(queries.installed_packages, self._on_installed, owner=self)

    def _on_orphans(self, names) -> None:
        if isinstance(names, proc.QueryError):
            return
        self._orphans = set(names)
        self._populate_installed()

    def _on_installed(self, packages) -> None:
        if isinstance(packages, proc.QueryError):
            self.status.setText("No se pudo leer la lista de paquetes")
            return
        self._installed = packages
        explicit = sum(1 for p in packages if p["explicit"])
        self.status.setText(
            f"{len(packages)} paquetes · {explicit} explícitos · "
            f"{len(packages) - explicit} dependencias"
        )
        self._populate_installed()

    def _filtered(self) -> list:
        needle = self.search.text().strip().lower()
        result = []
        for item in self._installed:
            if needle and needle not in item["name"].lower() and needle not in (
                item["description"] or ""
            ).lower():
                continue
            if self._filter == "explicit" and not item["explicit"]:
                continue
            if self._filter == "dep" and item["explicit"]:
                continue
            if self._filter == "aur" and item["repository"] != "aur":
                continue
            if self._filter == "orphan" and item["name"] not in self._orphans:
                continue
            result.append(item)
        return result

    def _populate_installed(self) -> None:
        rows = self._filtered()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for item in rows:
            add_row(
                self.table,
                [
                    item["name"],
                    item["version"],
                    human_bytes(item["size"]),
                    "AUR" if item["repository"] == "aur" else (item["repository"] or "—"),
                    "explícita" if item["explicit"] else "dependencia",
                ],
                data=item["name"],
            )
        self.table.setSortingEnabled(True)
        self.count.setText(f"{len(rows)} de {len(self._installed)}")

    def _on_filter(self, key: str) -> None:
        self._filter = key
        self._populate_installed()

    def _on_search(self) -> None:
        self._debounce.start()

    def _show_details(self, current, previous=None) -> None:
        name = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        item = next((p for p in self._installed if p["name"] == name), None)
        self.details.clear()
        if item is None:
            self.details.add("Selecciona un paquete", "Aquí verás su información completa.")
            self.btn_uninstall.setEnabled(False)
            self.btn_explicit.setEnabled(False)
            self.btn_deps.setEnabled(False)
            return
        required = item["required_by"]
        optional = item["optional_for"]
        depends = item["depends"]
        orphan = item["name"] in self._orphans
        self.details.add("Paquete", item["name"])
        self.details.add("Versión", item["version"])
        self.details.add(
            "Repositorio", "AUR (paru)" if item["repository"] == "aur" else (item["repository"] or "—")
        )
        self.details.add("Tamaño", human_bytes(item["size"]))
        self.details.add("Motivo", "Instalado explícitamente" if item["explicit"] else "Dependencia")
        if orphan:
            self.details.add("Estado", "Huérfano (nadie lo requiere)")
        self.details.add(
            "Requerido por",
            ", ".join(required[:8]) + (f" (+{len(required) - 8})" if len(required) > 8 else "")
            if required
            else "Nadie lo requiere",
        )
        if optional:
            self.details.add(
                "Opcional para",
                ", ".join(optional[:8])
                + (f" (+{len(optional) - 8})" if len(optional) > 8 else ""),
            )
        if depends:
            self.details.add("Depende de", ", ".join(depends[:10]))
        if item["description"]:
            self.details.add("Descripción", item["description"])
        if item["install_date"]:
            self.details.add("Instalado", item["install_date"])
        self.btn_uninstall.setEnabled(True)
        self.btn_explicit.setEnabled(not item["explicit"])
        self.btn_deps.setEnabled(item["explicit"])

    def _uninstall(self) -> None:
        names = selected_data(self.table)
        if not names:
            self.notify("Sin selección", "Selecciona un paquete.", "warn")
            return
        warnings = []
        for name in names:
            item = next((p for p in self._installed if p["name"] == name), None)
            if item and item["required_by"]:
                warnings.append(
                    f"{name}: requerido por {', '.join(item['required_by'][:6])}"
                )
        detail = "\n".join(warnings[:8])
        if not confirm(
            self,
            "Desinstalar paquetes",
            f"Se ejecutará 'sudo pacman -Rns' sobre {len(names)} paquete(s) "
            "incluyendo sus dependencias no usadas.",
            items=names,
            detail=detail,
            confirm_text="Desinstalar",
        ):
            return
        self.runner.run(["pacman", "-Rns", "--noconfirm", *names], privileged=True)

    def _mark(self, explicit: bool) -> None:
        names = selected_data(self.table)
        if not names:
            self.notify("Sin selección", "Selecciona un paquete.", "warn")
            return
        flag = "--asexplicit" if explicit else "--asdeps"
        self.runner.run(["pacman", "-D", flag, *names], privileged=True)

    def _search_remote(self) -> None:
        pattern = self.remote_search.text().strip()
        if not pattern:
            self.notify("Búsqueda vacía", "Escribe un nombre o patrón.", "warn")
            return
        self.remote_status.setText("Buscando…")
        proc.async_call(
            queries.search_remote,
            self._on_remote,
            pattern,
            include_aur=self.aur.isChecked(),
            owner=self,
        )

    def _on_remote(self, payload) -> None:
        if isinstance(payload, proc.QueryError):
            self.remote_status.setText(str(payload))
            return
        results, error = payload
        if error:
            self.remote_status.setText(error)
        else:
            self.remote_status.setText(f"{len(results)} resultados")
        self.remote_table.setRowCount(0)
        for item in results:
            add_row(
                self.remote_table,
                [
                    item["repo"],
                    item["name"],
                    item["version"],
                    "Sí" if item["installed"] else "No",
                    item["description"] or "—",
                ],
                data=item,
            )

    def _install(self) -> None:
        selected = selected_data(self.remote_table)
        if not selected:
            self.notify("Sin selección", "Selecciona paquetes a instalar.", "warn")
            return
        official = [item["name"] for item in selected if item["repo"] != "aur"]
        aur = [item["name"] for item in selected if item["repo"] == "aur"]
        items = [f"{item['repo']}/{item['name']} {item['version']}" for item in selected]
        if not confirm(
            self,
            "Instalar paquetes",
            "Se instalarán los siguientes paquetes:",
            items=items,
            detail=(
                "Oficiales: sudo pacman -S --needed --noconfirm\n"
                "AUR: paru -S --noconfirm --skipreview"
            ),
            confirm_text="Instalar",
            danger=False,
        ):
            return
        commands = []
        if official:
            commands.append(["pacman", "-S", "--needed", "--noconfirm", *official])
        if aur:
            if not auth.ensure_sudo(self):
                return
            commands.append(
                ["paru", "-S", "--noconfirm", "--skipreview", *[f"aur/{name}" for name in aur]]
            )
        self._run_queue(commands)

    def _run_queue(self, commands) -> None:
        self._queue = list(commands)
        self._run_next()

    def _run_next(self) -> None:
        if not self._queue:
            return
        cmd = self._queue.pop(0)
        self.runner.run(cmd, privileged=(cmd[0] == "pacman"))

    def _on_finished(self, result) -> None:
        if not result.ok and not result.cancelled:
            self._queue = []
            self.notify("La operación falló", f"Código {result.code}", "danger")
            return
        if getattr(self, "_queue", None):
            self._run_next()
            return
        if result.ok:
            self.notify("Operación completada", "Recargando información…", "success")
            self.load()

    def _build_installed(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar paquete instalado…")
        self.search.setToolTip("Filtra por nombre o descripción del paquete.")
        self.search.textChanged.connect(self._on_search)
        top.addWidget(self.search, 1)
        filters = Segmented(self.FILTERS)
        filters.changed.connect(self._on_filter)
        top.addWidget(filters)
        layout.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        self.table = make_table(
            ["Paquete", "Versión", "Tamaño", "Repo", "Motivo"],
            widths=[230, 170, 100, 90, 120],
            stretch=(0,),
            min_height=260,
            sortable=True,
        )
        self.table.itemSelectionChanged.connect(
            lambda: self._show_details(self.table.currentItem())
        )
        split.addWidget(self.table)

        detail_panel = Card(title="Detalles", icon_name="info")
        self.details = KVList()
        detail_panel.body.addWidget(self.details)
        self.btn_uninstall = DangerButton("Desinstalar")
        self.btn_uninstall.setToolTip(
            "Elimina el paquete y sus dependencias no usadas con 'pacman -Rns'."
        )
        self.btn_explicit = GhostButton("Marcar explícita")
        self.btn_explicit.setToolTip(
            "Marca el paquete como instalado a propósito para que no aparezca "
            "como huérfano (pacman -D --asexplicit)."
        )
        self.btn_deps = GhostButton("Marcar dependencia")
        self.btn_deps.setToolTip(
            "Marca el paquete como dependencia para que pueda considerarse "
            "huérfano si nadie lo necesita (pacman -D --asdeps)."
        )
        detail_panel.body.addLayout(
            _btn_row(self.btn_uninstall, self.btn_explicit, self.btn_deps)
        )
        split.addWidget(detail_panel)
        split.setSizes([700, 340])
        layout.addWidget(split, 1)

        bottom = QHBoxLayout()
        self.status = QLabel("Cargando…")
        self.status.setObjectName("Muted")
        self.count = QLabel("")
        self.count.setObjectName("Faint")
        bottom.addWidget(self.status)
        bottom.addStretch()
        bottom.addWidget(self.count)
        layout.addLayout(bottom)

        self.btn_uninstall.clicked.connect(self._uninstall)
        self.btn_explicit.clicked.connect(lambda: self._mark(True))
        self.btn_deps.clicked.connect(lambda: self._mark(False))
        self._show_details(None)
        return page

    def _build_install(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.remote_search = QLineEdit()
        self.remote_search.setPlaceholderText("Buscar en repositorios oficiales y AUR…")
        self.remote_search.setToolTip(
            "Busca por nombre o palabra clave. Pulsa Intro o el botón Buscar."
        )
        self.remote_search.returnPressed.connect(self._search_remote)
        top.addWidget(self.remote_search, 1)
        self.aur = QCheckBox("Incluir AUR (paru)")
        has_paru = proc.which("paru")
        self.aur.setChecked(has_paru)
        if not has_paru:
            self.aur.setEnabled(False)
            self.aur.setToolTip(
                "paru no está instalado: sin él no se pueden buscar paquetes de AUR."
            )
        else:
            self.aur.setToolTip(
                "Incluye paquetes de AUR en la búsqueda. Se compilan con paru."
            )
        top.addWidget(self.aur)
        search_btn = PrimaryButton("Buscar")
        search_btn.clicked.connect(self._search_remote)
        top.addWidget(search_btn)
        self.btn_install = PrimaryButton("Instalar seleccionadas")
        self.btn_install.setToolTip(
            "Instala las filas seleccionadas: oficiales con pacman y AUR con paru."
        )
        self.btn_install.clicked.connect(self._install)
        top.addWidget(self.btn_install)
        layout.addLayout(top)

        self.remote_table = make_table(
            ["Repo", "Paquete", "Versión", "Instalado", "Descripción"],
            widths=[90, 200, 150, 90, 0],
            stretch=(4,),
            min_height=240,
        )
        card = Card(title="Resultados", icon_name="search")
        card.body.addWidget(self.remote_table)
        self.remote_status = QLabel("Escribe un término y pulsa Buscar.")
        self.remote_status.setObjectName("Faint")
        card.body.addWidget(self.remote_status)
        layout.addWidget(card, 1)
        return page


def _btn_row(*buttons):
    layout = QHBoxLayout()
    layout.setSpacing(8)
    for button in buttons:
        layout.addWidget(button)
    return layout
