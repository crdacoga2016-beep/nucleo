from __future__ import annotations

import os
import shutil
import subprocess

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

BASE_ENV = {**os.environ, "LC_ALL": "C", "LANG": "C", "LANGUAGE": "C"}
BASE_ENV.pop("PACMAN_COLOR", None)

_pending: set = set()
_pool = QThreadPool.globalInstance()
_pool.setMaxThreadCount(max(4, _pool.maxThreadCount()))

try:
    import shiboken6
except Exception:
    shiboken6 = None


def _alive(owner) -> bool:
    if owner is None or shiboken6 is None:
        return True
    try:
        return shiboken6.isValid(owner)
    except Exception:
        return True


class QueryError(Exception):
    pass


class _Signals(QObject):
    done = Signal(object)


class _Task(QRunnable):
    def __init__(self, fn, args, kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.sig = _Signals()

    def run(self):
        try:
            payload = ("ok", self.fn(*self.args, **self.kwargs))
        except Exception as exc:
            payload = ("err", exc)
        try:
            self.sig.done.emit(payload)
        except RuntimeError:
            pass


def async_call(fn, callback, *args, owner=None, **kwargs) -> None:
    task = _Task(fn, args, kwargs)
    _pending.add(task)

    def _done(payload):
        _pending.discard(task)
        if not _alive(owner):
            return
        if payload[0] == "err":
            callback(QueryError(str(payload[1])))
        else:
            callback(payload[1])

    task.sig.done.connect(_done)
    _pool.start(task)


def run_sync(argv, timeout=30, input_text=None, env=None):
    try:
        proc = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            errors="replace",
            input=input_text,
            timeout=timeout,
            env=env or BASE_ENV,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "orden no encontrada"
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        return 124, out, "tiempo de espera agotado"


def which(name: str) -> bool:
    return shutil.which(name) is not None
