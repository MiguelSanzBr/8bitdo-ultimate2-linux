"""Keep an Ultimate 2.4G on X read, like Windows does, so it stays connected.

xpad only polls a pad while some program has its input node open. With nobody reading (no game open), the 2.4G
receiver takes the host for gone: right after the reconnection a profile switch causes (on X the receiver drops and
re-enumerates), it switches the controller off within ~5 s. Windows polls the pad all the time, so there it stays on.
This keeps the joystick node of every 8BitDo XInput pad of that PID (2dc8:3106, which the 1st-gen Ultimate Bluetooth
shares: reading it does no harm there) open and drained, reopening it after each reconnection. Run by ``u2ctl keepalive`` (the package's systemd user service).
"""
import glob
import itertools
import os
import select
import time

from . import discovery, protocol

DEV = "/dev/input"           # overridable by tests


def find_nodes():
    """Joystick nodes of the 8BitDo XInput pads (Ultimate 2.4G on X) plugged in now."""
    want = f"product=3/{protocol.VID:04x}/{protocol.PID_BT_XINPUT:04x}/"
    return [f"{DEV}/{os.path.basename(e)}" for e in sorted(glob.glob(discovery.SYS + "/class/input/js*"))
            if want in discovery._read(e + "/device/uevent").decode(errors="replace").lower()]


def run(rounds=None, scan=1.0):
    """Hold every pad's node open and drain it; rescan for new pads every ``scan`` seconds (``rounds``: tests)."""
    held, due = {}, 0.0                                # node -> fd; when to rescan
    try:
        for _ in itertools.count() if rounds is None else range(rounds):
            if time.monotonic() >= due:                # not on every input event: a game sends hundreds a second
                due = time.monotonic() + scan
                for node in find_nodes():
                    if node not in held:
                        try:
                            held[node] = os.open(node, os.O_RDONLY | os.O_NONBLOCK)
                        except OSError:                # not readable yet (udev still setting the ACL)
                            pass
            ready = select.select(list(held.values()), [], [], scan)[0] if held else time.sleep(scan) or []
            for node, fd in list(held.items()):
                if fd in ready:
                    try:
                        if os.read(fd, 512):
                            continue
                    except OSError:
                        pass
                    os.close(fd)                       # the pad went away (reconnection): reopen on the next scan
                    del held[node]
    finally:
        for fd in held.values():
            os.close(fd)
