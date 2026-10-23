from __future__ import annotations

import time

from PySide6.QtCore import (
    QDir,
    QObject,
    QProcess,
    QProcessEnvironment,
    QTimer,
    Signal,
)

from . import auth
from .proc import BASE_ENV
from .session import LogEntry, log

_ACTIVE: set = set()


class CommandResult:
    def __init__(self, argv, code, stdout, stderr, duration, cancelled=False, success=None):
        self.argv = list(argv)
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration
        self.cancelled = cancelled
        self._success = success

    @property
    def ok(self) -> bool:
        if self.cancelled:
            return False
        if self._success is None:
            return self.code == 0
        return self._success

    @property
    def command(self) -> str:
        return " ".join(self.argv)

    @property
    def combined(self) -> str:
        parts = [self.stdout]
        if self.stderr.strip():
            parts.append(self.stderr)
        return "".join(parts)


def _environment() -> QProcessEnvironment:
    env = QProcessEnvironment()
    for key, value in BASE_ENV.items():
        env.insert(key, value)
    return env


class CommandRunner(QObject):
    output = Signal(str, str)
    startedSignal = Signal(list)
    finishedSignal = Signal(object)
    runningChanged = Signal(bool)
    rejected = Signal()

    def __init__(self, parent=None, record=True, label=""):
        super().__init__(parent)
        self._proc = None
        self._argv: list = []
        self._chunks = {"stdout": [], "stderr": []}
        self._cancelled = False
        self._record = record
        self._label = label
        self._started_at = 0.0
        self._ok_codes: set = set()

    @property
    def running(self) -> bool:
        return self._proc is not None

    def run(self, argv, privileged=False, guard=True, ok_codes=(), echo=True) -> bool:
        if self.running:
            return False
        argv = [str(part) for part in argv]
        if not argv:
            return False

        if privileged and guard and not auth.is_root():
            if not auth.ensure_sudo(self.parent()):
                self.rejected.emit()
                return False

        full = argv
        if privileged and not auth.is_root():
            full = ["sudo", *argv]
        return self._start(full, ok_codes, echo)

    def _start(self, argv, ok_codes=(), echo=True) -> bool:
        proc = QProcess(self)
        proc.setProgram(argv[0])
        proc.setArguments(argv[1:])
        proc.setProcessChannelMode(QProcess.SeparateChannels)
        proc.setProcessEnvironment(_environment())
        proc.setWorkingDirectory(QDir.homePath())
        proc.readyReadStandardOutput.connect(lambda: self._read(proc, "stdout"))
        proc.readyReadStandardError.connect(lambda: self._read(proc, "stderr"))
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)

        self._proc = proc
        self._argv = argv
        self._chunks = {"stdout": [], "stderr": []}
        self._cancelled = False
        self._ok_codes = set(ok_codes)
        self._started_at = time.time()
        _ACTIVE.add(self)

        self.startedSignal.emit(argv)
        self.runningChanged.emit(True)
        if echo:
            self.output.emit("cmd", f"$ {self._display(argv)}\n")
        proc.start()
        return True

    @staticmethod
    def _display(argv) -> str:
        if argv and argv[0] == "sudo" and len(argv) > 1:
            return "sudo " + " ".join(argv[1:])
        return " ".join(argv)

    def _read(self, proc, stream: str) -> None:
        if proc is not self._proc:
            return
        try:
            data = (
                proc.readAllStandardOutput()
                if stream == "stdout"
                else proc.readAllStandardError()
            )
        except RuntimeError:
            return
        text = bytes(data).decode("utf-8", "replace")
        if not text:
            return
        self._chunks[stream].append(text)
        self.output.emit(stream, text)

    def _on_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._finalize(127, "no se pudo iniciar el proceso")

    def _on_finished(self, code, status) -> None:
        if self._proc is None:
            return
        self._read(self._proc, "stdout")
        self._read(self._proc, "stderr")
        self._finalize(code)

    def _finalize(self, code, extra="") -> None:
        proc = self._proc
        if proc is None:
            return
        self._proc = None
        _ACTIVE.discard(self)
        stdout = "".join(self._chunks["stdout"])
        stderr = "".join(self._chunks["stderr"]) + extra
        duration = max(0.0, time.time() - self._started_at)
        success = (code == 0) or (code in self._ok_codes)
        result = CommandResult(
            self._argv, code, stdout, stderr, duration, self._cancelled, success
        )
        if self._record:
            log.add(
                LogEntry(
                    self._argv,
                    code,
                    duration,
                    stdout,
                    stderr,
                    self._label,
                    self._cancelled,
                )
            )
        if self._cancelled:
            self.output.emit("sys", "— operación cancelada —\n")
        elif result.ok:
            self.output.emit("ok", f"✓ completado en {duration:.1f}s\n\n")
        else:
            self.output.emit("err", f"✕ terminó con código {code}\n\n")
        self.runningChanged.emit(False)
        self.finishedSignal.emit(result)
        try:
            proc.deleteLater()
        except RuntimeError:
            pass

    def send_input(self, text: str) -> bool:
        proc = self._proc
        if proc is None:
            return False
        try:
            proc.write((text + "\n").encode())
        except RuntimeError:
            return False
        self.output.emit("sys", f"› {text}\n")
        return True

    def cancel(self, force=False) -> None:
        proc = self._proc
        if proc is None:
            return
        self._cancelled = True
        try:
            if force:
                proc.kill()
            else:
                proc.terminate()
                QTimer.singleShot(3000, lambda p=proc: self._force(p))
        except RuntimeError:
            pass

    def _force(self, proc) -> None:
        try:
            if proc is self._proc and proc.state() != QProcess.ProcessState.NotRunning:
                proc.kill()
        except RuntimeError:
            pass


def shutdown_all() -> None:
    for runner in list(_ACTIVE):
        runner.cancel(force=True)


class Step:
    def __init__(self, label, argv, privileged=False):
        self.label = label
        self.argv = argv
        self.privileged = privileged


class SequenceRunner(QObject):
    stepState = Signal(int, str)
    output = Signal(str, str)
    finishedSequence = Signal(bool)
    runningChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps: list = []
        self._index = -1
        self._runner = None
        self._ok = True
        self._stop_on_error = True

    @property
    def running(self) -> bool:
        return self._runner is not None

    def start(self, steps, stop_on_error=True) -> bool:
        if self.running or not steps:
            return False
        if any(step.privileged for step in steps):
            if not auth.ensure_sudo(self.parent()):
                return False
        self._steps = list(steps)
        self._index = -1
        self._ok = True
        self._stop_on_error = stop_on_error
        runner = CommandRunner(self, record=True, label="secuencia")
        runner.output.connect(self.output)
        runner.finishedSignal.connect(self._advance)
        self._runner = runner
        self.runningChanged.emit(True)
        self._next()
        return True

    def _next(self) -> None:
        self._index += 1
        if self._index >= len(self._steps):
            self._finish(self._ok)
            return
        step = self._steps[self._index]
        self.stepState.emit(self._index, "running")
        self.output.emit("sys", f"\n▸ {step.label}\n")
        if not self._runner.run(step.argv, privileged=step.privileged, guard=False):
            self.stepState.emit(self._index, "error")
            self._ok = False
            self._finish(False)

    def _advance(self, result) -> None:
        if not (0 <= self._index < len(self._steps)):
            return
        if result.ok:
            self.stepState.emit(self._index, "ok")
            self._next()
            return
        if result.cancelled:
            self.stepState.emit(self._index, "cancelled")
        else:
            self.stepState.emit(self._index, "error")
        self._ok = False
        if self._stop_on_error:
            self._finish(False)
        else:
            self._next()

    def _finish(self, success) -> None:
        self._runner = None
        self.runningChanged.emit(False)
        self.finishedSequence.emit(success)

    def cancel(self) -> None:
        if self._runner:
            self._runner.cancel()
