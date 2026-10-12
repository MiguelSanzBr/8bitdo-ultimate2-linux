"""Mixin: the controller drawing (skins, LED rings, callouts), its per-frame animation and section icons."""
import math
import time
import tkinter.font as tkfont

from .. import config
from . import theme
from .catalog import DISPLAY
from .drawing import gradient_fill, led_frame, mix, rounded, rr_points, set_color, smooth_outline
from .geometry import (BEHIND, BODY, CALLOUTS, DPAD_CENTER, EMBLEM, HEIGHT, HOME_OFFSET, PARTS, RINGS, ROLES,
                       STICK_WELLS, WIDTH)
from .i18n import _
from .theme import ACCENT, BG, BODY_FILL, FG, SEL_FILL, SKINS


class ControllerView:
    """Needs from the App: ``s``, ``skin``, ``ctrl``, ``led_items``, ``led_glow``, ``_imgs``, ``swatches``,
    ``pad_down``, ``pad_axes``, ``press_t``, ``sel_btn``, ``_remapped``, ``colors``, ``v`` and the
    ``select_button``/``show``/``pick_color``/``paint`` methods."""

    # ------------------------------------------------------------ drawing
    def draw_controller(self, c, mode, ox=0):
        """Draw the controller on canvas ``c``.

        mode: ``"home"`` (click opens the button page, adds callouts and a glow), ``"map"`` (click selects a
        button) or ``"leds"`` (LEDs are clickable colour targets). ``ox`` shifts the drawing right (logical units).
        """
        s, sk = self.s, SKINS[self.skin]
        w = max(1, round(1.5 * s))
        P = lambda *xy: [(v + (ox if i % 2 == 0 else 0)) * s for i, v in enumerate(xy)]
        body = P(*[v for pt in BODY for v in pt])
        if mode == "home":                                  # soft violet glow under the controller
            for k in range(10):
                t = k / 9
                rx, ry = 250 - 140 * t, 46 - 26 * t
                c.create_oval(P(220 - rx, 262 - ry, 220 + rx, 262 + ry), outline="", fill=mix(BG, "#4b2f9a", .15 + .55 * t))
        c.create_polygon([v + (4 if i % 2 else 0) * s for i, v in enumerate(body)], smooth=True,
                         fill=mix(BG, "#000000", .45), outline="")
        parts = {}

        def make(name):
            shape, xy, label = PARTS[name]
            tag = f"b:{name}"
            base = sk[ROLES.get(name, "btn")]
            pts = None
            if name in ("L3", "R3"):
                xy = (xy[0], xy[1], xy[2] - 7)          # the cap moves inside its well
            if shape == "circle":
                x, y, r = xy
                box = P(x - r, y - r, x + r, y + r)
                glow = c.create_oval(box, outline="", width=max(2, round(2 * s)), state="hidden")
                part = c.create_oval(box, fill=base[0], outline=base[1], width=w, tags=tag)
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            elif shape == "poly":
                outline, (lx, ly) = xy
                pts = P(*[v for pt in outline for v in pt])
                box = (min(pts[::2]), min(pts[1::2]), max(pts[::2]), max(pts[1::2]))
                glow = c.create_polygon(pts, smooth=True, fill="", outline="", width=max(2, round(2 * s)), state="hidden")
                part = c.create_polygon(pts, smooth=True, fill=base[0], outline=base[1], width=w, tags=tag)
                cx, cy = (lx + ox) * s, ly * s
            else:
                box = P(*xy)
                glow = c.create_polygon(rr_points(*box, 6 * s), smooth=True, fill="", outline="",
                                        width=max(2, round(2 * s)), state="hidden")
                rad = min(4 * s if shape == "rect" else 7 * s, (box[3] - box[1]) / 2)
                part = rounded(c, *box, rad, fill=base[0], outline=base[1], width=w, tags=tag)
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            extra = [c.create_oval(cx - 7 * s, cy - 7 * s, cx + 7 * s, cy + 7 * s, outline=base[1], tags=tag),
                     c.create_arc(cx - 15 * s, cy - 15 * s, cx + 15 * s, cy + 15 * s, start=100, extent=80,
                                  style="arc", outline=mix(base[0], "#ffffff", .25), width=2 * s, tags=tag)] \
                if name in ("L3", "R3") else []
            text = c.create_text(cx, cy, text=label, fill=base[2], font=theme.font(7, "bold"), tags=tag) if label else None
            bx, by = (cx + 14 * s, cy - 6 * s) if shape == "poly" else (box[2], box[1])
            badge = c.create_oval(bx - 3 * s, by - 3 * s, bx + 3 * s, by + 3 * s, fill=ACCENT, outline=BODY_FILL, state="hidden")
            parts[name] = dict(body=part, text=text, glow=glow, badge=badge, extra=extra, box=box, shape=shape,
                               off=(0.0, 0.0), st=None, glowing=False, base=base, pts=pts)
            if mode == "map":
                c.tag_bind(tag, "<Button-1>", lambda e, n=name: (self.flash(n), self.select_button(n)))
            elif mode == "home":
                c.tag_bind(tag, "<Button-1>", lambda e, n=name: (self.flash(n), self.select_button(n), self.show("buttons")))

        for name in BEHIND:
            make(name)
        self._imgs[c] = gradient_fill(c, smooth_outline([(x * s, y * s) for x, y in BODY]),
                                      int(WIDTH * s), int(HEIGHT * s), sk["body"])
        c.create_image(ox * s, 0, image=self._imgs[c], anchor="nw")
        c.create_polygon(body, smooth=True, fill="", outline=sk["line"], width=max(1, round(2 * s)))
        for x, y, r in STICK_WELLS:
            c.create_oval(P(x - r, y - r, x + r, y + r), fill=sk["well"], outline="")
        dx0, dy0 = DPAD_CENTER
        rounded(c, *P(dx0 - 10, dy0 - 10, dx0 + 10, dy0 + 10), 5 * s, fill=sk["dpad"][0], outline="")   # d-pad hub
        if sk["emblem"]:                                    # flower emblem around Home
            ex, ey = EMBLEM
            for k in range(8):
                a, ln = math.radians(k * 45 - 90), (21 if k % 2 == 0 else 13)
                tip = (ex + ln * math.cos(a), ey + ln * math.sin(a))
                side = [(ex + ln * .5 * math.cos(a + d), ey + ln * .5 * math.sin(a + d)) for d in (.5, -.5)]
                c.create_polygon(P(ex, ey, *side[0], *tip, *side[1]), smooth=True, outline="#6e0f1d",
                                 fill=sk["emblem"] if k % 2 == 0 else mix(sk["emblem"], "#ffffff", .25))
        leds, glow = [], []
        for ring, (x, y, r) in enumerate(RINGS):          # soft halo behind the light ring
            for i in range(12):
                glow.append(c.create_arc(P(x - r, y - r, x + r, y + r), start=90 - 30 * i - 15, extent=30, style="arc",
                                         outline=sk["led_off"], width=11 * s))
        for ring, (x, y, r) in enumerate(RINGS):
            for i in range(12):
                item = c.create_arc(P(x - r, y - r, x + r, y + r), start=90 - 30 * i - 15.5, extent=31, style="arc",
                                    outline=sk["led_off"], width=(6 if mode == "leds" else 4.5) * s)
                if mode == "leds":
                    key = f"single{ring * 12 + i}"
                    c.tag_bind(item, "<Button-1>", lambda e, k=key: self.pick_color(k))
                    self.swatches[key] = (c, item)
                leds.append(item)
        self.led_items.append((c, leds))
        self.led_glow[c] = glow
        for name in PARTS:
            if name not in BEHIND:
                make(name)
        c.create_oval(P(dx0 - 4, dy0 - 4, dx0 + 4, dy0 + 4), fill="#a6a6ae", outline="#d8d8de")   # metal centre
        arrows = {(0, -1): "Up", (0, 1): "Down", (-1, 0): "Left", (1, 0): "Right"}
        for (dx, dy), name in arrows.items():
            x, y = dx0 + 20 * dx, dy0 + 20 * dy
            c.create_polygon(P(x + 3 * dx, y + 3 * dy, x - 3 * dy - 2 * dx, y - 3 * dx - 2 * dy,
                               x + 3 * dy - 2 * dx, y + 3 * dx - 2 * dy), fill="#55555c", outline="", tags=f"b:{name}")
        if mode == "home":
            self.callouts(c, ox)
        if mode == "leds":
            for item in leds:
                c.tag_raise(item)
        self.ctrl[c] = (parts, mode)
        return parts

    def callouts(self, c, ox):
        """Labels around the home drawing, linked to their part; clicking one opens its page."""
        s = self.s
        for text, side, y, (tx, ty), target in CALLOUTS:
            label = _(text)
            f = tkfont.Font(root=c, font=theme.font(9, "bold"))
            w, h = f.measure(label) / s + 26, 22
            x1 = 6 if side == "l" else 2 * ox + WIDTH - 6 - w
            x2, edge = x1 + w, (x1 + w if side == "l" else x1)
            tag = "co:" + text.replace(" ", "_")          # Tk splits tags at spaces
            rounded(c, x1 * s, (y - h / 2) * s, x2 * s, (y + h / 2) * s, h / 2 * s, fill=theme.CALLOUT_FILL,
                    outline=theme.CALLOUT_LINE, width=max(1, round(1.5 * s)), tags=tag)
            c.create_text((x1 + w / 2) * s, y * s, text=label, fill=FG, font=theme.font(9, "bold"), tags=tag)
            px, py = (tx + ox) * s, ty * s
            mx = (edge + (14 if side == "l" else -14)) * s
            c.create_line(edge * s, y * s, mx, y * s, px, py, fill=theme.CALLOUT_LINE, width=max(1, round(1.5 * s)))
            c.create_oval(px - 3 * s, py - 3 * s, px + 3 * s, py + 3 * s, fill=theme.CALLOUT_DOT, outline="")
            page = "sticks" if target == "sticks" else "buttons"
            c.tag_bind(tag, "<Button-1>", lambda e, t=target, p=page: (p == "buttons" and self.select_button(t), self.show(p)))

    def apply_skin(self, name):
        """Redraw every controller drawing with another skin (chosen from the controller's edition)."""
        self.skin = name
        for c, (parts, mode) in list(self.ctrl.items()):
            c.delete("all")
            self.led_items = [x for x in self.led_items if x[0] is not c]
            new = self.draw_controller(c, mode, ox=HOME_OFFSET if mode == "home" else 0)
            if mode == "map":
                self.map_items = new
            elif mode == "home":
                self.home_items = new
        if self.colors:
            for k in self.swatches:
                self.paint(k)
        self.refresh_mapping()

    def icon(self, c, kind, x, y):
        """Line icon of a section tile."""
        s, w = self.s, max(1, round(1.6 * self.s))
        P = lambda *xy: [v * s for v in xy]
        if kind == "buttons":
            for dx, dy in ((0, -9), (0, 9), (-9, 0), (9, 0)):
                c.create_oval(P(x + dx - 4, y + dy - 4, x + dx + 4, y + dy + 4), outline=FG, width=w)
        elif kind == "sticks":
            for r in (13, 7, 2):
                c.create_oval(P(x - r, y - r, x + r, y + r), outline=FG, width=w)
        elif kind == "triggers":
            rounded(c, *P(x - 9, y - 13, x + 9, y + 13), 8 * s, fill="", outline=FG, width=w)
            c.create_line(P(x - 9, y - 2, x + 9, y - 2), fill=FG, width=w)
        elif kind == "rumble":
            for dx in (-10, -3, 4, 11):
                c.create_line(P(x + dx, y - 10, x + dx - 3, y - 4, x + dx + 3, y + 4, x + dx, y + 10), fill=FG, width=w, smooth=True)
        elif kind == "gyro":
            c.create_oval(P(x - 14, y - 6, x + 14, y + 6), outline=FG, width=w)
            c.create_oval(P(x - 6, y - 14, x + 6, y + 14), outline=FG, width=w)
            c.create_oval(P(x - 2, y - 2, x + 2, y + 2), fill=FG, outline="")
        elif kind == "leds":
            c.create_oval(P(x - 6, y - 6, x + 6, y + 6), outline=FG, width=w)
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (.7, .7), (-.7, .7), (.7, -.7), (-.7, -.7)):
                c.create_line(P(x + dx * 9, y + dy * 9, x + dx * 13, y + dy * 13), fill=FG, width=w)
        else:  # profile
            c.create_oval(P(x - 5, y - 13, x + 5, y - 3), outline=FG, width=w)
            c.create_arc(P(x - 11, y - 1, x + 11, y + 21), start=0, extent=180, style="arc", outline=FG, width=w)

    # ------------------------------------------------------------ live state
    def flash(self, name):
        """Ripple on a button (mouse click feedback; real presses come from the joystick reader)."""
        self.press_t[name] = time.time()

    def trigger_level(self, name):
        """0..1 pressure of LT/RT from the joystick axes (js reports -32767 released .. 32767 full)."""
        axis = {"LT": 2, "RT": 5}.get(name)
        return None if axis is None else (self.pad_axes.get(axis, -32767) + 32767) / 65534

    def style(self, c, parts, mode, now):
        """Per-frame look of each part: pressed > trigger pressure > selected > normal, plus ripple and stick motion."""
        s = self.s
        for name, p in parts.items():
            level = self.trigger_level(name)
            if name in self.pad_down:
                st = (ACCENT, ACCENT, BG)
            elif level and level > .02:
                st = (mix(p["base"][0], ACCENT, level), ACCENT, p["base"][2])
            elif mode == "map" and name == self.sel_btn:
                st = (SEL_FILL, ACCENT, ACCENT)
            else:
                st = p["base"]
            if st != p["st"]:
                p["st"] = st
                c.itemconfigure(p["body"], fill=st[0], outline=st[1])
                if p["text"]:
                    c.itemconfigure(p["text"], fill=st[2])
            c.itemconfigure(p["badge"], state="normal" if mode != "leds" and name in self._remapped else "hidden")
            t = now - self.press_t.get(name, -1e9)
            if t < theme.PULSE:
                k = t / theme.PULSE
                g = (2 + 9 * k) * s
                x1, y1, x2, y2 = p["box"]
                ox, oy = p["off"]
                box = (x1 - g + ox, y1 - g + oy, x2 + g + ox, y2 + g + oy)
                if p["shape"] == "poly":            # grow the outline around its centre
                    mx, my, f = (x1 + x2) / 2, (y1 + y2) / 2, 1 + g / max((x2 - x1) / 2, 1)
                    c.coords(p["glow"], *[(v - (mx if i % 2 == 0 else my)) * f + (mx if i % 2 == 0 else my)
                                          for i, v in enumerate(p["pts"])])
                else:
                    c.coords(p["glow"], *(box if p["shape"] == "circle" else rr_points(*box, 6 * s + g)))
                c.itemconfigure(p["glow"], outline=mix(ACCENT, BODY_FILL, k), state="normal")
                p["glowing"] = True
            elif p["glowing"]:
                c.itemconfigure(p["glow"], state="hidden")
                p["glowing"] = False
            if name in ("L3", "R3"):
                ax = (0, 1) if name == "L3" else (3, 4)
                tx, ty = (self.pad_axes.get(a, 0) / 32767 * 6 * s for a in ax)
                dx, dy = tx - p["off"][0], ty - p["off"][1]
                if abs(dx) + abs(dy) > .5:
                    for item in [p["body"], p["text"], p["badge"], *p["extra"]]:
                        if item:
                            c.move(item, dx, dy)
                    p["off"] = (tx, ty)

    def select_button(self, name):
        self.sel_btn = name
        self.map_choice.set(self.v["keys"][name].get())
        self.refresh_mapping()

    def refresh_mapping(self):
        """Badge every button whose function differs from its default; update the side panel."""
        dflt = self._defaults(self.slot)["mapping"] if self.doc else {}
        self._remapped = {b for b in config.BUTTONS if dflt and self.v["keys"][b].get() != dflt[b]}
        cur = self.v["keys"][self.sel_btn].get()
        self.map_title.configure(text=_("Botão {}").format(DISPLAY.get(self.sel_btn, self.sel_btn)))
        self.map_sub.configure(text=_("função atual: {}").format(DISPLAY.get(cur, cur) or "—"))
        now = time.time()
        for c, (parts, mode) in self.ctrl.items():
            self.style(c, parts, mode, now)

    def animate(self):
        """Live LED preview, button presses and stick motion on the visible controller drawing."""
        now = time.time()
        visible = {"home": "home", "buttons": "map", "leds": "leds"}.get(self.page)
        frame = led_frame(self.v["theme"].get(), self.colors, self.v["hot_speed"].get(), now) if self.colors else None
        for c, (parts, mode) in self.ctrl.items():
            if mode != visible:
                continue
            self.style(c, parts, mode, now)
            leds = next(l for cv, l in self.led_items if cv is c)
            if frame:
                halo = mix(SKINS[self.skin]["body"][1], "#000000", .35)
                for item, g, color in zip(leds, self.led_glow[c], frame):
                    set_color(c, item, color)
                    set_color(c, g, mix(color, halo, .7))
        self.after(theme.FRAME_MS, self.animate)
