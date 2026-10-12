# Architecture

```
src/ultimate2/
├── protocol.py     constants, CRC-16, request/answer frames (pure functions)
├── discovery.py    sysfs scan: config hidraw node + joystick node of the same USB device
├── device.py       Device: open/close, read/write/commit the record, theme, slot, info, edition
├── config.py       1592-byte record <-> nested dict (FIELDS table), encode only what changed, defaults
├── cli.py          u2ctl (argparse)
└── gui/
    ├── theme.py        palette, fonts, timings, controller skins
    ├── catalog.py      UI vocabulary: sections, remap targets, gyro keys, LED colour targets
    ├── geometry.py     controller drawing coordinates (parts, LED rings, callouts)
    ├── drawing.py      rounded shapes, gradient fill, colour maths, LED effect preview
    ├── widgets.py      Pill, panel, field, Slider, Toggle, ColorPicker
    ├── controller.py   ControllerView mixin: draw/animate the controller, mapping highlight
    ├── pages.py        Pages mixin: layout helpers, home + section pages, navigation
    ├── editor.py       Editor mixin: config dict <-> Tk variables, LED colour targets
    ├── sync.py         DeviceSync mixin: worker-thread I/O, auto-save, polling, theme, backups
    ├── live_input.py   PadInput mixin: joystick reader thread
    └── app.py          App = Pages + ControllerView + Editor + DeviceSync + PadInput + tk.Tk
```

## Layers

1. **protocol** knows bytes on the wire and nothing else.
2. **discovery** and **device** do the I/O. `Device` looks up `discovery.find_devices()` at call time, so tests can
   swap it.
3. **config** is pure data transformation. `decode()` uses the declarative `FIELDS` table of
   `(path, offset, kind)`. `encode()` writes only the fields whose decoded value changed, so unknown or
   untouched bytes survive exactly.
4. **cli** and **gui** are front ends. Neither knows about frames or offsets.

## GUI data flow

```
controller ──read_device()──▶ base (bytes) ──decode──▶ doc (dict) ──load()──▶ Tk variables (self.v) ──▶ widgets
widgets ──trace──▶ changed() ──debounce──▶ autosave(): gather() → encode(doc, base) → changed_span → Device.write_config(range)
```

* Device I/O runs on short-lived worker threads (`DeviceSync.run`). Results come back through `after(0, …)` to the Tk
  thread, and `busy` serialises the jobs.
* `poll()` reads the active slot every `theme.POLL_MS`. `animate()` redraws only the visible controller drawing every
  `theme.FRAME_MS`.
* The joystick reader thread (`PadInput._read_pad`) only updates `pad_down`, `pad_axes` and `press_t`; `animate()`
  turns those into visuals.

## Testing

`tests/fake_device.py` emulates the firmware over a `SOCK_SEQPACKET` socketpair, which keeps the 64-byte report
boundaries and works with `select`. `FakeController.install(monkeypatch)` makes `Device()` find and open it. GUI tests
build a real Tk `App` (an X display is required; CI uses `xvfb-run`). Coverage is enforced at 100% lines and
branches (`.coveragerc`).
