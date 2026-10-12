"""Reusable rounded widgets drawn on canvases: Pill, panel, field, Slider, Toggle and the ColorPicker."""
import math
import tkinter as tk
import tkinter.font as tkfont

from . import theme
from .drawing import hex_to_hsv, hsv_to_hex, rounded, rr_points
from .i18n import _
from .theme import ACCENT, FG, LINE, MUTED, TILE, TILE_HI


class Pill(tk.Canvas):
    """Rounded button/chip: fill, hover, optional colour dot (canvas tag ``"dot"``); stretches with its cell."""

    def __init__(self, parent, text, s, cmd=None, fill=TILE_HI, fg=FG, hover=LINE, font=None, radius=None,
                 padx=16, pady=8, dot=False):
        font = font or (theme.FAMILY, 10)
        f = tkfont.Font(root=parent, font=font)
        self.dot_w = int(22 * s) if dot else 0
        w, h = f.measure(text) + int(2 * padx * s) + self.dot_w, f.metrics("linespace") + int(2 * pady * s)
        super().__init__(parent, width=w, height=h, bg=parent["bg"], highlightthickness=0, cursor="hand2" if cmd else "")
        self.text, self.font_, self.s, self.radius = text, font, s, radius
        self.fill, self.fg, self.hover, self.base, self.dot = fill, fg, hover, fill, dot
        self.dot_fill = "#000000"
        self.bind("<Configure>", lambda e: self.draw())
        if cmd:
            self.bind("<Button-1>", lambda e: cmd())
        if hover:
            self.bind("<Enter>", lambda e: self._hover(True))
            self.bind("<Leave>", lambda e: self._hover(False))
        self.draw()

    def _hover(self, on):
        self.fill = self.hover if on else self.base
        self.draw()

    def set(self, fill=None, fg=None, text=None):
        if fill:
            self.base = self.fill = fill
        self.fg = fg or self.fg
        self.text = text if text is not None else self.text
        self.draw()

    def draw(self):
        if self.find_withtag("dot"):
            self.dot_fill = self.itemcget("dot", "fill") or self.dot_fill
        w = max(self.winfo_width(), int(self["width"])) if self.winfo_width() > 1 else int(self["width"])
        h = int(self["height"])
        r = min(self.radius * self.s if self.radius else h / 2, h / 2)
        self.delete("all")
        rounded(self, 1, 1, w - 1, h - 1, r, fill=self.fill, outline="")
        cx = (w + self.dot_w) / 2
        if self.dot:
            d = 7 * self.s
            x = cx - tkfont.Font(root=self, font=self.font_).measure(self.text) / 2 - 12 * self.s
            self.create_oval(x - d, h / 2 - d, x + d, h / 2 + d, fill=self.dot_fill, outline=LINE, tags="dot")
        self.create_text(cx, h / 2, text=self.text, fill=self.fg, font=self.font_)


def panel(parent, s, fill=TILE, radius=14, padx=18, pady=14):
    """Rounded panel: a canvas with a rounded background and an inner frame that holds the content.

    Returns ``(canvas, inner_frame)``; pack the canvas, put widgets in the frame.
    """
    c = tk.Canvas(parent, bg=parent["bg"], highlightthickness=0, height=1, width=1)
    inner = tk.Frame(c, bg=fill)
    px, py = int(padx * s), int(pady * s)
    # starts at y=0 so Tk maps it inside the 1px-tall canvas; moved to (px, py) once its size is known
    win = c.create_window(px, 0, window=inner, anchor="nw")

    def redraw(e=None):
        w, h = c.winfo_width(), c.winfo_height()
        c.delete("bg")
        rounded(c, 0, 0, w, h, radius * s, fill=fill, outline="", tags="bg")
        c.tag_lower("bg")
        c.itemconfigure(win, width=max(w - 2 * px, 1))

    def fit(e=None):
        c.coords(win, px, py)
        c.configure(height=inner.winfo_reqheight() + 2 * py, width=inner.winfo_reqwidth() + 2 * px)
    inner.bind("<Configure>", fit)
    c.bind("<Configure>", redraw)
    return c, inner


def field(parent, var, width, font, s):
    """Rounded text field; returns the Entry (its master is the rounded canvas to pack)."""
    probe = tkfont.Font(root=parent, font=font)
    w, h = probe.measure("0" * width) + int(28 * s), probe.metrics("linespace") + int(16 * s)
    c = tk.Canvas(parent, width=w, height=h, bg=parent["bg"], highlightthickness=0)
    rounded(c, 1, 1, w - 1, h - 1, h / 2, fill=TILE_HI, outline="")
    e = tk.Entry(c, textvariable=var, width=width, bg=TILE_HI, fg=FG, insertbackground=FG, relief="flat",
                 font=font, highlightthickness=0, borderwidth=0)
    c.create_window(w / 2, h / 2, window=e)
    return e


class Slider(tk.Canvas):
    """Flat slider: rounded track, accent fill, round knob; bound to an IntVar."""

    def __init__(self, parent, var, lo, hi, s):
        super().__init__(parent, height=int(22 * s), bg=parent["bg"], highlightthickness=0, cursor="hand2")
        self.var, self.lo, self.hi, self.s = var, lo, hi, s
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Button-1>", self._at)
        self.bind("<B1-Motion>", self._at)
        var.trace_add("write", lambda *_: self.draw())

    def _at(self, e):
        pad = 9 * self.s
        w = max(self.winfo_width() - 2 * pad, 1)
        v = self.lo + round(min(max(e.x - pad, 0), w) / w * (self.hi - self.lo))
        if v != self.var.get():
            self.var.set(v)

    def draw(self):
        s, w = self.s, self.winfo_width()
        pad, y = 9 * s, 11 * s
        self.delete("all")
        if w <= 2 * pad:
            return
        f = (min(max(self.var.get(), self.lo), self.hi) - self.lo) / (self.hi - self.lo)
        x = pad + f * (w - 2 * pad)
        self.create_line(pad, y, w - pad, y, fill=LINE, width=4 * s, capstyle="round")
        self.create_line(pad, y, x, y, fill=ACCENT, width=4 * s, capstyle="round")
        self.create_oval(x - 7 * s, y - 7 * s, x + 7 * s, y + 7 * s, fill=FG, outline="")


class Toggle(tk.Canvas):
    """Switch bound to a BooleanVar."""

    def __init__(self, parent, var, s):
        super().__init__(parent, width=int(38 * s), height=int(20 * s), bg=parent["bg"], highlightthickness=0, cursor="hand2")
        self.var, self.s = var, s
        self.bind("<Button-1>", lambda e: var.set(not var.get()))
        var.trace_add("write", lambda *_: self.draw())
        self.draw()

    def draw(self):
        s, on = self.s, self.var.get()
        self.delete("all")
        rounded(self, 1, 1, 37 * s, 19 * s, 9 * s, fill=ACCENT if on else LINE, outline="")
        x = 28 * s if on else 10 * s
        self.create_oval(x - 7 * s, 3 * s, x + 7 * s, 17 * s, fill=FG, outline="")


class Select(Pill):
    """Drop-down selector: a pill with the current choice and a ▾; clicking opens a menu of ``(value, label)``
    options that sets ``var``."""

    def __init__(self, parent, var, options, s, **kw):
        self.var, self.labels = var, dict(options)
        self.menu = tk.Menu(parent, tearoff=0, bg=TILE, fg=FG, activebackground=LINE, activeforeground=ACCENT,
                            selectcolor=ACCENT, relief="flat", borderwidth=0, font=(theme.FAMILY, 10))
        for value, label in options:
            self.menu.add_radiobutton(label=label, value=value, variable=var)
        widest = max(self.labels.values(), key=len)
        super().__init__(parent, f"{widest}  ▾", s, cmd=self.open, **kw)     # sized for the longest choice
        self.set(text=self._text())
        var.trace_add("write", lambda *_: self.set(text=self._text()))

    def _text(self):
        return f"{self.labels.get(self.var.get(), self.var.get())}  ▾"

    def open(self):
        """Show the menu just above the pill (it lives in the window footer)."""
        self.menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() - self.menu.winfo_reqheight())


class ColorPicker(tk.Frame):
    """Inline HSV picker in the style of iro.js: hue/saturation wheel, brightness bar, hex field, presets, recents.

    ``on_change(color)`` is called for every user change (dragging calls it repeatedly).
    """
    PRESETS = ["#ff0000", "#ff7a00", "#ffd400", "#4cd964", "#00e5ff", "#0066ff", "#7a00ff", "#ff2bd6", "#ffffff", "#000000"]

    def __init__(self, parent, s, on_change):
        bg = parent["bg"]
        super().__init__(parent, bg=bg)
        self.s, self.on_change = s, on_change
        self.h, self.sat, self.val = 0.0, 1.0, 1.0
        self.recent = []
        d = self.d = int(170 * s)
        top = tk.Frame(self, bg=bg)
        top.pack(anchor="w")
        self.wheel = tk.Canvas(top, width=d, height=d, bg=bg, highlightthickness=0, cursor="crosshair")
        self.wheel.pack(side="left")
        self.img = tk.PhotoImage(master=self, width=d, height=d)
        self._render_wheel(bg)
        self.wheel.create_image(0, 0, image=self.img, anchor="nw")
        self.knob = self.wheel.create_oval(0, 0, 0, 0, outline="#ffffff", width=max(2, round(2 * s)))
        self.bar = tk.Canvas(top, width=int(22 * s), height=d, bg=bg, highlightthickness=0, cursor="hand2")
        self.bar.pack(side="left", padx=int(14 * s))
        self.bar_rects = [self.bar.create_rectangle(0, d * i / 48, 22 * s, d * (i + 1) / 48 + 1, outline="") for i in range(48)]
        # mask the gradient's corners with the background so the bar reads as a rounded pill
        self.bar.create_polygon(rr_points(-3 * s, -3 * s, 25 * s, d + 3 * s, 14 * s), smooth=True, fill="",
                                outline=bg, width=int(7 * s))
        self.bar_knob = self.bar.create_polygon(rr_points(0, 0, 1, 1, 0), smooth=True, fill="",
                                                outline="#ffffff", width=max(2, round(2 * s)))
        for w, fn in ((self.wheel, self._wheel_at), (self.bar, self._bar_at)):
            w.bind("<Button-1>", fn)
            w.bind("<B1-Motion>", fn)
            w.bind("<ButtonRelease-1>", lambda e: self._remember())
        info = tk.Frame(top, bg=bg)
        info.pack(side="left", fill="y")
        self.preview = tk.Canvas(info, width=int(64 * s), height=int(64 * s), bg=bg, highlightthickness=0)
        self.preview.pack(anchor="w")
        self.preview_dot = self.preview.create_oval(2, 2, 62 * s, 62 * s, outline=LINE, width=2)
        self.hex = tk.StringVar()
        e = field(info, self.hex, 8, ("Monospace", 11), s)
        e.master.pack(anchor="w", pady=int(10 * s))
        e.bind("<Return>", lambda ev: self._typed())
        e.bind("<FocusOut>", lambda ev: self._typed())
        tk.Label(info, text=_("Recentes"), bg=bg, fg=MUTED, font=(theme.FAMILY, 8)).pack(anchor="w")
        self.recent_row = tk.Canvas(info, width=int(110 * s), height=int(40 * s), bg=bg, highlightthickness=0)
        self.recent_row.pack(anchor="w")
        presets = tk.Canvas(self, width=int(26 * s * len(self.PRESETS)), height=int(30 * s), bg=bg, highlightthickness=0)
        presets.pack(anchor="w", pady=(int(10 * s), 0))
        for i, c in enumerate(self.PRESETS):
            x = (13 + 26 * i) * s
            dot = presets.create_oval(x - 10 * s, 5 * s, x + 10 * s, 25 * s, fill=c, outline=LINE, width=1)
            presets.tag_bind(dot, "<Button-1>", lambda e, c=c: self.choose(c))
        self._update()

    def _render_wheel(self, bg):
        d, r0 = self.d, self.d / 2
        rows = []
        for y in range(d):
            dy = y - r0 + .5
            row = []
            for x in range(d):
                dx = x - r0 + .5
                r = math.hypot(dx, dy)
                row.append(bg if r > r0 else hsv_to_hex((math.atan2(-dy, dx) / (2 * math.pi)) % 1, r / r0, 1))
            rows.append("{" + " ".join(row) + "}")
        self.img.put(" ".join(rows))

    def color(self):
        return hsv_to_hex(self.h, self.sat, self.val)

    def set(self, c):
        """Show colour ``c`` (``#rrggbb``) without notifying."""
        self.h, self.sat, self.val = hex_to_hsv(c[:7])
        self._update()

    def choose(self, c):
        """Pick colour ``c`` as if the user did it."""
        self.set(c)
        self.on_change(self.color())
        self._remember()

    def _wheel_at(self, e):
        r0 = self.d / 2
        dx, dy = e.x - r0, e.y - r0
        self.h = (math.atan2(-dy, dx) / (2 * math.pi)) % 1
        self.sat = min(math.hypot(dx, dy) / r0, 1.0)
        if self.val < .05:
            self.val = 1.0            # picking a hue while black would show nothing
        self._update()
        self.on_change(self.color())

    def _bar_at(self, e):
        self.val = 1 - min(max(e.y / self.d, 0.0), 1.0)
        self._update()
        self.on_change(self.color())

    def _typed(self):
        t = self.hex.get().strip().lower()
        t = t if t.startswith("#") else "#" + t
        if len(t) == 7 and all(ch in "0123456789abcdef" for ch in t[1:]):
            if t != self.color():
                self.choose(t)
        else:
            self.hex.set(self.color())

    def _remember(self):
        c = self.color()
        self.recent = [c] + [x for x in self.recent if x != c][:5]
        self.recent_row.delete("all")
        s = self.s
        for i, c in enumerate(self.recent):
            x, y = (12 + 24 * (i % 3)) * s, (10 + 20 * (i // 3)) * s
            dot = self.recent_row.create_oval(x - 8 * s, y - 8 * s, x + 8 * s, y + 8 * s, fill=c, outline=LINE)
            self.recent_row.tag_bind(dot, "<Button-1>", lambda e, c=c: self.choose(c))

    def _update(self):
        s, d, r0 = self.s, self.d, self.d / 2
        a, rr = self.h * 2 * math.pi, self.sat * (r0 - 2)
        x, y, k = r0 + rr * math.cos(a), r0 - rr * math.sin(a), 7 * s
        self.wheel.coords(self.knob, x - k, y - k, x + k, y + k)
        for i, item in enumerate(self.bar_rects):
            self.bar.itemconfigure(item, fill=hsv_to_hex(self.h, self.sat, 1 - i / 47))
        y = (1 - self.val) * d
        self.bar.coords(self.bar_knob, *rr_points(2 * s, max(2, y - 4 * s), 20 * s, min(d - 2, y + 4 * s), 4 * s))
        self.preview.itemconfigure(self.preview_dot, fill=self.color())
        self.hex.set(self.color())
