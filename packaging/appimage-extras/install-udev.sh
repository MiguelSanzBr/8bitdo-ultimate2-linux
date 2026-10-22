#!/bin/sh
# Installs the udev rule that lets you open the 8BitDo Ultimate 2 (needed once; an AppImage cannot do it itself).
# Run it from the folder of the download, then unplug and replug the controller.
set -eu

DIR=$(cd "$(dirname "$0")" && pwd)
SELF="$DIR/$(basename "$0")"
RULE="$DIR/70-8bitdo-u2.rules"
DEST=/etc/udev/rules.d/70-8bitdo-u2.rules

if [ ! -f "$RULE" ]; then
    echo "70-8bitdo-u2.rules must be in the same folder as this script." >&2
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        exec sudo sh "$SELF"
    elif command -v pkexec >/dev/null 2>&1; then
        exec pkexec sh "$SELF"
    fi
    echo "Run this script as root, for example: sudo sh $SELF" >&2
    exit 1
fi

install -D -m 644 "$RULE" "$DEST"
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger --action=add --subsystem-match=hidraw --subsystem-match=usb 2>/dev/null || true
echo "Rule installed in $DEST."
echo "Now unplug and replug the controller (or its 2.4G adapter)."
