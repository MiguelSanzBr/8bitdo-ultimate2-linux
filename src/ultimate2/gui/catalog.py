"""Vocabulary of the interface: sections, remap targets, gyro keys, LED colour targets, display names."""
from .. import config

SECTIONS = [("Botões", "buttons"), ("Analógicos", "sticks"), ("Gatilhos", "triggers"), ("Vibração", "rumble"),
            ("Giroscópio", "gyro"), ("LEDs", "leds"), ("Perfil", "profile")]

# functions a button can be remapped to, in display order (P3 = L4 does not exist on this controller)
KEY_NAMES = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "L3", "R3", "Select", "Start", "Home", "Menu", "Screenshot",
             "Up", "Down", "Left", "Right", "P1", "P2", "P4", "P5", "TurboSingle", "TurboAuto",
             "LS_Up", "LS_Down", "LS_Left", "LS_Right", "RS_Up", "RS_Down", "RS_Left", "RS_Right", "None"]
assert set(KEY_NAMES) == set(config.KEYCODES.values()) - {"P3"}

# names printed on the controller for the extra buttons (app: P1 = PR, P2 = PL, P3 = L4, P4 = R4)
DISPLAY = {"P1": "PR", "P2": "PL", "P3": "L4", "P4": "R4"}

# gyro activation buttons (the app's KeyMap table, which differs from the remap codes for RT/Home)
GYRO_KEYS = {"LT": 0x4000, "RT": 0x8000, "LB": 0x400, "RB": 0x800, "L3": 0x2, "R3": 0x4}

# what the colour picker can edit: key, label, LED theme that shows it
LED_TARGETS = [("dyn_color", "Dinâmico · cor", 2), ("dyn_bg", "Dinâmico · fundo", 2),
               ("hot_color", "Roda · cor", 3), ("hot_bg", "Roda · fundo", 3), ("single_all", "Personalizado · todos", 4)]
