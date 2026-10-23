from __future__ import annotations

import re
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QSplitter

from core import auth, proc, queries, runner, safety
from core.util import human_bytes, human_time
from ui.components.dialogs import confirm, info
from ui.components.widgets import Card, GhostButton, Hero, PrimaryButton
from ui.pages.common import Page, add_row, console_view, make_table


class UpdatePage(Page):
    key = "update"
    title = "Actualizar sistema"
    subtitle = "Actualiza repositorios de forma segura; el AUR se revisa aparte."

    def __init__(self, window):
        super().__init__(window)
        self._updates: list = []
        self._loaded = False
        self._loaded_at = 0.0
        self._reboot_names: list[str] = []
        self._queue: list = []
        self._after_queue = None
        self._kind = ""
        self._preflighting = False
        self._preflight_updates: list = []
        self._snapshot_jobs: list = []
        self._snapshot_after = None
        self._snapshot_id = 0
        self._aur_count = 0

        self.auto = QCheckBox("Auto-confirmar (--noconfirm)")
        self.auto.setChecked(True)
        self.auto.setToolTip(
            "Si lo desactivas podrás responder a pacman desde la consola inferior. "
            "No afecta a la revisión de seguridad."
        )
        self.auto.toggled.connect(self._toggle_auto)
        self.header.add_action(self.auto)

        self.btn_aur = GhostButton("Revisar AUR")
        self.btn_aur.setToolTip(
            "Muestra y actualiza los paquetes de AUR de forma manual. "
            "Crea un snapshot antes y avisa de los paquetes delicados. "
            "El botón «Actualizar sistema» nunca toca el AUR."
        )
        self.btn_aur.setEnabled(False)

        self.btn_check = GhostButton("Comprobar")
        self.btn_check.setToolTip("Vuelve a consultar los repositorios y el AUR.")
        self.btn_check.clicked.connect(lambda: self.load(force=True))
        self.header.add_action(self.btn_check)

        self.hero = Hero(
            "Comprobando actualizaciones…",
            "Consultando los repositorios configurados y el AUR.",
            icon_name="download",
        )
        self.btn_upgrade = PrimaryButton("Actualizar sistema")
        self.btn_upgrade.setToolTip(
            "Actualiza solo los repositorios oficiales y de CachyOS con "
            "'pacman -Syu'. Antes comprueba espacio, base de datos, keyring, "
            "snapshot y noticias; después ofrece huérfanas y caché."
        )
        self.btn_sync = GhostButton("Sincronizar bases (-Syy)")
        self.btn_sync.setToolTip(
            "Fuerza la descarga de las bases de datos de pacman sin instalar nada."
        )
        self.btn_reboot = GhostButton("Reiniciar sistema")
        self.btn_reboot.setToolTip(
            "Reinicia el equipo para aplicar kernel, systemd, glibc, NVIDIA o Mesa. "
            "Guarda tu trabajo antes."
        )
        self.btn_reboot.hide()
        self.hero.add_action(self.btn_sync)
        self.hero.add_action(self.btn_reboot)
        self.hero.add_action(self.btn_aur)
        self.hero.add_action(self.btn_upgrade)
        self.content.addWidget(self.hero)

        self.table = make_table(
            ["Paquete", "Versión actual", "Nueva versión", "Origen"],
            widths=[240, 190, 0, 90],
            stretch=(2,),
            min_height=170,
        )
        self.table.setToolTip(
            "Actualizaciones detectadas. Las filas AUR se actualizan aparte con "
            "«Revisar AUR»."
        )
        card = Card(title="Paquetes con actualización pendiente", icon_name="box")
        card.body.addWidget(self.table)

        self.console = console_view("Salida de pacman / paru", min_height=170)
        self.console.setToolTip(
            "Aquí aparece el proceso en vivo. Desplázate con la rueda del ratón "
            "o con la barra lateral. Usa los botones de la cabecera para ampliar, "
            "contraer, copiar o limpiar la salida."
        )

        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(card)
        split.addWidget(self.console)
        split.setSizes([430, 220])
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        self.content.addWidget(split, 1)

        self.runner = runner.CommandRunner(self, label="actualización")
        self.runner.output.connect(self._on_output)
        self.runner.runningChanged.connect(self._on_running)
        self.runner.finishedSignal.connect(self._on_finished)
        self.runner.rejected.connect(
            lambda: self.notify(
                "Permisos necesarios", "Autenticación cancelada.", "warn"
            )
        )

        self.btn_upgrade.clicked.connect(self.upgrade_all)
        self.btn_aur.clicked.connect(self.update_aur)
        self.btn_sync.clicked.connect(self.sync_databases)
        self.btn_reboot.clicked.connect(self.reboot)
        self.console.stop_btn.clicked.connect(lambda: self.runner.cancel())
        self.console.submitted.connect(self.runner.send_input)

    def on_show(self) -> None:
        if self.runner.running:
            return
        if not self._loaded or time.time() - self._loaded_at > 60:
            self._loaded = True
            self.load()

    def refresh(self) -> None:
        self.load(force=True)

    def load(self, force: bool = False) -> None:
        self._loaded_at = time.time()
        self.hero.title.setText("Comprobando actualizaciones…")
        self.hero.text.setText(
            "Consultando repositorios y AUR. El AUR solo se actualiza manualmente."
        )
        proc.async_call(queries.all_updates, self._on_updates, force, owner=self)

    def _on_updates(self, updates) -> None:
        if isinstance(updates, proc.QueryError):
            self.hero.title.setText("No se pudo comprobar")
            self.hero.text.setText(str(updates))
            return
        self._updates = updates
        self.table.setRowCount(0)
        for item in updates:
            add_row(
                self.table,
                [
                    item["name"],
                    item["old"],
                    item["new"],
                    "AUR" if item.get("aur") else "Oficial",
                ],
                colors=[None, None, None, "INFO" if item.get("aur") else None],
                data=item["name"],
            )
        count = len(updates)
        aur = sum(1 for item in updates if item.get("aur"))
        repo = count - aur
        self._aur_count = aur
        self.btn_aur.setText(f"Revisar AUR ({aur})" if aur else "Revisar AUR")
        self.btn_aur.setEnabled(
            bool(aur) and proc.which("paru") and not self.runner.running
        )
        if count == 0:
            self.hero.title.setText("Sistema al día")
            self.hero.text.setText("No hay actualizaciones pendientes.")
        else:
            plural = "actualización" if count == 1 else "actualizaciones"
            self.hero.title.setText(
                f"{count} {plural} disponible{'s' if count != 1 else ''}"
            )
            detail = f"{repo} de repositorios"
            if aur:
                detail += f" · {aur} de AUR (manual)"
            self.hero.text.setText(
                f"{detail} · comprobado a las {human_time(time.time())} · "
                "el AUR no se actualiza automáticamente."
            )

    def _toggle_auto(self, checked) -> None:
        if self.runner.running:
            self.console.show_input(not checked)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        if self.runner.running:
            return
        self.btn_upgrade.setEnabled(enabled)
        self.btn_sync.setEnabled(enabled)
        self.btn_check.setEnabled(enabled)
        self.auto.setEnabled(enabled)
        self.btn_aur.setEnabled(
            enabled and self._aur_count > 0 and proc.which("paru")
        )

    def _pacman_args(self, base: list) -> list:
        return base + (["--noconfirm"] if self.auto.isChecked() else [])

    def _paru_args(self, base: list) -> list:
        args = base + ["--skipreview", "--devel", "--sudoloop"]
        if self.auto.isChecked():
            args.append("--noconfirm")
        return args

    def _begin_repo_update(self, repo) -> None:
        self._reboot_names = safety.reboot_packages(
            [item["name"] for item in repo]
        )
        jobs = [(self._pacman_args(["pacman", "-Syu"]), True)]
        self._start_with_snapshot(jobs, after=self._finish_upgrade)

    def upgrade_all(self) -> None:
        if self.runner.running or self._preflighting:
            return
        repo = [item for item in self._updates if not item.get("aur")]
        aur = [item for item in self._updates if item.get("aur")]
        if not repo:
            if aur:
                self.notify(
                    "Solo hay actualizaciones de AUR",
                    "No se actualizará el AUR automáticamente. Pulsa «Revisar AUR».",
                    "info",
                )
            else:
                self.notify("Sin actualizaciones", "El sistema ya está al día.", "info")
            return

        self._preflight_updates = repo
        self._preflighting = True
        self._set_buttons_enabled(False)
        self.hero.title.setText("Revisando seguridad…")
        self.hero.text.setText(
            "Comprobando espacio, base de datos, keyring, snapshot y noticias."
        )
        proc.async_call(safety.preflight, self._on_preflight, repo, owner=self)

    def _on_preflight(self, checks) -> None:
        self._preflighting = False
        if isinstance(checks, proc.QueryError):
            self._set_buttons_enabled(True)
            self.notify("No se pudo revisar", str(checks), "danger")
            self._on_updates(self._updates)
            return
        fails = [check for check in checks if check.status == "fail"]
        warns = [check for check in checks if check.status == "warn"]
        items = [check.line() for check in checks]
        if fails:
            self._set_buttons_enabled(True)
            info(
                self,
                "Actualización bloqueada",
                "Se encontraron problemas críticos. No se ha modificado nada.",
                items=items,
                detail=(
                    "Corrige los avisos marcados con ✕ y vuelve a intentarlo. "
                    "Si no sabes cómo, revisa la consola o pide ayuda antes de forzar."
                ),
                danger=True,
            )
            self._on_updates(self._updates)
            return
        if warns:
            self._set_buttons_enabled(True)
            if not confirm(
                self,
                "Revisión completada con avisos",
                "Puedes continuar, pero revisa estos avisos:",
                items=items,
                detail="Se creará un snapshot antes de actualizar los repositorios.",
                confirm_text="Actualizar de forma segura",
                danger=False,
            ):
                self._on_updates(self._updates)
                return
        else:
            self.notify(
                "Comprobaciones superadas",
                "Creando snapshot y actualizando repositorios…",
                "success",
            )
        self._begin_repo_update(self._preflight_updates)

    def update_aur(self) -> None:
        if self.runner.running or self._preflighting:
            return
        aur = [item for item in self._updates if item.get("aur")]
        if not aur:
            self.notify("Sin AUR pendiente", "No hay paquetes de AUR por actualizar.", "info")
            return
        if not proc.which("paru"):
            self.notify(
                "paru no está instalado",
                "Instala paru para poder actualizar paquetes de AUR.",
                "warn",
            )
            return
        if safety.free_bytes() < 2 * 1024**3:
            self.notify(
                "Poco espacio",
                "Libera espacio antes de compilar paquetes de AUR.",
                "danger",
            )
            return

        listing = [
            f"{item['name']} · {item['old']} → {item['new']}" for item in aur
        ]
        risks = safety.aur_risks([item["name"] for item in aur])
        detail = (
            "Se creará un snapshot antes de continuar. "
            "Se omite la revisión de PKGBUILD (--skipreview)."
        )
        if risks:
            detail = "Riesgos detectados:\n" + "\n".join(risks) + "\n\n" + detail
        if not confirm(
            self,
            "Actualizar paquetes de AUR",
            "El AUR no es oficial. Revisa la lista antes de continuar:",
            items=listing,
            detail=detail,
            confirm_text="Actualizar AUR",
        ):
            return
        if not auth.ensure_sudo(
            self, "paru necesita permisos de administrador para actualizar el AUR."
        ):
            return

        self._reboot_names = safety.reboot_packages(
            [item["name"] for item in aur]
        )
        jobs = [(self._paru_args(["paru", "-Sua"]), False)]
        self._start_with_snapshot(jobs, after=self._finish_aur)

    def sync_databases(self) -> None:
        if self.runner.running or self._preflighting:
            return
        self._queue = []
        self._after_queue = None
        self._kind = "simple"
        self.runner.run(["pacman", "-Syy"], privileged=True)

    def reboot(self) -> None:
        if self._preflighting:
            return
        if confirm(
            self,
            "Reiniciar el sistema",
            "El equipo se reiniciará ahora mismo. Guarda tu trabajo antes de continuar.",
            confirm_text="Reiniciar",
        ):
            self._kind = "reboot"
            self.runner.run(["systemctl", "reboot"], privileged=True)

    def _start_with_snapshot(self, jobs, after=None) -> None:
        if self.runner.running:
            return
        self._snapshot_jobs = list(jobs)
        self._snapshot_after = after
        self._snapshot_id = 0
        self.console.clear()
        self.hero.title.setText("Creando snapshot de seguridad…")
        self.hero.text.setText("Se creará una instantánea antes de tocar el sistema.")
        self._kind = "snapshot"
        if not self.runner.run(
            [
                "snapper",
                "-c",
                "root",
                "create",
                "-p",
                "-d",
                "Núcleo: antes de actualizar",
            ],
            privileged=True,
        ):
            self._snapshot_jobs = []
            self._snapshot_after = None
            self.notify(
                "Sin snapshot",
                "Actualización cancelada: no se pudo iniciar el snapshot.",
                "danger",
            )
            self._on_updates(self._updates)

    def _start_queue(self, jobs, after=None) -> None:
        self._queue = list(jobs)
        self._after_queue = after
        self._run_next_job()

    def _run_next_job(self) -> None:
        if not self._queue:
            after = self._after_queue
            self._after_queue = None
            if after is not None:
                after()
            return
        argv, privileged = self._queue.pop(0)
        self._kind = "queue"
        if not self.runner.run(argv, privileged=privileged):
            self._queue = []
            self._after_queue = None
            self.notify(
                "No se pudo iniciar el comando",
                "Revisa la consola para ver el detalle.",
                "danger",
            )

    def _on_output(self, stream, text) -> None:
        self.console.append(text, stream)

    def _on_running(self, running) -> None:
        self.console.set_running(running)
        self.console.show_input(running and not self.auto.isChecked())
        self.btn_upgrade.setEnabled(not running)
        self.btn_sync.setEnabled(not running)
        self.btn_check.setEnabled(not running)
        self.auto.setEnabled(not running)
        self.btn_aur.setEnabled(
            not running and self._aur_count > 0 and proc.which("paru")
        )
        self.btn_upgrade.setText("Actualizando…" if running else "Actualizar sistema")

    def _on_finished(self, result) -> None:
        kind = self._kind
        self._kind = ""
        if kind == "snapshot":
            if result.ok:
                numbers = re.findall(r"\b(\d+)\b", result.stdout)
                self._snapshot_id = int(numbers[-1]) if numbers else 0
                jobs = self._snapshot_jobs
                after = self._snapshot_after
                self._snapshot_jobs = []
                self._snapshot_after = None
                if self._snapshot_id:
                    self.notify(
                        "Snapshot creado",
                        f"Instantánea {self._snapshot_id} lista por si hay que "
                        "volver atrás.",
                        "success",
                    )
                self.hero.title.setText("Actualizando…")
                self.hero.text.setText("No cierres la aplicación mientras se aplican los cambios.")
                self._start_queue(jobs, after=after)
            else:
                self._snapshot_jobs = []
                self._snapshot_after = None
                if not result.cancelled:
                    self.notify(
                        "No se pudo crear el snapshot",
                        "Actualización cancelada para no arriesgar el sistema. "
                        "Revisa la consola.",
                        "danger",
                    )
                self.load(force=True)
            return
        if kind == "queue":
            if result.ok:
                self._run_next_job()
                return
            self._queue = []
            self._after_queue = None
            if not result.cancelled:
                detail = f"Código de salida {result.code}. Revisa la consola."
                combined = result.combined.lower()
                if any(word in combined for word in ("signature", "pgp", "keyring")):
                    detail += (
                        " Parece un problema de firmas: actualiza "
                        "archlinux-keyring y cachyos-keyring antes de reintentar."
                    )
                if self._snapshot_id:
                    detail += (
                        f" Snapshot {self._snapshot_id} disponible por si "
                        "necesitas volver atrás."
                    )
                self.notify("La actualización falló", detail, "danger")
            self.load(force=True)
            return
        if kind == "simple":
            if result.ok:
                self.notify("Bases sincronizadas", "Listo.", "success")
                self.load(force=True)
            elif not result.cancelled:
                self.notify(
                    "No se pudo completar", f"Código {result.code}", "danger"
                )
            return
        if kind == "reboot" and not result.ok and not result.cancelled:
            self.notify(
                "No se pudo reiniciar", f"Código {result.code}", "danger"
            )

    def _show_reboot(self) -> None:
        names = self._reboot_names
        if not names:
            return
        listed = ", ".join(names[:6])
        if len(names) > 6:
            listed += f" y {len(names) - 6} más"
        self.btn_reboot.show()
        self.notify(
            "Reinicio recomendado",
            f"Se actualizaron {listed}. Reinicia para aplicar los cambios.",
            "warn",
        )
        self._reboot_names = []

    def _finish_upgrade(self) -> None:
        if self._reboot_names:
            self._show_reboot()
        else:
            self.notify("Sistema actualizado", "Proceso completado.", "success")
        self.load(force=True)
        self._ask_orphans()

    def _finish_aur(self) -> None:
        if self._reboot_names:
            self._show_reboot()
        else:
            self.notify(
                "AUR actualizado",
                "Si usas Caelestia/Quickshell, reinicia Hyprland o la sesión.",
                "success",
            )
        self.load(force=True)
        self._ask_orphans()

    def _ask_orphans(self) -> None:
        proc.async_call(queries.orphan_details, self._on_post_orphans, owner=self)

    def _on_post_orphans(self, items) -> None:
        if isinstance(items, proc.QueryError) or not items:
            self._ask_cache()
            return
        names = [item["name"] for item in items]
        size = sum(item["size"] for item in items)
        plural = "paquete huérfano" if len(names) == 1 else "paquetes huérfanos"
        listing = [
            f"{item['name']} · {human_bytes(item['size'])}" for item in items
        ]
        if confirm(
            self,
            "Eliminar dependencias huérfanas",
            f"La actualización dejó {len(names)} {plural} que ya no necesita "
            f"ningún paquete. Se pueden liberar ~{human_bytes(size)}.",
            items=listing,
            detail="Comando: sudo pacman -Rns --noconfirm <paquetes>",
            confirm_text="Eliminar huérfanas",
        ):
            self._removed_orphans = len(names)
            self._start_queue(
                [(["pacman", "-Rns", "--noconfirm", *names], True)],
                after=self._after_orphans,
            )
        else:
            self._ask_cache()

    def _after_orphans(self) -> None:
        self.notify(
            "Huérfanas eliminadas",
            f"{getattr(self, '_removed_orphans', 0)} paquetes eliminados.",
            "success",
        )
        self.load(force=True)
        self._ask_cache()

    def _ask_cache(self) -> None:
        proc.async_call(queries.cache_candidates, self._on_cache_candidates, owner=self)

    def _on_cache_candidates(self, payload) -> None:
        if isinstance(payload, proc.QueryError) or not payload.get("total"):
            return
        parts = []
        if payload["old"]:
            parts.append(f"{payload['old']} versiones antiguas")
        if payload["uninstalled"]:
            parts.append(f"{payload['uninstalled']} de paquetes desinstalados")
        commands = []
        if payload["old"]:
            commands.append((["paccache", "-rk2"], True))
        if payload["uninstalled"]:
            commands.append((["paccache", "-ruk0"], True))
        if not commands:
            return
        if not confirm(
            self,
            "Limpiar caché de paquetes",
            "Quedaron paquetes antiguos en la caché de pacman: "
            + " y ".join(parts)
            + f" (~{human_bytes(payload['bytes'])}). ¿Quieres limpiarla ahora?",
            detail=(
                "Se conservan las 2 últimas versiones de los paquetes instalados. "
                "Comandos: sudo paccache -rk2 y sudo paccache -ruk0"
            ),
            confirm_text="Limpiar caché",
            danger=False,
        ):
            return
        self._start_queue(commands, after=self._after_cache)

    def _after_cache(self) -> None:
        self.notify(
            "Caché limpiada",
            "Se eliminaron los paquetes antiguos y desinstalados.",
            "success",
        )
        self.load(force=True)
