# 8BitDo Ultimate 2.4G Wireless Controller

Notes for supporting the *Ultimate 2.4G Wireless Controller* (the first Ultimate with an Xbox layout, sold with a
2.4G receiver; X / D mode switch on the back, two back paddles P1/P2). It is the sibling of the
[1st-gen Ultimate Bluetooth](ULTIMATE_BT.md): same commands, record size and save key, but its own request header,
record details and way into config mode. Its official configurator is *8BitDo Ultimate Software* **V1** (`Ultimate2_4`
in the app: `PID_Ultimate2_4`, `PID_Ultimate2_4RR`). Everything below was taken from that app (`8BitDoAdvance.dll`:
`readUltimate2_4`, `writeUltimate2_4`, `getUltimate2_4CurrentSlot`, `ANSI_CRC_16_Ultimate2_4`, disassembled with Ghidra;
the .NET assembly with ILSpy) and from USBPcap captures of it on Windows, and then reproduced from Linux on a real
controller (firmware 2.04, receiver firmware 1.10).

## USB IDs

| USB ID | What | Config channel |
|---|---|---|
| `2dc8:3106` | the pad on X (cable or receiver), XInput (kernel: `xpad`) | none — needs the switch below |
| `2dc8:3012` | the pad on a cable with the switch on D; also the pad on X after the switch | HID, report `0x81` out / `0x02` in, inside the gamepad descriptor |
| `2dc8:3013` | the receiver after the switch (app: `PID_Ultimate2_4RR`) | same |
| `0005:2dc8:3012` | the pad over Bluetooth (switch on D, firmware 2.00+) | **none**: gamepad and rumble reports only |
| `2dc8:3109` "8BitDo IDLE" | the receiver with no controller | — |

**The configuration is per mode.** On D (cable, Bluetooth) the pad uses one record (`gamepad_mode` 1), on X
(receiver, cable on X) another one (`gamepad_mode` 3). Bluetooth uses the D record, so a change made through the
receiver does not apply there.

## Entering and leaving config mode

Unlike the Ultimate Bluetooth, the rumble knock alone does nothing: sent through `xpad`'s force feedback it reaches
the pad byte for byte (checked with usbmon) and firmware 2.04 ignores it. A USBPcap capture of the app on Windows
(receiver on X) shows the whole sequence. At connect, `xusb22` sends on the interrupt OUT endpoint `0x02`:

```
01 03 02      LED
02 08 03      (xpad never sends this one)
01 03 02
01 03 06
```

When the app starts it sends the knock `00 08 00 <strong> <weak> 00 00 00` with (1,0) (0,1) (1,1) (5,1) (0,0)
(the same steps as the Ultimate Bluetooth's), ~15 ms apart, three times ~400 ms apart. Half a second later the
receiver re-enumerates as `2dc8:3013` with the config channel, and the record read there is the X one.

Replayed over usbfs (`ultimate2.device.usb_knock`: detach `xpad`, claim interface 0, bulk writes to `0x02`) the same
bytes work on Linux, without root once the udev rule gives the user the USB device node (`uaccess` on `2dc8:3106`).
The fixed query `81 05 00 51 02` on the config channel switches it back to `3106` XInput, as for the Ultimate
Bluetooth.

A cable on D is `3012` too, and must not be "switched back": only the interfaces this process switched are given
back (`device.SWITCHED`).

## Protocol in config mode

```
request : 81 | n | 04 | u16 cmd | u16 sub | u32 len | u32 total | u32 offset | data[len]   (n = 17 + len, len ≤ 45)
answer  : 02 04 | u16 4 | u16 cmd | u32 len | u32 total | u32 offset | data[len]
```

That is the Ultimate Bluetooth's length-prefixed frame with **no CRC** in the header (the DLL writes a u32 length:
the CRC field of the other models stays 0). Answers echo `total` and `offset`; a late answer to a request that timed
out must be told apart by its offset. Only read, write and commit are answered: there is no `CMD_INFO`, no
`CMD_REPORT` (the app never sends it), no LED theme and no live-state query.

| Step | Ultimate 2.4G |
|---|---|
| version | `81 05 00 21 01` → `02 22 \| u16 firmware×100 \| u8 beta \| 0 \| u16 PID` (byte 6 is the PID, not a colorway) |
| read | `CMD_READ` chunks of ≤45 bytes, `total = 1652`; a 20-byte read at 0 gives `cur_slot` |
| write | `CMD_WRITE` chunks of ≤45 bytes; the app always writes the whole record |
| save | `CMD_COMMIT` with **sub `0x15`**; the answer comes within ~3 s |

## Config record: 1652 bytes (0x674)

`Ultimate2_4Advance.custom_config_record_t`: the offsets of the [Ultimate Bluetooth record](ULTIMATE_BT.md#config-record-1652-bytes-0x674),
with these differences:

| Field | Ultimate 2.4G |
|---|---|
| `crc_value` (12) | the app stores `ANSI_CRC_16_Ultimate2_4` (reflected `0x8408`, init `0xFFFF`, result byte-swapped, over the record as it stands); **the firmware overwrites it with its own save counter** (1, 2, …) |
| `cur_slot` (18) | (4 = no custom profile) **the firmware keeps its own value** on writes, so the app reads it first (`getUltimate2_4CurrentSlot`) |
| `file_name[3]` (20) | profile names, **UTF-16LE** (`Encoding.Unicode`), 16 characters |
| `map_key.key[20]` (224) | Xbox labels: `A B X Y LB RB LT RT L3 R3 Select Start Star Home Up Down Left Right P1 P2` |

After a save the record read back differs from the one written in `crc_value` and `cur_slot`: `config.same` compares
it without them.

Key codes are those of the Ultimate 2 for `A B X Y LB RB LT RT L3 R3 Select Start Up Down Left Right Menu Home`
(the app's `BasicAdvanceUIData.KEY_*_MAP`, RT and Home as set by `AutoR2AndHome` → `changeKey`), plus Screenshot
`0x400000`, Turbo `0x800000`/`0x1000000`, P1 `0x2000000`, P2 `0x4000000` and Swap `0x8000000`; there are no P3-P5
and no stick directions.

A new profile (the app's `clearMapping`, `clearRumble`, `clearSticks`, `clearTriger`, `clearMacro`, `clearfeature`,
then `enableFlagWithrecord`): identity mapping with Star = Menu (Screenshot in `gamepad_mode` 0) and P1/P2 = none,
rumble 1.0/1.0, sticks 0..128, triggers 0..255, no features, the macro records zeroed; the slot flag and every section
flag set to `0x20200911`.

## Staying connected on X

On X, a profile switch (the button above the LEDs) makes the receiver re-enumerate (`3106` → `3109` → `3106`).
Windows polls the pad's interrupt endpoint all the time; Linux' `xpad` only does while a program has the input node
open. With no game open, the receiver then drops the controller again ~5 s after each reconnection and finally
switches it off. Keeping the joystick node open fixes it: `u2ctl keepalive` holds the `js` node of every `2dc8:3106`
pad open and drained, reopening it after each reconnection. The .deb runs it as a systemd user service
(`ultimate2-keepalive.service`, enabled for every user at install time; it starts at the next login).

## Bluetooth: battery, and which record applies

Over Bluetooth there is no config channel, but that descriptor has the HID Battery Strength usage (`05 06 09 20`,
0..100) in the gamepad report, which the kernel exposes as `/sys/class/power_supply/hid-<mac>-battery`
(`ultimate2.battery`; UPower and desktop applets show it too). The receiver's descriptor (`3013`) has no such field and
it does not answer the Ultimate 2's `81 04 21 01 00 00 06`, so the battery is only known over Bluetooth.

Bluetooth uses the D record. When the pad is on Bluetooth while the X record is being edited through the receiver,
`u2ctl info` and `u2gui` warn that the changes do not apply there. With only Bluetooth, `u2gui` shows read-only the
copy of the D record it kept from the last cable read (`$XDG_DATA_HOME/ultimate2/ultimate24g-d.bin`). A profile
switch over Bluetooth sends no event, so the active profile is not shown there.

## Live input

In config mode the pad keeps sending gamepad reports through a generic HID gamepad, so `/dev/input/jsN` works,
with its own numbering (checked on a cable on D, `3012`): 16 buttons — A 0, B 1, X 3, Y 4, LB 6, RB 7, LT 8, RT 9, Select 10,
Start 11, Home 12, L3 13, R3 14 (Star and the paddles send nothing of their own) — and 8 axes: LX 0, LY 1, RX 2,
RY 3, RT 4, LT 5, d-pad hat 6/7. `u2gui` maps them onto `xpad`'s numbers (`live_input.JS_MAPS`).
