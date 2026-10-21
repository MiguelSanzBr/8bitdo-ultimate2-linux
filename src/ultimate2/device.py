"""Transport to the controller over ``/dev/hidraw``: read, write and save the config, LED theme, status."""
import fcntl
import os
import select
import struct
import sys
import time

from . import discovery, models
from .protocol import (BT_EXIT, BT_KNOCK, CHUNK, CMD_COMMIT, CMD_GET_THEME, CMD_LIVE, CMD_READ,
                       CMD_REPORT, CMD_SET_THEME, CMD_WRITE, LIVE_SUB, QUERY_VERSION, ANSWER_VERSION,
                       QUERY_PAD, ANSWER_PAD, REPORT_SIZE, build_request, parse_info, parse_reply)

RETRIES = 30             # the app's retry count per chunk
KNOCK_WAIT = 5.0         # seconds for the Ultimate Bluetooth to come back as its config-mode device
EVIOCSFF = 0x40304580    # _IOW('E', 0x80, struct ff_effect); sizeof(struct ff_effect) = 48 on 64-bit
EV_FF, FF_RUMBLE = 0x15, 0x50


def knock(node):
    """Switch an Ultimate Bluetooth from XInput to config mode: play the app's rumble steps (``BT_KNOCK``)
    through xpad's force feedback, which sends them as ``00 08 00 <strong> <weak> 00 00 00``."""
    fd = os.open(node, os.O_RDWR)
    try:
        eid = -1
        for i, (strong, weak) in enumerate(BT_KNOCK[:-1]):
            eff = bytearray(48)
            struct.pack_into("<HhH", eff, 0, FF_RUMBLE, eid, 0)
            struct.pack_into("<HH", eff, 10, 1000, 0)                    # replay: 1 s, no delay
            struct.pack_into("<HH", eff, 16, strong << 8, weak << 8)     # xpad sends magnitude >> 8
            fcntl.ioctl(fd, EVIOCSFF, eff)
            eid = struct.unpack_from("<h", eff, 2)[0]
            if i == 0:
                os.write(fd, struct.pack("<qqHHi", 0, 0, EV_FF, eid, 1))
            time.sleep(0.016)
        os.write(fd, struct.pack("<qqHHi", 0, 0, EV_FF, eid, 0))       # stop: the final (0, 0) step
    finally:
        os.close(fd)


def _find_or_knock():
    """Config interfaces; when none is there but an Ultimate Bluetooth is in XInput mode, switch it first.
    Returns ``(devices, knocked)``."""
    devs = list(discovery.find_devices())
    node = None if devs else discovery.find_bt_xinput()
    if not node:
        return devs, False
    try:
        knock(node)
    except OSError as e:
        sys.exit(f"cannot switch the Ultimate Bluetooth to config mode via {node} ({e})")
    end = time.time() + KNOCK_WAIT
    while time.time() < end:
        time.sleep(0.25)
        devs = [d for d in discovery.find_devices() if models.for_pid(d[1]).knock]
        if devs:
            time.sleep(0.5)                  # let udev apply the hidraw permissions
            return devs, True
    # now and then the pad powers off instead of coming back (same bytes, cause unknown)
    sys.exit("the Ultimate Bluetooth did not switch to config mode (if it turned off, press Home and try again)")


class Device:
    """One open controller. ``path`` selects a specific hidraw node (default: the first one found).

    Opening also opens the matching joystick node (see :func:`ultimate2.discovery.find_input_node`),
    without which the firmware ignores the config endpoint. Exits with a message (``SystemExit``)
    when there is no controller or no permission.

    ``model`` (:mod:`ultimate2.models`) says how this controller differs. With ``knock``, an Ultimate Bluetooth
    in XInput mode is switched to config mode first (and back by :meth:`close`, unless ``stay``: see
    :func:`leave_config_mode`).
    """

    def __init__(self, path=None, knock=False, stay=False):
        devs, knocked = _find_or_knock() if knock and not path else (list(discovery.find_devices()), False)
        self.knocked = knocked and not stay
        if path:
            devs = [d for d in devs if d[0] == path] or [(path, 0, "")]
        if not devs:
            sys.exit("no 8BitDo config interface found (is the controller plugged in / paired?)")
        self.path, self.pid, usb_dir = devs[0]
        self.model = models.for_pid(self.pid)
        self.poll_fd = None
        node = discovery.find_input_node(usb_dir) if usb_dir else None
        if node:
            try:
                self.poll_fd = os.open(node, os.O_RDONLY | os.O_NONBLOCK)
            except OSError as e:
                print(f"warning: cannot open {node} ({e}); controller may not answer", file=sys.stderr)
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError:
            sys.exit(f"permission denied on {self.path}: install udev/70-8bitdo-u2.rules (see README)")
        self._drain()

    def leave(self):
        """Ultimate Bluetooth: end the config session and switch back to a normal XInput gamepad, like the app on exit."""
        try:
            self.report(True)
            os.write(self.fd, BT_EXIT.ljust(REPORT_SIZE, b"\0"))
        except OSError:
            pass

    def close(self):
        if self.knocked:
            self.leave()
        for fd in (self.fd, self.poll_fd):
            if fd is not None:
                os.close(fd)

    # ------------------------------------------------------------ raw I/O
    def _drain(self):
        while select.select([self.fd], [], [], 0.02)[0]:
            os.read(self.fd, REPORT_SIZE)

    def send(self, cmd, sub=0, data=b"", total=0, offset=0, length=None, with_crc=True):
        os.write(self.fd, build_request(cmd, sub, data, total, offset, length, with_crc, prefixed=self.model.prefixed))

    def recv(self, cmd, timeout=0.5):
        """Wait for the answer to ``cmd``; returns ``(length, data)`` or ``None`` on timeout."""
        end = time.time() + timeout
        while (left := end - time.time()) > 0:
            if not select.select([self.fd], [], [], left)[0]:
                break
            r = parse_reply(os.read(self.fd, REPORT_SIZE), cmd)
            if r:
                return r
        return None

    def query(self, raw, want=None, timeout=0.5):
        """Send a fixed 64-byte command and return the first response (optionally matching a prefix)."""
        self._drain()
        os.write(self.fd, bytes(raw).ljust(REPORT_SIZE, b"\0"))
        end = time.time() + timeout
        while (left := end - time.time()) > 0:
            if not select.select([self.fd], [], [], left)[0]:
                break
            r = os.read(self.fd, REPORT_SIZE)
            if want is None or r.startswith(want):
                return r
        return None

    # ------------------------------------------------------------ status
    def info(self):
        """``{"firmware", "beta", "device_pid"}`` or ``None``.

        The Ultimate Bluetooth ignores ``CMD_INFO`` in config mode; its app reads the version query instead."""
        if self.model.info_by_version:
            r = self.query(QUERY_VERSION, want=ANSWER_VERSION)
            return {"firmware": r[2] | r[3] << 8, "beta": r[4], "device_pid": self.pid} if r else None
        r = self.query(b"\x81\x04\x00\x01", want=b"\x02\x04\x04\x00\x00\x01")
        return parse_info(r) if r else None

    def edition(self):
        """Colorway of the controller (the app's ``m_ControllerColor``), or ``None``."""
        r = self.query(QUERY_VERSION, want=ANSWER_VERSION)
        return r[6] if r else None

    def pad_status(self):
        """Through the dongle: ``{"battery", "firmware", "edition"}`` of the controller itself, or ``None`` (wired,
        or the controller does not answer). The app reads firmware and colour here; byte 18 is the battery %."""
        r = self.query(QUERY_PAD, want=ANSWER_PAD, timeout=.25)      # wired: nobody answers, keep it short
        return {"battery": r[18], "firmware": r[19] | r[20] << 8, "edition": r[23]} if r else None

    def live(self):
        """Ultimate Bluetooth in config mode (where it sends no gamepad reports): ``(buttons, axes)`` with the pressed
        buttons as key-code bits and ``axes`` = LX, LY, RX, RY, RT, LT (0-255), or ``None``."""
        self.send(CMD_LIVE, sub=LIVE_SUB, with_crc=False)
        r = self.recv(CMD_LIVE, timeout=0.2)
        if r is None:                            # reports came back on: reopen the session and ask again
            self.report(False)
            self.send(CMD_LIVE, sub=LIVE_SUB, with_crc=False)
            r = self.recv(CMD_LIVE, timeout=0.2)
        return (struct.unpack_from("<I", r[1])[0], tuple(r[1][4:10])) if r and r[0] >= 10 else None

    def report(self, on):
        """Turn the controller's input reports off/on around config writes (like the app).

        The Ultimate Bluetooth stops answering config requests once reports are back on, so its session is opened
        with reports off before reads too and only closed by :meth:`leave`, like its app does."""
        self.send(CMD_REPORT, sub=1 if on else 0, with_crc=False)
        self.recv(CMD_REPORT)

    def get_theme(self):
        """Active LED theme (see :data:`ultimate2.protocol.THEMES`), or ``None``."""
        self.send(CMD_GET_THEME)
        r = self.recv(CMD_GET_THEME)
        return r[1][0] if r and r[0] else None

    def set_theme(self, theme):
        self.send(CMD_SET_THEME, sub=theme)
        if self.recv(CMD_SET_THEME) is None:
            raise IOError("controller did not confirm the LED theme")

    def current_slot(self):
        """Active profile (0-2; 3 = default, no custom profile). Reads only the 20-byte header,
        like the app's ``getUltimate2CurrentSlot``."""
        self.send(CMD_READ, total=20, offset=0, length=20)
        r = self.recv(CMD_READ)
        return struct.unpack_from("<H", r[1], 18)[0] if r and r[0] >= 20 else None

    # ------------------------------------------------------------ config record
    def read_config(self):
        """The whole config record (``model.cfg_size`` bytes)."""
        if self.model.session:
            self.report(False)
        return self._read_record(self.model.cfg_size)

    def _read_record(self, size):
        buf = bytearray()
        tries = 0
        while len(buf) < size:
            self.send(CMD_READ, total=size, offset=len(buf), length=min(CHUNK, size - len(buf)))
            r = self.recv(CMD_READ)
            if not r or r[0] == 0:
                tries += 1
                if tries >= RETRIES:
                    raise IOError(f"read failed at offset {len(buf)}")
                continue
            tries = 0
            buf += r[1]
        return bytes(buf[:size])

    def write_config(self, data, start=0, end=None):
        """Write ``data[start:end]`` of the record and save it to flash.

        A sub-range is how the app updates one setting (``writeUltimate2dynamic`` writes 12 bytes at
        ``0x4b8 + 12*slot``). Raises ``IOError`` if a chunk or the save is not acknowledged.
        """
        size = self.model.cfg_size
        end = size if end is None else end
        assert len(data) == size and 0 <= start < end <= size
        self.report(False)
        off, tries = start, 0
        while off < end:
            self.send(CMD_WRITE, data=data[off:min(off + CHUNK, end)], total=size, offset=off)
            r = self.recv(CMD_WRITE)
            if not r or r[0] == 0:
                tries += 1
                if tries >= RETRIES:
                    raise IOError(f"write failed at offset {off}")
                continue
            tries = 0
            off += r[0]
        time.sleep(0.1)
        self.send(CMD_COMMIT, sub=self.model.commit_key, with_crc=False)
        ok = self.recv(CMD_COMMIT, timeout=3.0) is not None
        if not self.model.session:
            self.report(True)
        if not ok:
            raise IOError("controller did not confirm the save")


def leave_config_mode():
    """Switch every Ultimate Bluetooth found in config mode back to XInput (for front ends that opened it with
    ``stay=True``, when they close)."""
    for path, pid, _usb in discovery.find_devices():
        if models.for_pid(pid).knock:
            try:
                fd = os.open(path, os.O_WRONLY)
            except OSError:
                continue
            try:
                os.write(fd, build_request(CMD_REPORT, sub=1, with_crc=False, prefixed=True))
                os.write(fd, BT_EXIT.ljust(REPORT_SIZE, b"\0"))
            except OSError:
                pass
            finally:
                os.close(fd)
