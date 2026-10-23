from __future__ import annotations

import time

from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit

from core import proc, queries, runner, system
from core.util import human_date
from ui.components.dialogs import confirm, info
from ui.components.widgets import (
    Card,
    GhostButton,
    Hero,
    KVList,
    PrimaryButton,
)
from ui.pages.common import Page, console_view
from ui.responsive import ResponsiveGrid

MIRRORLIST = "/etc/pacman.d/mirrorlist"


class MirrorsPage(Page):
    key = "mirrors"
    title = "Espejos y repositorios"
    subtitle = "Consulta los servidores configurados y optimiza la mirrorlist con reflector."

    def __init__(self, window):
        super().__init__(window, scroll=True)
        self._queue: list = []
        self._info = {}

        self.hero = Hero(
            "Espejos de descarga",
            "Unos buenos espejos aceleran las actualizaciones y reducen errores.",
            icon_name="globe",
        )
        self.btn_sync = GhostButton("Sincronizar bases (-Syy)")
        self.btn_sync.setToolTip(
            "Fuerza la descarga de las bases de datos de pacman."
        )
        self.hero.add_action(self.btn_sync)
        self.content.addWidget(self.hero)

        status = Card(title="Configuración actual", icon_name="info")
        self.details = KVList()
        status.body.addWidget(self.details)
        self.content.addWidget(status)

        if not proc.which("reflector"):
            warning = Card(
                title="reflector no está instalado",
                subtitle="Instálalo con: sudo pacman -S reflector",
                icon_name="warning",
                danger=True,
            )
            self.content.addWidget(warning)
            self.reflector_available = False
        else:
            self.reflector_available = True
            self.content.addWidget(self._reflector_card())
        self.content.addStretch()
        self.console = console_view("Salida de reflector / pacman", interactive=False)
        self.content.addWidget(self.console)

        self.runner = runner.CommandRunner(self, label="espejos")
        self.runner.output.connect(lambda s, t: self.console.append(t, s))
        self.runner.runningChanged.connect(self.console.set_running)
        self.runner.finishedSignal.connect(self._on_finished)
        self.console.stop_btn.clicked.connect(lambda: self.runner.cancel())

        self.btn_sync.clicked.connect(
            lambda: self.runner.run(["pacman", "-Syy"], privileged=True)
        )
        self.load()

    def _reflector_card(self) -> Card:
        card = Card(
            title="Optimizar con reflector",
            subtitle="Genera una mirrorlist filtrada y ordenada por velocidad o frescura.",
            icon_name="sparkles",
        )
        grid_rows = [
            ("País (código o nombre, separado por comas)", self._country_field()),
            ("Protocolo", self._protocol_field()),
            ("Número de espejos", self._number_field()),
            ("Edad máxima", self._age_field()),
            ("Ordenar por", self._sort_field()),
        ]
        grid = ResponsiveGrid(min_column=230, spacing=12)
        for label_text, field in grid_rows:
            grid.addWidget(self._field(label_text, field))
        card.body.addWidget(grid)

        self.backup = QCheckBox("Guardar copia de seguridad de la mirrorlist actual")
        self.backup.setChecked(True)
        self.backup.setToolTip(
            "Guarda /etc/pacman.d/mirrorlist como mirrorlist.bak-AAAAAMMDD-HHMMSS "
            "antes de reescribirla."
        )
        card.body.addWidget(self.backup)

        self.preview = QLabel("")
        self.preview.setObjectName("Faint")
        self.preview.setWordWrap(True)
        card.body.addWidget(self.preview)

        row = QHBoxLayout()
        row.addStretch()
        self.btn_optimize = PrimaryButton("Optimizar espejos")
        self.btn_optimize.setToolTip(
            "Ejecuta reflector y reescribe /etc/pacman.d/mirrorlist con los "
            "mejores servidores según los filtros elegidos."
        )
        row.addWidget(self.btn_optimize)
        card.body.addLayout(row)
        self.btn_optimize.clicked.connect(self._optimize)
        self._update_preview()
        return card

    @staticmethod
    def _field(label, field):
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        text = QLabel(label)
        text.setObjectName("Soft")
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addWidget(field)
        return box

    def _country_field(self) -> QLineEdit:
        self.country = QLineEdit()
        self.country.setPlaceholderText("vacío = todos · ej: Spain, France, Germany")
        self.country.setToolTip(
            "Códigos o nombres de país separados por comas. Vacío = todos."
        )
        self.country.textChanged.connect(self._update_preview)
        return self.country

    def _protocol_field(self) -> QComboBox:
        self.protocol = QComboBox()
        self.protocol.addItems(["https", "https,http", "http,https", "any"])
        self.protocol.setToolTip("Protocolos permitidos para los espejos.")
        self.protocol.currentIndexChanged.connect(self._update_preview)
        return self.protocol

    def _number_field(self) -> QComboBox:
        self.number = QComboBox()
        self.number.addItems(["5", "10", "15", "20"])
        self.number.setCurrentIndex(1)
        self.number.setToolTip("Número máximo de espejos que se guardarán.")
        self.number.currentIndexChanged.connect(self._update_preview)
        return self.number

    def _age_field(self) -> QComboBox:
        self.age = QComboBox()
        self.age.addItems(["6 horas", "12 horas", "24 horas", "48 horas"])
        self.age.setCurrentIndex(1)
        self.age.setToolTip("Antigüedad máxima de la última sincronización del espejo.")
        self.age.currentIndexChanged.connect(self._update_preview)
        return self.age

    def _sort_field(self) -> QComboBox:
        self.sort = QComboBox()
        self.sort.addItems(["Velocidad de descarga", "Frescura"])
        self.sort.setToolTip(
            "Ordenar por velocidad (rate) o por frescura (age)."
        )
        self.sort.currentIndexChanged.connect(self._update_preview)
        return self.sort

    def _reflector_args(self) -> list:
        args = ["reflector", "--latest", self.number.currentText()]
        age = self.age.currentText().split()[0]
        args += ["--age", age, "--protocol", self.protocol.currentText()]
        if self.sort.currentIndex() == 0:
            args += ["--sort", "rate", "--connection-timeout", "4", "--download-timeout", "10"]
        else:
            args += ["--sort", "age"]
        country = self.country.text().strip()
        if country:
            args += ["--country", country]
        args += ["--save", MIRRORLIST]
        return args

    def _update_preview(self) -> None:
        if hasattr(self, "preview"):
            self.preview.setText("Comando: sudo " + " ".join(self._reflector_args()))

    def load(self) -> None:
        proc.async_call(queries.mirrorlist_info, self._on_info, owner=self)

    def _on_info(self, payload) -> None:
        if isinstance(payload, proc.QueryError):
            return
        self._info = payload
        self.details.clear()
        self.details.add("Servidores activos", str(payload["count"]))
        self.details.add("Actualizado", human_date(payload["mtime"]) if payload["mtime"] else "—")
        self.details.add("Sistema de archivos", system.filesystem_type("/"))
        for index, host in enumerate(payload["hosts"], start=1):
            self.details.add(f"Espejo {index}", host)

    def _optimize(self) -> None:
        commands = []
        if self.backup.isChecked():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            commands.append(
                (["cp", MIRRORLIST, f"{MIRRORLIST}.bak-{stamp}"], True)
            )
        commands.append((self._reflector_args(), True))
        if not confirm(
            self,
            "Optimizar espejos",
            "Se consultará la lista de espejos de Arch y se reescribirá la mirrorlist. "
            "Puede tardar un par de minutos si se ordena por velocidad.",
            detail="Comando: sudo " + " ".join(self._reflector_args()),
            confirm_text="Optimizar",
            danger=False,
        ):
            return
        self._queue = commands
        self._run_next()

    def _run_next(self) -> None:
        if not self._queue:
            return
        argv, privileged = self._queue.pop(0)
        self.runner.run(argv, privileged=privileged)

    def _on_finished(self, result) -> None:
        if not result.ok and not result.cancelled:
            self._queue = []
            self.notify("reflector falló", f"Código {result.code}", "danger")
            return
        if self._queue:
            self._run_next()
            return
        if result.ok:
            self.notify("Espejos optimizados", "Ejecuta 'Sincronizar bases' ahora.", "success")
            self.load()
