# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## 0.1.0-beta.8 — 2026-10-22

* Support for the **8BitDo Ultimate 2.4G Wireless Controller** (Xbox layout, X / D switch), over a USB cable or its
  2.4G receiver, as the `ULTIMATE_24G` model. Reverse-engineered from *Ultimate Software V1* (`8BitDoAdvance.dll`) and
  USBPcap captures of it; tested on a real pad, firmware 2.04, receiver 1.10.
  * With the switch on D a cable gives its config channel straight away (`2dc8:3012`). On X (`2dc8:3106`) `u2ctl`
    and `u2gui` send what Windows sends (xusb22's connect packets and the rumble knock, over usbfs) to reach the X
    configuration (`3012` / `3013`) and switch it back afterwards; the udev rule now also gives access to that USB
    node.
  * Over Bluetooth it has no configuration channel: `u2ctl` and `u2gui` say so.
  * New model fields: `header_crc`, `reports`, `colorway`, `echo_offset`, `own_slot`, `save_wait`, `layout`;
    `knock` says how the pad is switched (`"rumble"` or `"usb"`). `config.decode`/`encode`/`default_slot` take the
    model's layout, `config.same` verifies a write without the bytes the firmware owns.
  * `2dc8:3106` is shared with other 8BitDo XInput pads and receivers: one that does not switch is left alone
    afterwards (until it is replugged), so `u2gui`'s retries do not keep rumbling it.
  * Protocol notes: `docs/ULTIMATE_24G.md` and a summary at the end of `docs/PROTOCOL.md`.
  * Contributed by @alexandreafz (#10–#14).
* Ultimate 2.4G over Bluetooth: `u2ctl battery` (also in `u2ctl list`) and the `u2gui` badge show its battery (the
  kernel's `power_supply` of the HID pad); `u2gui` shows read-only the D configuration kept from the last cable read
  (the one Bluetooth uses), and `u2ctl info` and `u2gui` warn when the X configuration is edited while the pad is on
  Bluetooth.
* `u2ctl` speaks Brazilian Portuguese when the system does (messages, help, argparse's own words and device errors;
  `ultimate2.mensagens`), like `u2gui`. English stays the source text.
* `u2ctl keepalive`: keeps Ultimate 2.4G pads on X read, as Windows does, so a profile change through the receiver no
  longer switches the controller off when no game is open. The .deb installs it as the systemd user service
  `ultimate2-keepalive` and enables it for every user once (an administrator's `systemctl --global disable` stays).
* `u2gui`'s live view honours a `jscal` remap of the joystick node (#15, #16).
* The Backup / Restore file dialogs follow the window's colours, offer `*.bin` and hide hidden files.

## 0.1.0-beta.7 — 2026-10-20

* Support for the 1st-gen **8BitDo Ultimate Bluetooth Controller** (charging dock, Nintendo layout), on a USB cable
  straight to the PC. Reverse-engineered from a USB capture of *Ultimate Software V1*, which is the app that
  configures it (V2 no longer detects it); tested on a real pad, firmware 1.02.
  * `u2ctl` switches the pad to its config mode (a rumble sequence through `xpad`'s force feedback, no root needed)
    and back on every command: `info`, `dump`, `apply`, `new-slot`, `backup`, `restore`.
  * `u2gui` keeps it in config mode while the window is open and adapts to it: Nintendo face layout, back paddles
    P1/P2, no L4/R4, no gyro, LED or trigger-rumble pages, live view through the pad's own state query.
  * Now and then the pad powers off while switching modes; pressing Home brings it back and it is picked up again.
  * Protocol notes: `docs/ULTIMATE_BT.md` and a summary at the end of `docs/PROTOCOL.md`.
  * Contributed by @thiagonl (#7).
* `u2gui web` opens the browser version (WebHID). Its source moved into `web/` of this repository and it is served at <https://miguelsanzbr.github.io/8bitdo-ultimate2-linux/>.
* Internal: one `models.Model` per controller holds everything that differs between them.

## 0.1.0-beta.6 — 2026-10-15

* Flatpak: AppStream metadata, desktop entry and icon under the app ID `io.github.miguelsanzbr._8bitdo-ultimate2-linux` (`packaging/flatpak/`), ready for a
  Flathub submission. The Flatpak build bundles Tcl/Tk 8.6 and tkinter, which the Freedesktop runtime lacks.

## 0.1.0-beta.5 — 2026-10-15

* AppImage for any distribution: `ultimate2-appimage.zip` on the Releases page holds the AppImage, `install-udev.sh`
  (installs the udev rule once, with sudo or pkexec), the rule and a short notice. Built by the manual `appimage`
  workflow (python-appimage), as in the GameSir Cyclone 2 configurator.
* Arch Linux package: `packaging/aur/PKGBUILD` (package `8bitdo-ultimate2`), with a built `.pkg.tar.zst` on the
  Releases page.

## 0.1.0-beta.4 — 2026-10-12

* The drawing is in outline style by default. The colour (black, pink, or automatic from the edition) is chosen
  in a drop-down on the Profile page.

* The d-pad is one rounded cross: arms with round ends, no seams between them, larger arrows.

* Pink skin: the red flower around Home is gone; Home is pink with a white heart.

* The home screen shows a connection badge instead of the text line: a green Wi-Fi sign and, through the 2.4G
  dongle, the battery level (red at 15% or less, refreshed with the profile poll); a grey Wi-Fi with a red X when the
  controller does not answer. The firmware number moved to the bottom-right corner.
* Through the dongle the firmware and edition are the controller's own (they were the dongle's, so the pink edition
  showed as edition 0 and firmware 1.06). `u2ctl info` prints the controller's firmware, battery and colorway too.

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
