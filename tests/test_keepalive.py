"""keepalive: keep Ultimate 2.4G pads on X read (xpad only polls while someone reads), so they stay connected."""
import os

import pytest

from ultimate2 import cli, discovery, keepalive


def _js(sys_, idx, product):
    dev = sys_ / "devices" / "input" / f"js-input{idx}"
    dev.mkdir(parents=True)
    (dev / "uevent").write_text(f"PRODUCT={product}\n")
    js = sys_ / "class" / "input" / f"js{idx}"
    js.mkdir(parents=True)
    (js / "device").symlink_to(dev)


def test_keepalive_finds_only_8bitdo_pads_on_x(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "SYS", str(tmp_path / "sys"))
    monkeypatch.setattr(keepalive, "DEV", "/devx/input")
    _js(tmp_path / "sys", 0, "3/2dc8/3106/114")
    _js(tmp_path / "sys", 1, "3/045e/028e/114")
    _js(tmp_path / "sys", 2, "3/2dc8/3012/200")
    assert keepalive.find_nodes() == ["/devx/input/js0"]


def test_keepalive_holds_drains_and_reopens(tmp_path, monkeypatch):
    sys_, dev = tmp_path / "sys", tmp_path / "dev"
    dev.mkdir()
    monkeypatch.setattr(discovery, "SYS", str(sys_))
    monkeypatch.setattr(keepalive, "DEV", str(dev))
    for i in range(4):
        _js(sys_, i, "3/2dc8/3106/114")
    (dev / "js0").write_bytes(b"\x01" * 16)            # events, then EOF: the pad went away -> reopened later
    (dev / "js1").mkdir()                              # read error -> closed
    (dev / "js2").write_bytes(b"")
    os.chmod(dev / "js2", 0)                           # not readable yet -> skipped
    os.mkfifo(dev / "js3")                             # a quiet pad: open, nothing to read -> kept
    writer = os.open(dev / "js3", os.O_RDWR)
    opened, closed = [], []
    real_open, real_close = os.open, os.close

    def track_open(path, flags):
        fd = real_open(path, flags)                    # raises for js2 (no permission) and js3 (missing)
        opened.append((os.path.basename(path), fd))
        return fd
    monkeypatch.setattr(keepalive.os, "open", track_open)
    monkeypatch.setattr(keepalive.os, "close", lambda fd: closed.append(fd) or real_close(fd))
    keepalive.run(rounds=3, scan=0.01)
    os.close(writer)
    names = [n for n, _fd in opened]
    assert names.count("js3") == 1                     # quiet but there: held the whole time
    assert names.count("js0") == 2                     # held in round 1, EOF in round 2, reopened in round 3
    assert names.count("js1") == 3                     # read error: closed and retried every round
    assert "js2" not in names or os.getuid() == 0      # unreadable: skipped
    closed.remove(writer)                              # the test's own writer end
    assert sorted(fd for _n, fd in opened) == sorted(closed)   # everything closed in the end


def test_keepalive_without_pads_just_waits(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "SYS", str(tmp_path))
    slept = []
    monkeypatch.setattr(keepalive.time, "sleep", slept.append)
    keepalive.run(rounds=2, scan=0.5)
    assert slept == [0.5, 0.5]


def test_cli_keepalive(monkeypatch):
    calls = []
    monkeypatch.setattr(keepalive, "run", lambda: calls.append(1))
    cli.main(["keepalive"])
    assert calls == [1]


def test_keepalive_runs_until_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "SYS", str(tmp_path))
    ticks = []

    def sleep(s):
        ticks.append(s)
        if len(ticks) == 3:
            raise KeyboardInterrupt                    # how the service is stopped
    monkeypatch.setattr(keepalive.time, "sleep", sleep)
    with pytest.raises(KeyboardInterrupt):
        keepalive.run()
    assert ticks == [1.0, 1.0, 1.0]
