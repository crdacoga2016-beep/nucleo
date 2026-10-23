from __future__ import annotations

import os

from PySide6.QtWidgets import QHBoxLayout, QPushButton

from core import proc, queries, runner, safety, system
from core.util import human_bytes, human_duration, human_time
from ui import theme
from ui.components.dialogs import confirm, info
from ui.components.widgets import (
    Card,
    GhostButton,
    Hero,
    KVList,
    PrimaryButton,
    StepList,
    StatTile,
)
from ui.pages.common import Page, console_view
from ui.responsive import ResponsiveGrid, WrapRow

TRASH = os.path.expanduser("~/.local/share/Trash")


class DashboardPage(Page):
    key = "dashboard"
    title = "Panel general"
    subtitle = "Resumen del sistema y accesos rápidos a las tareas más habituales."

    def __init__(self, window):
        super().__init__(window, scroll=True)
        self._orphans: list = []
        self._updates: list = []
        self._updates_loaded = False
        self._preflighting = False

        self.hero = Hero(
            "Analizando el sistema…",
            "Recopilando información de tu equipo.",
            icon_name="sparkles",
        )
        self.btn_upgrade = PrimaryButton("Actualizar ahora")
        self.btn_upgrade.setToolTip("Ir a la página de actualizaciones para revisar y aplicar.")
        self.btn_maintain = GhostButton("Mantenimiento completo")
        self.btn_maintain.setToolTip(
            "Actualiza con revisión de seguridad, limpia caché, elimina huérfanas "
            "y vacía registros."
        )
        self.hero.add_action(self.btn_maintain)
        self.hero.add_action(self.btn_upgrade)
        self.content.addWidget(self.hero)

        self.tiles = ResponsiveGrid(min_column=190, spacing=12)
        self.tile_updates = StatTile("Actualizaciones", "download")
        self.tile_orphans = StatTile("Huérfanas", "unlink", accent=theme.C["WARN"])
        self.tile_cache = StatTile("Caché de paquetes", "database", accent=theme.C["INFO"])
        self.tile_disk = StatTile("Disco raíz", "disk")
        self.tile_packages = StatTile("Paquetes", "box")
        self.tile_failed = StatTile("Servicios fallidos", "warning", accent=theme.C["DANGER"])
        for tile in (
            self.tile_updates,
            self.tile_orphans,
            self.tile_cache,
            self.tile_disk,
            self.tile_packages,
            self.tile_failed,
        ):
            self.tiles.addWidget(tile)
        self.tile_updates.setToolTip("Actualizaciones pendientes de repositorios y AUR")
        self.tile_orphans.setToolTip(
            "Paquetes instalados como dependencia que ya nadie necesita"
        )
        self.tile_cache.setToolTip("Espacio ocupado por paquetes descargados en la caché")
        self.tile_disk.setToolTip("Uso del sistema de archivos raíz (/)")
        self.tile_packages.setToolTip("Total de paquetes instalados y cuántos vienen del AUR")
        self.tile_failed.setToolTip("Servicios de systemd que han fallado")
        self.content.addWidget(self.tiles)

        self.system_card = Card(title="Equipo", icon_name="cpu")
        self.system_info = KVList()
        self.system_card.body.addWidget(self.system_info)

        actions_card = Card(title="Acciones rápidas", icon_name="sparkles")
        actions_wrap = WrapRow(spacing=8)
        quick = [
            ("Actualizar", "update", "download"),
            ("Paquetes", "packages", "box"),
            ("Huérfanas", "orphans", "unlink"),
            ("Caché", "cache", "database"),
            ("Limpieza", "cleanup", "broom"),
            ("Snapshots", "snapshots", "layers"),
            ("Espejos", "mirrors", "globe"),
            ("Historial", "history", "clock"),
        ]
        for label, key, icon_name in quick:
            button = QPushButton(label)
            button.setMinimumHeight(36)
            button.setMinimumWidth(118)
            button.setCursor(button.cursor())
            button.setToolTip(f"Ir a {label}")
            button.clicked.connect(lambda _=False, k=key: self.window.navigate(k))
            actions_wrap.addWidget(button)
        actions_card.body.addWidget(actions_wrap)

        self.middle = ResponsiveGrid(min_column=300, spacing=14)
        self.middle.addWidget(self.system_card)
        self.middle.addWidget(actions_card)
        self.content.addWidget(self.middle)

        self.maintain_card = Card(
            title="Mantenimiento completo",
            subtitle="Actualiza con revisión de seguridad, limpia caché, elimina huérfanas y vacía registros en un solo paso.",
            icon_name="rocket",
        )
        self.steps = StepList()
        self.steps.set_steps(
            [
                "Actualizar el sistema (pacman -Syu)",
                "Limpiar caché de paquetes (paccache -rk2)",
                "Eliminar dependencias huérfanas",
                "Limpiar registros del sistema (journald)",
                "Vaciar la papelera",
            ]
        )
        self.maintain_card.body.addWidget(self.steps)
        self.maintain_console = console_view("Salida del mantenimiento", min_height=120)
        self.maintain_card.body.addWidget(self.maintain_console)
        row = QHBoxLayout()
        row.addStretch()
        self.btn_start = PrimaryButton("Iniciar mantenimiento")
        self.btn_start.setToolTip(
            "Ejecuta los pasos de la lista con confirmación previa."
        )
        row.addWidget(self.btn_start)
        self.maintain_card.body.addLayout(row)
        self.content.addWidget(self.maintain_card)
        self.content.addStretch()

        self.runner = runner.CommandRunner(self)
        self.sequence = runner.SequenceRunner(self)
        self.sequence.output.connect(
            lambda s, t: self.maintain_console.append(t, s)
        )
        self.sequence.stepState.connect(self.steps.set_state)
        self.sequence.runningChanged.connect(self._on_sequence_running)
        self.sequence.finishedSequence.connect(self._on_sequence_finished)

        self.tile_updates.clicked.connect(lambda: self.window.navigate("update"))
        self.tile_orphans.clicked.connect(lambda: self.window.navigate("orphans"))
        self.tile_cache.clicked.connect(lambda: self.window.navigate("cache"))
        self.tile_packages.clicked.connect(lambda: self.window.navigate("packages"))
        self.btn_upgrade.clicked.connect(self._upgrade_now)
        self.btn_maintain.clicked.connect(self._start_maintenance)
        self.btn_start.clicked.connect(self._start_maintenance)
        self.maintain_console.stop_btn.clicked.connect(self.sequence.cancel)

        self.refresh()

    def refresh(self, force: bool = False) -> None:
        self._load_system()
        proc.async_call(queries.all_updates, self._on_updates, force, owner=self)
        proc.async_call(queries.orphan_details, self._on_orphans, owner=self)
        proc.async_call(queries.cache_stats, self._on_cache, owner=self)
        proc.async_call(queries.package_counts, self._on_counts, owner=self)
        proc.async_call(queries.services_failed, self._on_failed, owner=self)

    def _load_system(self) -> None:
        self.system_info.clear()
        self.system_info.add("Sistema", system.os_name())
        self.system_info.add("Kernel", system.kernel())
        self.system_info.add("Equipo", system.hostname())
        self.system_info.add("Escritorio", system.desktop())
        self.system_info.add("CPU", system.cpu_model())
        self.system_info.add("Núcleos", f"{system.cpu_cores()} hilos")
        total, available = system.memory()
        self.system_info.add(
            "Memoria", f"{human_bytes(total - available)} usados de {human_bytes(total)}"
        )
        load = system.load_average()
        self.system_info.add("Carga media", "  ".join(f"{v:.2f}" for v in load))
        temp = system.cpu_temp()
        self.system_info.add("Temperatura", f"{temp:.1f} °C" if temp else "—")
        self.system_info.add("Sistema de archivos", system.filesystem_type("/"))
        self.system_info.add("Tiempo encendido", human_duration(system.uptime_seconds()))
        disk = system.disk_usage("/")
        self.tile_disk.set_number(
            disk["percent"], lambda value: f"{value:.0f}%"
        )
        self.tile_disk.set_sub(
            f"{human_bytes(disk['used'])} de {human_bytes(disk['total'])}"
        )

    def _on_updates(self, updates) -> None:
        if isinstance(updates, proc.QueryError):
            return
        self._updates = updates
        self._updates_loaded = True
        count = len(updates)
        aur = sum(1 for item in updates if item.get("aur"))
        self.tile_updates.set_number(count, lambda v: f"{int(v)}")
        if not count:
            self.tile_updates.set_sub("todo al día")
        elif aur:
            self.tile_updates.set_sub(f"{count - aur} oficiales · {aur} AUR")
        else:
            self.tile_updates.set_sub("pendientes de instalar")
        if count:
            self.hero.title.setText(f"{count} actualizaciones disponibles")
            detail = f"{count - aur} de repositorios"
            if aur:
                detail += f" · {aur} de AUR (paru)"
            self.hero.text.setText(
                f"{detail} · última comprobación: {human_time(proc_time())}"
            )
        else:
            self.hero.title.setText("Todo actualizado")
            self.hero.text.setText(
                f"{system.os_name()} · kernel {system.kernel()} · "
                f"encendido {human_duration(system.uptime_seconds())}"
            )

    def _on_orphans(self, items) -> None:
        if isinstance(items, proc.QueryError):
            return
        self._orphans = items
        total = sum(item["size"] for item in items)
        self.tile_orphans.set_number(len(items), lambda v: f"{int(v)}")
        self.tile_orphans.set_sub(
            human_bytes(total) + " recuperables" if items else "ninguna"
        )

    def _on_cache(self, stats) -> None:
        if isinstance(stats, proc.QueryError):
            return
        self.tile_cache.set_number(
            stats["total"], lambda v: human_bytes(v)
        )
        self.tile_cache.set_sub(f"{stats['count']} paquetes descargados")

    def _on_counts(self, counts) -> None:
        if isinstance(counts, proc.QueryError):
            return
        self.tile_packages.set_number(counts["total"], lambda v: f"{int(v)}")
        self.tile_packages.set_sub(
            f"{counts['explicit']} explícitos · {counts['foreign']} de AUR"
        )

    def _on_failed(self, failed) -> None:
        if isinstance(failed, proc.QueryError):
            return
        self.tile_failed.set_number(len(failed), lambda v: f"{int(v)}")
        self.tile_failed.set_sub(", ".join(failed[:2]) if failed else "ninguno")

    def _upgrade_now(self) -> None:
        self.window.navigate("update")

    def _start_maintenance(self) -> None:
        if self.sequence.running:
            self.notify("En curso", "El mantenimiento ya está ejecutándose.", "warn")
            return
        if self._preflighting:
            return
        if not self._updates_loaded:
            self.notify(
                "Comprobando",
                "Espera a que termine la revisión de actualizaciones.",
                "info",
            )
            self.refresh()
            return
        repo = [item for item in self._updates if not item.get("aur")]
        if not repo:
            self._confirm_maintenance(repo)
            return
        self._preflighting = True
        self.btn_start.setEnabled(False)
        self.btn_start.setText("Revisando seguridad…")
        proc.async_call(safety.preflight, self._on_maint_preflight, repo, owner=self)

    def _on_maint_preflight(self, checks) -> None:
        self._preflighting = False
        self.btn_start.setEnabled(True)
        self.btn_start.setText("Iniciar mantenimiento")
        if isinstance(checks, proc.QueryError):
            self.notify("No se pudo revisar", str(checks), "danger")
            return
        fails = [check for check in checks if check.status == "fail"]
        warns = [check for check in checks if check.status == "warn"]
        items = [check.line() for check in checks]
        if fails:
            info(
                self,
                "Mantenimiento bloqueado",
                "Se encontraron problemas críticos. No se ha modificado nada.",
                items=items,
                detail=(
                    "Corrige los avisos marcados con ✕ y vuelve a intentarlo. "
                    "Si no sabes cómo, revisa la consola o pide ayuda antes de forzar."
                ),
                danger=True,
            )
            return
        if warns and not confirm(
            self,
            "Revisión completada con avisos",
            "Puedes continuar, pero revisa estos avisos:",
            items=items,
            detail="Se creará un snapshot antes de actualizar los repositorios.",
            confirm_text="Continuar con el mantenimiento",
            danger=False,
        ):
            return
        repo = [item for item in self._updates if not item.get("aur")]
        self._confirm_maintenance(repo)

    def _confirm_maintenance(self, repo) -> None:
        orphans = queries.orphans()
        steps = []
        if repo:
            steps += [
                runner.Step(
                    "Crear snapshot de seguridad",
                    [
                        "snapper",
                        "-c",
                        "root",
                        "create",
                        "-p",
                        "-d",
                        "Núcleo: antes del mantenimiento",
                    ],
                    True,
                ),
                runner.Step(
                    "Actualizar el sistema", ["pacman", "-Syu", "--noconfirm"], True
                ),
            ]
        steps.append(
            runner.Step("Limpiar caché de paquetes", ["paccache", "-rk2"], True)
        )
        if orphans:
            steps.append(
                runner.Step(
                    f"Eliminar {len(orphans)} paquetes huérfanos",
                    ["pacman", "-Rns", "--noconfirm", *orphans],
                    True,
                )
            )
        steps += [
            runner.Step(
                "Limpiar registros del sistema", ["journalctl", "--vacuum-time=14d"], True
            ),
            runner.Step(
                "Vaciar la papelera", ["find", TRASH, "-mindepth", "1", "-delete"], False
            ),
        ]
        labels = [step.label for step in steps]
        self.steps.set_steps(labels)
        if not confirm(
            self,
            "Iniciar mantenimiento completo",
            "Se ejecutarán las siguientes tareas de forma secuencial:",
            items=labels,
            detail=(
                "Algunas requieren permisos de administrador. Los paquetes de AUR "
                "no se actualizan aquí: usa Actualizar > Revisar AUR. La actualización "
                "solo se aplica si pasan las comprobaciones de seguridad."
            ),
            confirm_text="Iniciar",
            danger=False,
        ):
            return
        self.maintain_console.clear()
        self.sequence.start(steps, stop_on_error=True)

    def _on_sequence_running(self, running) -> None:
        self.maintain_console.set_running(running)
        self.btn_start.setEnabled(not running)
        self.btn_start.setText("Mantenimiento en curso…" if running else "Iniciar mantenimiento")

    def _on_sequence_finished(self, success) -> None:
        if success:
            self.notify("Mantenimiento completado", "Todo listo.", "success")
        else:
            self.notify(
                "Mantenimiento interrumpido",
                "Revisa la consola para ver el detalle.",
                "warn",
            )
        self.refresh(force=True)


def proc_time() -> float:
    import time

    return time.time()
