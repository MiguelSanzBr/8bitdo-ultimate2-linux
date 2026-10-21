"""The configuration record: 1592 bytes on the Ultimate 2 (``custom_config_record_t_u2`` in the official app),
1652 bytes on the 1st-gen Ultimate Bluetooth (``UltimateBTAdvance.custom_config_record_t`` of Ultimate Software V1)
and on the Ultimate 2.4G (``Ultimate2_4Advance.custom_config_record_t``, same offsets, see :data:`LAYOUTS`).

Three profile slots, MSVC natural alignment, little endian. :func:`decode` turns the bytes into a
readable nested dict; :func:`encode` writes an edited dict back over the original bytes, touching only
the fields that changed so everything else round-trips exactly. The layout is picked from the record size, unless a
model names its own (``layout``). ``docs/PROTOCOL.md``, ``docs/ULTIMATE_BT.md`` and ``docs/ULTIMATE_24G.md`` list
every offset.
"""
import math
import struct

from .protocol import CFG_SIZE, CFG_SIZE_BT, crc16, crc16_24g

FLAGS = {0x20200911: "enabled", 0x20190000: "disabled", 0: "off"}
# physical buttons, in map_key.key[] order (app: P1 = PR, P2 = PL back paddles, P3 = L4, P4 = R4)
BUTTONS = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "L3", "R3", "Select", "Start", "Star",
           "Home", "Up", "Down", "Left", "Right", "P1", "P2", "P3", "P4"]
BUTTONS_BT = BUTTONS[:20]   # Ultimate Bluetooth: same order, two back paddles (P1, P2), no L4/R4
# output codes a button can be remapped to
KEYCODES = {0: "None", 0x1: "Start", 0x2: "L3", 0x4: "R3", 0x8: "Select", 0x10: "X", 0x20: "Y",
            0x40: "Right", 0x80: "Left", 0x100: "Down", 0x200: "Up", 0x400: "LB", 0x800: "RB",
            0x1000: "B", 0x2000: "A", 0x4000: "LT", 0x8000: "RT", 0x10000: "Menu", 0x20000: "Home",
            0x100000: "P5", 0x200000: "P3", 0x400000: "Screenshot", 0x800000: "TurboSingle",
            0x1000000: "TurboAuto", 0x2000000: "P1", 0x4000000: "P2", 0x40000000: "P4",
            0x08000001: "RS_Up", 0x08000002: "RS_Down", 0x08000004: "RS_Left", 0x08000008: "RS_Right",
            0x08000010: "LS_Up", 0x08000020: "LS_Down", 0x08000040: "LS_Left", 0x08000080: "LS_Right"}
FEATURES = {0x1: "invert_LS_X", 0x2: "invert_LS_Y", 0x4: "invert_RS_X", 0x8: "invert_RS_Y",
            0x10: "swap_sticks", 0x80: "swap_triggers", 0x100: "swap_LS_dpad", 0x8000: "trigger_rumble"}
CRC_FIELD = (12, 16)     # byte range of crc_value
# Ultimate 2.4G: the codes of its app's BasicAdvanceUIData.KEY_*_MAP (RT and Home as set by AutoR2AndHome ->
# changeKey, same as the Ultimate 2): no P3-P5 or stick directions, but Swap
KEYCODES_24G = {0: "None", 0x1: "Start", 0x2: "L3", 0x4: "R3", 0x8: "Select", 0x10: "X", 0x20: "Y",
                0x40: "Right", 0x80: "Left", 0x100: "Down", 0x200: "Up", 0x400: "LB", 0x800: "RB",
                0x1000: "B", 0x2000: "A", 0x4000: "LT", 0x8000: "RT", 0x10000: "Menu", 0x20000: "Home",
                0x400000: "Screenshot", 0x800000: "TurboSingle", 0x1000000: "TurboAuto", 0x2000000: "P1",
                0x4000000: "P2", 0x8000000: "Swap"}

# Field kinds: B/H/I = unsigned ints, f = float, str32 = UTF-16BE name, F = flag, K = key code,
# M = feature bitmask, X = raw hex u32, C = #rrggbb color, r<N> = N raw bytes as a hex string; Ultimate 2.4G:
# str32le = UTF-16LE name (its app's Encoding.Unicode), k = key code of KEYCODES_24G.


def _from_names(table, val):
    if isinstance(val, int):
        return val
    rev = {v: k for k, v in table.items()}
    return rev[val] if val in rev else int(val, 16)


def _common(f, s, buttons, map_size, macros=None, xrumble=None, name="str32", key="K"):
    """Fields of slot ``s`` shared by both records; the sections after ``special`` move with the layout
    (``None``: the record has no such section)."""
    p = ("slots", s)
    f.append((p + ("flag",), 4 * s, "F"))
    f.append((p + ("name",), 20 + 32 * s, name))
    o = 116 + 12 * s
    f += [(p + ("rumble", "flag"), o, "F"), (p + ("rumble", "left"), o + 4, "f"), (p + ("rumble", "right"), o + 8, "f")]
    for sec, base in (("sticks", 152), ("triggers", 176), ("xinput_rumble", xrumble)):
        if base is None:
            continue
        o = base + 8 * s
        f += [(p + (sec, "flag"), o, "F"), (p + (sec, "left_start"), o + 4, "B"), (p + (sec, "left_end"), o + 5, "B"),
              (p + (sec, "right_start"), o + 6, "B"), (p + (sec, "right_end"), o + 7, "B")]
    o = 200 + 8 * s
    f += [(p + ("special", "flag"), o, "F"), (p + ("special", "features"), o + 4, "M")]
    o = 224 + map_size * s
    f.append((p + ("mapping", "flag"), o, "F"))
    f += [(p + ("mapping", b), o + 4 + 4 * i, key) for i, b in enumerate(buttons)]
    if macros is None:
        return
    o = macros + 216 * s
    f += [(p + ("macros", "flag"), o, "F"), (p + ("macros", "total_cnt"), o + 4, "B")]
    for r in range(4):
        q, ro = p + ("macros", "records", r), o + 8 + 52 * r
        f += [(q + ("name",), ro, "str32"), (q + ("gamepad_mode",), ro + 32, "B"), (q + ("special_flag",), ro + 33, "B"),
              (q + ("max_steps",), ro + 34, "H"), (q + ("offset",), ro + 36, "H"), (q + ("key_map",), ro + 40, "X"),
              (q + ("cycles_num",), ro + 44, "I"), (q + ("interval_ms",), ro + 48, "I")]


def _fields_bt(name="str32", key="K"):
    """``[(path, offset, kind)]`` of the Ultimate Bluetooth record (and, with its name and key kinds, the Ultimate
    2.4G's)."""
    f = [(("crc_value",), 12, "I"), (("gamepad_mode",), 16, "H"), (("cur_slot",), 18, "H")]
    for s in range(3):
        _common(f, s, BUTTONS_BT, 84, name=name, key=key)
        p, o = ("slots", s, "button_macros"), 476 + 392 * s     # macro_fun_record_t_Pro2: 18-step key macros
        f += [(p + ("flag",), o, "F"), (p + ("total_cnt",), o + 4, "B")]
        for r in range(4):
            q, ro = p + ("records", r), o + 8 + 96 * r
            f += [(q + ("key_map",), ro, "X"), (q + ("interval_time_index",), ro + 4, "r36"),
                  (q + ("key_index",), ro + 40, "r36"), (q + ("digital_joy",), ro + 76, "r18"), (q + ("max_index",), ro + 94, "B")]
    return f


def _fields():
    """``[(path, offset, kind)]`` for every field of the Ultimate 2 record."""
    f = [(("crc_value",), 12, "I"), (("gamepad_mode",), 16, "H"), (("cur_slot",), 18, "H")]
    for s in range(3):
        p = ("slots", s)
        _common(f, s, BUTTONS, 92, 500, 1148)
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
FIELDS_BT = _fields_bt()
FIELDS_24G = _fields_bt("str32le", "k")


def _layout(buf, layout=None):
    """Fields of the record ``buf``: those of ``layout`` (a :data:`LAYOUTS` key), else picked from its size."""
    if layout:
        return LAYOUTS[layout][0]
    if len(buf) == CFG_SIZE_BT:
        return FIELDS_BT
    if len(buf) == CFG_SIZE:
        return FIELDS
    raise ValueError(f"unknown config record size {len(buf)}")


def _get(buf, off, kind):
    if kind[0] == "r":
        return buf[off:off + int(kind[1:])].hex()
    if kind in ("str32", "str32le"):   # UTF-16BE (LE), max 16 chars, 0x0000-terminated; any 0xFF byte = erased
        raw = buf[off:off + 32]
        if b"\xff" in raw:
            return ""
        chars = [raw[i:i + 2] for i in range(0, 32, 2)]
        return b"".join(chars[:chars.index(b"\0\0")] if b"\0\0" in chars else chars).decode(
            "utf-16-be" if kind == "str32" else "utf-16-le", "replace")
    if kind == "f":
        v = struct.unpack_from("<f", buf, off)[0]
        return round(v, 4) if math.isfinite(v) else None   # erased flash (0xFFFFFFFF) is NaN
    v = struct.unpack_from("<" + ("I" if kind in "XCFKkM" else kind), buf, off)[0]
    if kind == "F":
        return FLAGS.get(v, f"0x{v:08x}")
    if kind == "K":
        return KEYCODES.get(v, f"0x{v:08x}")
    if kind == "k":
        return KEYCODES_24G.get(v, f"0x{v:08x}")
    if kind == "M":
        if v == 0xFFFFFFFF:
            return "0xffffffff"
        names = [n for b, n in FEATURES.items() if v & b]
        rest = v & ~sum(FEATURES)
        return names + ([f"0x{rest:08x}"] if rest else [])
    return f"0x{v:08x}" if kind == "X" else f"#{v:06x}" if kind == "C" else v


def _put(buf, off, kind, val):
    if kind[0] == "r":
        n = int(kind[1:])
        raw = bytes.fromhex(val)
        if len(raw) != n:
            raise ValueError(f"expected {n} bytes of hex, got {len(raw)}")
        buf[off:off + n] = raw
    elif kind in ("str32", "str32le"):
        buf[off:off + 32] = val[:16].encode("utf-16-be" if kind == "str32" else "utf-16-le").ljust(32, b"\0")
    elif kind == "f":
        struct.pack_into("<f", buf, off, float("nan") if val is None else float(val))
    elif kind in "XCFKkM":
        if kind == "F":
            v = _from_names(FLAGS, val)
        elif kind == "K":
            v = _from_names(KEYCODES, val)
        elif kind == "k":
            v = _from_names(KEYCODES_24G, val)
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
    diff = [i for i in range(len(old)) if old[i] != new[i] and not CRC_FIELD[0] <= i < CRC_FIELD[1]]
    return (diff[0], diff[-1] + 1) if diff else None


def same(written, read, layout=None, span=None):
    """Did the controller keep ``written`` (only ``span``, a ``(start, end)``, if given)? Models whose firmware owns
    ``crc_value`` and ``cur_slot`` (see :data:`LAYOUTS`) are compared without them."""
    a, b = bytearray(written), bytearray(read)
    if len(a) != len(b):
        return False
    for lo, hi in (LAYOUTS[layout][3] if layout else ()):
        a[lo:hi] = b[lo:hi]
    lo, hi = span or (0, len(a))
    return a[lo:hi] == b[lo:hi]


def decode(buf, layout=None):
    """Record bytes -> nested dict (``slots`` is a list of 3 profiles). ``layout``: see :func:`_layout`."""
    out = {}
    for path, off, kind in _layout(buf, layout):
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


def encode(doc, base, layout=None):
    """Write ``doc`` over the record ``base``; returns ``(new_bytes, changed_paths)``.

    Only fields that differ from ``decode(base)`` are written, so untouched bytes round-trip exactly;
    missing fields are skipped. ``crc_value`` is recomputed like the app's ``ANSI_CRC_16_Ultimate2`` /
    ``ANSI_CRC_16_UltimateBT`` (or the one of ``layout``).
    """
    buf = bytearray(base)
    cur = decode(base, layout)
    changed = []
    for path, off, kind in _layout(base, layout):
        if path == ("crc_value",):
            continue
        try:
            new = _lookup(doc, path)
        except (KeyError, IndexError, TypeError):
            continue
        if new != _lookup(cur, path):
            _put(buf, off, kind, new)
            changed.append("/".join(map(str, path)))
    struct.pack_into("<I", buf, CRC_FIELD[0], (LAYOUTS[layout][1] if layout else crc16)(buf))
    return bytes(buf), changed


def default_slot(doc, n, name, layout=None):
    """Fill slot ``n`` of ``doc`` with the defaults the Windows app uses for a new profile."""
    if layout:
        return LAYOUTS[layout][2](doc, n, name)
    if "button_macros" in doc["slots"][n]:
        return _default_slot_bt(doc, n, name)
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


def _default_slot_bt(doc, n, name):
    """Ultimate Bluetooth: the app's ``temp_new`` defaults with every section enabled (``enableFlagWithrecord``)."""
    mode = doc["gamepad_mode"]
    ident = ["A", "B", "X", "Y"] if mode in (0, 1) else ["B", "A", "Y", "X"]
    keys = ident + ["LB", "RB", "LT", "RT", "L3", "R3", "Select", "Start",
                    "Screenshot" if mode == 0 else "Menu", "Home", "Up", "Down", "Left", "Right", "None", "None"]
    on = "enabled"
    trig = 77 if mode == 0 else 0
    doc["slots"][n] = dict(doc["slots"][n], flag=on, name=name,
        rumble=dict(flag=on, left=1.0, right=1.0),
        sticks=dict(flag=on, left_start=0, left_end=128, right_start=0, right_end=128),
        triggers=dict(flag=on, left_start=trig, left_end=255, right_start=trig, right_end=255),
        special=dict(flag=on, features=[]),
        mapping=dict(flag=on, **dict(zip(BUTTONS_BT, keys))),
        button_macros=dict(flag=on, total_cnt=0, records=[dict(key_map="0x00000000", interval_time_index="00" * 36,
                           key_index="00" * 36, digital_joy="00" * 18, max_index=0) for _ in range(4)]))
    return doc


def _default_slot_24g(doc, n, name):
    """Ultimate 2.4G (``Ultimate2_4AdvanceUI``): sections read with their flag off are reset by its ``clearMapping``,
    ``clearRumble``, ``clearSticks``, ``clearTriger``, ``clearMacro`` and ``clearfeature`` (identity mapping, Star =
    Menu or Screenshot in mode 0), then saving enables the slot and every section (``enableFlagWithrecord``)."""
    keys = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "L3", "R3", "Select", "Start",
            "Screenshot" if doc["gamepad_mode"] == 0 else "Menu", "Home", "Up", "Down", "Left", "Right", "None", "None"]
    on = "enabled"
    doc["slots"][n] = dict(doc["slots"][n], flag=on, name=name,
        rumble=dict(flag=on, left=1.0, right=1.0),
        sticks=dict(flag=on, left_start=0, left_end=128, right_start=0, right_end=128),
        triggers=dict(flag=on, left_start=0, left_end=255, right_start=0, right_end=255),
        special=dict(flag=on, features=[]),
        mapping=dict(flag=on, **dict(zip(BUTTONS_BT, keys))),
        button_macros=dict(flag=on, total_cnt=0, records=[dict(key_map="0x00000000", interval_time_index="00" * 36,
                           key_index="00" * 36, digital_joy="00" * 18, max_index=0) for _ in range(4)]))
    return doc


# records that share a size but not their details: layout -> (fields, record CRC, new-profile defaults, byte ranges
# the firmware owns). The Ultimate 2.4G firmware stores a save counter in crc_value and keeps its own cur_slot.
LAYOUTS = {"ultimate_24g": (FIELDS_24G, crc16_24g, _default_slot_24g, (CRC_FIELD, (18, 20)))}
