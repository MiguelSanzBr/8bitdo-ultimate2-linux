"""Device transport against the fake firmware (never touches real hardware)."""
import os
import select

import pytest

from ultimate2 import discovery
from ultimate2 import device as dm
from ultimate2.device import Device
from ultimate2.protocol import CFG_SIZE, CMD_COMMIT, CMD_READ, CMD_REPORT, CMD_WRITE


@pytest.fixture
def fast(monkeypatch):
    """Cap every recv() timeout (default 0.5 s, commit 3 s) so failure paths stay quick."""
    orig = Device.recv
    monkeypatch.setattr(Device, "recv", lambda self, cmd, timeout=0.5: orig(self, cmd, min(timeout, 0.2)))


@pytest.fixture
def dev(fake):
    d = Device()
    yield d
    d.close()


def _stub(dev, recv):
    dev.send = lambda *a, **k: None
    dev.recv = recv


def test_retries():
    assert dm.RETRIES == 30


# ------------------------------------------------------------ construction
def test_explicit_path_matching(fake):
    d = Device(fake.path)
    assert (d.path, d.pid) == (fake.path, fake.usb_pid) and d.poll_fd is not None
    d.close()


def test_explicit_path_not_matching(fake, monkeypatch):
    prev = os.open
    monkeypatch.setattr(os, "open", lambda p, f, *a: prev(fake.path if p == "/dev/other" else p, f, *a))
    d = Device("/dev/other")
    assert (d.path, d.pid, d.poll_fd) == ("/dev/other", 0, None)
    d.close()


def test_no_devices(monkeypatch):
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([]))
    with pytest.raises(SystemExit, match="no 8BitDo config interface"):
        Device()


def test_no_input_node(fake, monkeypatch):
    monkeypatch.setattr(discovery, "find_input_node", lambda usb_dir: None)
    d = Device()
    assert d.poll_fd is None
    d.close()


def test_permission_denied(fake, monkeypatch):
    prev = os.open

    def op(p, f, *a):
        if p == fake.path:
            raise PermissionError
        return prev(p, f, *a)
    monkeypatch.setattr(os, "open", op)
    with pytest.raises(SystemExit, match="permission denied"):
        Device()


def test_js_open_failure_warns(fake, monkeypatch, capsys):
    prev = os.open

    def op(p, f, *a):
        if p == fake.js_path:
            raise OSError("boom")
        return prev(p, f, *a)
    monkeypatch.setattr(os, "open", op)
    d = Device()
    assert d.poll_fd is None and "warning: cannot open" in capsys.readouterr().err
    d.close()


# ------------------------------------------------------------ low level io
def test_drain_pending(dev, fake):
    for _ in range(3):
        fake._dev.send(b"\0" * 64)
    dev._drain()
    assert not select.select([dev.fd], [], [], 0.05)[0]


def test_send_pads_and_crc(dev, fake):
    dev.send(CMD_WRITE, data=b"abc", total=10, offset=0)
    dev.send(CMD_READ, total=10, length=5)       # data defaults to zero padding
    dev.recv(CMD_READ)
    assert fake.log[0][:3] == (CMD_WRITE, 0, 3) and fake.log[1][:3] == (CMD_READ, 0, 5)


def test_recv(dev, fake):
    assert dev.recv(CMD_READ, timeout=0) is None            # loop never entered
    assert dev.recv(CMD_READ, timeout=0.05) is None         # select timeout
    fake._dev.send(b"\x02\x04")                             # too short
    fake._dev.send(b"\x03" * 64)                            # bad magic
    fake._dev.send(b"\x02\x05" + b"\0" * 62)                # bad second byte
    fake._reply(CMD_WRITE, b"zz")                           # other command
    fake._reply(CMD_READ, b"abc")
    assert dev.recv(CMD_READ) == (3, b"abc")


def test_query_and_info(dev, fake):
    r = dev.query(b"\x81\x04\x00\x01")                        # want=None
    assert r[:6] == b"\x02\x04\x04\x00\x00\x01"
    assert dev.query(b"\x81\x04\x00\x01", want=b"nope", timeout=0.1) is None
    assert dev.query(b"\x81\x04\x00\x01", timeout=0) is None
    assert dev.info() == {"firmware": 110, "beta": 0, "device_pid": 0x6012}


def test_info_none(dev, fake, monkeypatch):
    fake.silent = {0x0100}
    monkeypatch.setattr(Device, "query", lambda self, raw, want=None, timeout=0.5: None)
    assert dev.info() is None


def test_report(dev, fake):
    dev.report(True)
    dev.report(False)
    assert [(c, s) for c, s, *_ in fake.log] == [(CMD_REPORT, 1), (CMD_REPORT, 0)]


def test_close_skips_none_poll(dev):
    os.close(dev.poll_fd)
    dev.poll_fd = None
    # closed by the fixture afterwards; only fd is closed here


# ------------------------------------------------------------ edition / theme / slot
def test_edition(dev, fake):
    assert dev.edition() == 3
    fake.edition = 0
    assert dev.edition() == 0


def test_edition_no_answer(dev, monkeypatch):
    monkeypatch.setattr(dev, "query", lambda raw, want=None, timeout=0.5: None)
    assert dev.edition() is None


def test_pad_status_through_the_dongle(dev, fake):
    assert dev.pad_status() is None                          # wired: the query goes unanswered
    fake.pad = {"battery": 86, "firmware": 110, "edition": 3}
    assert dev.pad_status() == {"battery": 86, "firmware": 110, "edition": 3}


def test_get_and_set_theme(dev, fake):
    assert dev.get_theme() == 2
    dev.set_theme(3)
    assert fake.theme == 3 and dev.get_theme() == 3


def test_get_theme_no_answer(dev, monkeypatch):
    monkeypatch.setattr(dev, "recv", lambda cmd, timeout=0.5: None)
    assert dev.get_theme() is None


def test_set_theme_not_confirmed(dev, monkeypatch):
    monkeypatch.setattr(dev, "recv", lambda cmd, timeout=0.5: None)
    with pytest.raises(IOError, match="LED theme"):
        dev.set_theme(4)


def test_current_slot(fake):
    fake.cfg[18:20] = (2).to_bytes(2, "little")
    d = Device()
    assert d.current_slot() == 2
    d.close()


def test_current_slot_no_answer(dev, monkeypatch):
    monkeypatch.setattr(dev, "recv", lambda cmd, timeout=0.5: (4, b"1234"))   # short answer
    assert dev.current_slot() is None
    monkeypatch.setattr(dev, "recv", lambda cmd, timeout=0.5: None)
    assert dev.current_slot() is None


# ------------------------------------------------------------ config read/write
DATA = bytes(range(256)) * 6 + bytes(56)


def test_fake_roundtrip(dev, fake):
    dev.write_config(DATA)
    assert dev.read_config() == DATA == bytes(fake.cfg)


def test_read_retry_with_drop(dev, fake, fast):
    fake.cfg[:] = DATA
    fake.drop = 1
    assert dev.read_config() == DATA


def test_write_retry_with_drop(dev, fake, fast):
    fake.drop = 2                        # report(False) unanswered, first chunk lost
    dev.write_config(DATA)
    assert bytes(fake.cfg) == DATA


def test_read_zero_length_and_none_retry(dev):
    chunks = iter([(0, b""), None] + [(len(DATA[o:o + 45]), DATA[o:o + 45]) for o in range(0, CFG_SIZE, 45)])
    _stub(dev, lambda cmd, timeout=0.5: next(chunks))
    assert dev.read_config() == DATA


def test_read_exhausted(dev):
    _stub(dev, lambda cmd, timeout=0.5: None)
    with pytest.raises(IOError, match="read failed at offset 0"):
        dev.read_config()


def test_write_zero_length_then_ok(dev):
    acks = iter([(0, b"")] + [(45, b"")] * 40)

    def recv(cmd, timeout=0.5):
        if cmd == CMD_WRITE:
            return next(acks)
        return (0, b"") if cmd == CMD_COMMIT else None
    _stub(dev, recv)
    dev.write_config(DATA)


def test_write_exhausted(dev):
    _stub(dev, lambda cmd, timeout=0.5: None)
    with pytest.raises(IOError, match="write failed at offset 0"):
        dev.write_config(DATA)


def test_commit_not_confirmed(dev, fake, fast):
    fake.silent = {CMD_COMMIT}
    with pytest.raises(IOError, match="did not confirm"):
        dev.write_config(DATA)
    assert fake.log[-1][0] == CMD_REPORT          # reporting re-enabled even on failure


def test_partial_write_only_touches_range(dev, fake):
    data = bytearray(fake.cfg)
    data[1208:1220] = bytes(range(12))          # slot 0 led_dynamic
    data[5] = 0x00                              # outside the range: must not be written
    dev.write_config(bytes(data), 1208, 1220)
    assert fake.cfg[1208:1220] == bytes(range(12)) and fake.cfg[5] == 0xFF
    writes = [(c, ln, off) for c, _, ln, off in fake.log if c == CMD_WRITE]
    assert writes == [(CMD_WRITE, 12, 1208)]


def test_partial_write_bad_range(dev, fake):
    with pytest.raises(AssertionError):
        dev.write_config(bytes(fake.cfg), 10, 10)
