"""Shape of the controller drawing, in logical units inside a 440x330 box (scaled by the UI factor).

The outline and the button centres were traced from the silhouette (alpha channel only) of the official front
render with ``tools/trace_silhouette.py``, scaled to 440 units wide and moved 18 units down so the triggers fit above.
"""

BODY = [(105, 18), (132, 20), (138, 26), (171, 24), (301, 26), (305, 21), (310, 19), (340, 18), (368, 25), (395, 43),
        (396, 52), (406, 60), (417, 82), (428, 128), (439, 227), (439, 260), (435, 285), (428, 301), (418, 313),
        (403, 321), (388, 326), (367, 304), (333, 248), (320, 235), (299, 229), (131, 230), (120, 234), (111, 241),
        (74, 303), (52, 326), (49, 326), (29, 318), (15, 306), (7, 293), (2, 275), (0, 229), (10, 136), (20, 88),
        (30, 66), (36, 57), (44, 52), (44, 43), (49, 39), (75, 24)]
WIDTH, HEIGHT = 440, 330

# shoulders seen from the front: bumpers are the body's top corners, triggers peek out behind them
LB_PTS = ((44, 48), (44, 43), (49, 39), (75, 24), (105, 18), (132, 20), (138, 26), (112, 28), (82, 33), (60, 40))
LT_PTS = ((52, 36), (62, 22), (84, 8), (116, 3), (140, 8), (146, 22), (120, 22), (80, 26))

# L4: a small curved tab sitting on the body's top edge against the inner end of LT; it rises along LT's curve and
# slopes down towards the centre (a doubled point keeps a sharp corner in Tk's smoothed polygons)
L4_PTS = ((138, 26), (138, 26), (139, 17), (145, 11), (154, 11), (162, 15), (167, 21), (169, 26), (169, 26))


def mirror(pts):
    return tuple((WIDTH - x, y) for x, y in pts)


DPAD_CENTER = (159, 175)
DPAD_ARM, DPAD_HALF = 38, 14     # d-pad cross: arm length and half width
DPAD_DIRS = {"Up": (0, -1), "Right": (1, 0), "Down": (0, 1), "Left": (-1, 0)}


def _dpad(pts, dx, dy):
    """Rotate points drawn for the Up arm towards (dx, dy) and move them onto the d-pad centre."""
    cx, cy = DPAD_CENTER
    return tuple((cx - y * dx - x * dy, cy + x * dx - y * dy) for x, y in pts)


# one arm, and the whole cross, as smoothed polygons: the doubled inner corners stay sharp, the ends come out round
_A, _H = DPAD_ARM, DPAD_HALF
DPAD_ARMS = {n: _dpad(((-_H, -_H), (-_H, -_H), (-_H, -_A), (_H, -_A), (_H, -_H), (_H, -_H)), *d)
             for n, d in DPAD_DIRS.items()}
DPAD_CROSS = tuple(p for d in DPAD_DIRS.values() for p in _dpad(((-_H, -_A), (_H, -_A), (_H, -_H), (_H, -_H)), *d))

# name -> (shape, coords, label). shape: circle (x, y, r) | rect/rrect (x1, y1, x2, y2) | poly (points, label point)
PARTS = {
    "LT": ("poly", (LT_PTS, (112, 13)), "LT"), "RT": ("poly", (mirror(LT_PTS), (328, 13)), "RT"),
    "LB": ("poly", (LB_PTS, (96, 27)), "LB"), "RB": ("poly", (mirror(LB_PTS), (344, 27)), "RB"),
    "L3": ("circle", (93, 106, 32), ""), "R3": ("circle", (281, 177, 32), ""),
    **{n: ("poly", (DPAD_ARMS[n], (DPAD_CENTER[0] + 26 * d[0], DPAD_CENTER[1] + 26 * d[1])), "")
       for n, d in DPAD_DIRS.items()},
    "Y": ("circle", (347, 73, 15), "Y"), "A": ("circle", (347, 136, 15), "A"),
    "X": ("circle", (316, 104, 15), "X"), "B": ("circle", (379, 104, 15), "B"),
    "Select": ("circle", (162, 67, 10), "−"), "Start": ("circle", (277, 67, 10), "+"),
    "Home": ("circle", (220, 67, 14), ""), "Star": ("circle", (250, 99, 10), "★"),
    "P3": ("poly", (L4_PTS, (152, 19)), "L4"), "P4": ("poly", (mirror(L4_PTS), (288, 19)), "R4"),   # shoulder extras
    "P2": ("rrect", (176, 300, 210, 316), "PL"), "P1": ("rrect", (230, 300, 264, 316), "PR"),   # back paddles
}
# parts of the face that are not configurable, drawn fully rounded (x1, y1, x2, y2): round button, profile button,
# centre dot, player LEDs; DECOR_SQUARE is the square drawn in the middle of the round button
DECOR = [(180, 89, 200, 109), (207, 113, 233, 125), (219, 98, 221, 100), *((219, y - 1, 221, y + 1) for y in (147, 156, 165))]
DECOR_SQUARE = (186, 95, 194, 103)
# pixel-art heart drawn in the middle of Home (11x9 cells of HEART_PX units)
HEART = ["..XX...XX..", ".X..X.X..X.", "X....X....X", "X.........X", ".X.......X.", "..X.....X..", "...X...X...",
         "....X.X....", ".....X....."]
HEART_PX = 1.8
BEHIND = ("LT", "RT")            # parts drawn behind the body
# button roles pick the skin colours (theme.SKINS); everything else uses "btn"
ROLES = {**dict.fromkeys(("A", "B", "X", "Y"), "face"), **dict.fromkeys(("Up", "Down", "Left", "Right"), "dpad"),
         **dict.fromkeys(("L3", "R3"), "stick"), **dict.fromkeys(("LB", "RB", "P3", "P4"), "shoulder"),
         **dict.fromkeys(("LT", "RT"), "trigger"), "Home": "home"}

# 24 RGB LEDs: 12 around each stick (index 0 at the top, clockwise; left stick first)
RINGS = [(93, 106, 37), (281, 177, 37)]
STICK_WELLS = [(93, 106, 32), (281, 177, 32)]

# outline style: grip contours and the arch inside the grips
DETAILS = [((60, 168), (36, 233), (26, 280), (34, 318)), ((380, 168), (404, 233), (414, 280), (406, 318)),
           ((84, 306), (118, 250), (136, 240), (304, 240), (322, 250), (356, 306))]

# home-page callouts: label, side, label y, target point on the controller, button (or "sticks") opened on click
CALLOUTS = [("LT", "l", 13, (96, 12), "LT"), ("L4", "l", 36, (142, 21), "P3"), ("LB", "l", 59, (54, 42), "LB"),
            ("Analógico esquerdo", "l", 106, (61, 106), "sticks"), ("D-pad", "l", 175, (121, 175), "Up"),
            ("RT", "r", 13, (344, 12), "RT"), ("R4", "r", 36, (298, 21), "P4"), ("RB", "r", 59, (386, 42), "RB"),
            ("Botões ABXY", "r", 104, (394, 104), "A"), ("Analógico direito", "r", 177, (313, 177), "sticks"),
            ("Traseiros PL / PR", "r", 308, (264, 308), "P1")]
HOME_OFFSET = 160                # room for the callouts left of the drawing


def drawing(key):
    """``(parts, rings, callouts)`` of the drawing for the model ``key``: the Ultimate 2, or the 1st-gen Ultimate
    Bluetooth (Nintendo face layout: A right, B bottom, X top, Y left; no L4/R4, no LED rings, back paddles P1/P2)."""
    if key == "ultimate2":
        return PARTS, RINGS, CALLOUTS
    xy = {n: PARTS[n][1] for n in "ABXY"}
    parts = {n: p for n, p in PARTS.items() if n not in ("P3", "P4")}
    parts.update({"A": ("circle", xy["B"], "A"), "B": ("circle", xy["A"], "B"), "X": ("circle", xy["Y"], "X"),
                  "Y": ("circle", xy["X"], "Y"), "P2": ("rrect", PARTS["P2"][1], "P2"), "P1": ("rrect", PARTS["P1"][1], "P1")})
    callouts = [("Traseiros P1 / P2", *c[1:]) if c[4] == "P1" else c for c in CALLOUTS if c[4] not in ("P3", "P4")]
    return parts, [], callouts
