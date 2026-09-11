#!/usr/bin/env bash
# Build KB-Portable-DASH.app and zip it. macOS only.
# Ad-hoc sign unless CODESIGN_IDENTITY is a Developer ID Application identity.
# If NOTARY_KEY_PATH is set, submit to Apple notary and staple.
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
ENTITLEMENTS="packaging/macos.entitlements"
MODE_FILE="dist/signing-mode.txt"

python -m pip install -e .
python -m pip install "pyinstaller==6.22.2"

PYI=(
  python -m PyInstaller
  --noconfirm
  --clean
  --windowed
  --name "$NAME"
  --osx-bundle-identifier "$BUNDLE_ID"
  --collect-all customtkinter
  --add-data "examples:examples"
  --add-data "config.example.toml:."
)
if [ -n "${CODESIGN_IDENTITY:-}" ] && [ "$CODESIGN_IDENTITY" != "-" ]; then
  PYI+=(--codesign-identity "$CODESIGN_IDENTITY" --osx-entitlements-file "$ENTITLEMENTS")
fi
PYI+=(main.py)
"${PYI[@]}"

if [ ! -d "$APP" ]; then
  echo "missing $APP" >&2
  exit 1
fi

mkdir -p dist
if [ -n "${CODESIGN_IDENTITY:-}" ] && [ "$CODESIGN_IDENTITY" != "-" ]; then
  codesign --force --deep --timestamp --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --sign "$CODESIGN_IDENTITY" "$APP"
  codesign --verify --deep --strict "$APP"
  echo "developer-id" >"$MODE_FILE"
else
  if [ "${REQUIRE_DEVELOPER_ID:-}" = "1" ]; then
    echo "CODESIGN_IDENTITY is required on main" >&2
    exit 1
  fi
  codesign --force --deep --sign - "$APP"
  codesign --verify --deep "$APP"
  echo "adhoc" >"$MODE_FILE"
fi

rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"

if [ -n "${NOTARY_KEY_PATH:-}" ]; then
  set +x
  xcrun notarytool submit "$ZIP" \
    --key "$NOTARY_KEY_PATH" \
    --key-id "$NOTARY_KEY_ID" \
    --issuer "$NOTARY_ISSUER" \
    --wait
  xcrun stapler staple "$APP"
  xcrun stapler validate "$APP"
  rm -f "$ZIP"
  ditto -c -k --keepParent "$APP" "$ZIP"
  echo "developer-id-notarized" >"$MODE_FILE"
  rm -f "$NOTARY_KEY_PATH"
elif [ "${REQUIRE_DEVELOPER_ID:-}" = "1" ]; then
  echo "notary API key is required on main (APP_STORE_CONNECT_API_KEY / KEY_ID / ISSUER_ID)." >&2
  exit 1
fi

echo "$ZIP"
cat "$MODE_FILE"
