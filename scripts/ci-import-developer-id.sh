#!/usr/bin/env bash
# Import a base64 Developer ID .p12 into an ephemeral keychain for GitHub Actions.
# Does not print the certificate or password. Writes CODESIGN_IDENTITY to GITHUB_ENV.
set -euo pipefail
set +x

if [ -z "${MACOS_CERTIFICATE:-}" ]; then
  if [ "${REQUIRE_DEVELOPER_ID:-}" = "1" ]; then
    echo "MACOS_CERTIFICATE is required on main (base64 Developer ID Application .p12)." >&2
    echo "Create the cert in Apple Developer, then: base64 -i cert.p12 | gh secret set MACOS_CERTIFICATE -R cgfixit/KB-PORTABLE-DASH" >&2
    exit 1
  fi
  echo "no Developer ID secret; ad-hoc sign"
  exit 0
fi

for name in MACOS_CERTIFICATE_PWD APPLE_TEAM_ID APP_STORE_CONNECT_API_KEY APP_STORE_CONNECT_KEY_ID APP_STORE_CONNECT_ISSUER_ID; do
  if [ -z "${!name:-}" ]; then
    echo "$name is required when MACOS_CERTIFICATE is set." >&2
    exit 1
  fi
done

TMP="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
P12="$TMP/developer-id.p12"
KEYCHAIN="$TMP/kb-signing.keychain-db"
P8="$TMP/AuthKey.p8"
KEYCHAIN_PWD="$(uuidgen)"

printf '%s' "$MACOS_CERTIFICATE" | base64 --decode >"$P12"
printf '%s' "$APP_STORE_CONNECT_API_KEY" | base64 --decode >"$P8"

security create-keychain -p "$KEYCHAIN_PWD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PWD" "$KEYCHAIN"
security import "$P12" -P "$MACOS_CERTIFICATE_PWD" -A -t cert -f pkcs12 -k "$KEYCHAIN" >/dev/null
security set-key-partition-list -S apple-tool:,apple: -s -k "$KEYCHAIN_PWD" "$KEYCHAIN" >/dev/null
security list-keychains -d user -s "$KEYCHAIN"

IDENTITY="$(security find-identity -v -p codesigning "$KEYCHAIN" | awk -F'"' '/Developer ID Application/{print $2; exit}')"
if [ -z "$IDENTITY" ]; then
  echo "imported .p12 has no Developer ID Application identity" >&2
  exit 1
fi

rm -f "$P12"

if [ -n "${GITHUB_ENV:-}" ]; then
  {
    echo "CODESIGN_IDENTITY=$IDENTITY"
    echo "NOTARY_KEY_PATH=$P8"
    echo "NOTARY_KEY_ID=$APP_STORE_CONNECT_KEY_ID"
    echo "NOTARY_ISSUER=$APP_STORE_CONNECT_ISSUER_ID"
    echo "APPLE_TEAM_ID=$APPLE_TEAM_ID"
  } >>"$GITHUB_ENV"
fi
echo "imported Developer ID Application identity"
