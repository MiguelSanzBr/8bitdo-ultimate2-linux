"""Pure protocol helpers: constants, CRC, request/reply framing."""
import struct

from ultimate2 import protocol as p


def test_constants():
    assert p.VID == 0x2DC8 and p.CFG_SIZE == 1592 and p.CHUNK == 45 and p.REPORT_SIZE == 64
    assert p.PIDS[0x6012] == "Ultimate 2"
    assert (p.CMD_WRITE, p.CMD_READ, p.CMD_COMMIT, p.CMD_REPORT) == (1, 2, 6, 7)
    assert (p.CMD_SET_THEME, p.CMD_GET_THEME, p.CMD_INFO, p.COMMIT_KEY) == (0x40, 0x41, 0x0100, 0x123)
    assert p.THEMES == {2: "dynamic", 3: "hotwheel", 4: "custom", 5: "off"}
    assert p.QUERY_VERSION.startswith(b"\x81\x05") and p.ANSWER_VERSION == b"\x02\x22"


def test_crc_known_value():
    # value seen on the wire for 45 zero bytes
    assert p.crc16(bytes(45)) == 0xCF30


def test_build_request_with_data():
    pkt = p.build_request(p.CMD_WRITE, data=b"abc", total=10, offset=4)
    assert len(pkt) == p.REPORT_SIZE and pkt[:2] == b"\x81\x04"
    assert struct.unpack_from("<HHHHII", pkt, 2) == (p.CMD_WRITE, 0, 3, p.crc16(b"abc"), 10, 4)
    assert pkt[18:21] == b"abc" and not any(pkt[21:])


def test_build_request_read_padding_and_no_crc():
    pkt = p.build_request(p.CMD_READ, total=10, length=5)       # empty data, zero-padded to length
    assert struct.unpack_from("<HHHHII", pkt, 2) == (p.CMD_READ, 0, 5, p.crc16(bytes(5)), 10, 0)
    pkt = p.build_request(p.CMD_COMMIT, sub=p.COMMIT_KEY, with_crc=False)
    assert struct.unpack_from("<HHHHII", pkt, 2) == (p.CMD_COMMIT, p.COMMIT_KEY, 0, 0, 0, 0)


def _answer(cmd, data=b"", length=None):
    n = len(data) if length is None else length
    return (b"\x02\x04" + struct.pack("<HHHHII", 4, cmd, n, 0, 0, 0) + data).ljust(64, b"\0")


def test_parse_reply():
    assert p.parse_reply(_answer(p.CMD_READ, b"abc"), p.CMD_READ) == (3, b"abc")
    assert p.parse_reply(_answer(p.CMD_READ), p.CMD_READ) == (0, b"")
    assert p.parse_reply(_answer(p.CMD_WRITE, b"zz"), p.CMD_READ) is None     # other command
    assert p.parse_reply(b"\x02\x04", p.CMD_READ) is None                     # too short
    assert p.parse_reply(b"\x03" * 64, p.CMD_READ) is None                    # bad first byte
    assert p.parse_reply(b"\x02\x05" + b"\0" * 62, p.CMD_READ) is None        # bad second byte


def test_parse_info():
    r = bytearray(64)
    r[18:24] = bytes([0x6E, 0x01, 3, 0, 0x12, 0x60])
    assert p.parse_info(bytes(r)) == {"firmware": 0x16E, "beta": 3, "device_pid": 0x6012}
