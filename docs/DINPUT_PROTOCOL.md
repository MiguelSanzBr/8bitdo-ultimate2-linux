# Can DInput read the Ultimate 2 Wireless's onboard profiles?

**No verified DInput profile-read path was found** for the **8BitDo Ultimate 2 Wireless Controller** (Windows/Android model with L4/R4 and PL/PR). Linux can receive its DInput gamepad reports, but those reports are not a backup of the controller's stored mappings, macros, dead zones or lighting. For a known onboard configuration read, this project's tested route is the USB cable in XInput mode. Whether that read represents the profile used in DInput is a separate, unresolved question.

## XInput versus receiver DInput in this configurator

| Feature | XInput baseline | DInput (`6012`) |
|---|---|---|
| Detection and reconnect | Detect config interface, retry after disconnect | Detect gamepad separately; retry configuration and reconnect the passive input reader |
| Live buttons, sticks, triggers | Linux joystick input; onboard remaps may duplicate ordinary buttons | Decode raw reports, including four independent L4/R4/PL/PR bits; no exclusive grab |
| Battery and active slot | Receiver status where available; active slot from configuration | Battery in 34-byte reports; unknown on short reports. No persistent slot bits found in the physical profile-cycle test below |
| Stored button maps, stick/trigger settings, rumble, gyro settings and LEDs | Edit via vendor config interface, subject to model capabilities | No verified config transport on the gamepad interface; GUI shows preview only when it cannot read configuration |
| Profile read/write and backup/restore | Cable config record; writes checked by reading back | Not verified in DInput. Use cable for cable-mode settings; do not assume the same profile bank |

Discovery, decoding, and GUI transitions have automated tests. On the physical test unit
the decoder reported the requested sequence `A → L4 → R4 → PL → PR → A` at
7.1, 8.8, 9.7, 10.3, 10.9 and 15.0 seconds. The 34-byte reports indicated 73% battery.
The tester confirmed Steam input worked with the patched app open and after it
closed. Cable mode enumerated as `310b`; a single-byte profile-name edit was
immediately verified against the complete 1,592-byte record. After a physical
USB reconnect the full record still matched the edit. Restoring the one byte
and reading back all 1,592 bytes produced an exact match to the original backup.
This validates cable persistence, not DInput profile access.

### Physical profile-cycle test (receiver DInput)

The tester repeatedly cycled the physical profile button, observed the different
profile lights, and marked settled states with 12 A taps. Exact LED-to-tap labels
were not recorded. In the first 196,608 reports all packets were 34 bytes with ID
`0x01`; bytes 8–13 showed only the A marker or zero. For each tap we compared
every bit across the quiet interval 1.00–0.06 seconds before its rising edge.
The **only bits constant within every interval but different between intervals**
were bits 0–3 of byte 14 (zero-based). That byte was battery: 90%, then 88%,
then 87%, not a repeating profile sequence. Sensor bytes fluctuated within
intervals. This rules out a simple persistent slot field in the sampled reports,
not every possible encoding or firmware-specific query. Leave the slot unknown.

The project's documented `cur_slot` query reads the config header over the
vendor interface; neither SDL's `6012` handling nor the receiver's observed HID
descriptor identifies a non-disruptive DInput equivalent. No speculative command,
profile write, or mode switch was used in this experiment.

## What the evidence establishes

| Connection | Evidence | Limit for onboard configuration |
|---|---|---|
| USB cable, XInput (`2dc8:310b`) | The [project protocol notes](PROTOCOL.md) identify HID interface 2, usage page `0xFF7A`, alongside XInput. The project verified the 1,592-byte, three-slot record on firmware 1.10. | This is a vendor request/reply exchange (output `0x81`, input `0x02`), not passive listening. Even a read sends an output report. |
| Receiver configuration interface (`2dc8:6013`) | The notes identify interface 0, usage page `0xFFA0`, and a query for the paired controller. The [README](../README.md#features) marks the dongle configuration path as untested. | A receiver or battery reply does not establish that a complete profile read works while the pad is in DInput, or which mode's record would be returned. |
| DInput over the receiver or Bluetooth (`2dc8:6012`) | [Valve steam-devices issue 64](https://github.com/ValveSoftware/steam-devices/issues/64) contains user reports for both transports describing extended buttons and gyro. [SDL's USB IDs](https://github.com/libsdl-org/SDL/blob/31a04a734f2e8e6f02cb691c70b70a5fa9cbe972/src/joystick/usb_ids.h) identify this PID as the Ultimate 2 Wireless. | The [SDL HIDAPI driver](https://github.com/libsdl-org/SDL/blob/31a04a734f2e8e6f02cb691c70b70a5fa9cbe972/src/joystick/hidapi/SDL_hidapi_8bitdo.c) handles gameplay reports and distinguishes 12-byte (firmware 1.02) from 34-byte (1.03) input. Its Ultimate 2 Wireless handling does not implement a stored-profile read. |

8BitDo's [product page](https://www.8bitdo.com/ultimate-2-wireless-controller/) advertises three custom profiles and Ultimate Software V2. The [model FAQ](https://support.8bitdo.com/faq/ultimate-2-wireless-controller.html) specifies the Windows/macOS configurator; the [Steam guide](https://www.8bitdo.com/steam/) documents Bluetooth pairing for this model. None of these pages specifies a DInput report or service for reading the onboard configuration.

## What to verify before adding support

`0x6012` occurs both as the controller's *internal* PID in configuration replies and as a *host-visible* DInput PID. Neither proves that a particular HID collection accepts configuration requests. [Discovery](../src/ultimate2/discovery.py) looks for the known vendor usage pages for this model. Similarly, `gamepad_mode` at record offset 16 identifies a mode; it is not a documented selector for reading a different mode's record. The older [Ultimate 2.4G](ULTIMATE_24G.md) has verified separate X/D records, but its PIDs, frame format and record size differ.

The most useful next evidence would be an **existing** descriptor dump and a trace of Ultimate Software V2 reading profiles from this exact model in DInput. Identify the firmware, bus, interface and report IDs, including any separate receiver interface. Check whether the device stays in DInput through the read, whether replies contain a complete record, and whether a known DInput slot name or mapping matches. A descriptor alone establishes report shapes, not their meaning. Until then, a saved cable backup can be inspected offline as a cable snapshot; it should not be presented as a live DInput read.

This review used published sources and repository files only. No controller was opened or queried.

### Receiver observation on the test machine

With the controller awake in DInput, `lsusb -v -d 2dc8:6012` showed one HID
interface (interrupt endpoints `0x84` IN and `0x05` OUT). Its kernel HID report
descriptor advertised input report `0x01` and output report `0x05` (Physical
Interface Device page `0x0F`), no feature report and no vendor configuration
collection of the types used by the existing transport. `u2ctl list` found the
DInput gamepad and no config interface. This explains why the **existing**
profile protocol is unavailable; it does not rule out an undocumented protocol.
`fuser` showed Steam and the source-checkout GUI simultaneously holding the
same hidraw node. Concurrent opens alone do not verify button delivery in Steam.
