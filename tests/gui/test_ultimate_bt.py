"""The GUI with a 1st-gen Ultimate Bluetooth: model switch, hidden sections, whole-record saves, live state."""
import os
import threading
import time
from types import SimpleNamespace

import pytest

from fake_device import FakeController
from ultimate2 import device, models, protocol
from ultimate2.gui import live_input, theme
from ultimate2.gui.geometry import PARTS

from .conftest import BACKUP, clear_timers, make_app, pump

CONFIG_BT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "ultimatebt_config.bin"),
                 "rb").read()


@pytest.fixture
def btfake(monkeypatch):
    f = FakeController(cfg=CONFIG_BT, firmware=102, report_pid=protocol.PID_BT_CONFIG,
                       usb_pid=protocol.PID_BT_CONFIG).install(monkeypatch)
    f.edition = 0x22
    yield f
    f.close()


@pytest.fixture
def btapp(shared_app, btfake):
    a = shared_app
    pump(a)
    clear_timers(a)
    a.doc, a.base, a.sel_btn = None, None, "P3"                 # a button the Ultimate Bluetooth does not have
    a.active_slot, a._remapped = None, set()
    a.pad_down.clear(), a.pad_axes.clear(), a.press_t.clear()
    a.show("home")
    a.select_slot(0, gather=False)
    a.read_device()
    pump(a)
    yield a
    pump(a)
    clear_timers(a)
    a.doc = None
    a.set_model(models.ULTIMATE2)                                         # the shared App goes back to the Ultimate 2


def mapped(w):
    return w.winfo_manager() != ""


def part_xy(a, name):
    parts, _mode = next(v for v in a.ctrl.values() if v[1] == "map")
    return parts.get(name)


def test_reads_and_adapts_the_window(btapp, mk):
    a = btapp
    assert a.model is models.ULTIMATE_BT and a.title() == "8BitDo Ultimate Bluetooth — Linux" and a.home_title.cget("text") == "Ultimate Bluetooth"
    assert a.doc["gamepad_mode"] == 3 and a.active_slot == 6 and a.base == CONFIG_BT and a.sel_btn == "A"
    assert not mapped(a.tiles["gyro"]) and not mapped(a.tiles["leds"]) and mapped(a.tiles["buttons"])
    assert not mapped(a.xr_card) and "P1/P2" in a.map_help.cget("text") and a.colors == {}
    assert part_xy(a, "P3") is None and part_xy(a, "P1") is not None
    x, y, _r = PARTS["B"][1]                                     # A sits where the Xbox layout has B (right)
    assert a.map_canvas.coords(part_xy(a, "A")["body"])[0] == pytest.approx((x - 15) * a.s)
    assert a.v["keys"]["A"].get() == "B" and "firmware 1.02" in a.fw_label.cget("text")
    assert "Ultimate Bluetooth (config mode)" in a.info_label.cget("text")
    a.set_model(models.ULTIMATE_BT)                                            # same model again: nothing to do
    b = mk(BACKUP)                                               # an Ultimate 2 afterwards: everything comes back
    assert b.model is models.ULTIMATE2 and mapped(b.tiles["gyro"]) and mapped(b.xr_card) and part_xy(b, "P3") is not None
    assert b.title() == "8BitDo Ultimate 2 — Linux" and "L4/R4" in b.map_help.cget("text")


def test_remap_saves_the_whole_record(btapp, btfake, monkeypatch):
    monkeypatch.setattr(theme, "AUTOSAVE_MS", 5)
    a = btapp
    btfake.log.clear()
    a.v["keys"]["A"].set("A")
    pump(a, lambda: "Salvo" in a.status.cget("text") and not a.busy)
    writes = [e for e in btfake.log if e[0] == protocol.CMD_WRITE]
    assert writes[0][3] == 0 and sum(e[2] for e in writes) == protocol.CFG_SIZE_BT
    assert any(e[:2] == (protocol.CMD_COMMIT, protocol.COMMIT_KEY_BT) for e in btfake.log)
    assert a.doc["slots"][0]["mapping"]["A"] == "A" and "sixaxis" not in a.doc["slots"][0]
    assert bytes(btfake.cfg) == a.base and a.base != CONFIG_BT
    a.select_slot(1)                                             # an empty slot shows the app defaults
    assert a.v["keys"]["A"].get() == "B" and not a.v["enabled"].get()


def test_restore_checks_the_bt_size(btapp, dlg, tmp_path):
    f = tmp_path / "u2.bin"
    f.write_bytes(BACKUP)
    dlg.open = str(f)
    btapp.restore()
    assert "esperado 1652" in dlg.errors[-1][1]


def test_switch_failure_opens_a_dialog(shared_app, dlg, monkeypatch):
    def cannot(self, path=None, **kw):
        raise SystemExit("cannot switch the Ultimate Bluetooth to config mode via /dev/input/event7 (denied)")
    monkeypatch.setattr(device.Device, "__init__", cannot)
    shared_app.read_device()
    pump(shared_app)
    assert dlg.errors and shared_app._retry_job is None


def test_read_device_asks_for_a_knock(shared_app, btfake, monkeypatch):
    seen = []
    real = device.Device.__init__

    def spy(self, path=None, knock=False, stay=False):
        seen.append((knock, stay))
        real(self, path, knock, stay)
    monkeypatch.setattr(device.Device, "__init__", spy)
    shared_app.read_device()
    pump(shared_app)
    assert seen[0] == (True, True)
    shared_app.doc = None
    shared_app.set_model(models.ULTIMATE2)


# ------------------------------------------------------------ live state
def test_live_state_maps_buttons_and_axes(btapp):
    a = btapp
    a.live_state(0x20000000 | 0x2000 | 0x10000 | 0x4000000, (0, 255, 128, 127, 255, 0))
    assert a.pad_down == {"A", "Star", "P1"} and set(a.press_t) == {"A", "Star", "P1"}
    assert a.pad_axes == {0: -32767, 1: 32512, 2: -32767, 3: 0, 4: -256, 5: 32767}
    a.live_state(0x20000000, (128,) * 4 + (0, 0))
    assert not a.pad_down


@pytest.fixture
def quick(monkeypatch):
    real = time.sleep
    monkeypatch.setattr(live_input, "time", SimpleNamespace(sleep=lambda s: real(min(s, .01)), time=time.time))


def test_poll_live_follows_the_pad_until_it_stops_answering(btapp, btfake, quick):
    a = btapp
    btfake.live = bytes.fromhex("00200020 7f80807f 0000 0000")
    a.busy = True                                                # a job is running: no polling
    t = threading.Thread(target=a._poll_live, daemon=True)
    t.start()
    time.sleep(.05)
    assert not a.pad_down
    a.busy = False
    end = time.time() + 2
    while "A" not in a.pad_down and time.time() < end:
        time.sleep(.01)
    assert "A" in a.pad_down
    btfake.silent.add(protocol.CMD_LIVE)
    t.join(3)
    assert not t.is_alive() and not a.pad_down


def test_poll_live_without_device_and_on_os_error(btapp, monkeypatch, quick):
    a = btapp

    def gone(self, path=None, **kw):
        raise SystemExit("no 8BitDo config interface found")
    monkeypatch.setattr(device.Device, "__init__", gone)
    a._poll_live()                                                  # returns after a pause
    monkeypatch.undo()


def test_poll_live_os_error(btapp, btfake, monkeypatch, quick):
    a = btapp
    monkeypatch.setattr(device.Device, "live", lambda self: (_ for _ in ()).throw(OSError(19, "gone")))
    a.pad_down.add("A")
    a._poll_live()
    assert not a.pad_down


def test_read_pad_hands_over_to_the_bt_poller(btapp, monkeypatch):
    a = btapp
    calls = []

    def poll():
        calls.append(1)
        a._closing = True
    monkeypatch.setattr(a, "_poll_live", poll)
    a._read_pad()
    a._closing = False
    assert calls == [1]


def test_closing_gives_the_pad_back(monkeypatch):
    left = []
    monkeypatch.setattr(device, "leave_config_mode", lambda: left.append(1))
    a = make_app(monkeypatch)
    a.model = models.ULTIMATE_BT
    a.destroy()
    b = make_app(monkeypatch)
    b.destroy()
    assert left == [1]


def test_poll_live_stops_when_the_model_changes(btapp, quick):
    a = btapp
    t = threading.Thread(target=a._poll_live, daemon=True)
    t.start()
    time.sleep(.05)
    a.model = models.ULTIMATE2                                                 # an Ultimate 2 was read meanwhile
    t.join(3)
    a.model = models.ULTIMATE_BT
    assert not t.is_alive()


def test_poll_failure_rereads_and_waits_for_it(btapp, monkeypatch):
    a = btapp
    reads = []
    monkeypatch.setattr(a, "read_device", lambda retry=False: reads.append(retry))

    def gone(self, path=None, **kw):
        raise SystemExit("no 8BitDo config interface found")    # replugged: back in XInput
    monkeypatch.setattr(device.Device, "__init__", gone)
    a.poll()
    pump(a)
    assert reads == [True] and not mapped_badge_ok(a)
    a._retry_job = a.after(10 ** 7, lambda: None)                 # the re-read is scheduled: polls stay out of its way
    a.poll()
    pump(a)
    assert reads == [True]
    a.after_cancel(a._retry_job)
    a._retry_job = None


def mapped_badge_ok(a):
    return bool(a.fw_label.cget("text"))
