"""Shape of the controller drawing, in logical units inside a 440x306 box (scaled by the UI factor)."""

BODY = [(120, 44), (320, 44), (372, 52), (404, 78), (424, 140), (438, 214), (432, 256), (404, 272), (374, 262),
        (340, 212), (100, 212), (66, 262), (36, 272), (8, 256), (2, 214), (16, 140), (36, 78), (68, 52)]
WIDTH, HEIGHT = 440, 306

# shoulders seen from the front: bumpers hug the body's top corners, triggers peek out behind them
LB_PTS = ((26, 96), (34, 68), (56, 47), (92, 35), (140, 31), (158, 36), (154, 45), (120, 46), (84, 51), (58, 63),
          (42, 80), (34, 100))
LT_PTS = ((58, 46), (64, 26), (86, 11), (124, 7), (148, 15), (152, 32), (112, 36), (78, 42))


def mirror(pts):
    return tuple((WIDTH - x, y) for x, y in pts)


# name -> (shape, coords, label). shape: circle (x, y, r) | rect/rrect (x1, y1, x2, y2) | poly (points, label point)
PARTS = {
    "LT": ("poly", (LT_PTS, (112, 21)), "LT"), "RT": ("poly", (mirror(LT_PTS), (328, 21)), "RT"),
    "LB": ("poly", (LB_PTS, (106, 40)), "LB"), "RB": ("poly", (mirror(LB_PTS), (334, 40)), "RB"),
    "L3": ("circle", (112, 104, 25), ""), "R3": ("circle", (280, 164, 23), ""),
    "Up": ("rect", (158, 134, 174, 154), ""), "Down": ("rect", (158, 166, 174, 186), ""),
    "Left": ("rect", (140, 152, 160, 168), ""), "Right": ("rect", (172, 152, 192, 168), ""),
    "Y": ("circle", (332, 79, 12), "Y"), "A": ("circle", (332, 129, 12), "A"),
    "X": ("circle", (307, 104, 12), "X"), "B": ("circle", (357, 104, 12), "B"),
    "Select": ("circle", (190, 98, 7), "−"), "Start": ("circle", (250, 98, 7), "+"),
    "Home": ("circle", (220, 76, 7), ""), "Star": ("circle", (220, 124, 7), "★"),
    "P2": ("rrect", (176, 286, 210, 302), "PL"), "P1": ("rrect", (230, 286, 264, 302), "PR"),
}
BEHIND = ("LT", "RT")            # parts drawn behind the body
# button roles pick the skin colours (theme.SKINS); everything else uses "btn"
ROLES = {**dict.fromkeys(("A", "B", "X", "Y"), "face"), **dict.fromkeys(("Up", "Down", "Left", "Right"), "dpad"),
         **dict.fromkeys(("L3", "R3"), "stick"), **dict.fromkeys(("LB", "RB"), "shoulder"),
         **dict.fromkeys(("LT", "RT"), "trigger"), "Home": "home"}

# 24 RGB LEDs: 12 around each stick (index 0 at the top, clockwise; left stick first)
RINGS = [(112, 104, 30), (280, 164, 28)]
STICK_WELLS = [(112, 104, 25), (280, 164, 23)]
EMBLEM = (220, 76)               # centre of the flower emblem around Home
DPAD_CENTER = (166, 160)

# home-page callouts: label, side, label y, target point on the controller, button (or "sticks") opened on click
CALLOUTS = [("LT", "l", 18, (96, 18), "LT"), ("LB", "l", 56, (56, 52), "LB"),
            ("Analógico esquerdo", "l", 146, (80, 112), "sticks"), ("D-pad", "l", 196, (140, 160), "Up"),
            ("RT", "r", 18, (344, 18), "RT"), ("RB", "r", 56, (384, 52), "RB"),
            ("Botões ABXY", "r", 146, (370, 104), "A"), ("Analógico direito", "r", 196, (306, 172), "sticks")]
HOME_OFFSET = 160                # room for the callouts left of the drawing
