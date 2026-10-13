# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## Unreleased

## 0.1.0-beta.3 — 2026-10-12

* Fixed: starting `u2gui` with the controller switched off (only the 2.4G dongle plugged in) showed an
  "[Errno 5] Input/output error" dialog. It now says the controller is off or out of range and reads it as soon as it
  answers. Only a permission problem still opens a dialog.
* Fixed: RT and Home had swapped remap codes (`0x8000` is RT, `0x20000` is Home). Any profile saved by `u2gui` or
  `u2ctl` made RT act as Home and Home as RT; open the profile and use "Reset all buttons" (or fix RT/Home) once.
* `u2gui` is available in English and Brazilian Portuguese. It starts in the system language and the choice can be
  changed with the selector next to Backup or on the Profile page (saved in `~/.config/ultimate2/gui.json`). The command line is unchanged.
* The controller drawing is shaded like a moulded part (rounded, lit edges and raised buttons). The pink edition skin
  uses colours taken from a photo of the controller.
* The four extra buttons use the official names: L4/R4 (small shoulder buttons, `P3`/`P4`) are drawn beside LT/RT and
  can be remapped (L4 was missing), and the back paddles (`P2`/`P1`) are labelled PL/PR again.
* Home shows a pixel-art heart; it changes colour with the button like the other labels.
* The extra buttons send no input of their own, so the drawing lights them when the function they are mapped to
  arrives (e.g. L4 mapped to LB lights with LB). Mapped to None they cannot be seen on Linux.
* New default drawing in outline style (light strokes, no fills), like the controller diagrams. Editions without a
  skin of their own use it.
* The drawing style can be chosen on the Profile page (outline, automatic from the edition, black or pink), for
  controllers whose edition is not detected.
* The drawing follows the real shape of the Ultimate 2: outline, shoulders and button positions were traced from
  the silhouette of the official render (alpha channel only, `tools/trace_silhouette.py`; no artwork is included).
  The round button, the capsule-shaped profile button and the player LEDs are drawn too.

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
