"""Drawing primitives: rounded shapes, gradients, colour maths and the LED effect preview."""
import colorsys
import math
import tkinter as tk

from . import theme


def rr_points(x1, y1, x2, y2, r):
    """Control points of a rounded rectangle (for ``create_polygon(..., smooth=True)``)."""
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def rounded(c, x1, y1, x2, y2, r, **kw):
    return c.create_polygon(rr_points(x1, y1, x2, y2, r), smooth=True, **kw)


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


def gradient_fill(master, pts, w, h, stops):
    """PhotoImage with polygon ``pts`` filled by a vertical 3-stop gradient (Tk canvases have no gradients)."""
    img = tk.PhotoImage(master=master, width=w, height=h)
    ys = [p[1] for p in pts]
    y0, y1 = max(0, int(min(ys))), min(h - 1, int(max(ys)))
    for y in range(y0, y1 + 1):
        yc, xs = y + .5, []
        for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1]):
            if (ya <= yc) != (yb <= yc):
                xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
        xs.sort()
        t = (y - y0) / max(y1 - y0, 1)
        color = mix(stops[0], stops[1], t * 2) if t < .5 else mix(stops[1], stops[2], t * 2 - 1)
        for xa, xb in zip(xs[::2], xs[1::2]):
            a, b = max(0, round(xa)), min(w, round(xb))
            if b > a:
                img.put(color, to=(a, y, b, y + 1))
    return img


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
