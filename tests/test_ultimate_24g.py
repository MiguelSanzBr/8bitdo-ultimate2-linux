"""Ultimate 2.4G: framing, record layout, transport, the XInput -> config mode switch over usbfs, discovery, CLI.

The expected bytes come from the hardware (controller firmware 2.04, receiver 1.10) and from 8BitDoAdvance.dll.
"""
import ctypes
import json
import os
import struct

import pytest

from fake_device import FakeController
from ultimate2 import cli, config, device, discovery, models
from ultimate2.device import Device
from ultimate2.protocol import (BT_EXIT, CFG_SIZE, CFG_SIZE_BT, CHUNK, CMD_COMMIT, CMD_READ, CMD_WRITE, COMMIT_KEY_BT,
                                build_request, crc16_24g)

M, L = models.ULTIMATE_24G, "ultimate_24g"
SIZE = CFG_SIZE_BT
# a controller that never had a custom profile: erased flash, gamepad_mode 1 (switch on D), cur_slot 4
BLANK = b"\xff" * 16 + bytes([1, 0, 4, 0]) + b"\xff" * (SIZE - 20)
# read from a real controller on D (firmware 2.04): three profiles, crc_value = the firmware's save counter (60)
REAL = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "ultimate24g_config.bin"), "rb").read()


@pytest.fixture
def u24(monkeypatch):
    f = FakeController(cfg=BLANK, firmware=204, usb_pid=0x3012).install(monkeypatch)
    yield f
    f.close()


@pytest.fixture
def fast(monkeypatch):
    orig = Device.recv
    monkeypatch.setattr(Device, "recv", lambda self, cmd, timeout=0.5, **kw: orig(self, cmd, min(timeout, 0.2), **kw))


def run(*args):
    cli.main(list(args))


def new_profile(base=BLANK, n=0, name="x"):
    return config.encode(config.default_slot(config.decode(base, L), n, name, L), base, L)[0]


# ------------------------------------------------------------ protocol
def test_requests_match_the_wire():
    # the header read that the controller answered: length byte, no CRC (the DLL's u32 length)
    assert build_request(CMD_READ, total=20, length=20, with_crc=M.header_crc, prefixed=M.prefixed)[:24].hex(" ") == \
        "81 25 04 02 00 00 00 14 00 00 00 14 00 00 00 00 00 00 00 00 00 00 00 00"
    pkt = build_request(CMD_COMMIT, sub=COMMIT_KEY_BT, with_crc=False, prefixed=True)
    assert len(pkt) == 64 and pkt[:19] == bytes([0x81, 17, 4, 6, 0, 0x15, 0]) + bytes(12)


def test_record_crc():
    assert crc16_24g(BLANK) == 0x10FE and crc16_24g(b"") == 0xFFFF


def test_model():
    assert (M.cfg_size, M.commit_key, M.knock, M.layout) == (1652, 0x15, "usb", L)
    assert not (M.header_crc or M.reports or M.colorway or M.leds or M.gyro or M.xinput_rumble or M.pad_status)
    assert M.echo_offset and M.own_slot and M.whole_writes and M.buttons == tuple(config.BUTTONS_BT)


# ------------------------------------------------------------ record
def test_decode_a_real_record():
    d = config.decode(REAL, L)
    assert (d["crc_value"], d["gamepad_mode"], d["cur_slot"]) == (60, 1, 0)
    assert [s["name"] for s in d["slots"]] == ["Linux", "Perfil 2", "Perfil 3"]          # UTF-16LE
    s = d["slots"][1]
    assert s["mapping"]["Star"] == "Menu" and (s["mapping"]["P1"], s["mapping"]["P2"]) == ("RB", "LB")
    assert "sixaxis" not in s and "xinput_rumble" not in s and s["button_macros"]["flag"] == "enabled"
    assert config.encode(d, REAL, L)[1] == []                    # nothing changed: nothing to write


def test_default_slot_like_the_app():
    s = config.default_slot(config.decode(BLANK, L), 1, "Linux", L)["slots"][1]
    assert s["flag"] == s["mapping"]["flag"] == s["button_macros"]["flag"] == "enabled"
    assert [s["mapping"][b] for b in config.BUTTONS_BT] == ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "L3", "R3",
        "Select", "Start", "Menu", "Home", "Up", "Down", "Left", "Right", "None", "None"]
    assert s["triggers"] == dict(flag="enabled", left_start=0, left_end=255, right_start=0, right_end=255)
    assert s["sticks"]["left_end"] == 128 and s["rumble"] == dict(flag="enabled", left=1.0, right=1.0)
    sw = config.decode(BLANK, L)
    sw["gamepad_mode"] = 0
    assert config.default_slot(sw, 0, "x", L)["slots"][0]["mapping"]["Star"] == "Screenshot"


def test_encode_codes_name_and_crc():
    doc = config.default_slot(config.decode(BLANK, L), 0, "Perfil ação", L)
    doc["slots"][0]["mapping"].update(A="B", B="A", P1="Home", P2="Swap")
    new, changed = config.encode(doc, BLANK, L)
    o = 224 + 4
    assert struct.unpack_from("<2I", new, o) == (0x1000, 0x2000)
    assert struct.unpack_from("<2I", new, o + 4 * 18) == (0x20000, 0x8000000)
    assert new[20:52] == "Perfil ação".encode("utf-16-le").ljust(32, b"\0")       # UTF-16LE, not BE
    assert new[476:480] == struct.pack("<I", 0x20200911) and new[868:] == BLANK[868:]   # other slots untouched
    crc_in = bytearray(new)
    crc_in[12:16] = BLANK[12:16]
    assert struct.unpack_from("<I", new, 12)[0] == crc16_24g(crc_in)            # over the record as it stood
    assert "slots/0/name" in changed and config.decode(new, L)["slots"][0]["name"] == "Perfil ação"
    d = config.decode(new, L)
    d["slots"][0]["mapping"]["A"] = "0x00040000"                                 # a code the table does not know
    assert config.decode(config.encode(d, new, L)[0], L)["slots"][0]["mapping"]["A"] == "0x00040000"


def test_same_ignores_what_the_firmware_owns():
    new = new_profile(n=2, name="z")
    assert config.changed_span(BLANK, new) == (8, SIZE - 1)      # slot 2 flag .. its macros (last: a padding byte)
    kept = bytearray(new)
    kept[12:16] = b"\x05\0\0\0"                                  # the firmware's save counter
    kept[18:20] = b"\x01\0"                                      # and its own active profile
    assert config.same(new, bytes(kept), L) and not config.same(new, bytes(kept))
    assert config.same(new, bytes(kept), L, (0, SIZE)) and not config.same(new, BLANK, L)
    kept[16] = 0
    assert not config.same(new, bytes(kept), L) and config.same(new, bytes(kept), L, (17, SIZE))
    assert not config.same(new, b"\xff" * CFG_SIZE, L)


# ------------------------------------------------------------ transport
def test_device_status(u24):
    d = Device()
    try:
        assert d.model is M and d.pid == 0x3012
        assert d.info() == {"firmware": 204, "beta": 0, "device_pid": 0x3012}
        assert d.edition() is None                               # byte 6 of its version answer is the PID
        assert d.current_slot() == 4 and d.read_config() == BLANK
        d.report(False)                                          # nothing sent: its app never toggles reports
        assert {e[0] for e in u24.log} == {CMD_READ}
    finally:
        d.close()


def test_write_whole_record_commit_0x15_and_verify(u24):
    new = new_profile()
    d = Device()
    try:
        d.write_config(new)
        writes = [e for e in u24.log if e[0] == CMD_WRITE]
        assert writes[0][3] == 0 and sum(e[2] for e in writes) == SIZE and max(e[2] for e in writes) == CHUNK
        assert u24.log[-1][:2] == (CMD_COMMIT, COMMIT_KEY_BT)
        got = d.read_config()
        assert struct.unpack_from("<I", got, 12)[0] == 1 and got != new and config.same(new, got, L)
    finally:
        d.close()


def test_write_keeps_the_controllers_active_profile(u24):
    u24.cfg[18:20] = b"\x01\0"                                   # the profile button was pressed after the read
    new = new_profile()                                          # still says cur_slot 4
    d = Device()
    try:
        d.write_config(new)
        assert bytes(u24.pending[18:20]) == b"\x01\0"            # what was sent: the app reads cur_slot first
        u24.silent.add(CMD_READ)                                 # no answer to that read: the record goes as is
        d.write_config(new)
        assert bytes(u24.pending[18:20]) == b"\x04\0"
    finally:
        d.close()


def test_late_answers_with_another_offset_are_skipped(u24):
    u24.stale = 6                                                # answers for a wrong offset arrive first
    d = Device()
    try:
        assert d.read_config() == BLANK
        new = new_profile()
        u24.stale = 6
        d.write_config(new)
        assert config.same(new, d.read_config(), L) and u24.stale == 0
    finally:
        d.close()


def test_write_without_commit_answer(u24, fast):
    u24.silent.add(CMD_COMMIT)
    d = Device()
    try:
        with pytest.raises(IOError, match="did not confirm the save"):
            d.write_config(BLANK)
    finally:
        d.close()


# ------------------------------------------------------------ XInput -> config mode over usbfs
@pytest.fixture
def usbfs(monkeypatch):
    """Fake usbfs: records the ioctls (and what goes out on the endpoint), no sleeping."""
    calls, opened = [], []
    real_open = os.open
    monkeypatch.setattr(device.os, "open", lambda path, flags, *a: opened.append(path) or real_open(os.devnull, os.O_RDWR)
                        if path.startswith("/devx/bus/usb") else real_open(path, flags, *a))

    def ioctl(fd, req, arg, mutate=False):
        if req == device.USBDEVFS_BULK:
            ep, n, _t, ptr = struct.unpack_from("III4xP", arg)
            calls.append(("out", ep, ctypes.string_at(ptr, n)))
        elif req == device.USBDEVFS_IOCTL:
            calls.append(("driver", struct.unpack_from("ii", arg)[1]))
        else:
            calls.append((req, struct.unpack_from("I", arg)[0]))
        return 0
    monkeypatch.setattr(device.fcntl, "ioctl", ioctl)
    monkeypatch.setattr(device.time, "sleep", lambda s: None)
    return calls, opened


def test_usb_knock_sends_the_windows_sequence(usbfs):
    calls, opened = usbfs
    device.usb_knock("/devx/bus/usb/003/009")
    assert opened == ["/devx/bus/usb/003/009"]
    assert calls[:2] == [("driver", device.USBDEVFS_DISCONNECT), (device.USBDEVFS_CLAIMINTERFACE, 0)]
    outs = [c[2] for c in calls if c[0] == "out"]
    assert {c[1] for c in calls if c[0] == "out"} == {device.EP_OUT_24G}
    assert outs[:4] == [bytes.fromhex(h) for h in ("010302", "020803", "010302", "010306")]
    assert outs[4:] == [bytes([0, 8, 0, s, w, 0, 0, 0]) for s, w in ((1, 0), (0, 1), (1, 1), (5, 1), (0, 0))] * 3
    assert calls[-2:] == [(device.USBDEVFS_RELEASEINTERFACE, 0), ("driver", device.USBDEVFS_CONNECT)]


def test_usb_knock_when_the_pad_already_left(usbfs, monkeypatch):
    def gone(fd, req, arg, mutate=False):                        # it re-enumerated: nothing to give back
        if req == device.USBDEVFS_RELEASEINTERFACE:
            raise OSError(19, "No such device")
        return 0
    monkeypatch.setattr(device.fcntl, "ioctl", gone)
    device.usb_knock("/devx/bus/usb/003/009")


@pytest.mark.parametrize("err", [61, 5])
def test_usb_knock_without_xpad_on_it(usbfs, monkeypatch, err):
    calls, _ = usbfs
    fake = device.fcntl.ioctl

    def unbound(fd, req, arg, mutate=False):                     # nothing bound to the interface: ENODATA
        if req == device.USBDEVFS_IOCTL and struct.unpack_from("ii", arg)[1] == device.USBDEVFS_DISCONNECT:
            raise OSError(err, os.strerror(err))
        return fake(fd, req, arg, mutate)
    monkeypatch.setattr(device.fcntl, "ioctl", unbound)
    if err == 61:
        device.usb_knock("/devx/bus/usb/003/009")
        assert len([c for c in calls if c[0] == "out"]) == 4 + 15
    else:
        with pytest.raises(OSError):
            device.usb_knock("/devx/bus/usb/003/009")

@pytest.fixture
def on_x(monkeypatch, u24):
    """An Ultimate 2.4G on X: no config interface until it is knocked, then the fake one (``u24``) shows up."""
    state = {"knocked": [], "polls": 0}
    real = discovery.find_devices

    def find():
        if not state["knocked"]:
            return iter([])
        state["polls"] += 1
        return real() if state["polls"] > 1 else iter([])      # still re-enumerating on the first poll
    monkeypatch.setattr(discovery, "find_devices", find)
    monkeypatch.setattr(discovery, "find_24g_xinput", lambda: "/devx/bus/usb/003/009")
    monkeypatch.setattr(device, "usb_knock", lambda node: state["knocked"].append(node))
    monkeypatch.setattr(device.time, "sleep", lambda s: None)
    device.SWITCHED.clear()
    device.NOT_24G.clear()
    return state


def _exited(fake):
    import time
    end = time.time() + 2
    while not fake.exited and time.time() < end:
        pass
    return fake.exited


def test_device_switches_from_x_and_back(on_x, u24):
    d = Device(knock=True)
    assert d.knocked and d.model is M and on_x["knocked"] == ["/devx/bus/usb/003/009"]
    assert device.SWITCHED == {u24.path}
    d.close()
    assert _exited(u24) and not device.SWITCHED


def test_close_waits_for_the_pad_back_on_x(on_x, u24, monkeypatch):
    d = Device(knock=True)
    seen = iter([None, None, "/devx/bus/usb/003/010"])            # re-enumerating, then back as 3106
    monkeypatch.setattr(discovery, "find_24g_xinput", lambda: next(seen))
    d.close()
    assert next(seen, "all") == "all"
    on_x.update(knocked=[], polls=0)
    monkeypatch.setattr(discovery, "find_24g_xinput", lambda: "/devx/bus/usb/003/010")
    d = Device(knock=True)
    assert d.knocked
    monkeypatch.setattr(discovery, "find_24g_xinput", lambda: None)
    monkeypatch.setattr(device, "KNOCK_WAIT", 0)                 # it never comes back: close gives up
    d.close()

def test_gui_keeps_config_mode_and_gives_back_only_what_it_switched(on_x, u24):
    d = Device(knock=True, stay=True)                            # the GUI: switched, but stays in config mode
    d.close()
    assert not u24.exited and device.SWITCHED == {u24.path}
    device.leave_config_mode()
    assert _exited(u24) and not device.SWITCHED


def test_a_cable_on_d_is_never_switched_back(u24):
    device.SWITCHED.clear()
    d = Device(knock=True)                                       # 3012 already there: nothing to switch
    assert not d.knocked
    d.close()
    device.leave_config_mode()
    import time
    time.sleep(0.2)
    assert not u24.exited


def test_switch_failures(on_x, monkeypatch):
    monkeypatch.setattr(device, "KNOCK_WAIT", 0)
    with pytest.raises(SystemExit, match="Ultimate 2.4G did not switch"):
        Device(knock=True)
    device.NOT_24G.clear()

    def denied(node):
        raise PermissionError(13, "Permission denied")
    on_x.update(knocked=[], polls=0)
    monkeypatch.setattr(device, "usb_knock", denied)
    with pytest.raises(SystemExit, match="cannot switch the Ultimate 2.4G .*003/009.*udev"):
        Device(knock=True)

    def broken(node):
        raise OSError(5, "Input/output error")
    monkeypatch.setattr(device, "usb_knock", broken)
    with pytest.raises(SystemExit, match=r"cannot switch the Ultimate 2.4G .*Input/output error\)$"):
        Device(knock=True)

    def timed_out(node):                                          # the receiver did not take the packet
        raise OSError(110, "Connection timed out")
    monkeypatch.setattr(device, "usb_knock", timed_out)
    with pytest.raises(SystemExit, match="Ultimate 2.4G did not switch to config mode"):
        Device(knock=True)


def test_another_3106_pad_is_knocked_only_once(on_x, monkeypatch):
    """2dc8:3106 is shared (Ultimate C 2.4G, other receivers): the GUI retries every few seconds and must not keep
    taking such a pad from xpad and rumbling it."""
    monkeypatch.setattr(device, "KNOCK_WAIT", 0)
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([]))  # it never comes back as a config interface
    with pytest.raises(SystemExit, match="Ultimate 2.4G did not switch"):
        Device(knock=True)
    with pytest.raises(SystemExit, match="no 8BitDo"):
        Device(knock=True)
    assert on_x["knocked"] == ["/devx/bus/usb/003/009"]
    monkeypatch.setattr(discovery, "find_24g_xinput", lambda: "/devx/bus/usb/003/012")   # replugged: a new node
    with pytest.raises(SystemExit, match="Ultimate 2.4G did not switch"):
        Device(knock=True)
    assert on_x["knocked"] == ["/devx/bus/usb/003/009", "/devx/bus/usb/003/012"]


def test_leave_config_mode_skips_a_vanished_node(monkeypatch):
    device.SWITCHED.clear()
    device.SWITCHED.add("/dev/hidraw-gone")
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([("/dev/hidraw-gone", 0x3013, "/x")]))
    device.leave_config_mode()
    assert not device.SWITCHED


# ------------------------------------------------------------ discovery
USB_DESC = b"\x05\x01\x09\x05\xa1\x01\x85\x03\x85\x02\x09\x02\x85\x81\x09\x03\xc0"   # gamepad + config reports 0x02/0x81
BT_DESC = b"\x05\x01\x09\x05\xa1\x01\x85\x03\x85\x05\x09\x70\xc0"    # the same pad over Bluetooth: gamepad + rumble only


def _hidraw(sys_, idx, pid, desc, bus=3):
    hid = sys_ / "devices" / f"usb{idx}" / "3-3" / "3-3:1.0" / f"{bus:04X}:2DC8:{pid:04X}.000{idx}"
    hid.mkdir(parents=True)
    (hid / "uevent").write_text(f"HID_ID={bus:04X}:00002DC8:0000{pid:04X}\n")
    (hid / "report_descriptor").write_bytes(desc)
    cls = sys_ / "class" / "hidraw" / f"hidraw{idx}"
    cls.mkdir(parents=True)
    (cls / "device").symlink_to(hid)


def _usbdev(sys_, name, vid, pid, product, bus, dev):
    d = sys_ / "bus" / "usb" / "devices" / name
    d.mkdir(parents=True)
    for k, v in (("idVendor", vid), ("idProduct", pid), ("product", product), ("busnum", bus), ("devnum", dev)):
        (d / k).write_text(f"{v}\n")


@pytest.fixture
def sysfs(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "SYS", str(tmp_path))
    monkeypatch.setattr(discovery, "DEV", "/devx")
    return tmp_path


def test_an_idle_receiver_is_no_controller(sysfs):
    _hidraw(sysfs, 1, 0x3109, b"\x06\x7a\xff\x09\x01")         # no pad linked: looks like an Ultimate 2 interface
    assert list(discovery.find_devices()) == []

def test_config_interface_by_pid_and_report(sysfs):
    _hidraw(sysfs, 2, 0x3012, USB_DESC)                         # gamepad that also carries the config reports
    _hidraw(sysfs, 3, 0x3013, b"\x05\x01\x09\x05")              # no config report: not a config interface
    assert [(x[0], x[1]) for x in discovery.find_devices()] == [("/devx/hidraw2", 0x3012)]


def test_bluetooth_is_not_configurable(sysfs):
    _hidraw(sysfs, 1, 0x3012, BT_DESC, bus=5)
    _hidraw(sysfs, 2, 0x6012, BT_DESC, bus=5)                   # another model over Bluetooth
    assert list(discovery.find_devices()) == [] and discovery.bluetooth_24g()
    with pytest.raises(SystemExit, match="over Bluetooth, which has no configuration channel"):
        Device()


def test_bluetooth_detection_ignores_others(sysfs):
    _hidraw(sysfs, 1, 0x3012, USB_DESC)                         # the cable
    _hidraw(sysfs, 2, 0x6012, BT_DESC, bus=5)
    assert not discovery.bluetooth_24g()


def test_xinput_pad_is_found_but_not_the_ultimate_bluetooth(sysfs):
    _usbdev(sysfs, "3-1", "046d", "c52b", "Receiver", 3, 2)
    _usbdev(sysfs, "3-2", "2dc8", "3106", "8BitDo Ultimate Controller", 3, 5)      # the 1st-gen Ultimate Bluetooth
    assert discovery.find_24g_xinput() is None
    _usbdev(sysfs, "3-3", "2dc8", "3106", "8BitDo Ultimate 2.4G", 3, 9)
    _usbdev(sysfs, "usb3", "", "", "", "", "")
    assert discovery.find_24g_xinput() == "/devx/bus/usb/003/009"


# ------------------------------------------------------------ CLI
def test_cli_list(monkeypatch, capsys):
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([("/dev/hidraw4", 0x3013, "/x")]))
    monkeypatch.setattr(discovery, "find_input_node", lambda usb: "/dev/input/js0")
    monkeypatch.setattr(discovery, "find_bt_xinput", lambda: None)
    monkeypatch.setattr(discovery, "find_24g_xinput", lambda: "/dev/bus/usb/003/009")
    monkeypatch.setattr(discovery, "bluetooth_24g", lambda: True)
    run("list")
    out = capsys.readouterr().out
    assert "2dc8:3013  Ultimate 2.4G receiver" in out
    assert "/dev/bus/usb/003/009  2dc8:3106  Ultimate 2.4G (XInput)  (switched to config mode on use)" in out
    assert "Ultimate 2.4G over Bluetooth: no configuration channel" in out


def test_cli_info_dump_and_theme(u24, capsys):
    run("info")
    out = capsys.readouterr().out
    assert "2dc8:3012 Ultimate 2.4G)" in out and "firmware    2.04" in out and "cur_slot=4" in out
    run("dump")
    assert json.loads(capsys.readouterr().out)["slots"][0]["name"] == ""
    with pytest.raises(SystemExit, match="no LED themes"):
        run("theme")


def test_cli_new_slot_and_apply(u24, capsys, tmp_path):
    run("new-slot", "0", "--name", "Linux")
    assert "saved and verified" in capsys.readouterr().out and u24.saves == 1
    doc = config.decode(bytes(u24.cfg), L)
    assert doc["slots"][0]["name"] == "Linux"
    doc["slots"][0]["mapping"]["A"] = "B"
    f = tmp_path / "e.json"
    f.write_text(json.dumps(doc))
    run("apply", str(f))
    assert "saved and verified" in capsys.readouterr().out
    assert config.decode(bytes(u24.cfg), L)["slots"][0]["mapping"]["A"] == "B"


def test_cli_backup_restore(u24, capsys, tmp_path):
    f = tmp_path / "b.bin"
    run("backup", str(f))
    assert f.read_bytes() == BLANK and f"saved {SIZE} bytes" in capsys.readouterr().out
    run("restore", str(f))
    assert "restored" in capsys.readouterr().out and u24.saves == 1
