#!/bin/bash
# macOS: "SOM Assembler.app" ilovasini yig'ish. Finder'da ikki marta bosing.
# Birinchi marta internet kerak (pywebview va PyInstaller o'rnatiladi), 1-3 daqiqa davom etadi.
set -euo pipefail
cd "$(dirname "$0")"

APP="SOM Assembler"
VENV=".venv-build"

echo "1/4  Virtual muhit va kutubxonalar..."
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r requirements.txt pyinstaller

echo "2/4  Ikonka (.icns)..."
ICONSET="build/icon.iconset"
rm -rf "build/icon.iconset"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z "$s" "$s" mac/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2))
  sips -z "$d" "$d" mac/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o build/icon.icns

echo "3/4  Ilovani yig'ish (PyInstaller)..."
"$VENV/bin/pyinstaller" --noconfirm --clean --log-level WARN --windowed \
  --name "$APP" --icon build/icon.icns --osx-bundle-identifier uz.som.assembler \
  --add-data "ui:ui" --add-data "examples:examples" \
  som_glass.py

echo "4/4  Tayyor: dist/$APP.app"
read -r -p "Applications papkasiga o'rnataymi? [y/N] " answer
if [[ "$answer" == [yY] ]]; then
  rm -rf "/Applications/SOM Assembler.app"
  cp -R "dist/$APP.app" /Applications/
  echo "O'rnatildi: Launchpad yoki Applications papkasidan oching."
  open "/Applications/$APP.app"
else
  open dist
fi
