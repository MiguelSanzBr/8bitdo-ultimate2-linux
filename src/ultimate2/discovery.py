"""Find the controller in sysfs: its vendor config ``hidraw`` node and the joystick node of the same device."""
import glob
import os

from . import protocol

SYS, DEV = "/sys", "/dev"   # roots, overridable by tests
# report descriptors of the config channel: usage page 0xFF7A (controller) / 0xFFA0 (2.4G dongle)
CONFIG_DESCRIPTORS = (b"\x06\x7a\xff", b"\x06\xa0\xff")


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return b""


def find_devices():
    """Yield ``(hidraw_path, pid, usb_dir)`` for every 8BitDo vendor config interface."""
    for d in sorted(glob.glob(SYS + "/class/hidraw/hidraw*")):
        ue = _read(d + "/device/uevent").decode(errors="replace")
        hid_id = next((l.split("=")[1] for l in ue.splitlines() if l.startswith("HID_ID=")), "")
        try:
            _, vid, pid = (int(x, 16) for x in hid_id.split(":"))
        except ValueError:
            continue
        if vid != protocol.VID:
            continue
        # the Ultimate Bluetooth's config mode has one gamepad interface; its config reports sit inside it
        if pid != protocol.PID_BT_CONFIG and _read(d + "/device/report_descriptor")[:3] not in CONFIG_DESCRIPTORS:
            continue
        usb_dir = os.path.dirname(os.path.dirname(os.path.realpath(d + "/device")))
        yield DEV + "/" + os.path.basename(d), pid, usb_dir


def find_input_node(usb_dir):
    """Joystick node (``js*``, else ``event*``) of the same USB device.

    The firmware only services the config endpoint while the host keeps draining its XInput
    reports, so this node must stay open during config I/O.
    """
    for pat in (SYS + "/class/input/js*", SYS + "/class/input/event*"):
        for n in sorted(glob.glob(pat)):
            if os.path.realpath(n + "/device").startswith(usb_dir + "/"):
                return DEV + "/input/" + os.path.basename(n)
    return None


def find_bt_xinput():
    """Event node of a 1st-gen Ultimate Bluetooth on a cable in XInput mode (``2dc8:3106``, product
    :data:`~ultimate2.protocol.BT_PRODUCT`), or ``None``. Its 2.4G receiver shares the PID, not the name."""
    for n in sorted(glob.glob(SYS + "/class/input/event*")):
        usb = os.path.realpath(n + "/device")
        while usb != "/" and not os.path.exists(usb + "/idVendor"):
            usb = os.path.dirname(usb)
        ids = (_read(usb + "/idVendor").strip(), _read(usb + "/idProduct").strip(), _read(usb + "/product").strip())
        if ids == (b"%04x" % protocol.VID, b"%04x" % protocol.PID_BT_XINPUT, protocol.BT_PRODUCT.encode()):
            return DEV + "/input/" + os.path.basename(n)
    return None
