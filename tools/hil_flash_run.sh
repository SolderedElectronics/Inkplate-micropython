#!/bin/bash
# Flash + sync + run one example for a given Inkplate board, for manual HIL testing
# (docs/hil_checklist.md). Reads boards/<board>/package.json's "urls" list to know
# exactly which files that board needs on-device -- same info package.json already
# tracks for the web installer, so there's one source of truth instead of a
# hand-maintained file list per board.
#
# Usage: tools/hil_flash_run.sh <board_dir> [example_relpath] [port]
#   board_dir       e.g. inkplate4tempera, inkplate6plusv2, inkplate6flick
#   example_relpath path under examples/<board_dir>/, default: basic_grayscale.py
#   port            serial port, default: auto-detected /dev/cu.wchusbserial*
#
# Examples:
#   tools/hil_flash_run.sh inkplate4tempera
#   tools/hil_flash_run.sh inkplate6plusv2 touchscreen.py
#   tools/hil_flash_run.sh inkplate6flick displayimagesd/display_image_sd.py

set -euo pipefail

BOARD_DIR="${1:?usage: $0 <board_dir> [example_relpath] [port]}"
EXAMPLE_RELPATH="${2:-basic_grayscale.py}"
PORT="${3:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MICROPYTHON_ESP32_DIR="$HOME/Documents/GitHub/micropython/ports/esp32"
IDF_ACTIVATE="$HOME/.espressif/tools/activate_idf_v5.5.2.sh"
USER_C_MODULES="$REPO_ROOT/firmware/usermods/inkplate"

PACKAGE_JSON="$REPO_ROOT/boards/$BOARD_DIR/package.json"
EXAMPLE_PATH="$REPO_ROOT/examples/$BOARD_DIR/$EXAMPLE_RELPATH"

# Inkplate13SPECTRA is the one board on ESP32-S3 (octal PSRAM); every other
# board here is classic ESP32. See docs/refactor_plan.md HIL log for the
# confirmed-working S3 BOARD/BOARD_VARIANT combo.
if [ "$BOARD_DIR" = "inkplate13spectra" ]; then
    MP_BOARD=ESP32_GENERIC_S3
    MP_BOARD_VARIANT=SPIRAM_OCT
else
    MP_BOARD=ESP32_GENERIC
    MP_BOARD_VARIANT=SPIRAM
fi

if [ ! -f "$PACKAGE_JSON" ]; then
    echo "error: no such board: $PACKAGE_JSON not found" >&2
    exit 1
fi
if [ ! -f "$EXAMPLE_PATH" ]; then
    echo "error: no such example: $EXAMPLE_PATH not found" >&2
    exit 1
fi

if [ -z "$PORT" ]; then
    PORT="$(ls /dev/cu.wchusbserial* 2>/dev/null | head -1)"
    if [ -z "$PORT" ]; then
        echo "error: no /dev/cu.wchusbserial* found, pass a port explicitly" >&2
        exit 1
    fi
fi
echo "== board=$BOARD_DIR ($MP_BOARD/$MP_BOARD_VARIANT) example=$EXAMPLE_RELPATH port=$PORT =="

echo "== flashing firmware =="

# IDF's activate script refuses to run unless it sees $0 look like a shell name
# (its is-sourced check inspects ${0##*/}), which breaks when `source`d from
# inside another script's subshell -- $0 there is still this script's path, not
# "bash". Run it in a nested `bash -c` instead: $0="bash" satisfies the check,
# real args passed positionally from $1 onward.
bash -c '
    set -e
    cd "$1"
    set +u
    # shellcheck disable=SC1090
    source "$2"
    set -u
    export PATH="$IDF_PATH/tools:$PATH"
    make BOARD="$3" BOARD_VARIANT="$4" \
        USER_C_MODULES="$5" \
        PORT="$6" deploy
' bash "$MICROPYTHON_ESP32_DIR" "$IDF_ACTIVATE" "$MP_BOARD" "$MP_BOARD_VARIANT" "$USER_C_MODULES" "$PORT"
echo "== removing known-obsolete on-device modules (harmless if already gone) =="
mpremote connect "$PORT" fs rm inkplate_gs.py inkplate_mono.py inkplate_partial.py mcp23017.py 2>/dev/null || true

echo "== syncing board+shared modules from boards/$BOARD_DIR/package.json =="
python3 - "$PACKAGE_JSON" <<'PYEOF' | while IFS=$'\t' read -r src dest; do
import json, sys
data = json.load(open(sys.argv[1]))
for dest, url in data["urls"]:
    # url looks like "github:SolderedElectronics/Inkplate-micropython/boards/x/y.py"
    repo_path = url.split("Inkplate-micropython/", 1)[1]
    print(f"{repo_path}\t{dest}")
PYEOF
    echo "  $src -> :$dest"
    mpremote connect "$PORT" fs cp "$REPO_ROOT/$src" ":$dest"
done

echo "== resetting board =="
mpremote connect "$PORT" reset
sleep 6

echo "== running $EXAMPLE_RELPATH =="
mpremote connect "$PORT" run "$EXAMPLE_PATH"
