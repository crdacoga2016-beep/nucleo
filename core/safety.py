from __future__ import annotations

import os
import re
import shutil
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .proc import run_sync
from .util import human_bytes

PACMAN_LOG = "/var/log/pacman.log"
SNAPPER_CONFIG = "/etc/snapper/configs/root"
NEWS_FEEDS = (
    ("Arch Linux", "https://archlinux.org/feeds/news/"),
    ("CachyOS", "https://cachyos.org/rss.xml"),
)
MANUAL_NEWS_MARKERS = (
    "manual intervention",
    "manual action",
    "manual steps",
    "requires manual",
)

REBOOT_PREFIXES = ("linux", "systemd", "nvidia", "lib32-nvidia")
REBOOT_NAMES = {
    "glibc",
    "lib32-glibc",
    "mesa",
    "lib32-mesa",
}


@dataclass
class Check:
    key: str
    title: str
    status: str
    detail: str = ""

    def line(self) -> str:
        mark = {"ok": "✓", "warn": "⚠", "fail": "✕", "info": "ℹ"}.get(
            self.status, "•"
        )
        if self.detail:
            return f"{mark} {self.title}: {self.detail}"
        return f"{mark} {self.title}"


def _last_full_upgrade() -> datetime | None:
    pattern = re.compile(
        r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4})\]"
        r"\s+\[PACMAN\]\s+starting full system upgrade"
    )
    try:
        with open(PACMAN_LOG, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 8_000_000))
            text = handle.read().decode("utf-8", "replace")
    except OSError:
        return None
    matches = pattern.findall(text)
    if not matches:
        return None
    try:
        return datetime.fromisoformat(matches[-1])
    except ValueError:
        return None


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _news_since() -> datetime:
    now = datetime.now(timezone.utc)
    last = _last_full_upgrade()
    since = last or (now - timedelta(days=30))
    since = max(since, now - timedelta(days=120))
    return since - timedelta(hours=12)


def _recent_news() -> tuple[list[dict], bool]:
    since = _news_since()
    items: list[dict] = []
    errors = 0
    for source, url in NEWS_FEEDS:
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Nucleo/1.0 (safe update check)"}
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                data = response.read(600_000)
            root = ET.fromstring(data)
            for node in root.findall("./channel/item"):
                title = (node.findtext("title") or "").strip()
                description = _clean_html(node.findtext("description") or "")
                published = node.findtext("pubDate") or ""
                try:
                    date = parsedate_to_datetime(published)
                except (TypeError, ValueError):
                    continue
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                if date < since:
                    continue
                text = f"{title} {description}".lower()
                items.append(
                    {
                        "source": source,
                        "title": title,
                        "link": (node.findtext("link") or "").strip(),
                        "date": date,
                        "critical": any(marker in text for marker in MANUAL_NEWS_MARKERS),
                    }
                )
        except Exception:
            errors += 1
    items.sort(key=lambda item: item["date"], reverse=True)
    return items[:6], errors == len(NEWS_FEEDS)


def _check_lock() -> Check:
    if os.path.exists("/var/lib/pacman/db.lck"):
        return Check(
            "lock",
            "Bloqueo de pacman",
            "fail",
            "hay otra actualización en curso (existe /var/lib/pacman/db.lck). "
            "Espera a que termine o comprueba que no sea un bloqueo huérfano.",
        )
    return Check("lock", "Bloqueo de pacman", "ok", "libre")


def _check_space() -> Check:
    free = shutil.disk_usage("/").free
    if free < 2 * 1024**3:
        return Check(
            "space",
            "Espacio libre",
            "fail",
            f"solo quedan {human_bytes(free)} en /. Libera espacio antes de actualizar.",
        )
    if free < 5 * 1024**3:
        return Check(
            "space",
            "Espacio libre",
            "warn",
            f"quedan {human_bytes(free)} en /. Es recomendable tener al menos 5 GiB.",
        )
    detail = f"{human_bytes(free)} libres en /"
    if os.path.ismount("/boot"):
        boot_free = shutil.disk_usage("/boot").free
        if boot_free < 150 * 1024**2:
            return Check(
                "space",
                "Espacio libre",
                "fail",
                f"/boot solo tiene {human_bytes(boot_free)}. El kernel no cabrá.",
            )
        if boot_free < 300 * 1024**2:
            return Check(
                "space",
                "Espacio libre",
                "warn",
                f"{detail}; /boot tiene {human_bytes(boot_free)}.",
            )
        detail += f"; /boot tiene {human_bytes(boot_free)}"
    return Check("space", "Espacio libre", "ok", detail)


def _check_database() -> Check:
    code, out, err = run_sync(["pacman", "-Dk"], timeout=30)
    if code != 0:
        detail = (err or out).strip().splitlines()
        return Check(
            "database",
            "Base de datos de pacman",
            "fail",
            detail[-1] if detail else f"código {code}",
        )
    return Check("database", "Base de datos de pacman", "ok", "consistente")


def _check_keyring(updates) -> Check:
    code, out, err = run_sync(["pacman-key", "--list-keys"], timeout=30)
    if code != 0:
        detail = (err or out).strip().splitlines()
        return Check(
            "keyring",
            "Llavero de pacman",
            "fail",
            "no se puede leer el llavero; actualízalo antes de continuar. "
            + (detail[-1] if detail else ""),
        )
    pending = sorted(
        {item["name"] for item in updates}
        & {"archlinux-keyring", "cachyos-keyring"}
    )
    if pending:
        return Check(
            "keyring",
            "Llavero de pacman",
            "warn",
            f"hay actualización de {', '.join(pending)}. Se aplicará en esta "
            "transacción; si aparece un error de firma, actualízalo primero.",
        )
    return Check("keyring", "Llavero de pacman", "ok", "legible y al día")


def _check_snapshot() -> Check:
    if not shutil.which("snapper"):
        return Check(
            "snapshot",
            "Snapshot",
            "fail",
            "snapper no está instalado; no se puede crear una instantánea previa.",
        )
    if not os.path.exists(SNAPPER_CONFIG):
        return Check(
            "snapshot",
            "Snapshot",
            "fail",
            "no hay configuración de snapper para root. No se puede crear la "
            "instantánea previa.",
        )
    snap_pac = run_sync(["pacman", "-Qq", "snap-pac"], timeout=10)[0] == 0
    detail = "snapper listo"
    detail += "; snap-pac activo" if snap_pac else "; snap-pac no detectado"
    return Check("snapshot", "Snapshot", "ok", detail + "; se creará uno manual")


def _check_news() -> Check:
    items, all_failed = _recent_news()
    if all_failed and not items:
        return Check(
            "news",
            "Noticias",
            "info",
            "no se pudieron leer los feeds; continúa solo si tienes conexión.",
        )
    critical = [item for item in items if item["critical"]]
    if critical:
        listing = "; ".join(
            f"{item['title']} ({item['source']})" for item in critical[:3]
        )
        links = " ".join(item["link"] for item in critical[:2] if item["link"])
        return Check(
            "news",
            "Noticias",
            "fail",
            f"intervención manual requerida: {listing}. {links}".strip(),
        )
    if items:
        listing = "; ".join(
            f"{item['title']} ({item['source']})" for item in items[:3]
        )
        return Check(
            "news",
            "Noticias",
            "warn",
            f"{len(items)} aviso(s) reciente(s): {listing}",
        )
    return Check(
        "news", "Noticias", "ok", "sin avisos nuevos desde la última actualización"
    )


def preflight(updates) -> list[Check]:
    return [
        _check_lock(),
        _check_space(),
        _check_database(),
        _check_keyring(updates),
        _check_snapshot(),
        _check_news(),
    ]


def aur_risks(names) -> list[str]:
    risks = []
    for name in names:
        low = name.lower()
        if low.endswith("-git") or any(
            key in low for key in ("caelestia", "quickshell", "m3shapes")
        ):
            risks.append(
                f"{name}: paquete de desarrollo o vinculado a Caelestia/Quickshell; "
                "puede romper la shell."
            )
    return risks


def free_bytes(path: str = "/") -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0


def reboot_packages(names) -> list[str]:
    found = set()
    for name in names:
        low = name.lower()
        if low.startswith(REBOOT_PREFIXES) or low in REBOOT_NAMES:
            found.add(name)
    return sorted(found)
