from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal

MAX_ENTRIES = 200
MAX_OUTPUT = 120_000


class LogEntry:
    def __init__(self, argv, code, duration, stdout, stderr, label="", cancelled=False):
        self.time = time.time()
        self.argv = list(argv)
        self.code = code
        self.duration = duration
        self.stdout = stdout[-MAX_OUTPUT:]
        self.stderr = stderr[-MAX_OUTPUT:]
        self.label = label
        self.cancelled = cancelled

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.cancelled

    @property
    def command(self) -> str:
        return " ".join(self.argv)


class SessionLog(QObject):
    appended = Signal(object)
    cleared = Signal()

    def __init__(self):
        super().__init__()
        self._entries: list[LogEntry] = []

    @property
    def entries(self) -> list[LogEntry]:
        return self._entries

    def add(self, entry: LogEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > MAX_ENTRIES:
            del self._entries[0 : len(self._entries) - MAX_ENTRIES]
        self.appended.emit(entry)

    def clear(self) -> None:
        self._entries.clear()
        self.cleared.emit()


log = SessionLog()
