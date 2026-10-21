"""``u2ctl`` — command line interface: inspect, back up, edit and restore the controller config."""
import argparse
import json
import struct
import sys

from . import config, device, discovery
from .protocol import PID_BT_XINPUT, PIDS, THEMES, VID


def parser():
    ap = argparse.ArgumentParser(prog="u2ctl", description="Configure the 8BitDo Ultimate 2 Wireless (and the 1st-gen "
                                 "Ultimate Bluetooth, on a USB cable) on Linux.")
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
        return

    dev = device.Device(a.device, knock=True)
    try:
        _run(a, dev)
    finally:
        dev.close()


def _run(a, dev):
    if a.cmd == "info":
        i = dev.info() or sys.exit("no answer from controller")
        cfg = dev.read_config()
        mode, slot = struct.unpack_from("<HH", cfg, 16)
        print(f"device      {dev.path} ({VID:04x}:{dev.pid:04x} {PIDS.get(dev.pid, '?')})")
        print(f"firmware    {i['firmware'] / 100:.2f}" + (f" beta {i['beta']}" if i["beta"] else ""))
        print(f"report pid  0x{i['device_pid']:04x} ({PIDS.get(i['device_pid'], '?')})")
        print(f"mode/slot   gamepad_mode={mode} cur_slot={slot}")
        pad = dev.pad_status() if dev.model.pad_status else None
        if pad:                                    # 2.4G: the controller behind the dongle
            print(f"controller  firmware {pad['firmware'] / 100:.2f}, battery {pad['battery']}%, colorway {pad['edition']}")
    elif a.cmd == "dump":
        text = json.dumps(config.decode(dev.read_config()), indent=2, ensure_ascii=False)
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
            doc = config.default_slot(config.decode(cur), a.slot, a.name)
        new, changed = config.encode(doc, cur)
        print("changed:", *changed or ["(nothing)"], sep="\n  ")
        if changed and not a.dry_run:
            dev.write_config(new)
            if dev.read_config() != new:
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
        if dev.read_config() != data:
            sys.exit("verify failed: controller config differs from the backup")
        print("restored")
