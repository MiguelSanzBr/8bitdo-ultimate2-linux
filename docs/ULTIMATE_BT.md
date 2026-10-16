# 8BitDo Ultimate Bluetooth Controller (1st gen, with charging dock)

Notes for supporting the original *Ultimate Bluetooth Controller* (Nintendo layout, charging dock with a 2.4G
receiver, two back paddles P1/P2, Bluetooth / 2.4G mode switch on the back). Its official configurator is
*8BitDo Ultimate Software* **V1** (Windows build 2.16, `8BitDo-Ultimate-Software-for-Windows.zip` on the controller's
support page); V2 still carries `UltimateBT` code but does not detect this pad. Everything below was taken from a
USB capture of V1 configuring the pad (usbmon on the Linux host while the device was passed to a Windows VM),
cross-checked with both apps decompiled (ILSpy) and `8BitDoAdvance.dll` disassembled, and then reproduced from
Linux on a real controller (firmware 1.02).

## USB IDs

| USB ID | What | Config channel |
|---|---|---|
| `2dc8:3106` "8BitDo Ultimate Controller" | the pad on a USB cable, XInput (kernel: `xpad`) | none — needs the knock below |
| `2dc8:6007` "8BitDo Ultimate Controller" | the pad in config mode (app: `PID_UltimateBT`) | HID, report `0x81` out / `0x02` in, inside the gamepad descriptor |
| `2dc8:3106` "Ultimate Wireless Controller" | its 2.4G receiver (app: `PID_UltimateBTRR`) | none seen |
| `2dc8:3109` | the receiver while the pad sits in the dock (app: `PID_IDLE`) | answers reads/writes, but they reach the receiver's own (blank) record and are never saved — **not** the pad's config |
| `057e:2009` | Switch mode | — |

## Entering and leaving config mode

The app switches the pad from XInput to config mode by sending XInput rumble packets on the interrupt OUT endpoint,
about 16 ms apart:

```
00 08 00 01 00 00 00 00      strong 1, weak 0
00 08 00 00 01 00 00 00      0, 1
00 08 00 01 01 00 00 00      1, 1
00 08 00 05 01 00 00 00      5, 1
00 08 00 00 00 00 00 00      0, 0
```

The pad then re-enumerates as `2dc8:6007`. On Linux the same bytes come out of `xpad`'s force feedback (an
`FF_RUMBLE` effect with magnitudes `<< 8`, updated in place), so no root and no detaching of `xpad` is needed
(`ultimate2.device.knock`). Before the knock the app also sets the XInput LED (`01 03 06`); it is not required.

The fixed query `81 05 00 51 02` (sent on `6007`) switches it back to `3106` XInput.

Now and then (3 times out of about 16 here, with byte-identical knocks) the pad drops off the bus and powers off instead
of coming back as `6007`; pressing Home turns it on again in XInput mode (it enumerates as a Switch Pro Controller
for a moment first). `u2ctl` says so.

## Protocol in config mode

Same commands as the Ultimate 2, but every request carries a length byte after the report ID:

```
Ultimate 2:          81 04 <16-byte header> <data>
Ultimate Bluetooth:  81 <n+1> 04 <16-byte header> <data>      n = 16 + len(data)
```

(`8BitDoAdvance.dll` `0x1040f340`: PIDs `0x6009 0x2028 0x6012 0x600f 0x600b 0x2062` use the first form,
everything else the second.) Answers are unchanged: `02 04 04 00 <cmd> <len> …`, data at byte 18.

Session as the app does it: version query `81 05 00 21 01` (answer `02 22`, u16 firmware ×100, beta, …, byte 6 =
colorway), `CMD_REPORT` 0, reads/writes, `CMD_REPORT` 1. Once reports are back on (`CMD_REPORT` 1) the pad stops
answering config requests. `CMD_INFO` (`0x0100`) is not answered in config mode.

In config mode the pad sends no gamepad reports at all. Its app polls `CMD_LIVE` (`3`, sub `0x15`, ~20 times a
second) instead: the 12-byte answer is a u32 of pressed buttons as key-code bits (physical buttons, before any
profile remap; bit `0x20000000` is always set), then LX, LY, RX, RY, RT, LT as u8 (sticks centred at 0x80).
The back paddles report `0x04000000` (P1) and `0x02000000` (P2).

| Step | Ultimate Bluetooth |
|---|---|
| read | `CMD_READ` chunks of ≤45 bytes, `total = 1652` |
| write | `CMD_WRITE` chunks of ≤45 bytes, `total = 1652` |
| save | `CMD_COMMIT` with **sub `0x15`** (the Ultimate 2's `0x123` is accepted into RAM but never saved, and gets no answer) |

The app leaves `crc_value` alone on ordinary edits and the firmware does not reject records whose CRC it did not
compute (it is recomputed by `ANSI_CRC_16_UltimateBT` only when a profile is enabled or disabled; its exact formula
is still unknown).

## Config record: 1652 bytes (0x674)

V1's `custom_config_record_t`. Three profile slots, MSVC natural alignment, little endian. Flags: `0x20200911`
enabled, `0x20190000` disabled, `0xFFFFFFFF` erased. The first 224 bytes are laid out exactly like the Ultimate 2
record. (V2's version of the struct is 2324 bytes: the same 1652 followed by `record_macro_fun[3]` and
`x_rumble[3]`, which this pad never transfers.)

| Offset | Size | Field |
|---|---|---|
| 0 | 3×4 | `flag[3]` — profile slot enabled |
| 12 | 4 | `crc_value` |
| 16 | 2 | `gamepad_mode` (3 on a Windows cable; 0's default map has Screenshot, so likely Switch) |
| 18 | 2 | `cur_slot` (0-2; ≥3 = no custom profile; reads 6 with the profile LED off) |
| 20 | 3×32 | `file_name[3]` (the app leaves it empty) |
| 116 | 3×12 | `rumble[3]`: u32 flag, float zoom_out[2] |
| 152 | 3×8 | `joystick[3]`: u32 flag, (start,end)×2 — defaults 0/128 |
| 176 | 3×8 | `trigger[3]`: u32 flag, (start,end)×2 — defaults 0/255 (77/255 when `gamepad_mode` 0) |
| 200 | 3×8 | `special_feature[3]`: u32 flag, u32 feature bits (same bits as Ultimate 2) |
| 224 | 3×84 | `map_key[3]`: u32 flag, u32 key[20] |
| 476 | 3×392 | `macro_fun[3]` (`macro_fun_record_t_Pro2`): u32 flag, u8 total_cnt, 4×96-byte records (u32 key_map, u16 interval_time_index[18], u16 key_index[18], u8 digital_joy[18], u8 max_index) |

`map_key.key[i]` is the output code (same bit values as the Ultimate 2 `KEYCODES`, named after Xbox positions:
`A` = bottom, `B` = right) for physical button `i`, named after the labels printed on this pad:

```
0 A (right)   1 B (bottom)   2 X (top)   3 Y (left)   4 L   5 R   6 ZL   7 ZR   8 L3   9 R3
10 Select(-)   11 Start(+)   12 Star   13 Home
14 Up   15 Down   16 Left   17 Right   18 P1   19 P2 (back paddles, default None)
```

So the default map for `gamepad_mode` 3 is `B, A, Y, X, …` (each face button sends the Xbox button in the same
position) and `A: "A"` in `u2ctl dump` means the right button now acts as the bottom one. Checked with `evtest`:
a profile with A↔B and X↔Y swapped turns the right button from `BTN_EAST` into `BTN_SOUTH`, and so on.

The profile button (the small one above the three LEDs) only steps through slots whose `flag` is enabled; with
only slot 0, it toggles between the default setting (no LED) and slot 0 (one LED).
