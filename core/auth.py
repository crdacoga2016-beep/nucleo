from __future__ import annotations

import os

from .proc import run_sync, which

_password: str | None = None


def sudo_available() -> bool:
    return which("sudo")


def is_root() -> bool:
    return os.geteuid() == 0


def sudo_cached() -> bool:
    if is_root():
        return True
    if not sudo_available():
        return False
    return run_sync(["sudo", "-n", "true"], timeout=8)[0] == 0


def verify_password(password: str) -> bool:
    code, _, _ = run_sync(
        ["sudo", "-S", "-p", "", "true"],
        timeout=20,
        input_text=password + "\n",
    )
    return code == 0


def forget() -> None:
    global _password
    _password = None


def ensure_sudo(parent, reason: str = "", interactive: bool = True) -> bool:
    global _password
    if sudo_cached():
        return True
    if not sudo_available():
        return False
    if _password and verify_password(_password):
        return True
    _password = None
    if not interactive:
        return False

    from ui.components.dialogs import password_dialog

    error = ""
    for _ in range(3):
        result = password_dialog(parent, reason, error)
        if result is None:
            return False
        password, remember = result
        if verify_password(password):
            if remember:
                _password = password
            return True
        error = "Contraseña incorrecta. Inténtalo de nuevo."
    return False
