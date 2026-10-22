"""Battery over Bluetooth (the kernel's power_supply of the HID pad) and the Ultimate 2.4G's Bluetooth hints in u2ctl."""
import pytest

from fake_device import FakeController
from ultimate2 import battery, cli, config, discovery

SIZE = 1652
BLANK = b"\xff" * 16 + bytes([1, 0, 4, 0]) + b"\xff" * (SIZE - 20)


def run(*args):
    cli.main(list(args))


def _supply(sys_, name, hid_dir, uevent):
    dev = sys_ / "devices" / "virtual" / "misc" / "uhid" / hid_dir
    dev.mkdir(parents=True, exist_ok=True)
    ps = sys_ / "class" / "power_supply" / name
    ps.mkdir(parents=True)
    (ps / "device").symlink_to(dev)
    (ps / "uevent").write_text(uevent)


def test_battery_over_bluetooth(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "SYS", str(tmp_path))
    assert battery.bluetooth() is None
    _supply(tmp_path, "hid-00:11:22:33:44:55-battery", "0005:054C:09CC.0001",          # another vendor's pad
            "POWER_SUPPLY_CAPACITY=50\nPOWER_SUPPLY_STATUS=Discharging\n")
    _supply(tmp_path, "hid-e4:17:d8:00:00:02-battery", "0005:2DC8:6012.0002",          # another 8BitDo pad
            "POWER_SUPPLY_CAPACITY=40\nPOWER_SUPPLY_STATUS=Discharging\n")
    _supply(tmp_path, "hid-e4:17:d8:00:00:00-battery", "0005:2DC8:3012.0009",          # no report yet
            "POWER_SUPPLY_STATUS=Unknown\n")
    assert battery.bluetooth() is None
    _supply(tmp_path, "hid-e4:17:d8:00:00:01-battery", "0005:2DC8:3012.000A",
            "POWER_SUPPLY_NAME=hid-e4:17:d8:00:00:01-battery\nPOWER_SUPPLY_CAPACITY=92\n"
            "POWER_SUPPLY_STATUS=Discharging\nPOWER_SUPPLY_MODEL_NAME=8BitDo Ultimate wireless\nnoise\n")
    assert battery.bluetooth() == {"capacity": 92, "status": "Discharging", "name": "8BitDo Ultimate wireless"}


def test_cli_battery_and_list(monkeypatch, capsys):
    monkeypatch.setattr(battery, "bluetooth", lambda: {"capacity": 91, "status": "Discharging", "name": "8BitDo X"})
    run("battery")
    assert "8BitDo X: 91% (discharging)" in capsys.readouterr().out
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([]))
    monkeypatch.setattr(discovery, "bluetooth_24g", lambda: True)
    run("list")
    assert "battery     91% (discharging)" in capsys.readouterr().out
    monkeypatch.setattr(battery, "bluetooth", lambda: None)
    run("list")
    assert "battery" not in capsys.readouterr().out
    with pytest.raises(SystemExit, match="only known over Bluetooth"):
        run("battery")


def test_cli_warns_about_bluetooth_with_the_x_configuration(monkeypatch, capsys):
    doc = config.decode(BLANK, "ultimate_24g")
    doc["gamepad_mode"] = 3                                     # the X configuration, read through the receiver
    f = FakeController(cfg=config.encode(doc, BLANK, "ultimate_24g")[0], firmware=204, usb_pid=0x3013).install(monkeypatch)
    try:
        monkeypatch.setattr(discovery, "bluetooth_24g", lambda: True)
        run("info")
        assert "also connected over Bluetooth" in capsys.readouterr().out
        monkeypatch.setattr(discovery, "bluetooth_24g", lambda: False)
        run("info")
        assert "Bluetooth" not in capsys.readouterr().out
    finally:
        f.close()


def test_joystick_node_over_bluetooth(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "SYS", str(tmp_path))
    monkeypatch.setattr(discovery, "DEV", "/devx")
    assert discovery.bluetooth_24g_input() is None
    for i, hid_id in enumerate(("0003:00002DC8:00003012", "0005:00002DC8:00003012")):   # cable on D, then Bluetooth
        hid = tmp_path / "devices" / "virtual" / "misc" / "uhid" / f"{hid_id[:4]}:2DC8:3012.000{i}"
        (hid / "input" / f"input{i}" / f"js{i}").mkdir(parents=True)
        (hid / "uevent").write_text(f"HID_ID={hid_id}\n")
        (tmp_path / "class" / "hidraw" / f"hidraw{i}").mkdir(parents=True)
        (tmp_path / "class" / "hidraw" / f"hidraw{i}" / "device").symlink_to(hid)
        (tmp_path / "class" / "input").mkdir(parents=True, exist_ok=True)
        (tmp_path / "class" / "input" / f"js{i}").mkdir()
        (tmp_path / "class" / "input" / f"js{i}" / "device").symlink_to(hid / "input" / f"input{i}")
    assert discovery.bluetooth_24g_input() == "/devx/input/js1"
