# 8BitDo Ultimate 2 in the browser

*Português: [README.md](README.md)*

Configurator for the **8BitDo Ultimate 2** controller that runs in the browser over WebHID. It reads the configuration,
remaps buttons (including the back paddles and L4/R4), tunes sticks and triggers, changes the LED theme and colours and
writes everything to the controller's flash, checking it with a read-back.

## Why

*8BitDo Ultimate Software* only exists for Windows and macOS. To use the controller on Linux I reverse-engineered the
protocol and wrote [8bitdo-ultimate2-linux](https://github.com/MiguelSanzBr/8bitdo-ultimate2-linux) (the `u2ctl` CLI
and the `u2gui` interface, in Python). This project is the same thing in the browser: nothing to install besides the
udev rule, and the protocol is a faithful port of the Python code.

Not affiliated with 8BitDo. The protocol was reverse-engineered for interoperability.

## Architecture

DDD + hexagonal, without ceremony: the core does not know React, the DOM, `navigator` or WebHID exist.

```
adapters/      ui/ (React)   webhid.ts   gamepad-drain.ts   demo.ts
                    │ calls use cases         │ implement the ports
                    ▼                         ▼
application/   ConfigSession, ControllerLink    ports: ReportChannel, InputDrain
                    │
                    ▼
domain/        ConfigRecord, value objects, packet.ts, record.ts   (pure, no I/O)
```

- **domain/**: pure functions. `packet.ts` is the framing (port of `protocol.py`), `record.ts` the 1592-byte record
  codec (port of `config.py`), `config-record.ts` the aggregate with its invariants (always 1592 bytes, the CRC must
  match before any write), `values.ts` the ranges and names and `live-input.ts` turns the Gamepad API into the drawing.
- **application/**: use cases and ports. `ControllerLink` is the port of `device.py` (request/answer, 45-byte chunks,
  30 retries, commit) on top of the `ReportChannel` port. The joystick drain is a port too (`InputDrain`), started and
  stopped by `ConfigSession`.
- **adapters/**: WebHID, `GamepadDrain`, the simulated controller of the demo mode and the React screen, which only
  calls use cases.

Why: the protocol is the expensive part to get right and the part that must not break. Keeping it pure means it can be
tested byte by byte against the Python code without a browser, and the transport (WebHID, demo, maybe WebUSB) can change
without touching the core. The dependency rule is enforced by ESLint (`no-restricted-imports` and
`no-restricted-globals` per folder) and by a test (`src/architecture.test.ts`) that checks the rule catches each
violation.

## How it works

The config channel is a vendor HID collection (usage page `0xFF7A` on the controller, `0xFFA0` on the 2.4G dongle)
with output report `0x81` and input report `0x02`, 64 bytes including the id. Request `81 04` + header (`cmd`, `sub`,
`len`, CRC-16/MODBUS of the data, `total`, `offset`), answer `02 04` echoing the command. The whole record is 1592 bytes
(3 profiles, mapping, sticks, triggers, gyro, LEDs, macros) and travels in 45-byte chunks. Details in
[docs/PROTOCOL.md](https://github.com/MiguelSanzBr/8bitdo-ultimate2-linux/blob/main/docs/PROTOCOL.md) of the Linux repo.

IDs in Chrome's device picker: VID `0x2DC8`, PIDs `0x310B` (wired, XInput), `0x6012` (Ultimate 2) and `0x6013`
(2.4G dongle), on both config usage pages.

### The XInput quirk

The firmware only services the config endpoint while the host keeps draining the controller's joystick reports. On
Windows the XInput driver does that by itself. On Linux `xpad` only polls while someone holds `/dev/input/js*` open, so
the Python code keeps that node open during config I/O (`discovery.find_input_node`). Without it writes stall and only
a replug recovers.

A browser cannot open `js*`. The bet here: while the config session is open, the page keeps calling
`navigator.getGamepads()` every 16 ms (`GamepadDrain`, with `setInterval` because `requestAnimationFrame` stops in a
background tab), and Chrome, to answer it, keeps the joystick open and read. The drain starts **before** the channel is
opened and stops on disconnect. If the controller does not answer, the screen asks you to move a stick or press a
button and, if it keeps failing, to reconnect the controller.

**This is a hypothesis.** It has not been validated on the real controller. On Windows the expectation is that the
XInput driver already polls and the drain is not even needed, but that has not been checked either.

### Live button feedback

Like the desktop app: press the controller's buttons and they light up on the drawing. The button turns purple and
sinks quickly, fading out on release; triggers fill with the pull and sticks show where the thumb went. With
`prefers-reduced-motion` only the colour changes.

It reuses the drain's polling: `GamepadDrain` runs `getGamepads()` through the domain's `readPad` (`live-input.ts`, the
W3C `standard` layout, which is positional and therefore works for XInput and Switch) and only notifies on change. The
screen redraws just the controller, at most once per frame (`requestAnimationFrame`). On the landing page the drawing
also lights up if the browser already sees the controller, no WebHID needed. In demo mode, holding a click on a part of
the drawing simulates the press.

Gamepad API limits:

- PL/PR, L4/R4 and ★ are not exposed by the Gamepad API, so they never light up. There is no fake for them.
- Chrome only exposes the gamepad after the first button press with the page open, hence the hint under the drawing.
- What lights up is what the controller sends, profile remap included: with A mapped to B, pressing A is expected to light B.
- Without the `standard` mapping (a driver Chrome does not recognise) nothing lights up, rather than the wrong button.
- The 8BitDo is picked by vendor `2dc8` in the `id`; otherwise the first connected gamepad is used.

### Write safety

1. Connecting reads everything first (info, record, theme). You can download a `.bin` backup (same format as
   `u2ctl backup`, restore it with `u2ctl restore`).
2. Edits stay on screen. Nothing goes to the controller before the review.
3. "Revisar e gravar" builds the plan: encode only rewrites changed fields (unknown bytes come back untouched), checks
   ranges (stick 0 to 128, trigger 0 to 255, known button function, `#rrggbb` colour) and recomputes `crc_value`.
4. A dialog lists each change (before → after). Only the "Gravar no controle" button confirms the plan, and a
   confirmation is single use.
5. Before writing, the aggregate checks size and CRC. A record that does not validate is never sent.
6. It writes, sends the `0x123` commit to flash, reads the 1592 bytes back and compares. A mismatch is an error and the
   LED theme is left alone.

## Tests

Vitest + Testing Library (unit and screen) and Playwright (demo mode E2E). Real TDD: in the history each unit has a
`Teste: ...` commit with the failing test before the implementation commit, and structural changes are in
`Refatoração: ...` commits, green before and after. Expected bytes come from running the Python code (commit `af02fde`)
and are pasted as literals, each with a comment naming the function it mirrors.

| Guarantee | Test |
|---|---|
| CRC-16/MODBUS, request building and answer parsing match the Python code byte by byte | `src/domain/packet.test.ts` |
| record decode/encode equal to Python (new profile, remap, name, features, colour, CRC) | `src/domain/record.test.ts` |
| encode without edits returns the same bytes; an edit only touches that field | `record.test.ts` (20 random records) |
| a record with a wrong CRC or size is never written | `config-record.test.ts`, `config-session.test.ts` |
| out-of-range values are rejected before becoming bytes | `values.test.ts`, `config-record.test.ts`, `App.test.tsx` |
| nothing is written without confirmation; a confirmation is single use | `config-session.test.ts`, `App.test.tsx` |
| a read-back that differs from what was written is an error | `config-session.test.ts` (`corruptCommit`), `App.test.tsx` |
| the drain starts before the channel, stays on for the whole session and stops at the end | `config-session.test.ts` "Connect", `gamepad-drain.test.ts` with a fake `getGamepads` |
| without the drain the simulated controller stays silent and the screen says what to do | `demo.test.ts`, `App.test.tsx` |
| 30 retries, timeouts and commit as in `device.py` | `src/application/link.test.ts` |
| WebHID: VID/PID/usage page filters, separate report id, open errors mention the udev rule | `src/adapters/webhid.test.ts` |
| Gamepad API to lit drawing: positional standard layout, analog triggers, dead zone, vendor 2dc8 | `src/domain/live-input.test.ts` |
| the drain only notifies on change; the drawing lights up on the landing page, connected and in demo by pointer | `gamepad-drain.test.ts`, `App.test.tsx`, `e2e/demo.spec.ts` |
| domain and application do not import adapters, React or the DOM | `src/architecture.test.ts` + ESLint |
| full flow in Chrome: demo, read, remap, confirm, see it applied; 375px without horizontal scroll | `e2e/demo.spec.ts` |

### Coverage

v8 coverage with a 100% threshold on statements, branches, functions and lines over `src/`; below that
`npm run coverage` fails and so does CI. Current result: 182 tests, statements 871/871, branches 464/464,
functions 258/258, lines 703/703.

Excluded, each with the reason in `vite.config.ts`:

- `src/main.tsx`: bootstrap, only mounts `<App/>` on `#root`; the E2E covers it.
- `src/application/ports.ts` and `src/domain/types.ts`: type declarations only, no JS left to measure.
- `src/vite-env.d.ts`: Vite type reference.
- `src/test/**` and the `*.test.*` files themselves.

### Mutation testing (manual)

I broke the main protections on purpose, ran the suite and restored them:

| Mutation | Result |
|---|---|
| `recordProblem` accepts any CRC | 3 tests failed (`record`, `config-record`, `config-session`) |
| `applyChanges` ignores the confirmation | 2 tests failed (`config-session`) |
| screen writes straight from "Revisar e gravar", skipping the dialog | 6 tests failed (`App.test.tsx`) |
| `ConfigSession.connect` does not start the drain | 35 tests failed (session, screen, wiring) |
| adapter import inside `domain/` | ESLint reported `no-restricted-imports` |

## Running

Needs Node 24.

```bash
npm install
npm run dev          # http://localhost:5176/8bitdo-ultimate2-linux/
npm run lint && npm run typecheck
npm run coverage     # fails below 100%
npm run e2e          # build + preview on 4176 + Playwright (chromium)
npm run build
docker compose up --build   # built site on nginx at http://localhost:8090/8bitdo-ultimate2-linux/
```

GitHub Pages deploy is in `../.github/workflows/pages.yml` (base `/8bitdo-ultimate2-linux/`).

### Linux: udev rule

Chrome opens the controller through hidraw, and without permission `open()` fails. Install the same rule as the Linux
repo and replug the controller:

```bash
echo 'KERNEL=="hidraw*", ATTRS{idVendor}=="2dc8", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/70-8bitdo-u2.rules
sudo udevadm control --reload && sudo udevadm trigger --action=add --subsystem-match=hidraw
```

The name starts with `70-` because it must sort before `73-seat-late.rules`, which turns `uaccess` into an ACL.

## Ported and not ported

Ported: framing and CRC, the full record codec (every field decodes and encodes back unchanged, macros and gyro
included), the app's new-profile defaults, info (firmware, beta, PID), LED theme, read and write with retries and
commit, read-back verification, `.bin` backup.

Editable on screen: profiles (create with the app defaults, rename), the 22 buttons, stick dead zone and range,
trigger ranges, the 8 options (invert axes, swap sticks/triggers/d-pad, trigger rumble), LED theme and the dynamic
theme colours.

The screen follows the desktop app's layout: the same controller drawing (ported from `geometry.py` to SVG) with
clickable callouts that jump to the field, one tile per category (Buttons, Sticks, Triggers, LEDs, Profile), profile
tabs on top and a bar with the number of staged changes. Light and dark themes, following the system with a toggle.
With staged changes the browser asks before closing or reloading the tab, and everything works from the keyboard (Tab
shows focus, there is a skip-to-content link and the review keeps focus inside the dialog).

Not ported (bytes are preserved, there is just no screen): macro editor, gyro (six-axis), rumble strength, trigger
rumble range, hotwheel colours and the 24 custom LEDs, changing `gamepad_mode`. Also left out: edition/colourway query
(`81 05`), status of the controller behind the dongle (battery), active profile polling, backup restore (use
`u2ctl restore`), partial writes (`changed_span`; this writes the whole record like `u2ctl apply`)
and an English UI.

## Known limits

- Desktop Chrome and Edge only (WebHID). Other browsers get a warning and the demo mode.
- Draining via `getGamepads()` is a hypothesis and **has not been validated on hardware**. Chrome may only expose the
  gamepad after a button press, and in a background tab `setInterval` is throttled to once per second. If it stalls,
  replug.
- **This web version has not run against the real controller yet.** Everything was tested against the simulated
  controller, a port of the Python `tests/fake_device.py`. The protocol itself was verified on hardware (firmware 1.10,
  wired) by the Linux project.
- Live button feedback was only tested with a fake `getGamepads()` (unit and E2E), **not with the real controller**.
  The `standard` mapping in Switch mode and the Home index depend on Chrome recognising the controller.
- 2.4G dongle: not tested by the Linux project either.
- As in Python, answers are matched by command only, not by offset. A late answer for another chunk could land in the
  wrong place; the final read-back catches that when writing, but not on the initial read.
- Deliberate differences from Python: ranges checked before encoding, a name that does not fit in 32 bytes is rejected
  (in Python the `bytearray` would grow and `write_config`'s `assert` would stop it), and reports are turned back on even
  when a write chunk fails.
- Float rounding of rumble strength on an exact tie (e.g. `0.03125`) gives `0.0313` here and `0.0312` with Python's
  `round()`. Display only; unedited bytes come back unchanged.

## License

[MIT](LICENSE), Copyright (c) 2026 Miguel Sanz Boragan.
