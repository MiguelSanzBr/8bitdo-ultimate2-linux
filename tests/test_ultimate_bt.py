"""1st-gen Ultimate Bluetooth: XInput -> config mode knock, framing, 1652-byte record, transport, CLI."""
import os
import struct

import pytest

from fake_device import FakeController
from ultimate2 import cli, config, device, discovery, models
from ultimate2.device import Device
from ultimate2.protocol import (BT_KNOCK, CFG_SIZE_BT, CMD_COMMIT, CMD_READ, CMD_REPORT, CMD_WRITE, COMMIT_KEY_BT,
                                PID_BT_CONFIG, build_request)

# read from a real controller (firmware 1.02): slot 0 enabled with the app's defaults, gamepad_mode 3
CONFIG_BT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "ultimatebt_config.bin"), "rb").read()


@pytest.fixture
def bt(monkeypatch):
    f = FakeController(cfg=CONFIG_BT, firmware=102, report_pid=PID_BT_CONFIG, usb_pid=PID_BT_CONFIG).install(monkeypatch)
    f.edition = 0x22
    yield f
    f.close()


def run(*args):
    cli.main(list(args))


# ------------------------------------------------------------ protocol
def test_prefixed_requests_match_what_the_controller_answered():
    assert build_request(CMD_READ, total=20, length=20, prefixed=True)[:19].hex(" ") == \
        "81 25 04 02 00 00 00 14 00 24 1b 14 00 00 00 00 00 00 00"
    pkt = build_request(CMD_READ, total=CFG_SIZE_BT, length=45, prefixed=True)   # largest chunk fills the report
    assert len(pkt) == 64 and pkt[:15].hex(" ") == "81 3e 04 02 00 00 00 2d 00 30 cf 74 06 00 00"
    assert build_request(CMD_COMMIT, sub=COMMIT_KEY_BT, with_crc=False, prefixed=True)[:8].hex(" ") == \
        "81 11 04 06 00 15 00 00"                                   # as captured from the Windows app


# ------------------------------------------------------------ record layout
def test_fields_fit_and_never_overlap():
    size = {"B": 1, "H": 2, "I": 4, "f": 4, "X": 4, "C": 4, "F": 4, "K": 4, "M": 4, "str32": 32}
    used = []
    for _path, off, kind in config.FIELDS_BT:
        used += range(off, off + (int(kind[1:]) if kind[0] == "r" else size[kind]))
    assert len(used) == len(set(used)) and max(used) < CFG_SIZE_BT
    assert CFG_SIZE_BT - len(used) == 21                        # alignment padding only


def test_decode_real_record_and_unknown_size():
    d = config.decode(CONFIG_BT)
    assert (d["gamepad_mode"], d["cur_slot"]) == (3, 6)
    s = d["slots"][0]
    assert s["flag"] == "enabled" and len(s["mapping"]) == 21 and list(s["mapping"])[-2:] == ["P1", "P2"]
    assert [s["mapping"][b] for b in ("A", "B", "X", "Y", "Star", "P1")] == ["B", "A", "Y", "X", "Menu", "None"]
    assert "sixaxis" not in s and "macros" not in s and "xinput_rumble" not in s
    assert d["slots"][1]["flag"] == "0xffffffff" and d["slots"][1]["button_macros"]["records"][0]["key_index"] == "ff" * 36
    new, changed = config.encode(d, CONFIG_BT)
    assert changed == [] and new[:12] == CONFIG_BT[:12] and new[16:] == CONFIG_BT[16:]
    with pytest.raises(ValueError, match="unknown config record size 5"):
        config.decode(b"12345")


@pytest.mark.parametrize("mode, face, star, trig", [(0, ["A", "B", "X", "Y"], "Screenshot", 77),
                                                    (1, ["A", "B", "X", "Y"], "Menu", 0),
                                                    (3, ["B", "A", "Y", "X"], "Menu", 0)])
def test_default_slot(mode, face, star, trig):
    base = bytearray(CONFIG_BT)
    struct.pack_into("<H", base, 16, mode)
    doc = config.default_slot(config.decode(bytes(base)), 1, "Linux")
    new, changed = config.encode(doc, bytes(base))
    s = config.decode(new)["slots"][1]
    assert s["flag"] == "enabled" and s["name"] == "Linux"
    assert [s["mapping"][b] for b in ("A", "B", "X", "Y", "Star", "P1")] == face + [star, "None"]
    assert (s["sticks"]["left_start"], s["sticks"]["left_end"], s["triggers"]["left_start"]) == (0, 128, trig)
    assert s["button_macros"]["flag"] == "enabled" and s["button_macros"]["records"][3]["digital_joy"] == "00" * 18
    assert all(c.startswith("slots/1/") for c in changed)
    assert config.changed_span(bytes(base), new)[0] >= 4    # crc_value alone is ignored


def test_raw_field_length_is_checked():
    doc = config.decode(CONFIG_BT)
    doc["slots"][0]["button_macros"]["records"][0]["digital_joy"] = "00"
    with pytest.raises(ValueError, match="expected 18 bytes"):
        config.encode(doc, CONFIG_BT)


# ------------------------------------------------------------ discovery
def _usb(sys_, name, vid, pid, product, event):
    usb = sys_ / "devices" / name
    for k, v in (("idVendor", vid), ("idProduct", pid), ("product", product)):
        (usb / k).parent.mkdir(parents=True, exist_ok=True)
        (usb / k).write_text(v + "\n")
    node = usb / f"{name}:1.0" / "input" / "input9"
    node.mkdir(parents=True)
    cls = sys_ / "class" / "input" / event
    cls.mkdir(parents=True)
    (cls / "device").symlink_to(node)


def test_find_bt_xinput(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "SYS", str(tmp_path / "sys"))
    monkeypatch.setattr(discovery, "DEV", "/devx")
    assert discovery.find_bt_xinput() is None
    _usb(tmp_path / "sys", "3-1", "2dc8", "3106", "Ultimate Wireless Controller", "event3")   # its 2.4G receiver
    _usb(tmp_path / "sys", "3-2", "2dc8", "3106", "8BitDo Ultimate Controller", "event7")
    assert discovery.find_bt_xinput() == "/devx/input/event7"
    (tmp_path / "sys" / "class" / "input" / "event8").mkdir()           # dangling node: walks up to "/"
    assert discovery.find_bt_xinput() == "/devx/input/event7"


def test_config_mode_needs_no_vendor_descriptor(tmp_path, monkeypatch):
    from test_discovery import hid_ev, make_hid
    monkeypatch.setattr(discovery, "SYS", str(tmp_path / "sys"))
    monkeypatch.setattr(discovery, "DEV", "/devx")
    make_hid(tmp_path / "sys", 1, hid_ev(0x2DC8, PID_BT_CONFIG), b"\x05\x01\x09\x05")
    assert [d[:2] for d in discovery.find_devices()] == [("/devx/hidraw1", PID_BT_CONFIG)]


# ------------------------------------------------------------ knock
def test_knock_plays_the_app_sequence(monkeypatch):
    sent, writes = [], []
    monkeypatch.setattr(device.os, "open", lambda p, f: 99)
    monkeypatch.setattr(device.os, "close", lambda fd: None)
    monkeypatch.setattr(device.os, "write", lambda fd, b: writes.append(struct.unpack("<qqHHi", b)[2:]))
    monkeypatch.setattr(device.time, "sleep", lambda s: None)

    def ioctl(fd, req, eff):
        assert req == device.EVIOCSFF and len(eff) == 48
        sent.append(struct.unpack_from("<HhH", eff, 0) + struct.unpack_from("<HH", eff, 16))
        struct.pack_into("<h", eff, 2, 5)                        # kernel assigns effect id 5
    monkeypatch.setattr(device.fcntl, "ioctl", ioctl)
    device.knock("/dev/input/event7")
    assert [(s >> 8, w >> 8) for *_, s, w in sent] + [(0, 0)] == list(BT_KNOCK)
    assert [e[1] for e in sent] == [-1, 5, 5, 5] and writes == [(0x15, 5, 1), (0x15, 5, 0)]


@pytest.fixture
def xinput_then_config(bt, monkeypatch):
    """Only the XInput node at first; the config interface shows up once knocked."""
    state = {"knocked": [], "polls": 0}
    real = discovery.find_devices

    def find():
        if not state["knocked"]:
            return iter([])
        state["polls"] += 1
        return real() if state["polls"] > 1 else iter([])      # still re-enumerating on the first poll
    monkeypatch.setattr(discovery, "find_devices", find)
    monkeypatch.setattr(discovery, "find_bt_xinput", lambda: "/dev/input/event7")
    monkeypatch.setattr(device, "knock", lambda node: state["knocked"].append(node))
    monkeypatch.setattr(device.time, "sleep", lambda s: None)
    return state


def test_device_knocks_and_switches_back(xinput_then_config, bt):
    with pytest.raises(SystemExit, match="no 8BitDo config interface"):
        Device()                                                 # the GUI never knocks
    d = Device(knock=True)
    assert d.knocked and d.model is models.ULTIMATE_BT and xinput_then_config["knocked"] == ["/dev/input/event7"]
    d.close()
    import time
    end = time.time() + 2
    while not bt.exited and time.time() < end:
        pass
    assert bt.exited


def test_knock_failures(xinput_then_config, monkeypatch):
    monkeypatch.setattr(device, "KNOCK_WAIT", 0)
    with pytest.raises(SystemExit, match="did not switch"):
        Device(knock=True)

    def denied(node):
        raise PermissionError(13, "Permission denied")
    xinput_then_config.update(knocked=[], polls=0)
    monkeypatch.setattr(device, "knock", denied)
    with pytest.raises(SystemExit, match="cannot switch .*event7"):
        Device(knock=True)


def test_no_knock_without_xinput_node(monkeypatch):
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([]))
    monkeypatch.setattr(discovery, "find_bt_xinput", lambda: None)
    with pytest.raises(SystemExit, match="no 8BitDo config interface"):
        Device(knock=True)


def test_close_ignores_a_vanished_device(bt):
    d = Device()
    d.knocked = True
    os.close(d.fd)
    d.fd = os.open(os.devnull, os.O_RDONLY)                       # writing fails: the pad already left
    d.close()


# ------------------------------------------------------------ transport
def test_device_reads_and_writes_the_bt_record(bt):
    d = Device()
    try:
        assert d.model is models.ULTIMATE_BT and d.model.cfg_size == CFG_SIZE_BT and d.poll_fd is not None
        assert d.info() == {"firmware": 102, "beta": 0, "device_pid": PID_BT_CONFIG} and d.edition() == 0x22
        bt.log.clear()
        assert d.read_config() == CONFIG_BT
        reads = [e for e in bt.log if e[0] == CMD_READ]
        # the session stays open (reports off) until leave(): its app only turns reports back on when it exits
        assert max(e[2] for e in reads) == 45 and bt.log[0][:2] == (CMD_REPORT, 0) and bt.log[-1][0] == CMD_READ
        bt.log.clear()
        new = config.encode(config.default_slot(config.decode(CONFIG_BT), 1, "Linux"), CONFIG_BT)[0]
        d.write_config(new)
        cmds = [e[:2] for e in bt.log]
        assert cmds[0] == (CMD_REPORT, 0) and cmds[-1] == (CMD_COMMIT, COMMIT_KEY_BT)
        assert {e[0] for e in bt.log[1:-1]} == {CMD_WRITE} and bytes(bt.cfg) == new
        bt.log.clear()
        assert d.live() == (0x20000000, (0x7f, 0x80, 0x80, 0x7f, 0, 0))
        bt.live = bytes.fromhex("00200020 00ff80 7f c7 00 0000")
        assert d.live() == (0x20002000, (0, 0xff, 0x80, 0x7f, 0xc7, 0))
    finally:
        d.close()


def test_info_without_answer(bt, monkeypatch):
    d = Device()
    try:
        monkeypatch.setattr(d, "query", lambda *a, **k: None)
        assert d.info() is None
    finally:
        d.close()


# ------------------------------------------------------------ CLI
def test_cli_list(bt, monkeypatch, capsys):
    monkeypatch.setattr(discovery, "find_bt_xinput", lambda: "/dev/input/event7")
    run("list")
    out = capsys.readouterr().out
    assert "2dc8:6007  Ultimate Bluetooth (config mode)" in out
    assert "/dev/input/event7  2dc8:3106  Ultimate Bluetooth (XInput)  (switched to config mode on use)" in out


def test_cli_info_and_theme(bt, capsys):
    run("info")
    out = capsys.readouterr().out
    assert "firmware    1.02" in out and "gamepad_mode=3 cur_slot=6" in out and "controller" not in out
    with pytest.raises(SystemExit, match="no LED themes"):
        run("theme")


def test_cli_new_slot_backup_restore(bt, capsys, tmp_path):
    run("new-slot", "1", "--name", "Linux")
    assert "saved and verified" in capsys.readouterr().out
    assert config.decode(bytes(bt.cfg))["slots"][1]["name"] == "Linux"
    f = tmp_path / "bt.bin"
    run("backup", str(f))
    assert f"saved {CFG_SIZE_BT} bytes" in capsys.readouterr().out
    f.write_bytes(CONFIG_BT)
    run("restore", str(f))
    assert bytes(bt.cfg) == CONFIG_BT
    f.write_bytes(CONFIG_BT[:1592])
    with pytest.raises(SystemExit, match=f"expected {CFG_SIZE_BT} bytes, got 1592"):
        run("restore", str(f))


def test_live_reopens_the_session_once(bt):
    d = Device()
    try:
        bt.drop = 1                                              # first ask lost: REPORT 0, then ask again
        bt.log.clear()
        assert d.live() is not None
        assert [e[:2] for e in bt.log] == [(3, 0x15), (CMD_REPORT, 0), (3, 0x15)]
        bt.silent.add(3)
        assert d.live() is None
    finally:
        d.close()


def test_stay_and_leave(xinput_then_config, bt):
    d = Device(knock=True, stay=True)                            # the GUI: knocked, but keeps config mode
    assert not d.knocked and d.model is models.ULTIMATE_BT
    d.close()
    assert not bt.exited
    d = Device()
    bt.log.clear()
    d.leave()
    _wait(lambda: bt.exited)
    assert bt.log[-1][:2] == (CMD_REPORT, 1)
    d.close()


def _wait(cond):
    import time
    end = time.time() + 2
    while not cond() and time.time() < end:
        pass
    assert cond()


def test_leave_config_mode(bt, monkeypatch):
    other = [("/dev/hidraw-other", 0x310B, ""), ("/dev/hidraw-gone", PID_BT_CONFIG, "")]
    monkeypatch.setattr(discovery, "find_devices", lambda: iter(other + [(bt.path, PID_BT_CONFIG, "")]))
    real_open = os.open

    def fake_open(path, flags, *a):
        if path == "/dev/hidraw-gone":
            raise FileNotFoundError(path)
        return real_open(path, flags, *a)                         # bt.path is still served by FakeController
    monkeypatch.setattr(os, "open", fake_open)
    device.leave_config_mode()
    _wait(lambda: bt.exited)


def test_leave_config_mode_ignores_write_errors(monkeypatch):
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([("/dev/null", PID_BT_CONFIG, "")]))
    closed = []
    monkeypatch.setattr(device.os, "open", lambda p, f: 7)
    monkeypatch.setattr(device.os, "write", lambda fd, b: (_ for _ in ()).throw(OSError(19, "No such device")))
    monkeypatch.setattr(device.os, "close", closed.append)
    device.leave_config_mode()
    assert closed == [7]
