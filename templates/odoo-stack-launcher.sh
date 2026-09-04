#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

readonly INSTALLER_URL="__INSTALLER_URL__"
readonly INSTALLER_SHA256="__INSTALLER_SHA256__"
readonly INSTALLER_RELEASE="__INSTALLER_RELEASE__"
TEMP_ROOT=""

log() {
    printf '[able-living-install] %s\n' "$*"
}

fail() {
    log "ERROR: $*" >&2
    exit 1
}

cleanup() {
    local status=$?

    if [ -n "$TEMP_ROOT" ] && [ -d "$TEMP_ROOT" ]; then
        rm -rf -- "$TEMP_ROOT"
    fi
    exit "$status"
}
trap cleanup EXIT

for command in curl mktemp sha256sum; do
    command -v "$command" >/dev/null 2>&1 \
        || fail "$command is required to download the installer"
done

TEMP_ROOT=$(mktemp -d /tmp/able-living-install.XXXXXX)
readonly INSTALLER_PATH="$TEMP_ROOT/odoo-stack-install.sh"

log "downloading Odoo Stack installer release $INSTALLER_RELEASE"
curl --fail --silent --show-error --location \
    --proto '=https' --tlsv1.2 \
    "$INSTALLER_URL" \
    --output "$INSTALLER_PATH"

printf '%s  %s\n' "$INSTALLER_SHA256" "$INSTALLER_PATH" | sha256sum -c -
chmod 0700 "$INSTALLER_PATH"

if [ "$(id -u)" -eq 0 ]; then
    bash "$INSTALLER_PATH" "$@"
else
    command -v sudo >/dev/null 2>&1 \
        || fail "run this command as root or install sudo"
    sudo bash "$INSTALLER_PATH" "$@"
fi
