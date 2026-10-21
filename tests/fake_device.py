"""In-process emulator of the Ultimate 2 firmware's config channel (or the Ultimate Bluetooth's, or the Ultimate
2.4G's, picked from ``usb_pid``), for tests.

The fake hidraw node is one end of a SOCK_SEQPACKET socketpair (keeps 64-byte report boundaries and
works with select/os.read/os.write); a thread answers on the other end like the real controller.
"""
import os, socket, struct, threading

from ultimate2 import discovery, protocol as u


class FakeController:
    def __init__(self, cfg=None, firmware=110, beta=0, report_pid=0x6012, usb_pid=0x310B):
        self.u24g = usb_pid in u.PIDS_24G       # Ultimate 2.4G: length-prefixed, no CRC, answers echo the offset
        self.bt = usb_pid == u.PID_BT_CONFIG or self.u24g   # Ultimate Bluetooth in config mode: length-prefixed requests
        self.cfg = bytearray(cfg if cfg is not None else b"\xff" * (u.CFG_SIZE_BT if self.bt else u.CFG_SIZE))
        self.pending = bytearray(self.cfg)
        self.firmware, self.beta, self.report_pid, self.usb_pid = firmware, beta, report_pid, usb_pid
        self.path, self.js_path = "/dev/hidraw-fake", "/dev/input/js-fake"
        self.drop = 0              # ignore the next N requests (simulates lost/late answers)
        self.silent = set()        # commands never answered
        self.corrupt_commit = False  # store something else on commit (verify-failure path)
        self.log = []              # (cmd, sub, length, offset) of every framed request
        self.theme = 2
        self.edition = 3
        self.pad = None            # through the dongle: {"battery", "firmware", "edition"} of the controller
        self.exited = False        # Ultimate Bluetooth: got the "back to XInput" query
        self.saves = 0             # Ultimate 2.4G: its firmware stores a save counter in crc_value
        self.stale = 0             # Ultimate 2.4G: precede the next N read/write answers with one for another offset
        self.live = bytes.fromhex("00000020 7f80807f 0000 0000")   # its config-mode live state (idle)
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
        monkeypatch.setattr(discovery, "find_bt_xinput", lambda: None)     # never the real sysfs
        monkeypatch.setattr(discovery, "find_24g_xinput", lambda: None)
        return self

    def close(self):
        self._dev.close()
        self.host.close()

    # ---- firmware side
    def _reply(self, cmd, data=b"", length=None, total=0, offset=0):
        length = len(data) if length is None else length
        hdr = struct.pack("<HHHHII", 4, cmd, length, 0 if self.u24g else u.crc16(data), total, offset)
        self._dev.send((b"\x02\x04" + hdr + data).ljust(64, b"\0"))

    def _serve(self):
        while True:
            try:
                pkt = self._dev.recv(64)
            except OSError:
                return
            if not pkt:
                return
            if pkt[:5] == u.BT_EXIT:
                self.exited = True
                continue
            if pkt[:5] == b"\x81\x05\x00\x21\x01" and self.u24g:   # version: firmware, beta, 0, its PID
                self._dev.send(struct.pack("<BBHBBH", 0x02, 0x22, self.firmware, self.beta, 0, self.usb_pid).ljust(64, b"\0"))
                continue
            if pkt[:5] == b"\x81\x05\x00\x21\x01":       # version / colorway query
                self._dev.send(bytes([0x02, 0x22, self.firmware & 0xFF, self.firmware >> 8, self.beta, 0,
                                      self.edition]).ljust(64, b"\0"))
                continue
            if pkt[:7] == u.QUERY_PAD:                   # controller behind the dongle (silent when wired)
                if self.pad:
                    p = self.pad
                    self._dev.send((u.ANSWER_PAD + bytes(12) + bytes([p["battery"], p["firmware"] & 0xFF,
                                    p["firmware"] >> 8, 0, 0, p["edition"]])).ljust(64, b"\0"))
                continue
            if self.bt:                                  # 81 <n+1> 04 <header>: drop the length byte
                if pkt[0] != 0x81 or pkt[2] != 0x04 or pkt[1] != 17 + struct.unpack_from("<H", pkt, 7)[0]:
                    continue
                pkt = pkt[:1] + pkt[2:]
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
            if self.u24g and cmd in (0x0100, u.CMD_REPORT, u.CMD_LIVE, u.CMD_SET_THEME, u.CMD_GET_THEME):
                continue                # only read, write and commit
            if self.u24g and self.stale and cmd in (u.CMD_READ, u.CMD_WRITE):
                self.stale -= 1         # a late answer to an earlier request: another offset
                self._reply(cmd, b"\xee" * length if cmd == u.CMD_READ else b"", length, total, off + 1000)
            if cmd == 0x0100 and self.bt:   # not answered in the Ultimate Bluetooth's config mode
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
                if sub != (u.COMMIT_KEY_BT if self.bt else u.COMMIT_KEY):
                    continue                    # wrong key: stays in RAM, no answer (like the real pad)
                slot = self.cfg[18:20]
                self.cfg[:] = self.pending
                if self.u24g:           # its firmware keeps its own cur_slot and counts the saves in crc_value
                    self.saves += 1
                    self.cfg[18:20] = slot
                    struct.pack_into("<I", self.cfg, 12, self.saves)
                if self.corrupt_commit:
                    self.cfg[100] ^= 0xFF
                self._reply(cmd)
            elif cmd == u.CMD_REPORT:
                self._reply(cmd)
            elif cmd == u.CMD_LIVE and sub == u.LIVE_SUB:
                self._reply(cmd, self.live)
            elif cmd == u.CMD_SET_THEME:
                self.theme = sub
                self._reply(cmd)
            elif cmd == u.CMD_GET_THEME:
                self._reply(cmd, bytes([self.theme]))
