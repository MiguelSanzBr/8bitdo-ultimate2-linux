# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## Unreleased

* `u2gui` is available in English and Brazilian Portuguese. It starts in the system language and the choice can be
  changed on the Profile page (saved in `~/.config/ultimate2/gui.json`). The command line is unchanged.

## 0.1.0-beta.2 — 2026-10-12

* The udev rule is now `70-8bitdo-u2.rules`. As `99-…` it sorted after systemd's `73-seat-late.rules`, so the
  `uaccess` tag never became an ACL and users got "permission denied" on the hidraw node.
* The home-page callouts with more than one word ("Analógico esquerdo", "Botões ABXY", …) now respond to
  clicks. Tk splits canvas tags at spaces, so their bindings never matched.

## 0.1.0-beta.1 — 2026-10-12

First public beta.

* Reverse-engineered configuration protocol of the 8BitDo Ultimate 2 Wireless (documented in `docs/PROTOCOL.md`).
* `u2ctl`: info, list, dump/apply JSON, new-slot, LED theme, backup/restore. Writes are verified.
* `u2gui`: dark interface modelled on the official app. It includes a live controller drawing (pressed buttons,
  sticks, triggers, LED effects), skins by controller edition (lilac edition 3), button remapping on the drawing,
  sticks/triggers/rumble/gyro pages, an inline colour wheel, auto-save with partial writes, active-profile tracking
  and backups.
* udev rule for user access to the hidraw node; `.deb` package (`packaging/build-deb.sh`).
* Firmware emulator and a test suite with 100% line and branch coverage.
