"""u2gui and an Ultimate 2.4G on Bluetooth: battery badge, X-while-Bluetooth warning, read-only copy of the D record."""
import pytest

from fake_device import FakeController
from ultimate2 import battery, config, discovery, models
from ultimate2.gui import sync, theme

from .conftest import clear_timers, pump

L = "ultimate_24g"
SIZE = 1652
BLANK = b"\xff" * 16 + bytes([1, 0, 4, 0]) + b"\xff" * (SIZE - 20)


def with_mode(mode, base=BLANK):
    doc = config.decode(base, L)
    doc["gamepad_mode"] = mode
    return config.encode(doc, base, L)[0]


def battery_text(a):
    return [a.pill.itemcget(i, "text") for i in a.pill.find_withtag("battery")]


@pytest.fixture
def window(shared_app):
    """The shared App, reset before and after: no record, no read-only copy, no banners, the Ultimate 2."""
    a = shared_app

    def reset():
        pump(a)
        clear_timers(a)
        a.doc, a.base, a.readonly, a.active_slot, a.conn = None, None, False, None, None
        a.btinfo.pack_forget()
        a.conflict.pack_forget()
        a.select_slot(0, gather=False)
        a.set_model(models.ULTIMATE2)
    reset()
    yield a
    reset()


@pytest.fixture
def cable(monkeypatch):
    """An Ultimate 2.4G on a cable with the switch on D."""
    f = FakeController(cfg=BLANK, firmware=204, usb_pid=0x3012).install(monkeypatch)
    yield f
    f.close()


@pytest.fixture
def bluetooth_only(monkeypatch):
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([]))
    monkeypatch.setattr(discovery, "bluetooth_24g", lambda: True)
    monkeypatch.setattr(discovery, "find_bt_xinput", lambda: None)
    monkeypatch.setattr(discovery, "find_24g_xinput", lambda: None)


def read(a):
    a.read_device()
    pump(a, lambda: not a.busy)
    pump(a)


def test_battery_shown_while_configuring_through_the_cable(window, cable, monkeypatch):
    a = window
    read(a)
    assert a.model is models.ULTIMATE_24G and battery_text(a) == []
    monkeypatch.setattr(battery, "bluetooth", lambda: {"capacity": 64, "status": "Discharging", "name": "8BitDo"})
    read(a)
    assert a.conn == ("2.04", 64) and battery_text(a) == ["64%"]
    monkeypatch.setattr(battery, "bluetooth", lambda: {"capacity": 63, "status": "Discharging", "name": "8BitDo"})
    monkeypatch.setattr(theme, "POLL_MS", 10 ** 7)
    a.poll()
    pump(a, lambda: a.conn == ("2.04", 63))
    monkeypatch.setattr(battery, "bluetooth", lambda: None)
    a.poll()
    pump(a, lambda: not a.busy)
    assert a.conn == ("2.04", 63)                    # Bluetooth gone: the last value stays until the next read


def test_warns_when_editing_x_while_the_pad_is_on_bluetooth(window, cable, monkeypatch):
    a = window
    cable.cfg[:] = cable.pending[:] = with_mode(3)               # the X configuration (receiver)
    bt = [True]
    monkeypatch.setattr(discovery, "bluetooth_24g", lambda: bt[0])
    monkeypatch.setattr(theme, "POLL_MS", 10 ** 7)
    read(a)
    assert a.conflict.winfo_manager() == "pack"
    a.check_conflict()                                          # already shown: stays
    bt[0] = False                                               # Bluetooth gone: the warning goes away
    a.poll()
    pump(a)
    assert a.conflict.winfo_manager() == ""


def test_no_warning_for_the_d_configuration(window, cable, monkeypatch):
    read(window)
    monkeypatch.setattr(discovery, "bluetooth_24g", lambda: True)      # the D record is what Bluetooth uses
    assert window.check_conflict() is False and window.conflict.winfo_manager() == ""


def test_bluetooth_shows_the_copy_from_the_last_cable_read(window, cable, monkeypatch):
    a = window
    doc = config.default_slot(config.decode(BLANK, L), 1, "Corrida", L)
    doc["slots"][1]["special"]["features"] = ["swap_LS_dpad"]
    cable.cfg[:] = cable.pending[:] = config.encode(doc, BLANK, L)[0]
    read(a)                                                     # 1) over the cable (D): the copy is kept
    assert open(sync.cache_path(), "rb").read() == bytes(cable.cfg) and not a.readonly
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([]))          # 2) only on Bluetooth
    monkeypatch.setattr(discovery, "bluetooth_24g", lambda: True)
    monkeypatch.setattr(battery, "bluetooth", lambda: {"capacity": 77, "status": "Discharging", "name": "8BitDo"})
    a.doc = None
    a.set_model(models.ULTIMATE2)
    read(a)
    assert a.readonly and a.model is models.ULTIMATE_24G and a.doc["slots"][1]["name"] == "Corrida"
    text = a.btinfo_text.cget("text")
    assert "somente leitura" in text and "Bateria: 77%." in text and "/" in text   # the copy's date
    assert battery_text(a) == ["77%"] and a.fw_label.cget("text") == "" and a.btinfo.winfo_manager() == "pack"
    a.select_slot(1, gather=False)
    assert a.v["feat"]["swap_LS_dpad"].get() is True
    a.v["feat"]["swap_LS_dpad"].set(False)                      # nothing is written: the shown value comes back
    pump(a, lambda: a.v["feat"]["swap_LS_dpad"].get() is True)
    assert a._save_job is None and "Somente leitura" in a.status.cget("text")
    read(a)                                                     # still on Bluetooth: the copy is not reloaded
    assert a.slot == 1
    monkeypatch.setattr(battery, "bluetooth", lambda: None)
    monkeypatch.setattr(theme, "POLL_MS", 10 ** 7)
    a.poll()                                                    # read-only poll: just the badge
    assert a.readonly and battery_text(a) == []


def test_bluetooth_without_a_copy_says_to_plug_the_cable_once(window, bluetooth_only, monkeypatch):
    monkeypatch.setattr(battery, "bluetooth", lambda: None)
    read(window)
    assert not window.readonly and "uma vez para o programa guardar" in window.btinfo_text.cget("text")
    assert window._retry_job                                    # tried again later: the cable may come


def test_a_copy_of_another_size_is_ignored(window, bluetooth_only, monkeypatch):
    import os
    os.makedirs(os.path.dirname(sync.cache_path()))
    open(sync.cache_path(), "wb").write(b"\xff" * 10)
    monkeypatch.setattr(battery, "bluetooth", lambda: None)
    read(window)
    assert not window.readonly


def test_keeping_the_copy_is_only_a_convenience(window, monkeypatch, tmp_path):
    (tmp_path / "ultimate2").write_text("a file where the folder should be")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    window.keep_copy(b"x")                                      # no error


def test_buttons_light_up_over_bluetooth(window, bluetooth_only, monkeypatch):
    from ultimate2.gui import live_input
    a = window
    monkeypatch.setattr(discovery, "bluetooth_24g_input", lambda: "/dev/input/js7")
    opened = []
    for model, want in ((models.ULTIMATE2, []), (models.ULTIMATE_24G, ["/dev/input/js7"])):
        a.set_model(model)
        a._closing = False
        monkeypatch.setattr(live_input.os, "open", lambda p, f: opened.append(p) or 77)
        monkeypatch.setattr(live_input.os, "read", lambda fd, n: b"")
        monkeypatch.setattr(live_input.os, "close", lambda fd: None)
        monkeypatch.setattr(live_input.time, "sleep", lambda s: setattr(a, "_closing", True))
        a._read_pad()
        assert opened == want
    a._closing = False
