"""find_devices / find_input_node / _read against a fake sysfs tree (never touches real /sys or /dev)."""
import os

import pytest

from ultimate2 import discovery as d
from ultimate2.protocol import VID


@pytest.fixture
def sysroot(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "SYS", str(tmp_path / "sys"))
    monkeypatch.setattr(d, "DEV", "/devx")
    return tmp_path / "sys"


def make_hid(sys_, idx, uevent, desc, usb="1-1"):
    usbdir = sys_ / "devices" / "pci" / f"usb{idx}" / usb
    hid = usbdir / f"{usb}:1.0" / f"0003:2DC8:6012.000{idx}"
    hid.mkdir(parents=True)
    if uevent is not None:
        (hid / "uevent").write_text(uevent)
    if desc is not None:
        (hid / "report_descriptor").write_bytes(desc)
    cls = sys_ / "class" / "hidraw" / f"hidraw{idx}"
    cls.mkdir(parents=True)
    (cls / "device").symlink_to(hid)
    return os.path.realpath(usbdir)


def hid_ev(vid, pid, bus=3):
    return f"DRIVER=hid\nHID_ID={bus:04X}:{vid:08X}:{pid:08X}\nHID_NAME=x\n"


def test_defaults_and_descriptors():
    assert (d.SYS, d.DEV) == ("/sys", "/dev")
    assert d.CONFIG_DESCRIPTORS == (b"\x06\x7a\xff", b"\x06\xa0\xff")


def test_read_oserror(tmp_path):
    assert d._read(str(tmp_path / "nope")) == b""
    (tmp_path / "f").write_bytes(b"abc")
    assert d._read(str(tmp_path / "f")) == b"abc"


def test_find_devices(sysroot):
    make_hid(sysroot, 0, hid_ev(0x046D, 0x6012), b"\x06\x7a\xff")           # other vendor
    make_hid(sysroot, 1, "HID_ID=zz:yy:xx\n", b"\x06\x7a\xff")               # bad HID_ID
    make_hid(sysroot, 2, "DRIVER=hid\n", b"\x06\x7a\xff")                    # no HID_ID line
    make_hid(sysroot, 3, hid_ev(VID, 0x6012), b"\x05\x01\x09")             # wrong descriptor prefix
    make_hid(sysroot, 4, hid_ev(VID, 0x6012), b"\x06\x7a\xff\x09")         # controller
    make_hid(sysroot, 5, hid_ev(VID, 0x6013), b"\x06\xa0\xff\x09")         # dongle
    make_hid(sysroot, 6, None, None)                                         # no uevent / descriptor at all
    u4 = os.path.realpath(sysroot / "devices" / "pci" / "usb4" / "1-1")
    u5 = os.path.realpath(sysroot / "devices" / "pci" / "usb5" / "1-1")
    assert list(d.find_devices()) == [("/devx/hidraw4", 0x6012, u4), ("/devx/hidraw5", 0x6013, u5)]


def test_find_dinput_wireless_keeps_gamepad_and_config_discovery_separate(sysroot):
    gamepad = b"\x05\x01\x09\x05\xa1\x01\x85\x01\xc0"
    vendor = b"\x06\x7a\xff\x09\x01\xa1\x01\x85\x02\x85\x81\xc0"
    cfg_usb = make_hid(sysroot, 0, hid_ev(VID, 0x6012), vendor)
    make_hid(sysroot, 1, hid_ev(VID, 0x6012, bus=5), gamepad)
    make_hid(sysroot, 2, hid_ev(VID, 0x6013), gamepad)
    make_hid(sysroot, 3, hid_ev(0x1234, 0x6012), gamepad)
    make_hid(sysroot, 4, hid_ev(VID, 0x6012), None)
    assert d.find_dinput_wireless() is None
    make_hid(sysroot, 5, hid_ev(VID, 0x6012), gamepad[:-1] + b"\x85\x02\x85\x81\xc0")
    assert d.find_dinput_wireless() == "/devx/hidraw5"
    assert list(d.find_devices()) == [("/devx/hidraw0", 0x6012, cfg_usb)]


def test_find_input_node_js(sysroot):
    usb = make_hid(sysroot, 0, hid_ev(VID, 0x6012), b"\x06\x7a\xff")
    other = make_hid(sysroot, 1, hid_ev(VID, 0x6012), b"\x06\x7a\xff")
    for name, base in (("js0", other), ("js1", usb)):
        n = sysroot / "class" / "input" / name
        tgt = os.path.join(base, "1-1:1.0", "input", "in_" + name)
        os.makedirs(tgt)
        n.mkdir(parents=True)
        (n / "device").symlink_to(tgt)
    assert d.find_input_node(usb) == "/devx/input/js1"


def test_find_input_node_event_fallback(sysroot):
    usb = make_hid(sysroot, 0, hid_ev(VID, 0x6012), b"\x06\x7a\xff")
    n = sysroot / "class" / "input" / "event3"
    tgt = os.path.join(usb, "1-1:1.0", "input", "in3")
    os.makedirs(tgt)
    n.mkdir(parents=True)
    (n / "device").symlink_to(tgt)
    assert d.find_input_node(usb) == "/devx/input/event3"


def test_find_input_node_none(sysroot):
    usb = make_hid(sysroot, 0, hid_ev(VID, 0x6012), b"\x06\x7a\xff")
    assert d.find_input_node(usb) is None
