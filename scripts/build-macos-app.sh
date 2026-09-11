#!/usr/bin/env bash
# Build an ad-hoc-signed KB-Portable-DASH.app and zip it. macOS only.
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "scripts/build-macos-app.sh is macOS-only" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NAME="KB-Portable-DASH"
BUNDLE_ID="com.cgfixit.kb-portable-dash"
APP="dist/${NAME}.app"
ZIP="dist/${NAME}-macos.zip"

python -m pip install -e .
python -m pip install "pyinstaller==6.22.2"

python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$NAME" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --collect-all customtkinter \
  --add-data "examples:examples" \
  --add-data "config.example.toml:." \
  main.py

if [ ! -d "$APP" ]; then
  echo "missing $APP" >&2
  exit 1
fi

# Ad-hoc sign. No Apple Developer ID is configured on this repo.
codesign --force --deep --sign - "$APP"
codesign --verify --deep "$APP"

rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"
echo "$ZIP"
