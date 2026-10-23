from __future__ import annotations

import re
import time

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
SIZE_RE = re.compile(r"([\d.]+)\s*([KMGTP]?)i?B", re.IGNORECASE)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def human_bytes(value, decimals=None) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024.0
        index += 1
    if decimals is None:
        decimals = 0 if index == 0 else (1 if value < 100 else 0)
    text = f"{value:,.{decimals}f}"
    text = text.replace(",", "\u00a0").replace(".", ",")
    return f"{text} {units[index]}"


def human_bytes_plain(value) -> str:
    return human_bytes(value).replace("\u00a0", " ")


def parse_human_size(text: str) -> int:
    match = SIZE_RE.search(text or "")
    if not match:
        return 0
    number = float(match.group(1))
    unit = match.group(2).upper()
    power = {"": 0, "K": 1, "M": 2, "G": 3, "T": 4, "P": 5}.get(unit, 0)
    return int(number * (1024**power))


def human_duration(seconds) -> str:
    seconds = int(max(0, seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {secs} s"
    return f"{secs} s"


def human_time(timestamp) -> str:
    return time.strftime("%d/%m %H:%M:%S", time.localtime(timestamp))


def human_date(timestamp) -> str:
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(timestamp))


def plural(count, singular, plural_form) -> str:
    return f"{count} {singular if count == 1 else plural_form}"
