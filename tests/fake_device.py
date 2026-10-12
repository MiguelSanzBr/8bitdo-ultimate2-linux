"""In-process emulator of the Ultimate 2 firmware's config channel, for tests.

The fake hidraw node is one end of a SOCK_SEQPACKET socketpair (keeps 64-byte report boundaries and
works with select/os.read/os.write); a thread answers on the other end like the real controller.
"""
import os, socket, struct, threading

from ultimate2 import discovery, protocol as u


class FakeController:
    def __init__(self, cfg=None, firmware=110, beta=0, report_pid=0x6012, usb_pid=0x310B):
        self.cfg = bytearray(cfg if cfg is not None else b"\xff" * u.CFG_SIZE)
        self.pending = bytearray(self.cfg)
        self.firmware, self.beta, self.report_pid, self.usb_pid = firmware, beta, report_pid, usb_pid
        self.path, self.js_path = "/dev/hidraw-fake", "/dev/input/js-fake"
        self.drop = 0              # ignore the next N requests (simulates lost/late answers)
        self.silent = set()        # commands never answered
        self.corrupt_commit = False  # store something else on commit (verify-failure path)
        self.log = []              # (cmd, sub, length, offset) of every framed request
        self.theme = 2
        self.edition = 3
        self.host, self._dev = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self._t = threading.Thread(target=self._serve, daemon=True)
        self._t.start()

    # ---- wiring into u2ctl
    def install(self, monkeypatch):
        """Make ultimate2.device.Device() find and open this fake instead of real hardware."""
        real_open = os.open

        def fake_open(path, flags, *a):
            if path == self.path:
                return os.dup(self.host.fileno())
            if path == self.js_path:
                return real_open(os.devnull, os.O_RDONLY)
            return real_open(path, flags, *a)
        monkeypatch.setattr(os, "open", fake_open)
        monkeypatch.setattr(discovery, "find_devices", lambda: iter([(self.path, self.usb_pid, "/fake/usb")]))
        monkeypatch.setattr(discovery, "find_input_node", lambda usb_dir: self.js_path)
        return self

    def close(self):
        self._dev.close()
        self.host.close()

    # ---- firmware side
    def _reply(self, cmd, data=b"", length=None, total=0, offset=0):
        length = len(data) if length is None else length
        hdr = struct.pack("<HHHHII", 4, cmd, length, u.crc16(data), total, offset)
        self._dev.send((b"\x02\x04" + hdr + data).ljust(64, b"\0"))

    def _serve(self):
        while True:
            try:
                pkt = self._dev.recv(64)
            except OSError:
                return
            if not pkt:
                return
            if pkt[:5] == b"\x81\x05\x00\x21\x01":       # version / colorway query
                self._dev.send(bytes([0x02, 0x22, self.firmware & 0xFF, self.firmware >> 8, self.beta, 0,
                                      self.edition]).ljust(64, b"\0"))
                continue
            if pkt[:2] != b"\x81\x04" or len(pkt) < 18:
                continue
            cmd, sub, length, _crc, total, off = struct.unpack_from("<HHHHII", pkt, 2)
            data = pkt[18:18 + length]
            self.log.append((cmd, sub, length, off))
            if self.drop:
                self.drop -= 1
                continue
            if cmd in self.silent:
                continue
            if cmd == 0x0100:           # device info
                body = bytearray(8)
                struct.pack_into("<HBxH", body, 0, self.firmware, self.beta, self.report_pid)
                self._reply(0x0100, bytes(body))
            elif cmd == u.CMD_READ:
                self._reply(cmd, bytes(self.cfg[off:off + length]), total=total, offset=off)
            elif cmd == u.CMD_WRITE:
                self.pending[off:off + length] = data
                self._reply(cmd, length=length, total=total, offset=off)
            elif cmd == u.CMD_COMMIT:
                self.cfg[:] = self.pending
                if self.corrupt_commit:
                    self.cfg[100] ^= 0xFF
                self._reply(cmd)
            elif cmd == u.CMD_REPORT:
                self._reply(cmd)
            elif cmd == u.CMD_SET_THEME:
                self.theme = sub
                self._reply(cmd)
            elif cmd == u.CMD_GET_THEME:
                self._reply(cmd, bytes([self.theme]))
