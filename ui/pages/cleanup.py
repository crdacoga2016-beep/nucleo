from __future__ import annotations

import os
import shutil

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel

from core import proc, queries, runner, system
from core.util import human_bytes
from ui.components.dialogs import confirm, info
from ui.components.widgets import (
    Badge,
    Card,
    DangerButton,
    GhostButton,
    PrimaryButton,
)
from ui.pages.common import Page, console_view
from ui.responsive import ResponsiveGrid

TRASH = os.path.expanduser("~/.local/share/Trash")
THUMBS = os.path.expanduser("~/.cache/thumbnails")
USER_CACHE = os.path.expanduser("~/.cache")
PACMAN_LOG = "/var/log/pacman.log"
LOG_LIMIT = 200 * 1024 * 1024


def dir_bytes(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def clear_dir(path: str) -> int:
    if not os.path.isdir(path):
        return 0
    freed = 0
    for name in os.listdir(path):
        target = os.path.join(path, name)
        try:
            if os.path.islink(target) or os.path.isfile(target):
                freed += os.path.getsize(target)
                os.unlink(target)
            else:
                freed += dir_bytes(target)
                shutil.rmtree(target, ignore_errors=True)
        except OSError:
            pass
    return freed


class CleanerCard(Card):
    def __init__(self, title, subtitle, icon_name, button_text, danger=False):
        super().__init__(title=title, subtitle=subtitle, icon_name=icon_name, danger=danger)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.size = QLabel("…")
        self.size.setObjectName("Soft")
        row.addWidget(self.size)
        row.addStretch()
        self.button = DangerButton(button_text) if danger else GhostButton(button_text)
        row.addWidget(self.button)
        self.body.addLayout(row)

    def set_size(self, text: str) -> None:
        self.size.setText(text)


class CleanupPage(Page):
    key = "cleanup"
    title = "Limpieza"
    subtitle = "Libera espacio eliminando cachés temporales, registros antiguos y papelera."

    def __init__(self, window):
        super().__init__(window, scroll=True)
        self._loaded = False
        self._pending_log_trim = None

        refresh = GhostButton("Recalcular tamaños")
        refresh.setToolTip("Vuelve a medir cuánto ocupa cada categoría.")
        refresh.clicked.connect(self.load)
        self.header.add_action(refresh)

        self.card_trash = CleanerCard(
            "Papelera",
            "Elementos eliminados que aún ocupan espacio.",
            "broom",
            "Vaciar papelera",
            danger=True,
        )
        self.card_thumbs = CleanerCard(
            "Miniaturas",
            "Caché de miniaturas regenerable de ~/.cache/thumbnails.",
            "eye",
            "Eliminar miniaturas",
        )
        self.card_cache = CleanerCard(
            "Caché de usuario",
            "Contenido de ~/.cache. Se regenera solo, aunque algunas apps pueden ir más lentas la primera vez.",
            "database",
            "Limpiar ~/.cache",
            danger=True,
        )
        self.card_log = CleanerCard(
            "Registro de pacman",
            "Conserva lo más reciente y recorta el archivo si supera los 200 MB.",
            "terminal",
            "Recortar registro",
        )
        self.card_journal = CleanerCard(
            "Registros del sistema (journald)",
            "Elimina registros anteriores al periodo elegido.",
            "clock",
            "Limpiar journal",
        )
        self.journal_days = QComboBox()
        self.journal_days.addItems(["7 días", "14 días", "30 días", "90 días"])
        self.journal_days.setCurrentIndex(1)
        self.journal_days.setToolTip("Periodo de registros que se conservará.")
        self.card_journal.body.addWidget(self.journal_days)

        self.card_paccache = CleanerCard(
            "Caché de paquetes",
            "Conserva las 2 últimas versiones descargadas.",
            "box",
            "paccache -rk2",
        )
        self.card_paccache.button.setObjectName("Primary")

        grid = ResponsiveGrid(min_column=300, spacing=14)
        cards = [
            self.card_trash,
            self.card_thumbs,
            self.card_cache,
            self.card_log,
            self.card_journal,
            self.card_paccache,
        ]
        self.card_trash.button.setToolTip(
            "Elimina definitivamente todos los elementos de la papelera."
        )
        self.card_thumbs.button.setToolTip(
            "Borra la caché de miniaturas; se regenerará automáticamente."
        )
        self.card_cache.button.setToolTip(
            "Vacía ~/.cache. Las aplicaciones lo reconstruirán, pero pueden "
            "tardar más la primera vez."
        )
        self.card_log.button.setToolTip(
            "Solo se activa si /var/log/pacman.log supera 200 MB."
        )
        self.card_journal.button.setToolTip(
            "Elimina registros de systemd más antiguos que el periodo elegido."
        )
        self.card_paccache.button.setToolTip(
            "Conserva las 2 últimas versiones de cada paquete instalado."
        )
        for card in cards:
            grid.addWidget(card)
        self.content.addWidget(grid)
        self.content.addStretch()

        self.console = console_view("Salida")
        self.content.addWidget(self.console)

        self.runner = runner.CommandRunner(self, label="limpieza")
        self.runner.output.connect(lambda s, t: self.console.append(t, s))
        self.runner.runningChanged.connect(self.console.set_running)
        self.runner.finishedSignal.connect(self._on_finished)
        self.console.stop_btn.clicked.connect(lambda: self.runner.cancel())

        self.card_trash.button.clicked.connect(self._trash)
        self.card_thumbs.button.clicked.connect(lambda: self._clear(THUMBS, "Miniaturas"))
        self.card_cache.button.clicked.connect(self._user_cache)
        self.card_log.button.clicked.connect(self._trim_log)
        self.card_journal.button.clicked.connect(self._journal)
        self.card_paccache.button.clicked.connect(
            lambda: self.runner.run(["paccache", "-rk2"], privileged=True)
        )

    def on_show(self) -> None:
        if not self._loaded:
            self._loaded = True
            self.load()

    def load(self) -> None:
        proc.async_call(self._sizes, self._on_sizes, owner=self)

    @staticmethod
    def _sizes() -> dict:
        return {
            "trash": queries.trash_size(),
            "thumbs": queries.thumbnail_size(),
            "cache": queries.user_cache_size(),
            "journal": system.journal_usage(),
            "log": system.pacman_log_size(),
            "pkgcache": queries.cache_stats()["total"],
        }

    def _on_sizes(self, sizes) -> None:
        if isinstance(sizes, proc.QueryError):
            return
        self.card_trash.set_size(human_bytes(sizes["trash"]) + " en papelera")
        self.card_thumbs.set_size(human_bytes(sizes["thumbs"]))
        self.card_cache.set_size(human_bytes(sizes["cache"]))
        self.card_journal.set_size(human_bytes(sizes["journal"]) + " en journald")
        self.card_log.set_size(human_bytes(sizes["log"]))
        self.card_paccache.set_size(human_bytes(sizes["pkgcache"]) + " en caché")
        self.card_log.button.setEnabled(sizes["log"] > LOG_LIMIT)

    def _run_clear(self, path, label, freed_cb=None) -> None:
        def work():
            return clear_dir(path)

        def done(freed):
            if isinstance(freed, proc.QueryError):
                self.notify("No se pudo limpiar", str(freed), "danger")
                return
            self.notify(label, f"Liberados {human_bytes(freed)}", "success")
            self.load()

        proc.async_call(work, done, owner=self)

    def _trash(self) -> None:
        if not confirm(
            self,
            "Vaciar la papelera",
            "Se eliminarán definitivamente todos los elementos de la papelera.",
            confirm_text="Vaciar",
        ):
            return
        self._run_clear(TRASH, "Papelera vaciada")

    def _clear(self, path, label) -> None:
        if not confirm(
            self,
            f"Eliminar {label.lower()}",
            f"Se eliminará el contenido de {path}.",
            confirm_text="Eliminar",
        ):
            return
        self._run_clear(path, label)

    def _user_cache(self) -> None:
        if not confirm(
            self,
            "Limpiar la caché de usuario",
            "Se eliminará todo el contenido de ~/.cache. Las aplicaciones "
            "lo reconstruirán, pero pueden tardar un poco más la próxima vez.",
            confirm_text="Limpiar",
        ):
            return
        self._run_clear(USER_CACHE, "Caché de usuario limpiada")

    def _journal(self) -> None:
        days = self.journal_days.currentText().split()[0]
        self.runner.run(
            ["journalctl", f"--vacuum-time={days}d"], privileged=True
        )

    def _trim_log(self) -> None:
        size = system.pacman_log_size()
        if size <= LOG_LIMIT:
            info(
                self,
                "Sin cambios necesarios",
                f"El registro ocupa {human_bytes(size)}, por debajo del límite de 200 MB.",
            )
            return
        if not confirm(
            self,
            "Recortar /var/log/pacman.log",
            f"El registro ocupa {human_bytes(size)}. Se conservarán "
            "aproximadamente los últimos 200 MB.",
            confirm_text="Recortar",
        ):
            return

        def work():
            with open(PACMAN_LOG, "rb") as handle:
                handle.seek(size - LOG_LIMIT)
                handle.readline()
                data = handle.read()
            tmp = "/tmp/nucleo-pacman.log"
            with open(tmp, "wb") as handle:
                handle.write(data)
            return tmp

        def done(result):
            if isinstance(result, proc.QueryError):
                self.notify("No se pudo recortar", str(result), "danger")
                return
            self._pending_log_trim = result
            self.runner.run(["cp", result, PACMAN_LOG], privileged=True)

        proc.async_call(work, done, owner=self)

    def _on_finished(self, result) -> None:
        if self._pending_log_trim:
            try:
                os.unlink(self._pending_log_trim)
            except OSError:
                pass
            self._pending_log_trim = None
        if result.ok:
            self.notify("Limpieza completada", "Operación realizada.", "success")
            self.load()
        elif not result.cancelled:
            self.notify("No se pudo completar", f"Código {result.code}", "danger")
