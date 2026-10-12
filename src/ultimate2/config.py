"""The 1592-byte configuration record (``custom_config_record_t_u2`` in the official app).

Three profile slots, MSVC natural alignment, little endian. :func:`decode` turns the bytes into a
readable nested dict; :func:`encode` writes an edited dict back over the original bytes, touching only
the fields that changed so everything else round-trips exactly. ``docs/PROTOCOL.md`` lists every offset.
"""
import math
import struct

from .protocol import CFG_SIZE, crc16

FLAGS = {0x20200911: "enabled", 0x20190000: "disabled", 0: "off"}
# physical buttons, in map_key.key[] order (app: P1 = PR, P2 = PL back paddles, P3 = L4, P4 = R4)
BUTTONS = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "L3", "R3", "Select", "Start", "Star",
           "Home", "Up", "Down", "Left", "Right", "P1", "P2", "P3", "P4"]
# output codes a button can be remapped to
KEYCODES = {0: "None", 0x1: "Start", 0x2: "L3", 0x4: "R3", 0x8: "Select", 0x10: "X", 0x20: "Y",
            0x40: "Right", 0x80: "Left", 0x100: "Down", 0x200: "Up", 0x400: "LB", 0x800: "RB",
            0x1000: "B", 0x2000: "A", 0x4000: "LT", 0x8000: "Home", 0x10000: "Menu", 0x20000: "RT",
            0x100000: "P5", 0x200000: "P3", 0x400000: "Screenshot", 0x800000: "TurboSingle",
            0x1000000: "TurboAuto", 0x2000000: "P1", 0x4000000: "P2", 0x40000000: "P4",
            0x08000001: "RS_Up", 0x08000002: "RS_Down", 0x08000004: "RS_Left", 0x08000008: "RS_Right",
            0x08000010: "LS_Up", 0x08000020: "LS_Down", 0x08000040: "LS_Left", 0x08000080: "LS_Right"}
FEATURES = {0x1: "invert_LS_X", 0x2: "invert_LS_Y", 0x4: "invert_RS_X", 0x8: "invert_RS_Y",
            0x10: "swap_sticks", 0x80: "swap_triggers", 0x100: "swap_LS_dpad", 0x8000: "trigger_rumble"}
CRC_FIELD = (12, 16)     # byte range of crc_value

# Field kinds: B/H/I = unsigned ints, f = float, str32 = UTF-16BE name, F = flag, K = key code,
# M = feature bitmask, X = raw hex u32, C = #rrggbb color.


def _from_names(table, val):
    if isinstance(val, int):
        return val
    rev = {v: k for k, v in table.items()}
    return rev[val] if val in rev else int(val, 16)


def _fields():
    """``[(path, offset, kind)]`` for every field of the record."""
    f = [(("crc_value",), 12, "I"), (("gamepad_mode",), 16, "H"), (("cur_slot",), 18, "H")]
    for s in range(3):
        p = ("slots", s)
        f.append((p + ("flag",), 4 * s, "F"))
        f.append((p + ("name",), 20 + 32 * s, "str32"))
        o = 116 + 12 * s
        f += [(p + ("rumble", "flag"), o, "F"), (p + ("rumble", "left"), o + 4, "f"), (p + ("rumble", "right"), o + 8, "f")]
        for sec, base in (("sticks", 152), ("triggers", 176), ("xinput_rumble", 1148)):
            o = base + 8 * s
            f += [(p + (sec, "flag"), o, "F"), (p + (sec, "left_start"), o + 4, "B"), (p + (sec, "left_end"), o + 5, "B"),
                  (p + (sec, "right_start"), o + 6, "B"), (p + (sec, "right_end"), o + 7, "B")]
        o = 200 + 8 * s
        f += [(p + ("special", "flag"), o, "F"), (p + ("special", "features"), o + 4, "M")]
        o = 224 + 92 * s
        f.append((p + ("mapping", "flag"), o, "F"))
        f += [(p + ("mapping", BUTTONS[i]), o + 4 + 4 * i, "K") for i in range(22)]
        o = 500 + 216 * s
        f += [(p + ("macros", "flag"), o, "F"), (p + ("macros", "total_cnt"), o + 4, "B")]
        for r in range(4):
            q, ro = p + ("macros", "records", r), o + 8 + 52 * r
            f += [(q + ("name",), ro, "str32"), (q + ("gamepad_mode",), ro + 32, "B"), (q + ("special_flag",), ro + 33, "B"),
                  (q + ("max_steps",), ro + 34, "H"), (q + ("offset",), ro + 36, "H"), (q + ("key_map",), ro + 40, "X"),
                  (q + ("cycles_num",), ro + 44, "I"), (q + ("interval_ms",), ro + 48, "I")]
        o = 1172 + 12 * s
        f += [(p + ("sixaxis", "flag"), o, "F"), (p + ("sixaxis", "keys_map"), o + 4, "X"), (p + ("sixaxis", "trigger_mode"), o + 8, "B"),
              (p + ("sixaxis", "sensitivity"), o + 9, "B"), (p + ("sixaxis", "dead_compensate"), o + 10, "B"),
              (p + ("sixaxis", "mapping_type"), o + 11, "B")]
        o = 1208 + 12 * s
        f += [(p + ("led_dynamic", "flag"), o, "F"), (p + ("led_dynamic", "color"), o + 4, "C"), (p + ("led_dynamic", "bg_color"), o + 8, "C")]
        o = 1244 + 16 * s
        f += [(p + ("led_hotwheel", "flag"), o, "F"), (p + ("led_hotwheel", "color"), o + 4, "C"),
              (p + ("led_hotwheel", "bg_color"), o + 8, "C"), (p + ("led_hotwheel", "speed"), o + 12, "B")]
        o = 1292 + 100 * s
        f.append((p + ("led_single", "flag"), o, "F"))
        f += [(p + ("led_single", "colors", i), o + 4 + 4 * i, "C") for i in range(24)]
    return f


FIELDS = _fields()


def _get(buf, off, kind):
    if kind == "str32":   # UTF-16BE, max 16 chars, 0x0000-terminated; any 0xFF byte = erased
        raw = buf[off:off + 32]
        if b"\xff" in raw:
            return ""
        chars = [raw[i:i + 2] for i in range(0, 32, 2)]
        return b"".join(chars[:chars.index(b"\0\0")] if b"\0\0" in chars else chars).decode("utf-16-be", "replace")
    if kind == "f":
        v = struct.unpack_from("<f", buf, off)[0]
        return round(v, 4) if math.isfinite(v) else None   # erased flash (0xFFFFFFFF) is NaN
    v = struct.unpack_from("<" + ("I" if kind in "XCFKM" else kind), buf, off)[0]
    if kind == "F":
        return FLAGS.get(v, f"0x{v:08x}")
    if kind == "K":
        return KEYCODES.get(v, f"0x{v:08x}")
    if kind == "M":
        if v == 0xFFFFFFFF:
            return "0xffffffff"
        names = [n for b, n in FEATURES.items() if v & b]
        rest = v & ~sum(FEATURES)
        return names + ([f"0x{rest:08x}"] if rest else [])
    return f"0x{v:08x}" if kind == "X" else f"#{v:06x}" if kind == "C" else v


def _put(buf, off, kind, val):
    if kind == "str32":
        buf[off:off + 32] = val[:16].encode("utf-16-be").ljust(32, b"\0")
    elif kind == "f":
        struct.pack_into("<f", buf, off, float("nan") if val is None else float(val))
    elif kind in "XCFKM":
        if kind == "F":
            v = _from_names(FLAGS, val)
        elif kind == "K":
            v = _from_names(KEYCODES, val)
        elif kind == "M":
            v = int(val, 16) if isinstance(val, str) else sum(_from_names(FEATURES, x) for x in val)
        else:
            v = int(str(val).lstrip("#"), 16) if isinstance(val, str) else int(val)
        struct.pack_into("<I", buf, off, v)
    else:
        struct.pack_into("<" + kind, buf, off, int(val))


def changed_span(old, new):
    """``(start, end)`` of the bytes that differ, ignoring ``crc_value`` (the app's partial writes never
    refresh it, so the firmware does not check it); ``None`` if nothing changed."""
    diff = [i for i in range(CFG_SIZE) if old[i] != new[i] and not CRC_FIELD[0] <= i < CRC_FIELD[1]]
    return (diff[0], diff[-1] + 1) if diff else None


def decode(buf):
    """Record bytes -> nested dict (``slots`` is a list of 3 profiles)."""
    out = {}
    for path, off, kind in FIELDS:
        node = out
        for k in path[:-1]:
            node = node.setdefault(k, {})
        node[path[-1]] = _get(buf, off, kind)

    def fix(n):   # integer-keyed dicts become lists
        if isinstance(n, dict):
            if n and all(isinstance(k, int) for k in n):
                return [fix(n[k]) for k in sorted(n)]
            return {k: fix(v) for k, v in n.items()}
        return n
    return fix(out)


def _lookup(doc, path):
    for k in path:
        doc = doc[k]
    return doc


def encode(doc, base):
    """Write ``doc`` over the record ``base``; returns ``(new_bytes, changed_paths)``.

    Only fields that differ from ``decode(base)`` are written, so untouched bytes round-trip exactly;
    missing fields are skipped. ``crc_value`` is recomputed like the app's ``ANSI_CRC_16_Ultimate2``.
    """
    buf = bytearray(base)
    cur = decode(base)
    changed = []
    for path, off, kind in FIELDS:
        if path == ("crc_value",):
            continue
        try:
            new = _lookup(doc, path)
        except (KeyError, IndexError, TypeError):
            continue
        if new != _lookup(cur, path):
            _put(buf, off, kind, new)
            changed.append("/".join(map(str, path)))
    struct.pack_into("<I", buf, CRC_FIELD[0], crc16(buf))
    return bytes(buf), changed


def default_slot(doc, n, name):
    """Fill slot ``n`` of ``doc`` with the defaults the Windows app uses for a new profile."""
    mode = doc["gamepad_mode"]
    s = doc["slots"][n]
    ident = ["B", "A", "Y", "X"] if mode == 0 else ["A", "B", "X", "Y"]
    keys = ident + ["LB", "RB", "LT", "RT", "L3", "R3", "Select", "Start",
                    "Screenshot" if mode == 0 else "Menu", "Home", "Up", "Down", "Left", "Right"] + ["None"] * 4
    on = "enabled"
    doc["slots"][n] = dict(s, flag=on, name=name,
        rumble=dict(flag=on, left=1.0, right=1.0),
        sticks=dict(flag=on, left_start=17, left_end=128, right_start=17, right_end=128),
        triggers=dict(flag=on, left_start=77 if mode == 0 else 0, left_end=255,
                      right_start=77 if mode == 0 else 0, right_end=255),
        xinput_rumble=dict(flag=on, left_start=1, left_end=100, right_start=1, right_end=100),
        special=dict(flag=on, features=[]),
        mapping=dict(flag=on, **dict(zip(BUTTONS, keys))),
        sixaxis=dict(s["sixaxis"], flag="disabled", sensitivity=10, dead_compensate=40),
        led_dynamic=dict(flag=on, color="#260032", bg_color="#084e50"),
        led_hotwheel=dict(flag=on, color="#cc6200", bg_color="#cc0000", speed=7),
        led_single=dict(flag=on, colors=["#7e3200"] * 24))
    s = doc["slots"][n]
    s["macros"] = dict(s.get("macros", {}), flag=on, total_cnt=0)
    s["macros"]["records"] = [dict(name="", gamepad_mode=mode, special_flag=0, max_steps=0, offset=0,
                                   key_map="0x00000000", cycles_num=0, interval_ms=0) for _ in range(4)]
    return doc
