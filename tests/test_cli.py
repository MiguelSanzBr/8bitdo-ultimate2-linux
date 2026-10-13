"""CLI main() end to end against the fake controller."""
import json
import struct
import argparse

import pytest

from ultimate2 import cli, config, device
from ultimate2.protocol import CFG_SIZE, CMD_WRITE


def run(monkeypatch, *args):
    cli.main(list(args))


@pytest.fixture
def seeded(fake):
    """Fake controller holding a valid profile-0 config (gamepad_mode 0)."""
    base = bytearray(b"\xff" * CFG_SIZE)
    struct.pack_into("<H", base, 16, 0)
    new, _ = config.encode(config.default_slot(config.decode(bytes(base)), 0, "Hello"), bytes(base))
    fake.cfg[:] = new
    fake.pending[:] = new
    return fake


def test_list(fake, monkeypatch, capsys):
    run(monkeypatch, "list")
    out = capsys.readouterr().out
    assert "/dev/hidraw-fake  2dc8:310b  wired (XInput)  poll=/dev/input/js-fake" in out
    fake.usb_pid = 0x1234
    run(monkeypatch, "list")
    assert "2dc8:1234  ?" in capsys.readouterr().out


def test_info(fake, monkeypatch, capsys):
    run(monkeypatch, "-d", fake.path, "info")
    out = capsys.readouterr().out
    assert "firmware    1.10\n" in out and "beta" not in out
    assert "report pid  0x6012 (Ultimate 2)" in out and "gamepad_mode=" in out
    assert "controller" not in out                           # wired: nothing behind a dongle


def test_info_through_the_dongle(fake, monkeypatch, capsys):
    fake.pad = {"battery": 86, "firmware": 110, "edition": 3}
    run(monkeypatch, "info")
    assert "controller  firmware 1.10, battery 86%, colorway 3\n" in capsys.readouterr().out


def test_info_beta(fake, monkeypatch, capsys):
    fake.beta, fake.report_pid = 3, 0x1111
    run(monkeypatch, "info")
    out = capsys.readouterr().out
    assert "firmware    1.10 beta 3" in out and "0x1111 (?)" in out


def test_info_no_answer(fake, monkeypatch):
    monkeypatch.setattr(device.Device, "info", lambda self: None)
    with pytest.raises(SystemExit, match="no answer from controller"):
        run(monkeypatch, "info")


def test_dump_stdout_and_file(seeded, monkeypatch, capsys, tmp_path):
    run(monkeypatch, "dump")
    doc = json.loads(capsys.readouterr().out)
    assert doc["slots"][0]["name"] == "Hello"
    out = tmp_path / "d.json"
    run(monkeypatch, "dump", "-o", str(out))
    assert capsys.readouterr().out == "" and json.loads(out.read_text()) == doc


def _dump(monkeypatch, capsys, tmp_path):
    f = tmp_path / "c.json"
    run(monkeypatch, "dump", "-o", str(f))
    capsys.readouterr()
    return f, json.loads(f.read_text())


def test_apply_changes(seeded, monkeypatch, capsys, tmp_path):
    f, doc = _dump(monkeypatch, capsys, tmp_path)
    doc["slots"][0]["name"] = "Edited"
    doc["slots"][0]["rumble"]["left"] = 0.5
    f.write_text(json.dumps(doc))
    run(monkeypatch, "apply", str(f))
    out = capsys.readouterr().out
    assert "slots/0/name" in out and "slots/0/rumble/left" in out and "saved and verified" in out
    assert config.decode(bytes(seeded.cfg))["slots"][0]["name"] == "Edited"


def test_apply_nothing_and_dry_run(seeded, monkeypatch, capsys, tmp_path):
    f, doc = _dump(monkeypatch, capsys, tmp_path)
    run(monkeypatch, "apply", str(f))
    assert "(nothing)" in capsys.readouterr().out
    doc["slots"][0]["name"] = "Dry"
    f.write_text(json.dumps(doc))
    run(monkeypatch, "apply", "--dry-run", str(f))
    out = capsys.readouterr().out
    assert "slots/0/name" in out and "saved" not in out
    assert all(c != CMD_WRITE for c, *_ in seeded.log)


def test_apply_verify_failure(seeded, monkeypatch, capsys, tmp_path):
    f, doc = _dump(monkeypatch, capsys, tmp_path)
    doc["slots"][0]["name"] = "Bad"
    f.write_text(json.dumps(doc))
    seeded.corrupt_commit = True
    with pytest.raises(SystemExit, match="verify failed"):
        run(monkeypatch, "apply", str(f))


def test_new_slot(seeded, monkeypatch, capsys):
    run(monkeypatch, "new-slot", "1", "--name", "Foo")
    out = capsys.readouterr().out
    assert "slots/1/name" in out and "saved and verified" in out
    assert config.decode(bytes(seeded.cfg))["slots"][1]["name"] == "Foo"
    run(monkeypatch, "new-slot", "2", "-n")
    assert "slots/2/name" in capsys.readouterr().out
    assert config.decode(bytes(seeded.cfg))["slots"][2]["name"] != "Linux"


def test_backup_restore(seeded, monkeypatch, capsys, tmp_path):
    f = tmp_path / "raw.bin"
    run(monkeypatch, "backup", str(f))
    assert f"saved {CFG_SIZE} bytes" in capsys.readouterr().out
    assert f.read_bytes() == bytes(seeded.cfg)
    new = bytes(range(256)) * 6 + bytes(56)
    f.write_bytes(new)
    run(monkeypatch, "restore", str(f))
    assert capsys.readouterr().out.strip() == "restored" and bytes(seeded.cfg) == new


def test_restore_wrong_size(seeded, monkeypatch, tmp_path):
    f = tmp_path / "short.bin"
    f.write_bytes(b"abc")
    with pytest.raises(SystemExit, match="expected 1592 bytes, got 3"):
        run(monkeypatch, "restore", str(f))


def test_restore_verify_failed(seeded, monkeypatch, capsys, tmp_path):
    f = tmp_path / "raw.bin"
    f.write_bytes(bytes(CFG_SIZE))
    seeded.corrupt_commit = True
    with pytest.raises(SystemExit, match="verify failed"):
        run(monkeypatch, "restore", str(f))


def test_unknown_subcommand_falls_through(fake, monkeypatch):
    # argparse can't produce this; it only exists to cover the final elif's implicit else
    class P:
        def parse_args(self, argv):
            return argparse.Namespace(cmd="bogus", device=None)
    monkeypatch.setattr(cli, "parser", lambda: P())
    cli.main([])


def test_theme_show_and_set(fake, monkeypatch, capsys):
    run(monkeypatch, "theme")
    assert capsys.readouterr().out.strip() == "dynamic"
    run(monkeypatch, "theme", "off")
    assert capsys.readouterr().out.strip() == "off" and fake.theme == 5


def test_theme_unknown_value(fake, monkeypatch, capsys):
    fake.theme = 9
    run(monkeypatch, "theme")
    assert capsys.readouterr().out.strip() == "unknown (9)"


def test_parser():
    a = cli.parser().parse_args(["-d", "/dev/x", "new-slot", "1"])
    assert (a.device, a.cmd, a.slot, a.name, a.dry_run) == ("/dev/x", "new-slot", 1, "Linux", False)
    with pytest.raises(SystemExit):
        cli.parser().parse_args([])
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["new-slot", "3"])
