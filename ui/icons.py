from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "home": '<path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1v-9z"/>',
    "grid": (
        '<rect x="3.5" y="3.5" width="7" height="7" rx="2"/>'
        '<rect x="13.5" y="3.5" width="7" height="7" rx="2"/>'
        '<rect x="3.5" y="13.5" width="7" height="7" rx="2"/>'
        '<rect x="13.5" y="13.5" width="7" height="7" rx="2"/>'
    ),
    "refresh": (
        '<path d="M20.5 12a8.5 8.5 0 1 1-2.5-6"/>'
        '<path d="M20.5 3.5V9H15"/>'
    ),
    "box": (
        '<path d="M21 8.2l-9-5-9 5v7.6l9 5 9-5V8.2z"/>'
        '<path d="M3.2 8.2L12 13l8.8-4.8"/>'
        '<path d="M12 13v7.8"/>'
    ),
    "unlink": (
        '<path d="M9.5 7H7.5a5 5 0 0 0 0 10h2"/>'
        '<path d="M14.5 7h2a5 5 0 0 1 0 10h-2"/>'
        '<path d="M8.5 12h7" stroke-dasharray="1.5 2.6"/>'
    ),
    "database": (
        '<ellipse cx="12" cy="6" rx="7.5" ry="3"/>'
        '<path d="M4.5 6v6c0 1.66 3.36 3 7.5 3s7.5-1.34 7.5-3V6"/>'
        '<path d="M4.5 12v6c0 1.66 3.36 3 7.5 3s7.5-1.34 7.5-3v-6"/>'
    ),
    "broom": (
        '<path d="M4 6h16"/>'
        '<path d="M8.5 6V4.2A1.2 1.2 0 0 1 9.7 3h4.6a1.2 1.2 0 0 1 1.2 1.2V6"/>'
        '<path d="M5.5 6l.9 13.1A1.9 1.9 0 0 0 8.3 21h7.4a1.9 1.9 0 0 0 1.9-1.9L18.5 6"/>'
        '<path d="M9.7 10.5v6M14.3 10.5v6"/>'
    ),
    "layers": (
        '<path d="M12 3l8.5 4.6L12 12.2 3.5 7.6 12 3z"/>'
        '<path d="M3.5 12l8.5 4.6 8.5-4.6"/>'
        '<path d="M3.5 16.4l8.5 4.6 8.5-4.6"/>'
    ),
    "globe": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M3.5 12h17"/>'
        '<path d="M12 3.5c2.6 2.3 4 5.3 4 8.5s-1.4 6.2-4 8.5c-2.6-2.3-4-5.3-4-8.5s1.4-6.2 4-8.5z"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 7.2v5l3.4 2"/>'
    ),
    "history": (
        '<path d="M3.6 12a8.4 8.4 0 1 0 2.6-6.1"/>'
        '<path d="M3.2 4v4.4h4.4"/>'
        '<path d="M12 8v4.6l3.2 1.9"/>'
    ),
    "search": (
        '<circle cx="10.8" cy="10.8" r="6.8"/>'
        '<path d="M20.5 20.5l-4.7-4.7"/>'
    ),
    "terminal": (
        '<path d="M4 17l5.5-5L4 7"/>'
        '<path d="M12.5 19h7.5"/>'
    ),
    "shield": '<path d="M12 3l7.5 3v5.6c0 4.6-3.2 7.6-7.5 9.4-4.3-1.8-7.5-4.8-7.5-9.4V6L12 3z"/>',
    "check": '<path d="M4.5 12.5l5 5L19.5 7"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "info": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 11.2v5.2"/>'
        '<circle cx="12" cy="7.9" r="0.9" fill="{c}" stroke="none"/>'
    ),
    "power": (
        '<path d="M12 3.5v8.2"/>'
        '<path d="M6.9 6.6a8 8 0 1 0 10.2 0"/>'
    ),
    "chevron": '<path d="M9.5 5.5L16 12l-6.5 6.5"/>',
    "copy": (
        '<rect x="8.5" y="8.5" width="11" height="11" rx="2.2"/>'
        '<path d="M5 15.5V5.8A1.8 1.8 0 0 1 6.8 4h9.7"/>'
    ),
    "maximize": (
        '<path d="M4 9.5V4h5.5"/>'
        '<path d="M20 14.5V20h-5.5"/>'
        '<path d="M4 4l6.5 6.5"/>'
        '<path d="M20 20l-6.5-6.5"/>'
    ),
    "restore": (
        '<path d="M9.5 4v5.5H4"/>'
        '<path d="M14.5 20v-5.5H20"/>'
        '<path d="M14.5 9.5L20 4"/>'
        '<path d="M9.5 14.5L4 20"/>'
    ),
    "minimize": '<path d="M5 12h14"/>',
    "disk": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<circle cx="12" cy="12" r="2.6"/>'
        '<path d="M12 3.5v5.9M12 14.6v5.9"/>'
    ),
    "cpu": (
        '<rect x="6.5" y="6.5" width="11" height="11" rx="2.2"/>'
        '<rect x="10" y="10" width="4" height="4" rx="1"/>'
        '<path d="M9.5 2.8v3.7M14.5 2.8v3.7M9.5 17.5v3.7M14.5 17.5v3.7M2.8 9.5h3.7M2.8 14.5h3.7M17.5 9.5h3.7M17.5 14.5h3.7"/>'
    ),
    "memory": (
        '<rect x="3.5" y="7" width="17" height="10" rx="2"/>'
        '<path d="M7 17v3M12 17v3M17 17v3"/>'
        '<path d="M8 10.5h8"/>'
    ),
    "download": (
        '<path d="M12 3.5v11"/>'
        '<path d="M7.5 10.5L12 15l4.5-4.5"/>'
        '<path d="M4.5 20.5h15"/>'
    ),
    "sparkles": (
        '<path d="M12 3.5l1.7 4.4L18 9.6l-4.3 1.7L12 15.7l-1.7-4.4L6 9.6l4.3-1.7L12 3.5z"/>'
        '<path d="M18.5 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z"/>'
    ),
    "warning": (
        '<path d="M12 4.2l8.6 14.6a1.2 1.2 0 0 1-1 1.8H4.4a1.2 1.2 0 0 1-1-1.8L12 4.2z"/>'
        '<path d="M12 9.5v5"/>'
        '<circle cx="12" cy="17.3" r="0.9" fill="{c}" stroke="none"/>'
    ),
    "rocket": (
        '<path d="M13.5 4.2c3-1.4 5.3-1 6.3-.9.1 1 .5 3.3-.9 6.3-1 2.2-3 4.3-5.2 5.6l-2.6-2.6-2.6-2.6c1.3-2.2 3.4-4.2 5-5.8z"/>'
        '<circle cx="15.6" cy="8.4" r="1.6"/>'
        '<path d="M8 14l-3.3.6L3 21l6.4-1.7L8 14z"/>'
    ),
    "filter": (
        '<path d="M3.5 5.5h17l-6.5 7.6v5.2l-4 2.2v-7.4L3.5 5.5z"/>'
    ),
    "eye": (
        '<path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12z"/>'
        '<circle cx="12" cy="12" r="2.8"/>'
    ),
    "arrow": '<path d="M4.5 12h14"/><path d="M13 6.5L18.5 12 13 17.5"/>',
}


def svg_source(name: str, color: str) -> str:
    body = PATHS[name].replace("{c}", color)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round" '
        'stroke-linejoin="round">{body}</svg>'
    ).replace("{c}", color).replace("{body}", body)


_cache: dict = {}


def pixmap(name: str, color: str = "#E6EAF2", size: int = 22) -> QPixmap:
    key = (name, color, size)
    if key in _cache:
        return _cache[key]
    renderer = QSvgRenderer(QByteArray(svg_source(name, color).encode("utf-8")))
    ratio = 2.0
    result = QPixmap(int(size * ratio), int(size * ratio))
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    result.setDevicePixelRatio(ratio)
    _cache[key] = result
    return result


def icon(name: str, color: str = "#E6EAF2", size: int = 22) -> QIcon:
    return QIcon(pixmap(name, color, size))
