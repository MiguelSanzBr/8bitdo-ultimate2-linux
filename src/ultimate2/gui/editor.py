"""Mixin: moves values between the decoded config (``self.doc``) and the widget variables (``self.v``)."""
import copy

from .. import config
from .catalog import GYRO_KEYS, KEY_NAMES, LED_TARGETS
from .drawing import set_color
from .i18n import _
from .theme import ACCENT, FG, LINE, TILE_HI
from .widgets import Pill


class Editor:
    def _defaults(self, n):
        """Slot ``n`` as the Windows app would create it."""
        return config.default_slot(copy.deepcopy(self.doc), n, _("Perfil {}").format(n + 1))["slots"][n]

    def load(self, s=None):
        """Show slot ``self.slot`` (or the given slot dict) in the widgets without triggering auto-save."""
        self._loading = True
        try:
            self._load(s)
        finally:
            self._loading = False

    def _load(self, s):
        n = self.slot
        cur = self.doc["slots"][n]
        enabled = cur["flag"] == "enabled"
        s = s or (cur if enabled else self._defaults(n))
        v = self.v
        v["name"].set(s["name"] or _("Perfil {}").format(n + 1))
        v["enabled"].set(enabled)
        self.profile_note.configure(text="" if enabled else
                                    _("Este perfil está vazio: os valores são os padrões do app. Ele é criado assim que você mudar algo."))
        dflt = self._defaults(n)
        for b in self.buttons:
            k = s["mapping"].get(b)
            v["keys"][b].set(k if k in KEY_NAMES else dflt["mapping"][b])
        for sec, key in (("sticks", "sticks"), ("triggers", "triggers"), ("xr", "xinput_rumble")):
            if key not in s:                  # the Ultimate Bluetooth has no trigger rumble, gyro or LEDs
                continue
            for k, var in v[sec].items():
                var.set(s[key][k] if s[key]["flag"] == "enabled" else dflt[key][k])
        feats = s["special"]["features"] if isinstance(s["special"]["features"], list) else []
        for f, var in v["feat"].items():
            var.set(f in feats)
        for side in ("left", "right"):
            x = s["rumble"][side]
            v[f"rumble_{side[0]}"].set(round((x if x is not None else 1.0) * 5))
        if "sixaxis" not in s:
            self.colors = {}
            self.refresh_targets()
            self.select_button(self.sel_btn)
            return
        g = s["sixaxis"]
        v["gyro_type"].set(g["mapping_type"] if g["flag"] == "enabled" and g["mapping_type"] in (1, 2) else 0)
        v["gyro_mode"].set(g["trigger_mode"] if g["trigger_mode"] in (1, 2) else 1)
        v["gyro_sens"].set(min(max(g["sensitivity"], 1), 10))
        v["gyro_dead"].set(min(g["dead_compensate"], 100))
        km = int(g["keys_map"], 16)
        v["gyro_key"].set(next((k for k, c in GYRO_KEYS.items() if c == km), "RT"))
        led = lambda sec, k: s[sec][k] if s[sec]["flag"] == "enabled" else dflt[sec][k]
        self.colors = {"dyn_color": led("led_dynamic", "color"), "dyn_bg": led("led_dynamic", "bg_color"),
                       "hot_color": led("led_hotwheel", "color"), "hot_bg": led("led_hotwheel", "bg_color")}
        self.colors.update({f"single{i}": c for i, c in enumerate(led("led_single", "colors"))})
        v["hot_speed"].set(min(max(led("led_hotwheel", "speed"), 1), 15))
        for k in self.swatches:
            self.paint(k)
        self.picker.set(self._color_of(self.color_target))
        self.refresh_targets()
        self.select_button(self.sel_btn)

    def gather(self):
        """Write widget values into ``self.doc`` for the current slot (mirrors the app's ``saveCurrentConfig``)."""
        n, v = self.slot, self.v
        cur = self.doc["slots"][n]
        if not v["enabled"].get():
            if cur["flag"] == "enabled":
                cur["flag"] = "off"           # app's delete path sets the slot flag to 0
            return
        s = copy.deepcopy(cur) if cur["flag"] == "enabled" else self._defaults(n)
        on = "enabled"
        s["flag"] = on
        s["name"] = v["name"].get()[:16]
        s["mapping"] = dict(flag=on, **{b: v["keys"][b].get() for b in self.buttons})
        for sec, key in (("sticks", "sticks"), ("triggers", "triggers"), ("xr", "xinput_rumble")):
            if key in s:
                s[key] = dict(flag=on, **{k: var.get() for k, var in v[sec].items()})
        old = s["special"]["features"] if isinstance(s["special"]["features"], list) else []
        keep = [f for f in old if f not in config.FEATURES.values()]       # unknown bits survive untouched
        s["special"] = dict(flag=on, features=keep + [f for f, var in v["feat"].items() if var.get()])
        s["rumble"] = dict(flag=on, left=v["rumble_l"].get() / 5, right=v["rumble_r"].get() / 5)
        if "sixaxis" not in s:
            self.doc["slots"][n] = s
            return
        t = v["gyro_type"].get()
        s["sixaxis"] = dict(flag=on if t else "disabled", keys_map=f"0x{GYRO_KEYS[v['gyro_key'].get()]:08x}",
                            trigger_mode=v["gyro_mode"].get(), sensitivity=v["gyro_sens"].get(),
                            dead_compensate=v["gyro_dead"].get(), mapping_type=t)
        c = self.colors
        s["led_dynamic"] = dict(flag=on, color=c["dyn_color"], bg_color=c["dyn_bg"])
        s["led_hotwheel"] = dict(flag=on, color=c["hot_color"], bg_color=c["hot_bg"], speed=v["hot_speed"].get())
        s["led_single"] = dict(flag=on, colors=[c[f"single{i}"] for i in range(24)])
        self.doc["slots"][n] = s

    # ------------------------------------------------------------ LED colours
    def _color_of(self, key):
        return self.colors.get("single0" if key == "single_all" else key, "#000000")[:7]

    def paint(self, key):
        canvas, item = self.swatches[key]
        set_color(canvas, item, self._color_of(key))
        if isinstance(canvas, Pill):
            canvas.dot_fill = self._color_of(key)

    def pick_color(self, key):
        """Choose what the colour picker edits; switch the controller to the LED theme that shows it."""
        self.color_target = key
        led_theme = 4 if key.startswith("single") else next(t for k, _l, t in LED_TARGETS if k == key)
        self.v["theme"].set(led_theme)
        self.picker.set(self._color_of(key))
        self.refresh_targets()

    def refresh_targets(self):
        key = self.color_target
        for k, cell in self.target_labels.items():
            on = k == key
            cell.set(fill=LINE if on else TILE_HI, fg=ACCENT if on else FG)
        label = next((_(l) for k, l, _t in LED_TARGETS if k == key), None) or _("LED {} (personalizado)").format(int(key[6:]) + 1)
        self.target_title.configure(text=_("Editando: {}").format(label))

    def on_pick(self, color):
        keys = [f"single{i}" for i in range(24)] if self.color_target == "single_all" else [self.color_target]
        for k in keys:
            self.colors[k] = color
            self.paint(k)
        self.paint("single_all")
        self.changed()

    # ------------------------------------------------------------ resets
    def reset_slot(self):
        if not self.doc:
            return
        self.load(self._defaults(self.slot))
        self.v["enabled"].set(True)
        self.set_status(_("Padrões restaurados."))

    def reset_mapping(self):
        if not self.doc:
            return
        for b, k in self._defaults(self.slot)["mapping"].items():
            if b in self.v["keys"]:
                self.v["keys"][b].set(k)
        self.select_button(self.sel_btn)
