"""live_input mixin: js_event decoding and the reader thread (all I/O patched)."""
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
