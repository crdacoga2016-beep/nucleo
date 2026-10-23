#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$APP_DIR"

if [[ ! -d venv ]]; then
    python3 -m venv venv
fi
./venv/bin/pip install --upgrade pip >/dev/null
./venv/bin/pip install -r requirements.txt

ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$ICON_DIR" "$APPS_DIR"
install -m644 assets/icon.svg "$ICON_DIR/nucleo.svg"

cat > "$APPS_DIR/nucleo.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Núcleo
GenericName=Centro de sistema
Comment=Administrador gráfico para tareas de Arch y CachyOS
Exec=sh -c 'cd "$APP_DIR" && exec ./run.sh'
Icon=nucleo
Terminal=false
Categories=System;PackageManager;Utility;
Keywords=pacman;cachyos;arch;actualizar;updates;orphans;snapshots;
StartupNotify=true
StartupWMClass=nucleo
EOF

update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
echo "Núcleo instalado en $APP_DIR"
