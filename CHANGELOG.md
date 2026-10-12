# Changelog

This project follows [Semantic Versioning](https://semver.org/).

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
