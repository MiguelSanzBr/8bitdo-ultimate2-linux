"""Transport to the controller over ``/dev/hidraw``: read, write and save the config, LED theme, status."""
import os
import select
import struct
import sys
import time

from . import discovery
from .protocol import (CFG_SIZE, CHUNK, CMD_COMMIT, CMD_GET_THEME, CMD_READ, CMD_REPORT, CMD_SET_THEME,
                       CMD_WRITE, COMMIT_KEY, QUERY_VERSION, ANSWER_VERSION, REPORT_SIZE, build_request, parse_info,
                       parse_reply)

RETRIES = 30             # the app's retry count per chunk


class Device:
    """One open controller. ``path`` selects a specific hidraw node (default: the first one found).

    Opening also opens the matching joystick node (see :func:`ultimate2.discovery.find_input_node`),
    without which the firmware ignores the config endpoint. Exits with a message (``SystemExit``)
    when there is no controller or no permission.
    """

    def __init__(self, path=None):
        devs = list(discovery.find_devices())
        if path:
            devs = [d for d in devs if d[0] == path] or [(path, 0, "")]
        if not devs:
            sys.exit("no 8BitDo config interface found (is the controller plugged in / paired?)")
        self.path, self.pid, usb_dir = devs[0]
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
            sys.exit(f"permission denied on {self.path}: install udev/99-8bitdo-u2.rules (see README)")
        self._drain()

    def close(self):
        for fd in (self.fd, self.poll_fd):
            if fd is not None:
                os.close(fd)

    # ------------------------------------------------------------ raw I/O
    def _drain(self):
        while select.select([self.fd], [], [], 0.02)[0]:
            os.read(self.fd, REPORT_SIZE)

    def send(self, cmd, sub=0, data=b"", total=0, offset=0, length=None, with_crc=True):
        os.write(self.fd, build_request(cmd, sub, data, total, offset, length, with_crc))

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
        """``{"firmware", "beta", "device_pid"}`` or ``None``."""
        r = self.query(b"\x81\x04\x00\x01", want=b"\x02\x04\x04\x00\x00\x01")
        return parse_info(r) if r else None

    def edition(self):
        """Colorway of the controller (the app's ``m_ControllerColor``), or ``None``."""
        r = self.query(QUERY_VERSION, want=ANSWER_VERSION)
        return r[6] if r else None

    def report(self, on):
        """Turn the controller's input reports off/on around config writes (like the app)."""
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
        """The whole 1592-byte config record."""
        buf = bytearray()
        tries = 0
        while len(buf) < CFG_SIZE:
            self.send(CMD_READ, total=CFG_SIZE, offset=len(buf), length=min(CHUNK, CFG_SIZE - len(buf)))
            r = self.recv(CMD_READ)
            if not r or r[0] == 0:
                tries += 1
                if tries >= RETRIES:
                    raise IOError(f"read failed at offset {len(buf)}")
                continue
            tries = 0
            buf += r[1]
        return bytes(buf[:CFG_SIZE])

    def write_config(self, data, start=0, end=CFG_SIZE):
        """Write ``data[start:end]`` of the record and save it to flash.

        A sub-range is how the app updates one setting (``writeUltimate2dynamic`` writes 12 bytes at
        ``0x4b8 + 12*slot``). Raises ``IOError`` if a chunk or the save is not acknowledged.
        """
        assert len(data) == CFG_SIZE and 0 <= start < end <= CFG_SIZE
        self.report(False)
        off, tries = start, 0
        while off < end:
            self.send(CMD_WRITE, data=data[off:min(off + CHUNK, end)], total=CFG_SIZE, offset=off)
            r = self.recv(CMD_WRITE)
            if not r or r[0] == 0:
                tries += 1
                if tries >= RETRIES:
                    raise IOError(f"write failed at offset {off}")
                continue
            tries = 0
            off += r[0]
        time.sleep(0.1)
        self.send(CMD_COMMIT, sub=COMMIT_KEY, with_crc=False)
        ok = self.recv(CMD_COMMIT, timeout=3.0) is not None
        self.report(True)
        if not ok:
            raise IOError("controller did not confirm the save")
