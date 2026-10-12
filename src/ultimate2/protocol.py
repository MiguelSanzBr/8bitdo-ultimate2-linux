"""Wire protocol of the controller's vendor HID channel (reverse-engineered from 8BitDoAdvance.dll).

Every report is 64 bytes. Requests start with ``81 04`` followed by a 16-byte header and up to
:data:`CHUNK` data bytes; answers start with ``02 04`` and echo the request command:

    header = u16 cmd, u16 sub, u16 len, u16 crc16(data), u32 total, u32 offset

See ``docs/PROTOCOL.md`` for the full description.
"""
import struct

VID = 0x2DC8
PIDS = {0x310B: "wired (XInput)", 0x6012: "Ultimate 2", 0x6013: "2.4G dongle"}
CFG_SIZE = 1592          # sizeof(custom_config_record_t_u2)
CHUNK = 45               # max payload per packet (61-byte frame - 16-byte header)
REPORT_SIZE = 64

CMD_WRITE, CMD_READ, CMD_COMMIT, CMD_REPORT = 1, 2, 6, 7
CMD_SET_THEME, CMD_GET_THEME = 0x40, 0x41
CMD_INFO = 0x0100
COMMIT_KEY = 0x123       # sub-command of CMD_COMMIT that persists the record to flash
THEMES = {2: "dynamic", 3: "hotwheel", 4: "custom", 5: "off"}   # active LED theme (global, not per slot)

QUERY_VERSION = b"\x81\x05\x00\x21\x01"   # answer starts 02 22; byte 6 = colorway (edition)
ANSWER_VERSION = b"\x02\x22"


def crc16(data):
    """CRC-16/MODBUS (reflected 0xA001, init 0xFFFF) — used for packets and the config record."""
    c = 0xFFFF
    for b in data:
        for _ in range(8):
            c = (c >> 1) ^ (0xA001 if (c ^ b) & 1 else 0)
            b >>= 1
    return c


def build_request(cmd, sub=0, data=b"", total=0, offset=0, length=None, with_crc=True):
    """64-byte request report. ``length`` pads ``data`` (reads send an empty, zero-padded payload)."""
    length = len(data) if length is None else length
    data = data.ljust(length, b"\0")
    c = crc16(data) if with_crc else 0
    pkt = b"\x81\x04" + struct.pack("<HHHHII", cmd, sub, length, c, total, offset) + data
    return pkt.ljust(REPORT_SIZE, b"\0")


def parse_reply(report, cmd):
    """``(length, data)`` if ``report`` is the answer to ``cmd``, else ``None``.

    Answer layout: ``02 04 | u16 4 | u16 cmd | u16 len | u16 crc | u32 | u32 | data``.
    """
    if len(report) >= 18 and report[0] == 2 and report[1] == 4 and struct.unpack_from("<HH", report, 2) == (4, cmd):
        n = struct.unpack_from("<H", report, 6)[0]
        return n, report[18:18 + n]
    return None


def parse_info(report):
    """Decode the CMD_INFO answer: firmware (x100), beta flag and the PID the controller reports."""
    return {"firmware": report[18] | report[19] << 8, "beta": report[20], "device_pid": report[22] | report[23] << 8}
