from __future__ import annotations

import os
import platform
import time

from .proc import run_sync
from .util import parse_human_size


def _read(path: str, default: str = "") -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return default


def os_release() -> dict:
    data = {}
    for line in _read("/etc/os-release").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"')
    return data


def os_name() -> str:
    info = os_release()
    return info.get("PRETTY_NAME") or info.get("NAME") or "Linux"


def kernel() -> str:
    return platform.release()


def hostname() -> str:
    return platform.node() or "equipo"


def uptime_seconds() -> float:
    try:
        return float(_read("/proc/uptime").split()[0])
    except (IndexError, ValueError):
        return 0.0


def memory() -> tuple[int, int]:
    total = available = 0
    for line in _read("/proc/meminfo").splitlines():
        if line.startswith("MemTotal:"):
            total = int(line.split()[1]) * 1024
        elif line.startswith("MemAvailable:"):
            available = int(line.split()[1]) * 1024
    return total, available


def cpu_model() -> str:
    for line in _read("/proc/cpuinfo").splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor() or "CPU"


def cpu_cores() -> int:
    return os.cpu_count() or 1


def desktop() -> str:
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "Hyprland"
    value = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION")
    return value or "—"


def load_average() -> tuple[float, float, float]:
    try:
        parts = _read("/proc/loadavg").split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except (IndexError, ValueError):
        return 0.0, 0.0, 0.0


def cpu_temp() -> float | None:
    base = "/sys/class/thermal"
    try:
        for zone in sorted(os.listdir(base)):
            if not zone.startswith("thermal_zone"):
                continue
            raw = _read(f"{base}/{zone}/temp").strip()
            if raw:
                value = int(raw) / 1000.0
                if 0 < value < 150:
                    return value
    except OSError:
        pass
    return None


def disk_usage(path: str = "/") -> dict:
    try:
        stat = os.statvfs(path)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - stat.f_bfree * stat.f_frsize
        percent = (used / total * 100) if total else 0.0
        return {
            "total": total,
            "used": used,
            "free": free,
            "percent": percent,
            "path": path,
        }
    except OSError:
        return {"total": 0, "used": 0, "free": 0, "percent": 0.0, "path": path}


def filesystem_type(path: str = "/") -> str:
    code, out, _ = run_sync(["findmnt", "-no", "FSTYPE", path], timeout=5)
    return out.strip() if code == 0 else ""


def journal_usage() -> int:
    code, out, _ = run_sync(["journalctl", "--disk-usage"], timeout=15)
    if code != 0:
        return 0
    return parse_human_size(out)


def pacman_log_size() -> int:
    try:
        return os.path.getsize("/var/log/pacman.log")
    except OSError:
        return 0


def now() -> float:
    return time.time()
