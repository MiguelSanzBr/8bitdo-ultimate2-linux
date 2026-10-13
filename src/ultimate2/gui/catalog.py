"""Vocabulary of the interface: sections, remap targets, gyro keys, LED colour targets, display names."""
from .. import config

SECTIONS = [("Botões", "buttons"), ("Analógicos", "sticks"), ("Gatilhos", "triggers"), ("Vibração", "rumble"),
            ("Giroscópio", "gyro"), ("LEDs", "leds"), ("Perfil", "profile")]

# functions a button can be remapped to, in display order
KEY_NAMES = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "L3", "R3", "Select", "Start", "Home", "Menu", "Screenshot",
             "Up", "Down", "Left", "Right", "P1", "P2", "P3", "P4", "P5", "TurboSingle", "TurboAuto",
             "LS_Up", "LS_Down", "LS_Left", "LS_Right", "RS_Up", "RS_Down", "RS_Left", "RS_Right", "None"]
assert set(KEY_NAMES) == set(config.KEYCODES.values())

# names printed on the controller (the app's mapping images): P1/P2 are the back paddles PR (right) and PL (left),
# P3/P4 the small shoulder buttons L4 and R4 beside LB/RB. In XInput mode they have no code of their own: they report
# the function they are mapped to (none by default)
DISPLAY = {"P1": "PR", "P2": "PL", "P3": "L4", "P4": "R4"}

# gyro activation buttons (same codes as the remap table)
GYRO_KEYS = {"LT": 0x4000, "RT": 0x8000, "LB": 0x400, "RB": 0x800, "L3": 0x2, "R3": 0x4}

# what the colour picker can edit: key, label, LED theme that shows it
LED_TARGETS = [("dyn_color", "Dinâmico · cor", 2), ("dyn_bg", "Dinâmico · fundo", 2),
               ("hot_color", "Roda · cor", 3), ("hot_bg", "Roda · fundo", 3), ("single_all", "Personalizado · todos", 4)]
