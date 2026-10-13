"""controller mixin: drawing, skins, callouts, icons, per-frame styling and the mapping highlight."""
import time
import tkinter as tk

import pytest

from ultimate2.gui import catalog, geometry, theme
from ultimate2.gui.drawing import mix

from .conftest import fire, leds_canvas, pump, px


# ---------------------------------------------------------------- drawing
def test_draw_controller_map_and_home_clicks(app):
    for cv, parts, mode in ((app.map_canvas, app.map_items, "map"), (app.home_canvas, app.home_items, "home")):
        assert set(parts) == set(geometry.PARTS) and app.ctrl[cv] == (parts, mode)
    app.show("home")
    fire(app, app.map_canvas, "b:Y")
    assert app.sel_btn == "Y" and "Y" in app.press_t and app.page == "home"
    fire(app, app.home_canvas, "b:X")
    assert app.sel_btn == "X" and "X" in app.press_t and app.page == "buttons"
    assert app.pages["buttons"].winfo_manager() == "pack"


def test_leds_canvas_dots_pick_target(app):
    cv = leds_canvas(app)
    assert len(app.led_items) == 3 and all(len(items) == 24 for _, items in app.led_items)
    canvas, item = app.swatches["single5"]
    assert canvas is cv
    fire(app, cv, item)
    pump(app)
    assert app.color_target == "single5" and app.v["theme"].get() == 4
    assert app.target_title.cget("text") == "Editando: LED 6 (personalizado)"


@pytest.mark.parametrize("text,target,page", [(c[0], c[4], "sticks" if c[4] == "sticks" else "buttons")
                                               for c in geometry.CALLOUTS])
def test_callouts_open_their_page(app, text, target, page):
    app.show("home")
    tag = "co:" + text.replace(" ", "_")
    assert " " not in tag and len(app.home_canvas.find_withtag(tag)) == 2   # a real click finds pill + label
    fire(app, app.home_canvas, tag)
    assert app.page == page
    if page == "buttons":
        assert app.sel_btn == target


def test_callout_geometry_and_modes(app):
    c = app.home_canvas
    assert len(c.find_withtag("co:LT")) == 2                             # pill + label
    assert not app.map_canvas.find_withtag("co:LT")                      # only the home drawing has callouts
    assert len(c.find_withtag("b:Up")) == 2                              # d-pad part + its arrow (see PARTS)
    right = c.bbox("co:RT")
    assert right[0] > c.bbox("co:LT")[2]


@pytest.mark.parametrize("kind", [k for _, k in catalog.SECTIONS] + ["other"])
def test_icon_kinds(app, kind, scratch):
    cv = tk.Canvas(scratch)
    app.icon(cv, kind, 50, 50)
    assert cv.find_all()


# ---------------------------------------------------------------- live state
def test_flash_and_trigger_level(app):
    app.flash("A")
    assert time.time() - app.press_t["A"] < 1
    assert app.trigger_level("A") is None
    assert app.trigger_level("LT") == 0 and app.trigger_level("RT") == 0
    app.pad_axes[2], app.pad_axes[5] = 32767, 0
    assert app.trigger_level("LT") == 1 and abs(app.trigger_level("RT") - .5) < 1e-3


def test_style_states(app):
    cv, parts = app.map_canvas, app.map_items
    now = time.time()
    app.sel_btn = "B"
    app.style(cv, parts, "map", now)
    assert parts["B"]["st"] == (theme.SEL_FILL, theme.ACCENT, theme.ACCENT)
    assert parts["Y"]["st"] == parts["Y"]["base"]          # skin colors: no constants here
    app.pad_down.add("Y")
    app.pad_axes[2] = 0                                    # LT half pressed
    app.pad_axes[5] = -32767 + 100                         # RT below the threshold
    app.style(cv, parts, "map", now)
    assert parts["Y"]["st"] == (theme.ACCENT, theme.ACCENT, theme.BG)
    lt = parts["LT"]
    assert lt["st"] == (mix(lt["base"][0], theme.ACCENT, .5), theme.ACCENT, lt["base"][2])
    assert parts["RT"]["st"] == parts["RT"]["base"]
    assert cv.itemcget(parts["Y"]["body"], "fill") == theme.ACCENT
    assert cv.itemcget(lt["body"], "fill") == lt["st"][0] != lt["base"][0]
    assert cv.itemcget(parts["L3"]["body"], "fill") == parts["L3"]["base"][0]        # L3 has no text item
    # selected highlight only exists in map mode
    app.style(app.home_canvas, app.home_items, "home", now)
    assert app.home_items["B"]["st"] == app.home_items["B"]["base"]


def test_style_badges_follow_remap(eapp):
    eapp._remapped = {"Y"}
    now = time.time()
    eapp.style(eapp.map_canvas, eapp.map_items, "map", now)
    eapp.style(leds_canvas(eapp), eapp.ctrl[leds_canvas(eapp)][0], "leds", now)
    assert eapp.map_canvas.itemcget(eapp.map_items["Y"]["badge"], "state") == "normal"
    assert eapp.map_canvas.itemcget(eapp.map_items["A"]["badge"], "state") == "hidden"
    lc = leds_canvas(eapp)
    assert lc.itemcget(eapp.ctrl[lc][0]["Y"]["badge"], "state") == "hidden"


def test_style_ripple_and_stick_motion(app):
    cv, parts = app.map_canvas, app.map_items
    app.flash("A")                                          # circle
    app.flash("LT")                                         # polygon
    app.flash("P1")                                         # rounded rectangle
    app.style(cv, parts, "map", time.time())
    assert cv.itemcget(parts["A"]["glow"], "state") == "normal" and parts["A"]["glowing"]
    assert cv.itemcget(parts["LT"]["glow"], "state") == "normal"
    assert cv.itemcget(parts["P1"]["glow"], "state") == "normal"
    gx = cv.coords(parts["LT"]["glow"])                     # poly glow: the outline scaled up around its center
    px_ = parts["LT"]["pts"]
    assert len(gx) == len(px_) and max(gx[::2]) - min(gx[::2]) > max(px_[::2]) - min(px_[::2])
    app.press_t["A"] = app.press_t["LT"] = time.time() - 5       # ripple over
    app.style(cv, parts, "map", time.time())
    assert cv.itemcget(parts["A"]["glow"], "state") == "hidden" and not parts["A"]["glowing"]
    app.style(cv, parts, "map", time.time())                # nothing glowing: stays hidden
    # stick caps follow the axes
    app.pad_axes.update({0: 32767, 1: 0, 3: 0, 4: -32767})
    before = cv.coords(parts["L3"]["body"])
    app.style(cv, parts, "map", time.time())
    assert parts["L3"]["off"][0] > 5 and parts["R3"]["off"][1] < -5
    assert cv.coords(parts["L3"]["body"])[0] > before[0]
    app.pad_axes[0] += 0
    off = parts["L3"]["off"]
    app.style(cv, parts, "map", time.time())                # same position: below the movement threshold
    assert parts["L3"]["off"] == off
    app.pad_axes.update({0: 0, 1: 0, 3: 0, 4: 0})
    app.style(cv, parts, "map", time.time())
    assert parts["L3"]["off"] == (0, 0)


def test_animate_draws_visible_canvas_only(app):
    app.apply_skin(app.skin)                                # fresh LED arcs (earlier tests animated the shared ones)
    off = theme.SKINS[app.skin]["led_off"]
    app.colors = {}
    app.page = "home"
    app.animate()                                           # no colors loaded: LED fills untouched
    _, leds = next(it for it in app.led_items if it[0] is app.home_canvas)
    assert app.home_canvas.itemcget(leds[0], "outline") == off
    app.v["theme"].set(5)
    app.colors = {"dyn_color": "#ff0000", "dyn_bg": "#0000ff", "hot_color": "#00ff00", "hot_bg": "#000000",
                  **{f"single{i}": "#123456" for i in range(24)}}
    app.page = "leds"
    app.animate()
    lc = leds_canvas(app)
    _, ledl = next(it for it in app.led_items if it[0] is lc)
    app.v["theme"].set(4)
    app.animate()
    assert lc.itemcget(ledl[0], "outline") == "#123456"
    halo = mix(theme.SKINS[app.skin]["body"][1], "#000000", .35)
    assert lc.itemcget(app.led_glow[lc][0], "outline") == mix("#123456", halo, .7)
    assert app.home_canvas.itemcget(leds[0], "outline") == off          # not visible: untouched
    app.page = "buttons"
    app.animate()
    app.page = "profile"                                    # no drawing on this page
    app.animate()
    assert app.tk.splitlist(app.tk.call("after", "info"))   # re-armed


# ---------------------------------------------------------------- mapping highlight
def test_select_button_and_refresh_mapping_without_doc(app):
    app.doc = None
    app.refresh_mapping()                  # doc None: empty defaults, nothing "changed"
    assert app.map_sub.cget("text").startswith("função atual") and not app._remapped
    assert app.map_canvas.itemcget(app.map_items["A"]["body"], "outline") == theme.ACCENT      # selected
    app.select_button("X")
    assert app.map_title.cget("text") == "Botão X"
    assert app.map_choice.get() == app.v["keys"]["X"].get()


def test_refresh_mapping_with_doc(eapp):
    eapp.v["keys"]["L3"].set("None")
    eapp.v["keys"]["Y"].set("Home")
    assert eapp._remapped == {"L3", "Y"}
    assert eapp.map_canvas.itemcget(eapp.map_items["L3"]["badge"], "state") == "normal"
    assert eapp.home_canvas.itemcget(eapp.home_items["Y"]["badge"], "state") == "normal"
    eapp.select_button("Y")
    assert eapp.map_canvas.itemcget(eapp.map_items["Y"]["text"], "fill") == theme.ACCENT      # selected text
    eapp.v["keys"]["Y"].set("Y")
    assert eapp._remapped == {"L3"}
    assert eapp.map_canvas.itemcget(eapp.map_items["Y"]["badge"], "state") == "hidden"


# ---------------------------------------------------------------- skins
@pytest.fixture
def skinned(app):
    """The shared App may be left on any skin by other tests: put it back afterwards."""
    old = app.skin
    yield app
    app.apply_skin(old)


@pytest.mark.parametrize("name", ["dark", "lilac"])
def test_apply_skin_draws_skin_colors(skinned, name):
    app, sk = skinned, theme.SKINS[name]
    app.colors = {}                                                      # else the LED swatches get repainted with the config
    app.apply_skin(name)
    assert app.skin == name
    assert app.map_items is app.ctrl[app.map_canvas][0] and app.home_items is app.ctrl[app.home_canvas][0]
    assert len(app.ctrl) == 3 and len(app.led_items) == 3 and len(app._imgs) == 3 and len(app.led_glow) == 3
    for c, (parts, mode) in app.ctrl.items():
        for pname, p in parts.items():
            assert p["base"] == sk[geometry.ROLES.get(pname, "btn")]
            shown = (theme.SEL_FILL, theme.ACCENT, theme.ACCENT) if (mode, pname) == ("map", app.sel_btn) else p["base"]
            assert p["st"] == shown                                      # refresh_mapping restyled the new items
            assert c.itemcget(p["body"], "fill") == shown[0] and c.itemcget(p["body"], "outline") == shown[1]
            if p["text"]:
                assert c.itemcget(p["text"], "fill") == shown[2]
        assert len(parts["L3"]["extra"]) == 2 and not parts["LB"]["extra"]
        assert [c.type(i) for i in parts["A"]["extra"]] == ["arc", "oval"]  # dome: lower rim shade + specular spot
        assert c.type(parts["L3"]["extra"][1]) == "arc"                 # stick cap highlight
        _, leds = next(x for x in app.led_items if x[0] is c)
        assert len(leds) == 24 and len(app.led_glow[c]) == 24
        assert {c.itemcget(i, "outline") for i in leds + app.led_glow[c]} == {sk["led_off"]}
        assert float(c.itemcget(leds[0], "width")) > float(c.itemcget(app.led_glow[c][0], "width")) * 0.4
        petals = [i for i in c.find_all() if c.type(i) == "polygon" and c.itemcget(i, "outline") == "#6e0f1d"]
        assert len(petals) == (8 if sk["emblem"] else 0)                 # flower emblem only on skins that have one
        if sk["emblem"]:
            assert {c.itemcget(i, "fill") for i in petals} == {sk["emblem"], mix(sk["emblem"], "#ffffff", .25)}
        image = [i for i in c.find_all() if c.type(i) == "image"]
        assert len(image) == 1 and app._imgs[c].width() > 0
        for n in ("LT", "RT"):                                           # triggers sit behind the body image
            assert parts[n]["shape"] == "poly" and parts[n]["body"] < image[0] < parts["A"]["body"]
        for n in ("LB", "RB"):                                           # bumpers (poly too) are drawn over it
            assert parts[n]["shape"] == "poly" and parts[n]["body"] > image[0] and len(parts[n]["pts"]) % 2 == 0
        assert parts["A"]["pts"] is None and parts["A"]["shape"] == "circle"
        img = app._imgs[c]
        assert px(img, 0, 0) is None and px(img, int(220 * app.s), int(100 * app.s))     # body filled, corner not


def test_apply_skin_keeps_interaction_and_leds_swatches(skinned):
    app = skinned
    app.apply_skin("dark")
    app.apply_skin("lilac")
    assert len(app.led_items) == 3 and sum(1 for c, _ in app.led_items if c is leds_canvas(app)) == 1
    cv = leds_canvas(app)
    canvas, item = app.swatches["single7"]
    assert canvas is cv and cv.type(item) == "arc"
    fire(app, cv, item)
    pump(app)
    assert app.color_target == "single7" and app.v["theme"].get() == 4
    fire(app, app.map_canvas, "b:Y")                                    # redrawn parts are still clickable
    assert app.sel_btn == "Y"
    fire(app, app.home_canvas, "b:X")
    assert app.sel_btn == "X" and app.page == "buttons"
    assert app.map_items["X"]["st"] == (theme.SEL_FILL, theme.ACCENT, theme.ACCENT)     # refresh_mapping restyled


def test_apply_skin_repaints_swatches_only_with_colors(skinned):
    app = skinned
    app.colors = {}
    app.apply_skin("dark")                                              # no colors loaded: arcs keep the skin's "off"
    cv = leds_canvas(app)
    canvas, item = app.swatches["single2"]
    assert canvas is cv and cv.itemcget(item, "outline") == theme.SKINS["dark"]["led_off"]
    app.colors = {"dyn_color": "#ff0000", "dyn_bg": "#0000ff", "hot_color": "#00ff00", "hot_bg": "#000000",
                  **{f"single{i}": f"#1000{i:02x}" for i in range(24)}}
    app.apply_skin("lilac")
    canvas, item = app.swatches["single2"]
    assert canvas.itemcget(item, "outline") == "#100002"
    cell, dot = app.swatches["hot_color"]
    assert cell.itemcget(dot, "fill") == "#00ff00"                       # pill dots repainted too


def test_outline_skin_draws_strokes_only(skinned):
    app = skinned
    app.colors = {}
    app.apply_skin("line")
    sk = theme.SKINS["line"]
    for c, (parts, mode) in app.ctrl.items():
        assert not [i for i in c.find_all() if c.type(i) == "image"]   # no shaded body image
        assert all(c.itemcget(p["body"], "fill") in (theme.BG, theme.SEL_FILL) for p in parts.values())
        assert not parts["A"]["extra"]                                   # no dome shading on outlines
        greys = [i for i in c.find_all() if c.type(i) == "line" and c.itemcget(i, "fill") == sk["detail"]]
        assert len(greys) == 3                                           # grip contours and the inner arch
        cross = [i for i in c.find_all() if c.type(i) == "polygon" and c.itemcget(i, "outline") == sk["line"]
                 and c.itemcget(i, "fill") == "" and len(c.coords(i)) == 24]
        assert len(cross) == 1                                           # hollow d-pad cross
    app.apply_skin("dark")
