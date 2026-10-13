"""Drawing primitives: rounded shapes, gradients, colour maths and the LED effect preview."""
import colorsys
import functools
import math
import tkinter as tk

from . import theme


def rr_points(x1, y1, x2, y2, r):
    """Control points of a rounded rectangle (for ``create_polygon(..., smooth=True)``)."""
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def rounded(c, x1, y1, x2, y2, r, **kw):
    return c.create_polygon(rr_points(x1, y1, x2, y2, r), smooth=True, **kw)


def stadium(x1, y1, x2, y2, steps=12):
    """Points of a box with fully rounded ends (a circle when it is square), for ``create_polygon``."""
    r = min(x2 - x1, y2 - y1) / 2
    cx1, cy1, cx2, cy2 = x1 + r, y1 + r, x2 - r, y2 - r
    out = []
    for k in range(4 * steps):              # quarter arcs, clockwise from the right end
        a = math.pi / 2 * k / steps - math.pi / 2
        cx = cx2 if math.cos(a) >= 0 else cx1
        cy = cy2 if math.sin(a) >= 0 else cy1
        out += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return out


def smooth_outline(pts, steps=10):
    """Points of the curve Tk draws for a closed ``smooth=True`` polygon (quadratic splines through edge midpoints)."""
    out = []
    for i in range(len(pts)):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
        a, b = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2), ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        for k in range(steps):
            t = k / steps
            out.append(tuple((1 - t) ** 2 * a[j] + 2 * (1 - t) * t * p1[j] + t * t * b[j] for j in (0, 1)))
    return out


def gradient_fill(master, pts, w, h, stops, bevel=0):
    """PhotoImage with polygon ``pts`` filled by a vertical 3-stop gradient (Tk canvases have no gradients).

    ``bevel`` > 0 (pixels) also lights the shape like a moulded part: the edges are rounded off over ``bevel``
    pixels, lit from above, with a soft highlight on the upper face.
    """
    img = tk.PhotoImage(master=master, width=w, height=h)
    for y, spans in enumerate(_shade(tuple(map(tuple, pts)), w, h, tuple(stops), bevel)):
        for x, colors in spans:
            img.put("{" + " ".join(colors) + "}", to=(x, y))
    return img


def _inside(pts, w, h):
    """Rows of 0/1 flags: which pixel centres lie inside the polygon (even-odd rule)."""
    rows = [bytearray(w) for _ in range(h)]
    for y in range(h):
        yc, xs = y + .5, []
        for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1]):
            if (ya <= yc) != (yb <= yc):
                xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
        xs.sort()
        for xa, xb in zip(xs[::2], xs[1::2]):
            a, b = max(0, round(xa)), min(w, round(xb))
            rows[y][a:b] = b"\1" * max(b - a, 0)
    return rows


def _heights(inside, w, h, bevel):
    """Rounded-edge height field 0..1: distance to the outline (chamfer transform), a quarter-circle profile
    over ``bevel`` pixels, then box-blurred twice so the transform's steps do not show in the lighting."""
    d = [[1e9 if v else 0.0 for v in row] for row in inside]
    for rng, step in ((range(h), -1), (range(h - 1, -1, -1), 1)):
        for y in rng:
            row, prev = d[y], d[y + step] if 0 <= y + step < h else None
            for x in (range(w) if step < 0 else range(w - 1, -1, -1)):
                if row[x]:
                    v = row[x]
                    if 0 <= x + step < w:
                        v = min(v, row[x + step] + 1)
                    if prev:
                        v = min(v, prev[x] + 1, *(prev[i] + 1.414 for i in (x - 1, x + 1) if 0 <= i < w))
                    row[x] = v
    hgt = [[math.sqrt(1 - (1 - min(v / bevel, 1.0)) ** 2) for v in row] for row in d]
    for _ in range(2):
        hgt = [[sum(r[max(0, x - 2):x + 3]) / len(r[max(0, x - 2):x + 3]) for x in range(w)] for r in hgt]
        cols = [[sum(c[max(0, y - 2):y + 3]) / len(c[max(0, y - 2):y + 3]) for y in range(h)] for c in zip(*hgt)]
        hgt = [list(r) for r in zip(*cols)]
    return hgt


LIGHT = (-0.3, -0.75, 0.6)          # light from above, slightly left, towards the viewer


@functools.lru_cache(maxsize=16)
def _shade(pts, w, h, stops, bevel):
    """Per row, the ``(x, [colours])`` spans to paint (cached: every drawing of a skin shares the same body)."""
    inside = _inside(list(pts), w, h)
    used = [y for y in range(h) if any(inside[y])]
    if not used:
        return [[] for _ in range(h)]
    top, bot = used[0], used[-1]
    hgt = _heights(inside, w, h, bevel) if bevel else None
    n = math.sqrt(sum(v * v for v in LIGHT))
    lx, ly, lz = (v / n for v in LIGHT)
    cx, cy, rx, ry = w / 2, top + (bot - top) * .22, w * .42, max((bot - top) * .22, 1)
    out = []
    for y in range(h):
        if not any(inside[y]):
            out.append([])
            continue
        t = (y - top) / max(bot - top, 1)
        base = _hex(mix(stops[0], stops[1], t * 2) if t < .5 else mix(stops[1], stops[2], t * 2 - 1))
        spans, x = [], 0
        while x < w:
            if not inside[y][x]:
                x += 1
                continue
            x0, colors = x, []
            while x < w and inside[y][x]:
                light = 0.0
                if hgt:
                    hr, hu, hd = hgt[y], hgt[max(y - 1, 0)], hgt[min(y + 1, h - 1)]
                    nx = -(hr[min(x + 1, w - 1)] - hr[max(x - 1, 0)]) * bevel * .5
                    ny = -(hd[x] - hu[x]) * bevel * .5
                    diff = (nx * lx + ny * ly + lz) / math.sqrt(nx * nx + ny * ny + 1) - lz    # 0 on the flat face
                    light = diff * (1.1 if diff > 0 else .55) + .22 * math.exp(-((x - cx) / rx) ** 2 - ((y - cy) / ry) ** 2)
                c = [v + (255 - v) * min(light, 1) for v in base] if light >= 0 else [v * (1 + max(light, -1) * .9) for v in base]
                colors.append("#%02x%02x%02x" % tuple(int(v) for v in c))
                x += 1
            spans.append((x0, colors))
        out.append(spans)
    return out


def _hex(c):
    return [int(c[i:i + 2], 16) for i in (1, 3, 5)]


def set_color(c, item, color):
    """LED arcs are coloured by outline, everything else by fill."""
    c.itemconfigure(item, **{"outline" if c.type(item) == "arc" else "fill": color})


def mix(a, b, t):
    """Blend two ``#rrggbb`` colours (t=0 -> a, t=1 -> b)."""
    ca, cb = (int(a[i:i + 2], 16) for i in (1, 3, 5)), (int(b[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def hex_to_hsv(c):
    return colorsys.rgb_to_hsv(*(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)))


def hsv_to_hex(h, s, v):
    return "#" + "".join(f"{round(x * 255):02x}" for x in colorsys.hsv_to_rgb(h, s, v))


def led_frame(led_theme, colors, speed, t):
    """Colours of the 24 LEDs at time ``t`` (s) — an approximation of the firmware effects for the preview."""
    if led_theme == 4:
        return [colors[f"single{i}"][:7] for i in range(24)]
    if led_theme == 3:
        head = t * speed * 1.2
        return [colors["hot_color"][:7] if (i % 12 - head) % 12 < 3 else colors["hot_bg"][:7] for i in range(24)]
    if led_theme == 2:
        return [mix(colors["dyn_color"][:7], colors["dyn_bg"][:7], (math.sin(t * 2 + i % 12 * .5) + 1) / 2)
                for i in range(24)]
    return [theme.LINE] * 24
