"""drawing: colour maths, rounded shapes, gradients, LED frames."""
import tkinter as tk

from ultimate2.gui import drawing, geometry, theme

from .conftest import px


def test_color_math():
    assert drawing.mix("#000000", "#ffffff", 0) == "#000000"
    assert drawing.mix("#000000", "#ffffff", .5) == "#808080"
    assert drawing.mix("#102030", "#102030", 1) == "#102030"
    assert drawing.hsv_to_hex(0, 1, 1) == "#ff0000"
    assert drawing.hsv_to_hex(*drawing.hex_to_hsv("#4cd964")) == "#4cd964"
    assert drawing.hex_to_hsv("#000000") == (0, 0, 0)
    pts = drawing.rr_points(0, 0, 10, 20, 3)
    assert len(pts) == 24 and pts[0] == 3 and pts[-1] == 0


def test_mirror():
    assert geometry.mirror([(0, 5), (100, 7)]) == ((geometry.WIDTH, 5), (geometry.WIDTH - 100, 7))


def test_rounded(scratch):
    cv = tk.Canvas(scratch)
    item = drawing.rounded(cv, 0, 0, 20, 20, 5, fill="red")
    assert cv.type(item) == "polygon"


C = {"dyn_color": "#ff0000ff", "dyn_bg": "#0000ff", "hot_color": "#00ff00", "hot_bg": "#000000",
     **{f"single{i}": f"#0000{i:02x}" for i in range(24)}}


def test_led_frame_themes():
    assert drawing.led_frame(4, C, 5, 0)[3] == "#000003" and len(drawing.led_frame(4, C, 5, 0)) == 24
    wheel = drawing.led_frame(3, C, 5, 0)                  # head at 0: LEDs 0..2 (and 12..14) lit
    assert wheel[:3] == ["#00ff00"] * 3 and wheel[3] == "#000000" and wheel[12] == "#00ff00" and len(wheel) == 24
    dyn = drawing.led_frame(2, C, 5, 0)
    assert len(dyn) == 24 and all(len(x) == 7 for x in dyn) and dyn[0] != dyn[6]
    assert drawing.led_frame(5, C, 5, 0) == [theme.LINE] * 24
    assert drawing.led_frame(0, C, 5, 0) == [theme.LINE] * 24


def test_set_color_arc_and_other(shared_app, scratch):
    c = tk.Canvas(scratch, width=50, height=50)
    arc = c.create_arc(5, 5, 45, 45, style="arc", outline="#000000")
    oval = c.create_oval(5, 5, 45, 45, fill="#000000", outline="#111111")
    drawing.set_color(c, arc, "#ff0000")
    drawing.set_color(c, oval, "#00ff00")
    assert c.itemcget(arc, "outline") == "#ff0000" and c.itemcget(oval, "fill") == "#00ff00"
    assert c.itemcget(oval, "outline") == "#111111"                   # non-arcs keep their outline


def test_smooth_outline_shape():
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    out = drawing.smooth_outline(pts, 4)
    assert len(out) == 16 and out[0] == (0.0, 5.0)                     # starts at the midpoint of the previous edge
    assert len(drawing.smooth_outline(pts)) == 40


def test_gradient_fill_inside_and_gradient(shared_app):
    stops = ("#000000", "#808080", "#ffffff")
    img = drawing.gradient_fill(shared_app, [(2, 2), (18, 2), (18, 18), (2, 18)], 20, 20, stops)
    assert (img.width(), img.height()) == (20, 20)
    assert px(img, 0, 0) is None and px(img, 19, 19) is None and px(img, 1, 10) is None and px(img, 10, 1) is None
    top, mid, bot = px(img, 10, 2), px(img, 10, 10), px(img, 10, 17)      # last scanline of the 2..18 box is y=17
    assert top == (0, 0, 0) and bot[0] > 230 and 100 < mid[0] < 156 and px(img, 10, 18) is None
    assert top[0] < px(img, 10, 6)[0] < mid[0] < px(img, 10, 14)[0] < bot[0]     # both gradient halves


def test_gradient_fill_clipped_polygon(shared_app):
    stops = ("#ff0000", "#00ff00", "#0000ff")
    img = drawing.gradient_fill(shared_app, [(-10, -10), (30, -10), (30, 30), (-10, 30)], 20, 20, stops)
    assert px(img, 0, 0) == (255, 0, 0) and px(img, 19, 19) == (0, 0, 255)    # rows clamped to the image
    assert all(px(img, x, y) for x, y in ((0, 5), (19, 5), (0, 19)))
    img = drawing.gradient_fill(shared_app, [(10, 10), (40, 10), (40, 50), (10, 50)], 20, 20, stops)   # partly right/below
    assert px(img, 9, 15) is None and px(img, 10, 15) and px(img, 19, 19) and px(img, 19, 10)
    for pts in ([(30, 2), (40, 2), (40, 8), (30, 8)],        # right of the image
                [(2, 30), (8, 30), (8, 40), (2, 40)],        # below the image
                [(-30, 2), (-5, 2), (-5, 8), (-30, 8)]):     # left of the image
        img = drawing.gradient_fill(shared_app, pts, 20, 20, stops)
        assert not any(px(img, x, y) for x in range(20) for y in range(20))


def test_gradient_fill_degenerate_polygons(shared_app):
    stops = ("#ff0000", "#00ff00", "#0000ff")
    for pts in ([(5, 5), (5.2, 5), (5.1, 5.9)],                # sliver narrower than a pixel
                [(3, 7), (9, 7), (15, 7)],                      # zero height: no edge crosses a scanline
                [(4, 4), (4, 4), (4, 4)]):                      # single point
        img = drawing.gradient_fill(shared_app, pts, 20, 20, stops)
        assert not any(px(img, x, y) for x in range(20) for y in range(20))
    img = drawing.gradient_fill(shared_app, [(2, 2), (6, 2), (6, 3), (2, 3)], 20, 20, stops)     # one scanline tall
    assert px(img, 3, 2) == (255, 0, 0) and px(img, 3, 3) is None


def test_gradient_fill_bevel_lights_the_edges(shared_app):
    stops = ("#808080", "#808080", "#808080")
    flat = drawing.gradient_fill(shared_app, [(2, 2), (38, 2), (38, 38), (2, 38)], 40, 40, stops)
    lit = drawing.gradient_fill(shared_app, [(2, 2), (38, 2), (38, 38), (2, 38)], 40, 40, stops, bevel=8)
    assert px(flat, 20, 4) == px(flat, 20, 36) == (128, 128, 128)
    assert px(lit, 20, 4)[0] > 128 > px(lit, 20, 36)[0]               # top edge catches the light, bottom is shaded
    assert px(lit, 0, 0) is None and px(lit, 20, 20)                    # still clipped to the shape
    edge = drawing.gradient_fill(shared_app, [(-5, -5), (45, -5), (45, 45), (-5, 45)], 40, 40, stops, bevel=8)
    assert all(px(edge, x, y) for x, y in ((0, 0), (39, 39), (0, 39)))  # a shape filling the image (no outline inside)


def test_stadium_is_a_circle_when_square_and_a_capsule_otherwise():
    pts = drawing.stadium(0, 0, 20, 20)
    xy = list(zip(pts[::2], pts[1::2]))
    assert all(abs(((x - 10) ** 2 + (y - 10) ** 2) ** .5 - 10) < 1e-9 for x, y in xy)
    xy = list(zip(*[iter(drawing.stadium(0, 0, 30, 10))] * 2))
    assert min(x for x, _ in xy) == 0 and max(x for x, _ in xy) == 30
    assert min(y for _, y in xy) == 0 and max(y for _, y in xy) == 10
