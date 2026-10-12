"""widgets: ColorPicker, Slider, Toggle, Pill, panel, field."""
import tkinter as tk

import pytest

from ultimate2.gui import theme, widgets

from .conftest import click, fire, texts, walk, xy


# ---------------------------------------------------------------- ColorPicker
@pytest.fixture
def pk(shared_app, scratch):
    got = []
    p = widgets.ColorPicker(scratch, 1.0, got.append)
    p.pack()
    p.got = got
    shared_app.update()
    return p


def test_picker_initial_and_set(pk):
    assert pk.color() == "#ff0000" and pk.hex.get() == "#ff0000"
    pk.set("#00ff00ff")                          # alpha is ignored, nothing is notified
    assert pk.color() == "#00ff00" and pk.hex.get() == "#00ff00" and not pk.got
    assert pk.preview.itemcget(pk.preview_dot, "fill") == "#00ff00"


def test_picker_choose_remembers(pk):
    pk.choose("#123456")
    assert pk.got == ["#123456"] and pk.recent == ["#123456"]
    pk.choose("#654321")
    pk.choose("#123456")                         # duplicates move to the front
    assert pk.recent == ["#123456", "#654321"]
    for c in ("#010101", "#020202", "#030303", "#040404", "#050505", "#060606"):
        pk.choose(c)
    assert len(pk.recent) == 6


def test_picker_wheel(pk):
    d = pk.d
    pk._wheel_at(xy(d, d / 2))                   # right edge: hue 0, full saturation
    assert pk.got[-1] == "#ff0000" and pk.sat == 1.0
    pk._wheel_at(xy(d / 2, d / 2))               # center: no saturation
    assert pk.sat == 0 and pk.got[-1] == "#ffffff"
    pk._wheel_at(xy(10 * d, d / 2))              # far outside: clamped
    assert pk.sat == 1.0
    pk.val = 0.0
    pk._wheel_at(xy(d / 2, 0))                   # picking a hue while black brings the brightness back
    assert pk.val == 1.0
    pk.val = .5
    pk._wheel_at(xy(d / 2, 0))
    assert pk.val == .5


def test_picker_bar(pk):
    d = pk.d
    pk._bar_at(xy(0, 0))
    assert pk.val == 1.0 and pk.got[-1] == "#ff0000"
    pk._bar_at(xy(0, d))
    assert pk.val == 0.0 and pk.got[-1] == "#000000"
    pk._bar_at(xy(0, -50))
    assert pk.val == 1.0
    pk._bar_at(xy(0, 5 * d))
    assert pk.val == 0.0
    pk._bar_at(xy(0, d / 2))
    assert pk.val == .5 and len(pk.got) == 5


def test_picker_mouse_bindings(shared_app, pk):
    click(shared_app, pk.wheel)                  # %x/%y are 0: top-left corner of the wheel
    click(shared_app, pk.wheel, "<B1-Motion>")
    click(shared_app, pk.bar)
    click(shared_app, pk.bar, "<B1-Motion>")
    assert len(pk.got) == 4 and not pk.recent
    click(shared_app, pk.wheel, "<ButtonRelease-1>")
    assert pk.recent == [pk.color()]
    click(shared_app, pk.bar, "<ButtonRelease-1>")
    assert len(pk.recent) == 1


def test_picker_typed(shared_app, pk):
    entry = next(w for w in walk(pk) if isinstance(w, tk.Entry))
    pk.hex.set("#00FF00")                        # valid, upper case
    click(shared_app, entry, "<Return>")
    assert pk.got == ["#00ff00"] and pk.hex.get() == "#00ff00"
    pk.hex.set("0000ff")                         # without '#'
    click(shared_app, entry, "<FocusOut>")
    assert pk.got[-1] == "#0000ff"
    pk.hex.set("0000ff")                         # same color: nothing happens
    pk._typed()
    assert len(pk.got) == 2
    for bad in ("#12", "#gggggg", "", "#12345678"):
        pk.hex.set(bad)
        pk._typed()
        assert pk.hex.get() == "#0000ff"
    assert len(pk.got) == 2


def test_picker_presets_and_recents(shared_app, pk):
    presets = next(w for w in pk.winfo_children() if isinstance(w, tk.Canvas))
    dots = presets.find_all()
    assert len(dots) == len(pk.PRESETS)
    fire(shared_app, presets, dots[4])
    assert pk.got == [pk.PRESETS[4]] and pk.recent == [pk.PRESETS[4]]
    for i in (0, 1, 2, 3):
        fire(shared_app, presets, dots[i])
    items = pk.recent_row.find_all()
    assert len(items) == 5                       # second row of recents appears from the 4th color on
    fire(shared_app, pk.recent_row, items[-1])   # oldest is the last chip
    assert pk.got[-1] == pk.PRESETS[4] and pk.recent[0] == pk.PRESETS[4]


# ---------------------------------------------------------------- Slider / Toggle
def test_slider_at(shared_app, scratch):
    var = tk.IntVar(master=shared_app, value=0)
    sl = widgets.Slider(scratch, var, 0, 10, 1.0)
    sl.winfo_width = lambda: 200
    pad = 9
    sl._at(xy(pad + 91, 0))                      # middle of the track
    assert var.get() == 5
    sl._at(xy(pad + 91, 0))                      # same value: not written again
    assert var.get() == 5
    sl._at(xy(-100, 0))
    assert var.get() == 0
    sl._at(xy(10000, 0))
    assert var.get() == 10


def test_slider_draw(shared_app, scratch):
    var = tk.IntVar(master=shared_app, value=50)
    sl = widgets.Slider(scratch, var, 0, 100, 1.0)
    sl.winfo_width = lambda: 10                  # narrower than the knob padding: nothing drawn
    sl.draw()
    assert not sl.find_all()
    sl.winfo_width = lambda: 200
    click(shared_app, sl, "<Configure>")
    assert len(sl.find_all()) == 3
    var.set(500)                                 # out of range is clamped; the trace redraws
    assert len(sl.find_all()) == 3
    sl.winfo_width = lambda: 200
    sl.delete("all")
    sl._at(xy(50, 0))
    sl.draw()
    assert len(sl.find_all()) == 3


def test_toggle_click_and_redraw(shared_app, scratch):
    var = tk.BooleanVar(master=shared_app, value=False)
    t = widgets.Toggle(scratch, var, 1.0)
    assert t.itemcget(t.find_all()[0], "fill") == theme.LINE
    click(shared_app, t)
    assert var.get() is True
    assert t.itemcget(t.find_all()[0], "fill") == theme.ACCENT
    click(shared_app, t)
    assert var.get() is False


# ---------------------------------------------------------------- Pill / panel / field
def test_pill_plain_has_no_bindings(shared_app, scratch):
    p = widgets.Pill(scratch, "x", 1.0, hover=None)             # no cmd, no hover: purely decorative
    assert not p.bind("<Button-1>") and not p.bind("<Enter>") and not p.bind("<Leave>")
    assert str(p.cget("cursor")) == "" and texts(p) == ["x"] and not p.find_withtag("dot")
    assert p.dot_w == 0 and p.fill == p.base == theme.TILE_HI


def test_pill_cmd_and_hover(shared_app, scratch):
    hits = []
    p = widgets.Pill(scratch, "go", 1.0, cmd=lambda: hits.append(1), fill="#123456", hover="#654321")
    assert str(p.cget("cursor")) == "hand2"
    click(shared_app, p)
    assert hits == [1]
    click(shared_app, p, "<Enter>")
    assert p.fill == "#654321" and p.base == "#123456"
    click(shared_app, p, "<Leave>")
    assert p.fill == "#123456"
    rect = p.find_all()[0]
    assert p.itemcget(rect, "fill") == "#123456"               # the redraw followed the state


def test_pill_set_arguments(shared_app, scratch):
    p = widgets.Pill(scratch, "a", 1.0, fill="#111111", fg="#222222")
    p.set()                                                     # nothing given: nothing changes
    assert (p.fill, p.base, p.fg, p.text) == ("#111111", "#111111", "#222222", "a")
    p.set(fill="#333333")                                       # fill also becomes the hover-off color
    assert (p.fill, p.base, p.fg, p.text) == ("#333333", "#333333", "#222222", "a")
    p.set(fg="#444444")
    assert (p.fill, p.fg, p.text) == ("#333333", "#444444", "a")
    p.set(text="b")
    assert p.text == "b" and texts(p) == ["b"]
    p.set(text="")                                              # empty text is a value, not "missing"
    assert p.text == "" and texts(p) == [""]
    p.set("#555555", "#666666", "c")
    assert (p.fill, p.base, p.fg, p.text) == ("#555555", "#555555", "#666666", "c")
    click(shared_app, p, "<Enter>")
    p.set(fill="#777777")
    click(shared_app, p, "<Leave>")
    assert p.fill == "#777777"


def test_pill_draw_size_and_radius(shared_app, scratch):
    p = widgets.Pill(scratch, "size", 1.0, radius=6)
    h = int(p["height"])
    assert p.winfo_width() <= 1                                 # not laid out yet: uses the requested width
    p.draw()
    assert p.bbox("all")[2] <= int(p["width"]) + 1
    p.winfo_width = lambda: 400                                 # laid out wider (stretched by its cell)
    p.draw()
    assert p.bbox("all")[2] >= 398
    p.radius = 10 ** 4                                          # radius is capped at half the height
    p.draw()
    assert p.bbox("all")[3] <= h
    big = widgets.Pill(scratch, "x", 2.0, radius=3)             # scaled radius smaller than h/2
    big.draw()
    click(shared_app, big, "<Configure>")                       # <Configure> redraws
    assert texts(big) == ["x"]


def test_pill_dot_survives_redraw(shared_app, scratch):
    p = widgets.Pill(scratch, "led", 1.0, dot=True)
    assert p.dot_w == 22 and len(p.find_withtag("dot")) == 1
    assert p.itemcget("dot", "fill") == "#000000"
    p.itemconfigure("dot", fill="#abcdef")                      # what App.paint does
    p.draw()
    assert p.itemcget("dot", "fill") == "#abcdef" and p.dot_fill == "#abcdef"
    p.set(fill="#101010", fg="#ffffff", text="longer text")     # chip repaint keeps the dot color
    click(shared_app, p, "<Enter>")
    click(shared_app, p, "<Leave>")
    assert p.itemcget("dot", "fill") == "#abcdef" and len(p.find_withtag("dot")) == 1
    p.itemconfigure("dot", fill="")                             # empty fill falls back to the last known color
    p.draw()
    assert p.itemcget("dot", "fill") == "#abcdef"
    p.dot_fill = "#fedcba"                                      # paint() on a not yet drawn color
    p.dot = False
    p.draw()
    assert not p.find_withtag("dot")


def test_panel_fit_and_redraw(shared_app, scratch):
    c, inner = widgets.panel(scratch, 1.0, fill="#123456", radius=10, padx=20, pady=10)
    tk.Label(inner, text="hello world", bg="#123456").pack()
    c.pack(fill="x")
    shared_app.update()
    assert inner.master is c and not c.find_withtag("bg")        # background only appears on the canvas <Configure>
    click(shared_app, inner, "<Configure>")                     # fit: canvas takes the content size + padding
    assert int(c["width"]) == inner.winfo_reqwidth() + 40 and int(c["height"]) == inner.winfo_reqheight() + 20
    win = [i for i in c.find_all() if c.type(i) == "window"][0]
    assert c.coords(win) == [20.0, 10.0]
    c.winfo_width = lambda: 300
    c.winfo_height = lambda: 80
    click(shared_app, c, "<Configure>")                         # redraw: one rounded bg below the window, inner stretched
    bg = c.find_withtag("bg")
    assert len(bg) == 1 and c.type(bg[0]) == "polygon" and c.itemcget(bg[0], "fill") == "#123456"
    assert c.find_all()[0] == bg[0] and int(float(c.itemcget(win, "width"))) == 260
    click(shared_app, c, "<Configure>")                         # redrawing replaces, never stacks, the background
    assert len(c.find_withtag("bg")) == 1
    c.winfo_width = lambda: 10                                  # narrower than the padding: width floors at 1
    click(shared_app, c, "<Configure>")
    assert int(float(c.itemcget(win, "width"))) == 1


def test_field_is_rounded_entry(shared_app, scratch):
    var = tk.StringVar(master=shared_app, value="abc")
    e = widgets.field(scratch, var, 12, ("Monospace", 11), 1.0)
    cv = e.master
    assert isinstance(e, tk.Entry) and isinstance(cv, tk.Canvas) and cv.master is scratch
    assert e.get() == "abc" and e.cget("textvariable") == str(var)
    assert [cv.type(i) for i in cv.find_all()] == ["polygon", "window"]
    e.insert(0, "x")
    assert var.get() == "xabc"
    assert int(cv["width"]) > 12 and int(cv["height"]) > 16


# ---------------------------------------------------------------- Select
def test_select_shows_the_choice_and_its_menu_sets_the_variable(shared_app, scratch, monkeypatch):
    var = tk.StringVar(value="en")
    sel = widgets.Select(scratch, var, [("pt", "Português (Brasil)"), ("en", "English")], 1.0)
    sel.pack()
    shared_app.update()
    assert sel.text == "English  ▾"
    assert [sel.menu.entrycget(i, "label") for i in range(2)] == ["Português (Brasil)", "English"]
    sel.menu.invoke(0)
    assert var.get() == "pt" and sel.text == "Português (Brasil)  ▾"
    var.set("xx")
    assert sel.text == "xx  ▾"                                   # an unknown value is shown as is
    posted = []
    monkeypatch.setattr(sel.menu, "tk_popup", lambda x, y: posted.append((x, y)))
    click(shared_app, sel)
    assert posted == [(sel.winfo_rootx(), sel.winfo_rooty() - sel.menu.winfo_reqheight())]   # opens above it
