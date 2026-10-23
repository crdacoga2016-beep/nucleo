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

# La entrada de menú sale de la plantilla nucleo.desktop del repo, con la ruta
# real sustituida. El Exec debe ser una ruta absoluta entre comillas: usar
# "sh -c 'cd ... && ...'" rompe la especificación de escritorio y los
# lanzadores estrictos (fuzzel, gtk-launch) descartan la entrada.
sed "s|@APP_DIR@|$APP_DIR|g" nucleo.desktop > "$APPS_DIR/nucleo.desktop"
chmod 644 "$APPS_DIR/nucleo.desktop"

update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
echo "Núcleo instalado en $APP_DIR"
