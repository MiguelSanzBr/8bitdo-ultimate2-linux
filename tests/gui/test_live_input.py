"""live_input mixin: joystick and DInput decoding and the reader thread (all I/O patched)."""
import array
import struct

import pytest

from ultimate2 import discovery
from ultimate2.gui import live_input


def test_pad_event_buttons_axes_and_init(app):
    app.pad_event(1, 1, 0)                                  # A down
    assert "A" in app.pad_down and "A" in app.press_t
    t = app.press_t["A"]
    app.pad_event(1, 1, 0)                                  # still down: no new ripple
    assert app.press_t["A"] == t
    app.pad_event(0, 1, 0)
    assert "A" not in app.pad_down
    app.pad_event(1, 1 | 0x80, 3)                           # initial-state burst: held, no ripple
    assert "Y" in app.pad_down and "Y" not in app.press_t
    app.pad_event(1, 1, 99)                                 # button number out of range: ignored
    app.pad_event(1, 3, 0)                                  # unknown kind: ignored
    app.pad_event(-1, 2, 6)
    assert "Left" in app.pad_down and "Right" not in app.pad_down and app.pad_axes[6] == -1
    app.pad_event(1, 2, 6)
    assert "Right" in app.pad_down and "Left" not in app.pad_down
    app.pad_event(-1, 2, 7)
    assert "Up" in app.pad_down
    app.pad_event(1, 2, 7)
    assert "Down" in app.pad_down and "Up" not in app.pad_down
    app.pad_event(5, 2, 2)
    app.pad_event(5, 2, 5)
    assert {"LT", "RT"} <= app.pad_down
    app.pad_event(0, 2, 2)
    assert "LT" not in app.pad_down
    app.pad_event(1234, 2, 0)                               # other axis: just stored
    assert app.pad_axes[0] == 1234


def pad_packets(*evs):
    return [struct.pack(live_input.JS_EVENT, 0, v, k, n) for v, k, n in evs]


def run_pad(app, mp, devs, read=None, node="/dev/input/js9", open_=lambda p, f: 77):
    """Run the joystick reader once against patched I/O; time.sleep ends the loop."""
    closed = []
    app._closing = False
    mp.setattr(discovery, "find_devices", devs)
    mp.setattr(discovery, "find_dinput_wireless", lambda: None)
    mp.setattr(discovery, "find_input_node", lambda usb: node)
    mp.setattr(live_input.os, "open", open_)
    mp.setattr(live_input.os, "read", read)
    mp.setattr(live_input.os, "close", closed.append)
    mp.setattr(live_input.time, "sleep", lambda s: setattr(app, "_closing", True))
    try:
        app._read_pad()
    finally:
        app._closing = False
    return closed


ONE_DEV = lambda: iter([("/dev/hidraw9", 0x310B, "/sys/usb")])


def test_read_pad_no_device_and_oserror(shared_app, monkeypatch):
    run_pad(shared_app, monkeypatch, lambda: iter([]), read=lambda fd, n: pytest.fail("no device"))

    def bad():
        raise OSError("sysfs gone")
        yield
    run_pad(shared_app, monkeypatch, bad, read=lambda fd, n: pytest.fail("no device"))


def test_read_pad_open_fails_or_no_node(shared_app, monkeypatch):
    def deny(p, f):
        raise OSError("denied")
    run_pad(shared_app, monkeypatch, ONE_DEV, open_=deny, read=lambda fd, n: pytest.fail("not opened"))
    run_pad(shared_app, monkeypatch, ONE_DEV, node=None, read=lambda fd, n: pytest.fail("no node"))


def test_read_pad_stream_then_short_read(shared_app, monkeypatch):
    app = shared_app
    app.pad_down.add("stale")
    app.pad_axes[9] = 9
    reads = iter(pad_packets((1, 1, 0), (7, 0x82, 0), (-1, 2, 6)) + [b"\x01\x02"])
    seen = []
    monkeypatch.setattr(app, "pad_event", lambda *a: seen.append(a))
    closed = run_pad(app, monkeypatch, ONE_DEV, read=lambda fd, n: next(reads))
    assert seen == [(1, 1, 0), (7, 0x82, 0), (-1, 2, 6)] and closed == [77]
    assert not app.pad_down and not app.pad_axes                # cleared when the node goes away


def test_read_pad_real_events_closing_and_read_error(shared_app, monkeypatch):
    app = shared_app
    pk = pad_packets((1, 1, 1))

    def read_then_close(fd, n):                                 # window closed while reading
        app._closing = True
        return pk[0]
    closed = run_pad(app, monkeypatch, ONE_DEV, read=read_then_close)
    assert closed == [77] and "B" in app.press_t

    def boom(fd, n):
        raise OSError("unplugged")
    with monkeypatch.context() as mp:
        assert run_pad(app, mp, ONE_DEV, read=boom) == [77]
    app.press_t.clear()


def test_read_pad_returns_when_already_closing(shared_app):
    shared_app._closing = True
    try:
        shared_app._read_pad()                                  # loop body never runs
    finally:
        shared_app._closing = False


def fake_ioctl(axmap, btnmap):
    def ioctl(fd, req, buf):
        if req == live_input.JSIOCGAXMAP:
            buf[:len(axmap)] = bytes(axmap)
        else:
            buf[:len(btnmap)] = array.array("H", btnmap)
    return ioctl


def test_js_maps_undo_jscal_remap(app, monkeypatch):
    # issue 15: jscal -u 8,0,1,3,4,2,5,16,17,... puts the right stick on js 2/3 and LT on js 4; A and B swapped
    monkeypatch.setattr(live_input.fcntl, "ioctl", fake_ioctl([0, 1, 3, 4, 2, 5, 16, 17], [0x131, 0x130, 0x133]))
    axes, buttons = live_input.js_maps(5)
    assert axes[2] == 3 and axes[3] == 4 and axes[4] == 2 and axes[6] == 6
    assert buttons[0] == "B" and buttons[1] == "A" and buttons[2] == "X"
    monkeypatch.setattr(app, "js_axes", axes)
    monkeypatch.setattr(app, "js_buttons", buttons)
    app.pad_event(20000, 2, 2)                              # right stick X
    assert app.pad_axes[3] == 20000 and "LT" not in app.pad_down
    app.pad_event(5, 2, 4)                                  # LT
    assert app.pad_axes[2] == 5 and "LT" in app.pad_down
    app.pad_event(1, 1, 0)
    assert "B" in app.pad_down and "A" not in app.pad_down
    app.pad_event(1, 1, 99)                                 # js numbers past the maps: ignored
    app.pad_event(1, 2, 99)
    assert 99 not in app.pad_axes and "A" not in app.pad_down


def test_js_maps_fallback_without_joydev_ioctls(monkeypatch):
    def enotty(fd, req, buf):
        raise OSError(25, "not a joystick node")
    monkeypatch.setattr(live_input.fcntl, "ioctl", enotty)
    assert live_input.js_maps(5) == (live_input.PadInput.js_axes, live_input.PadInput.js_buttons)


def test_decode_dinput_axes_hat_and_battery():
    # Enhanced SDL USB report. Also seen as 0x01 on the DInput receiver.
    report = bytes.fromhex("04 f5 00 ff 7f ff 20 ff 80 83 fc 00 00 00 b9") + bytes(19)
    assert live_input.decode_dinput(report) == (
        {"Left", "Down", "RB", "LT"},
        {0: -32767, 1: 32767, 2: 32767, 3: 0, 4: 32767, 5: -24544, 6: -1, 7: 1}, 57)
    assert live_input.decode_dinput(report[:14] + b"\xff" + report[15:])[2] is None
    assert live_input.decode_dinput(report[:14] + b"\x80" + report[15:])[2] == 0
    assert live_input.decode_dinput(b"\x03" + report[1:12])[2] is None
    for invalid in (b"", report[:-1], b"\x02" + report[1:], b"\x02" + bytes(63)):
        assert live_input.decode_dinput(invalid) is None


def test_read_pad_dinput_is_passive_and_clears_on_unplug(monkeypatch):
    app = live_input.PadInput()
    app._closing, app.pad_down, app.pad_axes, app.press_t = False, set(), {}, {}
    node = "/dev/hidraw12"
    opened, closed = [], []
    # Real neutral report from https://github.com/ascendedent/8bitdo-Linux-Software/issues/1.
    neutral = bytes.fromhex("010f7f7f7f7f0000000000000000617ffe4400000f05002d00100000000000000000")
    pressed = neutral[:8] + b"\x24\x00\x03" + neutral[11:]
    reads = iter([b"\x02" + bytes(63), pressed, neutral, pressed, neutral])

    def read(fd, size):
        assert (fd, size) == (77, 64)
        packet = next(reads, None)
        if packet is neutral:
            assert app.pad_down == {"P1", "P2", "P3", "P4"} and app.dinput_battery == 97
        if packet is pressed:
            assert not app.press_t                  # first valid state does not invent a new press
        if packet is None:
            assert not app.pad_down
            raise OSError("unplugged")
        return packet

    monkeypatch.setattr(discovery, "find_dinput_wireless", lambda: node)
    monkeypatch.setattr(discovery, "find_devices", lambda: pytest.fail("DInput bypasses config discovery"))
    monkeypatch.setattr(live_input.os, "open", lambda p, f: opened.append((p, f)) or 77)
    monkeypatch.setattr(live_input.os, "read", read)
    monkeypatch.setattr(live_input.os, "close", closed.append)
    monkeypatch.setattr(live_input.select, "select", lambda r, w, x, t: (r, [], []))
    monkeypatch.setattr(live_input.fcntl, "ioctl", lambda *_: pytest.fail("DInput makes no ioctls"))
    monkeypatch.setattr(live_input.os, "write", lambda *_: pytest.fail("DInput never writes"))
    monkeypatch.setattr(live_input.time, "sleep", lambda _: setattr(app, "_closing", True))
    app._read_pad()
    assert opened == [(node, live_input.os.O_RDONLY | live_input.os.O_NONBLOCK)] and closed == [77]
    assert {"P1", "P2", "P3", "P4"} <= app.press_t.keys()
    assert not app.pad_down and not app.pad_axes and app.dinput_battery is None


@pytest.mark.parametrize("stop", ["EOF", "closing"])
def test_dinput_reader_recovers_from_transient_events(monkeypatch, stop):
    pad = live_input.PadInput()
    pad._closing, pad.pad_down, pad.pad_axes = False, set(), {}
    closed = []
    monkeypatch.setattr(live_input.os, "open", lambda *_: (_ for _ in ()).throw(PermissionError()))
    pad._read_dinput("inaccessible")
    monkeypatch.setattr(live_input.os, "open", lambda *_: 41)
    monkeypatch.setattr(live_input.os, "close", closed.append)
    readiness = iter([False, True, True, True])
    monkeypatch.setattr(live_input.select, "select", lambda *_: ([41] if next(readiness) else [], [], []))
    packets = iter([None, b"\x00", b""])

    def read(*_):
        packet = next(packets)
        if packet is None:
            raise BlockingIOError()
        if packet == b"\x00" and stop == "closing":
            pad._closing = True
        return packet

    monkeypatch.setattr(live_input.os, "read", read)
    pad._read_dinput("reconnected")
    assert closed == [41] and pad.dinput_battery is None and not pad.pad_down
