# 8BitDo Ultimate 2 Wireless — configuration protocol

This was reverse-engineered from *8BitDo Ultimate Software V2* (v1.37) for interoperability. The sources were
`8BitDoAdvance.dll` (native, analysed with objdump and Ghidra through REA) and the app's .NET assemblies
(decompiled with ILSpy). Everything below was verified against a real controller, firmware 1.10.

## Devices

| USB ID | What | Config interface |
|---|---|---|
| `2dc8:310b` | controller over USB (XInput mode) | HID interface 2, usage page `0xFF7A` |
| `2dc8:6013` | 2.4G dongle (`Ultimate2RR`) | HID interface 0, usage page `0xFFA0` |
| `0x6012` | PID the controller reports internally (`PID_Ultimate2`) | — |

The config channel is a vendor HID collection with output report `0x81` and input report `0x02`, 63 bytes
each (64 including the report ID). On Linux it shows up as a `/dev/hidrawN` node.

> **Linux quirk.** The firmware only services the config endpoint while the host keeps draining the controller's
> XInput reports. Windows' XInput driver always does that. On Linux, `xpad` only polls while a program has the
> joystick open, so a tool must keep `/dev/input/jsN` (or `eventN`) of the same device open during config I/O.
> Otherwise writes stall with `ETIMEDOUT` and only a replug recovers the endpoint.

## Frames

All numbers are little endian.

```
request : 81 04 | u16 cmd | u16 sub | u16 len | u16 crc | u32 total | u32 offset | data[len]   (≤ 45 bytes)
answer  : 02 04 | u16 4   | u16 cmd | u16 len | u16 crc | u32 total | u32 offset | data[len]
```

* `crc` is CRC-16/MODBUS (reflected polynomial `0xA001`, init `0xFFFF`) of `data`. Header-only commands send `0`.
* Reads send `len` = the requested chunk size with zero-filled data.
* There are also fixed short queries (`81 05 …`) whose answers start with `02 05` or `02 22`.

## Commands

| cmd | sub | Meaning | Answer |
|---|---|---|---|
| `0x0001` (bytes `00 01`) | — | device info | data: `u16 firmware×100`, `u8 beta`, `…`, `u16 pid` at data offset 4 |
| `2` | 0 | read `len` bytes of the config record at `offset` (`total` = 1592) | the bytes |
| `1` | 0 | write `data` at `offset` | header echo; `len` = accepted bytes |
| `6` | `0x123` | commit the record to flash | header echo, within ~3 s |
| `7` | 0/1 | input reports off/on (the app wraps writes with it) | header echo |
| `0x40` | theme | set active LED theme: 2 dynamic, 3 hotwheel, 4 custom, 5 off | header echo |
| `0x41` | — | get active LED theme | data[0] = theme |
| `0x0120` (dongle) | — | is a controller connected? | data[0] = 1 if yes |
| `81 05 00 21 01` | fixed query | version and edition | `02 22`, `u16 fw`, `u8 beta`, …, byte 6 = **edition** (`m_ControllerColor`) |

The active profile ("current slot") is `cur_slot` in the record header. The app reads it with a 20-byte read at
offset 0.

The app writes one setting by sending only that setting's bytes (for example `writeUltimate2dynamic` writes 12
bytes at `0x4b8 + 12·slot`) followed by a commit. It never refreshes `crc_value` on those partial writes, so the
firmware does not validate it.

## Config record (1592 bytes)

`custom_config_record_t_u2`, MSVC natural alignment, three profile slots (`s` = 0..2):

| Offset | Size | Field |
|---|---|---|
| `0 + 4s` | 4 | slot flag: `0x20200911` enabled, `0x20190000` disabled, `0` deleted, `0xffffffff` erased |
| 12 | 4 | `crc_value` (CRC-16/MODBUS of the record) |
| 16 | 2 | `gamepad_mode`: 0 Switch, 1 Android, 3 Windows/XInput |
| 18 | 2 | `cur_slot`: active profile (3 = default, no custom profile) |
| `20 + 32s` | 32 | profile name, UTF-16BE, max 16 chars |
| `116 + 12s` | 12 | rumble: flag, `float left`, `float right` (0..1) |
| `152 + 8s` | 8 | sticks: flag, left start/end, right start/end (0..128) |
| `176 + 8s` | 8 | triggers: flag, LT start/end, RT start/end (0..255) |
| `200 + 8s` | 8 | special: flag, feature bits |
| `224 + 92s` | 92 | mapping: flag, 22 × u32 key codes |
| `500 + 216s` | 216 | macros: flag, count, 4 × 52-byte records (name, mode, steps, offset, trigger key, cycles, interval) |
| `1148 + 8s` | 8 | trigger rumble range (percent) |
| `1172 + 12s` | 12 | six-axis: flag, activation key, trigger mode, sensitivity, dead compensation, mapping type |
| `1208 + 12s` | 12 | LED dynamic: flag, colour, background (`0x00RRGGBB`) |
| `1244 + 16s` | 16 | LED hotwheel: flag, colour, background, speed (1..15) |
| `1292 + 100s` | 100 | LED custom: flag, 24 colours |

Every section has its own flag; a section is used only when its flag is `0x20200911`.

### Button order of `mapping` (physical buttons)

`A B X Y LB RB LT RT L3 R3 Select Start Star Home Up Down Left Right P1 P2 P3 P4`. On the Ultimate 2 Wireless the two
back buttons, printed L4 and R4, are `P2` (left) and `P1` (right); the app also defines `P3`/`P4` for other models.
In XInput mode the back buttons have no code of their own: they report the function they are mapped to (LB/RB by
default), which is why a press of L4 shows up as LB.

### Key codes (function assigned to a button)

| Code | Fn | Code | Fn | Code | Fn |
|---|---|---|---|---|---|
| `0x1` | Start | `0x200` | Up | `0x100000` | P5 |
| `0x2` | L3 | `0x400` | LB | `0x200000` | P3 |
| `0x4` | R3 | `0x800` | RB | `0x400000` | Screenshot |
| `0x8` | Select | `0x1000` | B | `0x800000` | Turbo (single) |
| `0x10` | X | `0x2000` | A | `0x1000000` | Turbo (auto) |
| `0x20` | Y | `0x4000` | LT | `0x2000000` | P1 |
| `0x40` | Right | `0x8000` | RT | `0x4000000` | P2 |
| `0x80` | Left | `0x10000` | Menu | `0x40000000` | P4 |
| `0x100` | Down | `0x20000` | Home | `0x080000xx` | stick directions |

`0` means disabled. Stick directions: RS Up/Down/Left/Right = `0x08000001/02/04/08`, LS = `0x08000010/20/40/80`.

### Feature bits

`0x1` invert LS X, `0x2` invert LS Y, `0x4` invert RS X, `0x8` invert RS Y, `0x10` swap sticks, `0x80` swap
triggers, `0x100` swap LS/d-pad, `0x8000` trigger rumble. Other bits are not fully understood; tools must preserve them.

## Live input

With `xpad`, `/dev/input/jsN` reports 11 buttons (`A B X Y LB RB Select Start Home L3 R3`) and 8 axes (LX, LY, LT, RX,
RY, RT, d-pad X, d-pad Y). Star, R4 and the back buttons are not reported as separate inputs.
