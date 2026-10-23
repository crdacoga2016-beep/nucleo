from __future__ import annotations

from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).resolve().parent.parent / "assets"

C = {
    "BG": "#0B0E15",
    "SIDEBAR": "#090C12",
    "CARD": "#141926",
    "CARD2": "#181E2C",
    "CARD_HOVER": "#1A2132",
    "INPUT_BG": "#0F141F",
    "BORDER": "#1F2735",
    "BORDER2": "#2A3448",
    "BORDER_HOVER": "#374264",
    "TEXT": "#E7EBF3",
    "TEXT2": "#C4CCDB",
    "MUTED": "#8A94A8",
    "FAINT": "#5A6478",
    "ACCENT": "#FF8A3D",
    "ACCENT2": "#FFB55C",
    "ACCENT_DARK": "#E8772A",
    "ACCENT_TXT": "#1B1005",
    "ACCENT_SOFT": "rgba(255, 138, 61, 0.14)",
    "ACCENT_LINE": "rgba(255, 138, 61, 0.34)",
    "SUCCESS": "#43D6A0",
    "SUCCESS_SOFT": "rgba(67, 214, 160, 0.14)",
    "DANGER": "#FF6B7A",
    "DANGER_SOFT": "rgba(255, 107, 122, 0.13)",
    "DANGER_LINE": "rgba(255, 107, 122, 0.32)",
    "WARN": "#FFC24B",
    "WARN_SOFT": "rgba(255, 194, 75, 0.14)",
    "INFO": "#63A9FF",
    "INFO_SOFT": "rgba(99, 169, 255, 0.14)",
    "CONSOLE": "#070A0F",
    "CONSOLE_LINE": "#161D2A",
}

UI_FONTS = ["Inter", "Adwaita Sans", "Cantarell", "Noto Sans", "DejaVu Sans"]
MONO_FONTS = [
    "JetBrainsMono Nerd Font",
    "JetBrains Mono",
    "CaskaydiaCove Nerd Font",
    "Noto Sans Mono",
    "DejaVu Sans Mono",
]

_families: set | None = None
_ui_family: str | None = None
_mono_family: str | None = None


def _load_families() -> set:
    global _families
    if _families is None:
        try:
            _families = set(QFontDatabase.families())
        except Exception:
            _families = set()
    return _families


def pick_family(candidates, fallback="sans-serif") -> str:
    families = _load_families()
    for name in candidates:
        if name in families:
            return name
    return fallback


def ui_family() -> str:
    global _ui_family
    if _ui_family is None:
        _ui_family = pick_family(UI_FONTS, "sans-serif")
    return _ui_family


def mono_family() -> str:
    global _mono_family
    if _mono_family is None:
        _mono_family = pick_family(MONO_FONTS, "monospace")
    return _mono_family


def font(size=10, weight=400, mono=False) -> QFont:
    result = QFont(mono_family() if mono else ui_family())
    result.setPointSizeF(size)
    try:
        result.setWeight(QFont.Weight(weight))
    except Exception:
        result.setWeight(weight)
    return result


def color(name: str, alpha: int | None = None) -> QColor:
    value = C[name]
    if value.startswith("rgba"):
        inside = value[value.index("(") + 1 : value.index(")")]
        parts = [p.strip() for p in inside.split(",")]
        result = QColor(int(parts[0]), int(parts[1]), int(parts[2]))
        if len(parts) > 3:
            result.setAlphaF(float(parts[3]))
    else:
        result = QColor(value)
    if alpha is not None:
        result.setAlpha(alpha)
    return result


_QSS = Template(
    """
* { outline: none; }

QWidget {
    color: $TEXT;
    font-family: "$UIFONT";
    font-size: 10pt;
}

#Root, QMainWindow { background: $BG; }
QDialog { background: $CARD; }

QLabel { background: transparent; color: $TEXT; }
#Muted { color: $MUTED; }
#Faint { color: $FAINT; }
#Soft { color: $TEXT2; }
#Accent { color: $ACCENT; }
#Success { color: $SUCCESS; }
#Danger { color: $DANGER; }
#Warn { color: $WARN; }
#PageTitle { font-size: 17pt; font-weight: 700; }
#PageSub { color: $MUTED; font-size: 9.5pt; }
#CardTitle { font-size: 11pt; font-weight: 600; }
#CardSub { color: $MUTED; font-size: 8.5pt; }
#StatValue { font-size: 16pt; font-weight: 700; }
#StatLabel { color: $MUTED; font-size: 8.5pt; }
#Mono { font-family: "$MONOFONT"; }
#Section { color: $MUTED; font-size: 8pt; font-weight: 700; }
#Monogram { font-size: 13pt; font-weight: 700; }

#Sidebar { background: $SIDEBAR; border-right: 1px solid rgba(255,255,255,0.03); }
#AppName { font-size: 13pt; font-weight: 800; letter-spacing: 2px; }
#AppTag { color: $FAINT; font-size: 8pt; letter-spacing: 1px; }
#NavSection { color: $FAINT; font-size: 7.5pt; font-weight: 700; }

QPushButton#Nav {
    background: transparent; color: $MUTED; border: 1px solid transparent;
    border-radius: 10px; text-align: left; padding: 0 12px; font-size: 9.5pt;
}
QPushButton#Nav:hover { background: rgba(255,255,255,0.035); color: $TEXT; }
QPushButton#Nav[active="true"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(255,138,61,0.16), stop:1 rgba(255,138,61,0.05));
    color: $ACCENT2; border: 1px solid $ACCENT_LINE; font-weight: 600;
}
#Sidebar[compact="true"] QPushButton#Nav { padding: 0; text-align: center; }
#Sidebar[compact="true"] #AppName { font-size: 10pt; letter-spacing: 0px; }
#Sidebar[compact="true"] #Badge { padding: 3px 6px; }

#Card {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 $CARD2, stop:1 $CARD);
    border: 1px solid $BORDER; border-radius: 16px;
}
#Card[danger="true"] { border: 1px solid $DANGER_LINE; }
#Hero {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(255,138,61,0.20), stop:0.5 rgba(255,138,61,0.07), stop:1 rgba(99,169,255,0.10));
    border: 1px solid $ACCENT_LINE; border-radius: 18px;
}
#Tile {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 $CARD2, stop:1 $CARD);
    border: 1px solid $BORDER; border-radius: 14px;
}
#Tile:hover { border: 1px solid $BORDER_HOVER; }

#IconBox { background: $ACCENT_SOFT; border-radius: 10px; }

QPushButton {
    background: $CARD2; color: $TEXT2; border: 1px solid $BORDER2;
    border-radius: 10px; padding: 0 16px; font-size: 9.5pt; font-weight: 500;
}
QPushButton:hover { background: $CARD_HOVER; color: $TEXT; border-color: $BORDER_HOVER; }
QPushButton:pressed { background: $INPUT_BG; }
QPushButton:disabled { color: $FAINT; background: rgba(255,255,255,0.02); border-color: $BORDER; }

QPushButton#Primary {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 $ACCENT2, stop:1 $ACCENT);
    color: $ACCENT_TXT; border: none; font-weight: 700;
}
QPushButton#Primary:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FFC271, stop:1 #FF9A4D);
}
QPushButton#Primary:disabled { background: rgba(255,138,61,0.25); color: rgba(27,16,5,0.6); }

QPushButton#Danger {
    background: $DANGER_SOFT; color: $DANGER; border: 1px solid $DANGER_LINE; font-weight: 600;
}
QPushButton#Danger:hover { background: rgba(255,107,122,0.22); }

QPushButton#Ghost { background: transparent; color: $MUTED; border: 1px solid $BORDER2; }
QPushButton#Ghost:hover { color: $TEXT; border-color: $BORDER_HOVER; background: rgba(255,255,255,0.03); }

QPushButton#IconBtn {
    background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 0;
}
QPushButton#IconBtn:hover { background: rgba(255,255,255,0.05); border-color: $BORDER2; }

QPushButton#Chip {
    background: $INPUT_BG; color: $MUTED; border: 1px solid $BORDER; border-radius: 9px;
    padding: 0 12px; font-size: 9pt; font-weight: 600;
}
QPushButton#Chip:hover { color: $TEXT; border-color: $BORDER_HOVER; }
QPushButton#Chip:checked {
    background: $ACCENT_SOFT; color: $ACCENT2; border-color: $ACCENT_LINE;
}

QLineEdit, QComboBox {
    background: $INPUT_BG; color: $TEXT; border: 1px solid $BORDER;
    border-radius: 10px; padding: 0 12px; min-height: 32px;
    selection-background-color: $ACCENT_LINE; selection-color: $TEXT;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid $ACCENT_LINE; }
QLineEdit::placeholder { color: $FAINT; }
QLineEdit#Password { font-family: "$MONOFONT"; }

QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
    background: $CARD2; border: 1px solid $BORDER2; border-radius: 10px;
    selection-background-color: $CARD_HOVER; color: $TEXT; padding: 4px; outline: none;
}

QCheckBox { spacing: 10px; color: $TEXT2; font-size: 9.5pt; }
QCheckBox::indicator {
    width: 40px; height: 22px; border-radius: 11px;
    background: #242C3C; border: 1px solid $BORDER2;
}
QCheckBox::indicator:unchecked { image: url($KNOB_OFF); }
QCheckBox::indicator:checked { background: $ACCENT; border-color: $ACCENT; image: url($KNOB_ON); }
QCheckBox::indicator:hover { border-color: $BORDER_HOVER; }

QTableWidget, QTableView, QListWidget, QTreeView {
    background: $INPUT_BG; alternate-background-color: rgba(255,255,255,0.016);
    border: 1px solid $BORDER; border-radius: 12px; gridline-color: transparent;
    selection-background-color: $ACCENT_SOFT; selection-color: $TEXT;
    font-size: 9.5pt; outline: none;
}
QTableWidget::item, QListWidget::item { padding: 6px 8px; border: none; }
QTableWidget::item:selected, QListWidget::item:selected { background: $ACCENT_SOFT; color: $TEXT; }
QHeaderView::section {
    background: $INPUT_BG; color: $MUTED; border: none;
    border-bottom: 1px solid $BORDER; padding: 8px 8px; font-size: 8.5pt; font-weight: 600;
}
QTableCornerButton::section { background: $INPUT_BG; border: none; }

QPlainTextEdit, QTextEdit {
    background: $CONSOLE; color: $TEXT2; border: 1px solid $CONSOLE_LINE;
    border-radius: 12px; padding: 10px; font-family: "$MONOFONT"; font-size: 9pt;
    selection-background-color: $ACCENT_LINE;
}

QProgressBar {
    background: #1A2130; border: none; border-radius: 5px; height: 10px;
    color: transparent; text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 $ACCENT, stop:1 $ACCENT2);
    border-radius: 5px;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical {
    background: #2A3448; border-radius: 5px; min-height: 32px;
}
QScrollBar::handle:vertical:hover { background: #3A4760; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #2A3448; border-radius: 5px; min-width: 32px; }
QScrollBar::handle:horizontal:hover { background: #3A4760; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; background: none; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }

QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 12px; }
QSplitter::handle:vertical { height: 12px; }

QToolTip {
    background: $CARD2; color: $TEXT; border: 1px solid $BORDER2;
    border-radius: 8px; padding: 6px 10px; font-size: 9pt;
}

QMenu { background: $CARD2; border: 1px solid $BORDER2; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 24px 7px 12px; border-radius: 7px; color: $TEXT2; }
QMenu::item:selected { background: $CARD_HOVER; color: $TEXT; }
QMenu::separator { height: 1px; background: $BORDER; margin: 5px 8px; }

QMessageBox { background: $CARD; }
QMessageBox QLabel { color: $TEXT; }
QMessageBox QPushButton { min-width: 84px; min-height: 32px; }

#Badge {
    border-radius: 9px; padding: 3px 10px; font-size: 8pt; font-weight: 700;
    background: rgba(255,255,255,0.05); color: $MUTED;
}
#Badge[kind="accent"] { background: $ACCENT_SOFT; color: $ACCENT2; }
#Badge[kind="success"] { background: $SUCCESS_SOFT; color: $SUCCESS; }
#Badge[kind="danger"] { background: $DANGER_SOFT; color: $DANGER; }
#Badge[kind="warn"] { background: $WARN_SOFT; color: $WARN; }
#Badge[kind="info"] { background: $INFO_SOFT; color: $INFO; }

#Toast {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 $CARD2, stop:1 $CARD);
    border: 1px solid $BORDER2; border-radius: 14px;
}
#ToastTitle { font-size: 10pt; font-weight: 700; }
#ToastText { color: $MUTED; font-size: 9pt; }
#Toast[kind="success"] { border: 1px solid rgba(67,214,160,0.35); }
#Toast[kind="danger"] { border: 1px solid $DANGER_LINE; }
#Toast[kind="warn"] { border: 1px solid rgba(255,194,75,0.35); }

#TermInput {
    background: $CONSOLE; border: 1px solid $BORDER2; border-radius: 10px;
    padding: 0 12px; min-height: 32px; font-family: "$MONOFONT";
}
#StepRow { border-radius: 10px; background: rgba(255,255,255,0.02); }
#StepRow[state="ok"] { background: $SUCCESS_SOFT; }
#StepRow[state="error"] { background: $DANGER_SOFT; }
#StepRow[state="running"] { background: $ACCENT_SOFT; }
#Divider { background: $BORDER; }
#Sep { background: rgba(255,255,255,0.05); }
"""
)


def stylesheet() -> str:
    values = dict(C)
    values["UIFONT"] = ui_family()
    values["MONOFONT"] = mono_family()
    values["KNOB_OFF"] = (ASSETS / "knob_off.svg").as_posix()
    values["KNOB_ON"] = (ASSETS / "knob_on.svg").as_posix()
    return _QSS.substitute(values)


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(font(10, 400))

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, color("BG"))
    palette.setColor(QPalette.ColorRole.WindowText, color("TEXT"))
    palette.setColor(QPalette.ColorRole.Base, color("INPUT_BG"))
    palette.setColor(QPalette.ColorRole.AlternateBase, color("CARD"))
    palette.setColor(QPalette.ColorRole.Text, color("TEXT"))
    palette.setColor(QPalette.ColorRole.Button, color("CARD2"))
    palette.setColor(QPalette.ColorRole.ButtonText, color("TEXT"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, color("CARD2"))
    palette.setColor(QPalette.ColorRole.ToolTipText, color("TEXT"))
    palette.setColor(QPalette.ColorRole.Highlight, color("ACCENT_DARK"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#1B1005"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, color("FAINT"))
    palette.setColor(QPalette.ColorRole.Link, color("ACCENT"))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, color("FAINT")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, color("FAINT")
    )
    app.setPalette(palette)

    app.setStyleSheet(stylesheet())
