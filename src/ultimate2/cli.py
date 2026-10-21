"""``u2ctl`` — command line interface: inspect, back up, edit and restore the controller config."""
import argparse
import json
import struct
import sys

from . import battery, config, device, discovery, keepalive, models
from .protocol import PID_BT_XINPUT, PIDS, THEMES, VID

BT_CONFLICT = ("warning: the controller is also connected over Bluetooth, which uses the D-mode configuration: "
               "changes made here (X mode) do not apply there")


def parser():
    ap = argparse.ArgumentParser(prog="u2ctl", description="Configure the 8BitDo Ultimate 2 Wireless (and the 1st-gen "
                                 "Ultimate Bluetooth, on a USB cable, and the Ultimate 2.4G) on Linux.")
    ap.add_argument("-d", "--device", help="hidraw node (default: auto-detect)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list detected devices")
    sub.add_parser("info", help="firmware version and active slot")
    p = sub.add_parser("dump", help="read config as JSON")
    p.add_argument("-o", "--output")
    p = sub.add_parser("apply", help="write edited JSON back")
    p.add_argument("file")
    p.add_argument("-n", "--dry-run", action="store_true")
    p = sub.add_parser("new-slot", help="turn slot 0-2 into a custom profile with app defaults")
    p.add_argument("slot", type=int, choices=range(3))
    p.add_argument("--name", default="Linux")
    p.add_argument("-n", "--dry-run", action="store_true")
    p = sub.add_parser("theme", help="show or set the active LED theme")
    p.add_argument("name", nargs="?", choices=list(THEMES.values()))
    sub.add_parser("battery", help="battery of the controller over Bluetooth (Ultimate 2.4G)")
    sub.add_parser("keepalive", help="keep Ultimate 2.4G pads on X read so they stay connected (systemd user service)")
    p = sub.add_parser("backup", help="save raw config record")
    p.add_argument("file")
    p = sub.add_parser("restore", help="write raw config record")
    p.add_argument("file")
    return ap


def main(argv=None):
    a = parser().parse_args(argv)

    if a.cmd == "list":
        for path, pid, usb in discovery.find_devices():
            print(f"{path}  {VID:04x}:{pid:04x}  {PIDS.get(pid, '?')}  poll={discovery.find_input_node(usb)}")
        bt = discovery.find_bt_xinput()
        if bt:
            print(f"{bt}  {VID:04x}:{PID_BT_XINPUT:04x}  {PIDS[PID_BT_XINPUT]}  (switched to config mode on use)")
        u24 = discovery.find_24g_xinput()
        if u24:
            print(f"{u24}  {VID:04x}:{PID_BT_XINPUT:04x}  Ultimate 2.4G (XInput)  (switched to config mode on use)")
        if discovery.bluetooth_24g():
            print("Ultimate 2.4G over Bluetooth: no configuration channel there (use the cable or the receiver)")
            b = battery.bluetooth()
            if b:
                print(f"battery     {b['capacity']}% ({b['status'].lower()})")
        return

    if a.cmd == "battery":
        b = battery.bluetooth() or sys.exit("no 8BitDo controller reporting its battery: it is only known over "
                                            "Bluetooth (the 2.4G receiver does not report it)")
        print(f"{b['name']}: {b['capacity']}% ({b['status'].lower()})")
        return

    if a.cmd == "keepalive":
        keepalive.run()
        return

    dev = device.Device(a.device, knock=True)
    try:
        _run(a, dev)
    finally:
        dev.close()


def _run(a, dev):
    layout = dev.model.layout or None
    if a.cmd == "info":
        i = dev.info() or sys.exit("no answer from controller")
        cfg = dev.read_config()
        mode, slot = struct.unpack_from("<HH", cfg, 16)
        print(f"device      {dev.path} ({VID:04x}:{dev.pid:04x} {PIDS.get(dev.pid, '?')})")
        print(f"firmware    {i['firmware'] / 100:.2f}" + (f" beta {i['beta']}" if i["beta"] else ""))
        print(f"report pid  0x{i['device_pid']:04x} ({PIDS.get(i['device_pid'], '?')})")
        print(f"mode/slot   gamepad_mode={mode} cur_slot={slot}")
        if dev.model is models.ULTIMATE_24G and mode == 3 and discovery.bluetooth_24g():
            print(BT_CONFLICT)
        pad = dev.pad_status() if dev.model.pad_status else None
        if pad:                                    # 2.4G: the controller behind the dongle
            print(f"controller  firmware {pad['firmware'] / 100:.2f}, battery {pad['battery']}%, colorway {pad['edition']}")
    elif a.cmd == "dump":
        text = json.dumps(config.decode(dev.read_config(), layout), indent=2, ensure_ascii=False)
        if a.output:
            with open(a.output, "w") as f:
                f.write(text + "\n")
        else:
            print(text)
    elif a.cmd in ("apply", "new-slot"):
        cur = dev.read_config()
        if a.cmd == "apply":
            with open(a.file) as f:
                doc = json.load(f)
        else:
            doc = config.default_slot(config.decode(cur, layout), a.slot, a.name, layout)
        new, changed = config.encode(doc, cur, layout)
        print("changed:", *changed or ["(nothing)"], sep="\n  ")
        if changed and not a.dry_run:
            dev.write_config(new)
            if not config.same(new, dev.read_config(), layout):
                sys.exit("verify failed: controller config differs from what was written")
            print("saved and verified")
    elif a.cmd == "theme":
        if not dev.model.leds:
            sys.exit("this controller has no LED themes")
        if a.name:
            dev.set_theme(next(k for k, v in THEMES.items() if v == a.name))
        t = dev.get_theme()
        print(THEMES.get(t, f"unknown ({t})"))
    elif a.cmd == "backup":
        with open(a.file, "wb") as f:
            f.write(dev.read_config())
        print(f"saved {dev.model.cfg_size} bytes to {a.file}")
    elif a.cmd == "restore":
        with open(a.file, "rb") as f:
            data = f.read()
        if len(data) != dev.model.cfg_size:
            sys.exit(f"{a.file}: expected {dev.model.cfg_size} bytes, got {len(data)}")
        dev.write_config(data)
        if not config.same(data, dev.read_config(), layout):
            sys.exit("verify failed: controller config differs from the backup")
        print("restored")
