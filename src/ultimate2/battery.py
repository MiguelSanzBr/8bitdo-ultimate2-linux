"""Battery of an 8BitDo pad connected over Bluetooth.

Over Bluetooth the Ultimate 2.4G's gamepad report carries the HID "Battery Strength" usage (``05 06 09 20``,
0..100), and the kernel turns it into ``/sys/class/power_supply/hid-<mac>-battery`` (what UPower and the desktop's
battery applet show). Its 2.4G receiver's descriptor has no such field and answers no battery query, so there is no
battery reading on X; on the cable the pad is charging.
"""
import glob
import os

from . import discovery, protocol


def bluetooth():
    """``{"capacity": %, "status": "Discharging"…, "name": …}`` of the first 8BitDo pad on Bluetooth, or ``None``."""
    for p in sorted(glob.glob(discovery.SYS + "/class/power_supply/hid-*-battery")):
        if f"0005:{protocol.VID:04X}:" not in os.path.realpath(p + "/device").upper():
            continue
        info = dict(l.split("=", 1) for l in discovery._read(p + "/uevent").decode(errors="replace").splitlines()
                    if "=" in l)
        try:
            capacity = int(info.get("POWER_SUPPLY_CAPACITY", ""))
        except ValueError:
            continue                                   # no report yet: the kernel learns it from the first one
        return {"capacity": capacity, "status": info.get("POWER_SUPPLY_STATUS", "Unknown"),
                "name": info.get("POWER_SUPPLY_MODEL_NAME", "8BitDo")}
    return None
