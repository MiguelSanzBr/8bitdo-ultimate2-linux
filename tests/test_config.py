"""Config record codec (pure, no device): layout, round trips, per-kind get/put, defaults."""
import json
import math
import random
import struct

from ultimate2 import config as c
from ultimate2.protocol import CFG_SIZE, crc16



def test_layout_covers_record():
    sizes = {"str32": 32, "H": 2, "B": 1, **dict.fromkeys("IXCFfKM", 4)}
    end = max(off + sizes[k] for _, off, k in c.FIELDS)
    assert end == CFG_SIZE == 1592


def test_roundtrip_and_edit():
    rnd = random.Random(0)
    for _ in range(20):
        b = bytes(rnd.getrandbits(8) for _ in range(CFG_SIZE))
        doc = json.loads(json.dumps(c.decode(b)))
        new, changed = c.encode(doc, b)
        assert new[16:] == b[16:] and not changed            # untouched -> identical bytes
        s = doc["slots"][1]["sticks"]
        s["left_start"] = (s["left_start"] + 1) % 256
        doc["slots"][2]["name"] = "Teste" if doc["slots"][2]["name"] != "Teste" else "X"
        new, changed = c.encode(doc, b)
        d2 = c.decode(new)
        assert d2["slots"][1]["sticks"]["left_start"] == s["left_start"]
        assert d2["slots"][2]["name"] == doc["slots"][2]["name"]
        assert len(changed) == 2


def test_new_slot_defaults():
    b = bytes([0xFF]) * 16 + bytes([3, 0, 3, 0]) + bytes([0xFF]) * (CFG_SIZE - 20)   # fresh controller
    new, _ = c.encode(json.loads(json.dumps(c.default_slot(c.decode(b), 1, "Teste"))), b)
    s = c.decode(new)["slots"][1]
    assert s["flag"] == "enabled" and s["name"] == "Teste"
    assert [s["mapping"][k] for k in ("A", "Star", "P1")] == ["A", "Menu", "None"]
    assert new[20:52] == b[20:52] and new[52 + 32:116] == b[52 + 32:116]   # slots 0 and 2 untouched



def test_tables():
    assert c.FLAGS[0x20200911] == "enabled" and len(c.BUTTONS) == 22 and c.CRC_FIELD == (12, 16)
    assert c.KEYCODES[0x2000] == "A" and c.FEATURES[0x1] == "invert_LS_X"


def test_decode_shape():
    d = c.decode(bytes(CFG_SIZE))
    assert len(d["slots"]) == 3 and len(d["slots"][0]["macros"]["records"]) == 4
    assert len(d["slots"][2]["led_single"]["colors"]) == 24


def g(raw, kind):
    return c._get(bytearray(raw.ljust(64, b"\0")), 0, kind)


def p(kind, val, size=64):
    b = bytearray(size)
    c._put(b, 0, kind, val)
    return b


def test_get_str32():
    assert g(b"\xff" * 32, "str32") == ""
    assert g("Hi".encode("utf-16-be"), "str32") == "Hi"
    full = "ABCDEFGHIJKLMNOP".encode("utf-16-be")        # 16 chars, no terminator
    assert g(full, "str32") == "ABCDEFGHIJKLMNOP"


def test_get_float():
    assert g(struct.pack("<f", 1.23456), "f") == 1.2346
    assert g(b"\xff\xff\xff\xff", "f") is None


def test_get_flag_key():
    assert g(struct.pack("<I", 0x20200911), "F") == "enabled"
    assert g(struct.pack("<I", 0x12345678), "F") == "0x12345678"
    assert g(struct.pack("<I", 0x2000), "K") == "A"
    assert g(struct.pack("<I", 0x77777), "K") == "0x00077777"


def test_get_mask():
    assert g(b"\xff" * 4, "M") == "0xffffffff"
    assert g(struct.pack("<I", 0x11), "M") == ["invert_LS_X", "swap_sticks"]
    assert g(struct.pack("<I", 0x10000001), "M") == ["invert_LS_X", "0x10000000"]
    assert g(bytes(4), "M") == []


def test_get_plain():
    assert g(struct.pack("<I", 0xAB), "X") == "0x000000ab"
    assert g(struct.pack("<I", 0x260032), "C") == "#260032"
    assert g(b"\x07", "B") == 7
    assert g(b"\x34\x12", "H") == 0x1234
    assert g(struct.pack("<I", 99), "I") == 99


def test_put_str32():
    b = p("str32", "A" * 20)
    assert bytes(b[:32]) == "A".encode("utf-16-be") * 16 and b[32] == 0
    assert bytes(p("str32", "Hi")[:6]) == b"\0H\0i\0\0"


def test_put_float():
    assert struct.unpack_from("<f", p("f", 0.5))[0] == 0.5
    assert math.isnan(struct.unpack_from("<f", p("f", None))[0])


def test_put_flag_key_names():
    rd = lambda b: struct.unpack_from("<I", b)[0]
    assert rd(p("F", "enabled")) == 0x20200911
    assert rd(p("F", 5)) == 5
    assert rd(p("F", "0x20190000")) == 0x20190000
    assert rd(p("K", "A")) == 0x2000
    assert rd(p("K", "0x1234")) == 0x1234
    assert c._from_names(c.KEYCODES, 7) == 7


def test_put_mask():
    rd = lambda b: struct.unpack_from("<I", b)[0]
    assert rd(p("M", ["invert_LS_X", 0x10, "0x80"])) == 0x91
    assert rd(p("M", "0x1f")) == 0x1f
    assert rd(p("M", [])) == 0


def test_put_x_c_and_ints():
    rd = lambda b: struct.unpack_from("<I", b)[0]
    assert rd(p("C", "#7e3200")) == 0x7e3200
    assert rd(p("X", "0x00000010")) == 0x10
    assert rd(p("X", 5)) == 5
    assert p("B", "7")[0] == 7
    assert struct.unpack_from("<H", p("H", 513))[0] == 513
    assert struct.unpack_from("<I", p("I", 70000))[0] == 70000


def test_encode_skips_missing_paths():
    base = bytes([0xFF]) * 16 + bytes([0, 0, 0, 0]) + bytes([0xFF]) * (CFG_SIZE - 20)
    # {} -> KeyError, short slots list -> IndexError, non-container slots -> TypeError
    for doc in ({}, {"slots": [{}]}, {"slots": 5}, {"gamepad_mode": 1, "slots": None}):
        new, changed = c.encode(doc, base)
        assert new[:12] == base[:12] and new[20:] == base[20:]
        assert changed == ([] if "gamepad_mode" not in doc else ["gamepad_mode"])
    # crc_value in the document is ignored and the real CRC is recomputed
    new, changed = c.encode({"crc_value": 1, "gamepad_mode": 2}, base)
    assert changed == ["gamepad_mode"]
    chk = bytearray(new)
    stored = struct.unpack_from("<I", chk, 12)[0]
    chk[12:16] = base[12:16]          # encode() hashes the buffer before the crc field is overwritten
    assert stored == crc16(chk)


def test_default_slot_modes():
    for mode, ident, menu, tstart in ((0, ["B", "A", "Y", "X"], "Screenshot", 77), (3, ["A", "B", "X", "Y"], "Menu", 0)):
        base = bytearray(b"\xff" * CFG_SIZE)
        struct.pack_into("<H", base, 16, mode)
        doc = c.default_slot(c.decode(bytes(base)), 1, "N")
        s = doc["slots"][1]
        assert [s["mapping"][k] for k in ("A", "B", "X", "Y")] == ident
        assert s["mapping"]["Star"] == menu
        assert s["triggers"]["left_start"] == tstart and s["name"] == "N"
        assert all(r["gamepad_mode"] == mode for r in s["macros"]["records"])


def test_changed_span():
    a = bytes(CFG_SIZE)
    assert c.changed_span(a, a) is None
    b = bytearray(a); b[12:16] = b"\x01\x02\x03\x04"            # crc only
    assert c.changed_span(a, bytes(b)) is None
    b[100] = 1; b[200] = 1
    assert c.changed_span(a, bytes(b)) == (100, 201)
