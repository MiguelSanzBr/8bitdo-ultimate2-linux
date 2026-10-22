"""The GUI with an Ultimate 2.4G: model switch, its function list, whole-record saves, its joystick numbering."""
import os

import pytest

from fake_device import FakeController
from ultimate2 import config, models, protocol
from ultimate2.gui import theme
from ultimate2.gui.geometry import PARTS

from .conftest import BACKUP, clear_timers, pump

L = "ultimate_24g"
REAL = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "ultimate24g_config.bin"),
            "rb").read()


@pytest.fixture
def u24fake(monkeypatch):
    f = FakeController(cfg=REAL, firmware=204, usb_pid=0x3013).install(monkeypatch)
    yield f
    f.close()


@pytest.fixture
def u24app(shared_app, u24fake):
    a = shared_app
    pump(a)
    clear_timers(a)
    a.doc, a.base, a.sel_btn = None, None, "P3"                 # a button the Ultimate 2.4G does not have
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
    a.set_model(models.ULTIMATE2)                               # the shared App goes back to the Ultimate 2


def mapped(w):
    return w.winfo_manager() != ""


def part(a, name):
    parts, _mode = next(v for v in a.ctrl.values() if v[1] == "map")
    return parts.get(name)


def chips(a):
    return [w.text for w in a.map_chips[0].winfo_children()[0].winfo_children()]


def test_reads_and_adapts_the_window(u24app, mk):
    a = u24app
    assert a.model is models.ULTIMATE_24G and a.title() == "8BitDo Ultimate 2.4G — Linux"
    assert [s["name"] for s in a.doc["slots"]] == ["Linux", "Perfil 2", "Perfil 3"] and a.sel_btn == "A"
    assert not mapped(a.tiles["gyro"]) and not mapped(a.tiles["leds"]) and not mapped(a.xr_card)
    assert part(a, "P3") is None and part(a, "P1") is not None and "P1/P2" in a.map_help.cget("text")
    x, _y, _r = PARTS["A"][1]                                   # Xbox face layout, like the Ultimate 2
    assert a.map_canvas.coords(part(a, "A")["body"])[0] == pytest.approx((x - 15) * a.s)
    assert "Swap" not in chips(a) and "LS_Up" not in chips(a) and "P3" not in chips(a) and "TurboAuto" in chips(a)
    assert "firmware 2.04" in a.fw_label.cget("text") and "Ultimate 2.4G receiver" in a.info_label.cget("text")
    a.select_slot(1)
    assert (a.v["keys"]["P1"].get(), a.v["keys"]["Star"].get()) == ("RB", "Menu")
    b = mk(BACKUP)                                              # an Ultimate 2 afterwards: its functions come back
    assert b.model is models.ULTIMATE2 and "LS_Up" in chips(b) and part(b, "P3") is not None


def test_remap_saves_the_whole_record(u24app, u24fake, monkeypatch):
    monkeypatch.setattr(theme, "AUTOSAVE_MS", 5)
    a = u24app
    u24fake.log.clear()
    a.v["keys"]["A"].set("B")
    pump(a, lambda: "Salvo" in a.status.cget("text") and not a.busy)
    writes = [e for e in u24fake.log if e[0] == protocol.CMD_WRITE]
    assert writes[0][3] == 0 and sum(e[2] for e in writes) == protocol.CFG_SIZE_BT
    assert u24fake.log[-1][0] == protocol.CMD_READ and u24fake.saves == 1   # verified, though the counter changed
    assert config.decode(bytes(u24fake.cfg), L)["slots"][0]["mapping"]["A"] == "B"
    a.select_slot(2)
    a.v["name"].set("Ação")
    pump(a, lambda: u24fake.saves == 2 and not a.busy)
    assert bytes(u24fake.cfg[84:116]) == "Ação".encode("utf-16-le").ljust(32, b"\0")


def test_restore_verifies_without_what_the_firmware_owns(u24app, u24fake, dlg, tmp_path):
    f = tmp_path / "u24.bin"
    f.write_bytes(REAL)
    dlg.open = str(f)
    u24app.restore()
    pump(u24app, lambda: not u24app.busy)
    assert "restaurado" in u24app.status.cget("text") and u24fake.saves == 1 and bytes(u24fake.cfg) != REAL


def test_joystick_numbering(u24app):
    a = u24app
    a.pad_event(1, 1, 3)                                        # js button 3 is X on its generic HID node
    a.pad_event(1, 1, 13)                                       # and 13 is L3
    assert {"X", "L3"} <= a.pad_down
    a.pad_event(32767, 2, 5)                                    # axis 5 is LT: xpad's axis 2
    a.pad_event(-32767, 2, 2)                                   # axis 2 is RX: xpad's axis 3
    assert a.pad_axes[2] == 32767 and a.pad_axes[3] == -32767 and "LT" in a.pad_down
    a.pad_event(1, 1, 2)                                        # no button 2
    assert a.trigger_level("LT") == 1.0

