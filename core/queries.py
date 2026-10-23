from __future__ import annotations

import csv
import io
import os
import re
import threading
import time
from urllib.parse import urlparse

from .proc import run_sync, which
from .util import parse_human_size


def _parse_update_lines(out: str, aur: bool) -> list[dict]:
    updates = []
    for line in out.splitlines():
        line = line.strip()
        if not line or " -> " not in line or line.endswith("[ignored]"):
            continue
        left, new = line.rsplit(" -> ", 1)
        parts = left.split()
        if len(parts) < 2:
            continue
        updates.append(
            {
                "name": parts[0],
                "old": " ".join(parts[1:]),
                "new": new.strip(),
                "aur": aur,
                "source": "aur" if aur else "repo",
            }
        )
    return updates


def pending_updates() -> list[dict]:
    if not which("checkupdates"):
        return []
    code, out, _ = run_sync(["checkupdates"], timeout=240)
    return _parse_update_lines(out, False)


def aur_updates() -> list[dict]:
    if not which("paru"):
        return []
    code, out, err = run_sync(["paru", "-Qua", "--devel"], timeout=240)
    if code not in (0, 1):
        return []
    return _parse_update_lines(out, True)


_updates_lock = threading.Lock()
_updates_cache_time = 0.0
_updates_cache: list[dict] = []
_UPDATES_CACHE_SECONDS = 5.0


def all_updates(force: bool = False) -> list[dict]:
    global _updates_cache_time, _updates_cache
    with _updates_lock:
        if not force and time.time() - _updates_cache_time < _UPDATES_CACHE_SECONDS:
            return [dict(item) for item in _updates_cache]
        updates = pending_updates() + aur_updates()
        updates.sort(key=lambda item: (item["aur"], item["name"].lower()))
        _updates_cache = [dict(item) for item in updates]
        _updates_cache_time = time.time()
        return [dict(item) for item in updates]


def cache_candidates(keep: int = 2) -> dict:
    result = {"old": 0, "uninstalled": 0, "total": 0, "bytes": 0}
    if not which("paccache"):
        return result

    def probe(args) -> tuple[int, int]:
        code, out, _ = run_sync(["paccache", *args], timeout=90)
        text = out.replace("\n", " ")
        count = re.search(r"(\d+)\s+candidates?", text)
        saved = re.search(
            r"disk space saved:\s*([\d.,]+)\s*([KMGT]?i?B)", text, re.IGNORECASE
        )
        return (
            int(count.group(1)) if count else 0,
            parse_human_size(saved.group(0)) if saved else 0,
        )

    result["old"], old_bytes = probe([f"-dk{keep}"])
    result["uninstalled"], uninstalled_bytes = probe(["-duk0"])
    result["total"] = result["old"] + result["uninstalled"]
    result["bytes"] = old_bytes + uninstalled_bytes
    return result


def orphans() -> list[str]:
    code, out, _ = run_sync(["pacman", "-Qdtq"], timeout=30)
    if code not in (0, 1):
        return []
    return sorted(line.strip() for line in out.splitlines() if line.strip())


def installed_info() -> dict[str, dict]:
    code, out, _ = run_sync(["pacman", "-Qi"], timeout=90)
    if code != 0:
        return {}
    info: dict[str, dict] = {}
    for block in out.split("\n\n"):
        if not block.strip():
            continue
        fields = {}
        for line in block.splitlines():
            if not line or line.startswith(" "):
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
        name = fields.get("Name")
        if not name:
            continue
        required = fields.get("Required By", "")
        optional = fields.get("Optional For", "")
        info[name] = {
            "name": name,
            "version": fields.get("Version", ""),
            "description": fields.get("Description", ""),
            "size": parse_human_size(fields.get("Installed Size", "0")),
            "reason": fields.get("Install Reason", ""),
            "required_by": [] if required in ("", "None") else required.split(),
            "optional_for": [] if optional in ("", "None") else optional.split(),
            "repository": fields.get("Repository")
            or fields.get("Installed From", ""),
            "install_date": fields.get("Install Date", ""),
            "packager": fields.get("Packager", ""),
            "url": fields.get("URL", ""),
            "licenses": fields.get("Licenses", ""),
            "depends": []
            if fields.get("Depends On", "") in ("", "None")
            else fields.get("Depends On", "").split(),
        }
    return info


def aur_packages() -> set[str]:
    if not which("paru"):
        return set()
    code, out, _ = run_sync(["paru", "-Qm"], timeout=30)
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if parts:
            names.add(parts[0])
    return names


def installed_packages() -> list[dict]:
    code, out, _ = run_sync(["pacman", "-Q"], timeout=45)
    if code != 0:
        return []
    info = installed_info()
    aur = aur_packages()
    packages = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, version = parts[0], parts[1]
        meta = info.get(name, {})
        reason = meta.get("reason", "")
        packages.append(
            {
                "name": name,
                "version": version,
                "size": meta.get("size", 0),
                "description": meta.get("description", ""),
                "reason": reason,
                "explicit": reason.startswith("Explicitly"),
                "required_by": meta.get("required_by", []),
                "optional_for": meta.get("optional_for", []),
                "repository": "aur" if name in aur else meta.get("repository", ""),
                "install_date": meta.get("install_date", ""),
                "url": meta.get("url", ""),
                "licenses": meta.get("licenses", ""),
                "depends": meta.get("depends", []),
            }
        )
    packages.sort(key=lambda item: item["name"].lower())
    return packages


def package_counts() -> dict:
    def count(argv) -> int:
        code, out, _ = run_sync(argv, timeout=45)
        if code != 0:
            return 0
        return len([line for line in out.splitlines() if line.strip()])

    total = count(["pacman", "-Q"])
    explicit = count(["pacman", "-Qe"])
    foreign = count(["paru", "-Qm"]) if which("paru") else 0
    return {"total": total, "explicit": explicit, "foreign": foreign}


def orphan_details(names=None) -> list[dict]:
    names = orphans() if names is None else names
    if not names:
        return []
    info = installed_info()
    result = []
    for name in names:
        meta = info.get(name, {})
        result.append(
            {
                "name": name,
                "version": meta.get("version", ""),
                "size": meta.get("size", 0),
                "description": meta.get("description", ""),
            }
        )
    return result


def search_remote(pattern: str, include_aur=False) -> tuple[list[dict], str]:
    pattern = pattern.strip()
    if not pattern:
        return [], ""
    if include_aur and which("paru"):
        code, out, err = run_sync(["paru", "-Ss", pattern], timeout=180)
    else:
        code, out, err = run_sync(["pacman", "-Ss", pattern], timeout=120)
    if code not in (0, 1):
        return [], (err.strip() or "la búsqueda falló")
    results = []
    current = None
    for line in out.splitlines():
        if not line.strip():
            current = None
            continue
        if line.startswith(" "):
            if current is not None:
                extra = line.strip()
                if extra:
                    current["description"] = (
                        current["description"] + " " + extra
                    ).strip()
            continue
        fields = line.split()
        head = fields[0]
        if "/" not in head or len(fields) < 2:
            current = None
            continue
        repo, name = head.split("/", 1)
        current = {
            "repo": repo,
            "name": name,
            "version": fields[1],
            "installed": "[installed]" in line or "[instalado]" in line,
            "description": "",
        }
        results.append(current)
    return results, ""


def cache_files() -> list[dict]:
    path = "/var/cache/pacman/pkg"
    if not os.path.isdir(path):
        return []
    code, out, _ = run_sync(
        ["find", path, "-maxdepth", "1", "-type", "f", "-printf", "%s\t%T@\t%p\n"],
        timeout=60,
    )
    if code != 0:
        return []
    files = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            size = int(parts[0])
            mtime = float(parts[1])
        except ValueError:
            continue
        full = parts[2]
        files.append(
            {
                "path": full,
                "name": os.path.basename(full),
                "size": size,
                "mtime": mtime,
            }
        )
    files.sort(key=lambda item: item["size"], reverse=True)
    return files


def cache_stats() -> dict:
    files = cache_files()
    packages = [item for item in files if ".pkg.tar" in item["name"]]
    return {
        "total": sum(item["size"] for item in files),
        "count": len(packages),
        "files": files,
        "newest": max((item["mtime"] for item in files), default=0),
        "oldest": min((item["mtime"] for item in files), default=0),
    }


def path_size(path: str) -> int:
    if not os.path.exists(path):
        return 0
    code, out, _ = run_sync(["du", "-sb", path], timeout=180)
    if code != 0:
        return 0
    try:
        return int(out.split("\t")[0])
    except (ValueError, IndexError):
        return 0


def user_cache_size() -> int:
    return path_size(os.path.expanduser("~/.cache"))


def thumbnail_size() -> int:
    return path_size(os.path.expanduser("~/.cache/thumbnails"))


def trash_size() -> int:
    return path_size(os.path.expanduser("~/.local/share/Trash"))


def mirrorlist_info() -> dict:
    path = "/etc/pacman.d/mirrorlist"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        mtime = os.path.getmtime(path)
    except OSError:
        return {"count": 0, "hosts": [], "mtime": 0}
    servers = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Server"):
            servers.append(stripped.split("=", 1)[1].strip())
    hosts = []
    for server in servers:
        host = urlparse(server).netloc or server
        if host not in hosts:
            hosts.append(host)
    return {"count": len(servers), "hosts": hosts[:8], "mtime": mtime}


def snapshots(config: str = "root") -> dict:
    if not which("snapper"):
        return {"ok": False, "rows": [], "error": "snapper no está instalado"}
    code, out, err = run_sync(
        ["sudo", "-n", "snapper", "--iso", "--csvout", "-c", config, "list"],
        timeout=45,
    )
    if code != 0:
        message = err.strip()
        if "password" in message.lower() or code in (1, 126):
            message = "se necesitan permisos de administrador"
        return {"ok": False, "rows": [], "error": message or "no se pudo leer"}
    reader = csv.reader(io.StringIO(out))
    raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not raw_rows:
        return {"ok": True, "rows": []}

    header = [cell.strip().lower() for cell in raw_rows[0]]
    data_rows = raw_rows[1:]
    index = {}
    if any(cell in ("#", "number", "num") for cell in header):
        for position, cell in enumerate(header):
            index[cell] = position

    def cell(row, *names, default=""):
        for name in names:
            if name in index and index[name] < len(row):
                return row[index[name]].strip()
        return default

    rows = []
    for row in data_rows:
        number = cell(row, "#", "number", "num")
        if not number.isdigit():
            continue
        rows.append(
            {
                "number": int(number),
                "type": cell(row, "type", default="single"),
                "date": cell(row, "post-date", "date", "pre-date"),
                "description": cell(row, "description", "desc"),
                "user": cell(row, "user", "username"),
            }
        )
    rows.sort(key=lambda item: item["number"], reverse=True)
    return {"ok": True, "rows": rows}


def services_failed() -> list[str]:
    code, out, _ = run_sync(
        ["systemctl", "--failed", "--no-legend", "--plain"], timeout=15
    )
    if code != 0:
        return []
    return [line.split()[0] for line in out.splitlines() if line.strip()]


def last_update_time() -> float:
    try:
        return os.path.getmtime("/var/lib/pacman/local")
    except OSError:
        return 0.0


def snapshot_age(reference: float) -> str:
    from .util import human_duration

    if not reference:
        return "—"
    return human_duration(time.time() - reference) + " atrás"
