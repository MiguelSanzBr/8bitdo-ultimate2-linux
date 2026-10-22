#!/bin/sh
# Build dist/ultimate2_<version>_all.deb (needs dpkg-deb; run from anywhere).
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | sed 's/b\([0-9]*\)$/~beta\1/')
PKG=ultimate2
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
DEST="$STAGE/${PKG}_${VERSION}_all"

install -d "$DEST/DEBIAN" "$DEST/usr/bin" "$DEST/usr/lib/python3/dist-packages" "$DEST/usr/lib/systemd/user" \
    "$DEST/usr/lib/udev/rules.d" "$DEST/usr/share/applications" \
    "$DEST/usr/share/icons/hicolor/scalable/apps" "$DEST/usr/share/doc/$PKG"

# python package (no caches)
cp -r "$ROOT/src/ultimate2" "$DEST/usr/lib/python3/dist-packages/"
find "$DEST/usr/lib/python3/dist-packages" -name __pycache__ -prune -exec rm -rf {} +
find "$DEST/usr/lib/python3/dist-packages" -type d -exec chmod 755 {} +
find "$DEST/usr/lib/python3/dist-packages" -type f -exec chmod 644 {} +

for cmd in u2ctl:ultimate2.cli u2gui:ultimate2.gui.app; do
    name=${cmd%%:*}; mod=${cmd#*:}
    printf '#!/usr/bin/python3\nimport sys\nfrom %s import main\nsys.exit(main())\n' "$mod" > "$DEST/usr/bin/$name"
    chmod 755 "$DEST/usr/bin/$name"
done

install -m 644 "$ROOT/udev/70-8bitdo-u2.rules" "$DEST/usr/lib/udev/rules.d/"
install -m 644 "$ROOT/packaging/ultimate2-keepalive.service" "$DEST/usr/lib/systemd/user/"
install -m 644 "$ROOT/packaging/u2gui.desktop" "$DEST/usr/share/applications/"
install -m 644 "$ROOT/packaging/ultimate2.svg" "$DEST/usr/share/icons/hicolor/scalable/apps/"
install -m 644 "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$DEST/usr/share/doc/$PKG/"
install -m 644 "$ROOT/LICENSE" "$DEST/usr/share/doc/$PKG/copyright"

SIZE=$(du -sk "$DEST/usr" | cut -f1)
cat > "$DEST/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-tk
Installed-Size: $SIZE
Maintainer: Miguel Sanz <123277580+MiguelSanzBr@users.noreply.github.com>
Homepage: https://github.com/MiguelSanzBr/8bitdo-ultimate2-linux
Description: Linux configurator for the 8BitDo Ultimate 2 Wireless controller
 Open-source replacement for the configuration part of 8BitDo Ultimate
 Software: button remapping, sticks, triggers, rumble, gyro, LED rings,
 profiles and backups. Provides the u2ctl command and the u2gui interface.
 Not affiliated with 8BitDo.
EOF

cat > "$DEST/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger --subsystem-match=hidraw --subsystem-match=usb 2>/dev/null || true
    systemctl --global enable ultimate2-keepalive.service 2>/dev/null || true   # starts at the next login
    command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
    command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
EOF
cat > "$DEST/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
udevadm control --reload-rules 2>/dev/null || true
if [ "$1" = remove ] || [ "$1" = purge ]; then
    systemctl --global disable ultimate2-keepalive.service 2>/dev/null || true
fi
EOF
chmod 755 "$DEST/DEBIAN/postinst" "$DEST/DEBIAN/postrm"

mkdir -p "$ROOT/dist"
fakeroot dpkg-deb --build "$DEST" "$ROOT/dist/${PKG}_${VERSION}_all.deb" >/dev/null 2>&1 \
    || dpkg-deb --root-owner-group --build "$DEST" "$ROOT/dist/${PKG}_${VERSION}_all.deb"
echo "$ROOT/dist/${PKG}_${VERSION}_all.deb"
