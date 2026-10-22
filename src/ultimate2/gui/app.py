"""The ``u2gui`` main window: state, layout skeleton and the mixins that do the work."""
import json
import os
import sys
import threading
import webbrowser
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from .. import config, device, models
from . import i18n, theme
from .catalog import DISPLAY_FOR, SECTIONS, sections
from .controller import ControllerView
from .editor import Editor
from .i18n import _
from .live_input import PadInput
from .pages import Pages
from .sync import DeviceSync
from .theme import BG, DANGER, DEFAULT_SKIN, EDITION_SKINS, FG, MUTED, SKINS, TILE, WARN
from .widgets import Pill, Select, panel

SETTINGS = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "ultimate2", "gui.json")


def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass                       # only a convenience (the interface language)


class App(Pages, ControllerView, Editor, DeviceSync, PadInput, tk.Tk):
    """Main window. ``self.v`` holds one Tk variable per editable setting of the selected slot."""

    def __init__(self):
        super().__init__()
        lang = load_settings().get("lang")
        i18n.LANG = lang if lang in i18n.LANGS else i18n.system_lang()
        self.restart = False
        self.model = models.ULTIMATE2    # replaced by the controller actually read, see set_model
        self.title("8BitDo Ultimate 2 — Linux")
        self.configure(bg=BG)
        theme.FAMILY = theme.pick_family(self)
        # UI scale from the real font size (desktop DPI/font scaling); 10pt Sans is ~15px tall at 96 dpi
        self.s = max(1.0, tkfont.Font(root=self, font=theme.font(10)).metrics("linespace") / 15)
        self.doc = None          # decoded config being edited
        self.base = None         # raw config as last read from / written to the controller
        self.slot = 0
        self.active_slot = None  # profile in use on the controller (3 = default, no custom profile)
        self.busy = False
        self.sel_btn = "A"
        self.color_target = "hot_color"
        self.theme_dev = None    # LED theme as last read from / written to the controller
        self._loading = False
        self._save_job = None
        self._retry_job = None             # pending read_device() while the controller is off
        self.led_items = []      # (canvas, [24 item ids]) for the live LED preview
        self.skin_pref = load_settings().get("skin", DEFAULT_SKIN)  # outline by default; "auto" = from the edition
        self.skin = self.skin_pref if self.skin_pref in SKINS else DEFAULT_SKIN
        self.edition = None      # last edition read from the controller
        self.led_glow = {}       # canvas -> 24 halo arcs (dimmed copy of the LED colours)
        self._imgs = {}          # canvas -> body gradient image (kept referenced)
        self.ctrl = {}           # canvas -> (parts, mode) of every controller drawing
        self.page = "home"
        self.pad_down = set()    # buttons currently held on the real controller
        self.pad_axes = {}       # js axis number -> value
        self.press_t = {}        # button -> time of the last press (ripple animation)
        self._remapped = set()
        self._closing = False
        self.conn = None         # connection badge state of the last successful read
        self.readonly = False    # Ultimate 2.4G on Bluetooth: showing the copy kept from the last cable read
        self._style()
        self._vars()
        self._build()
        w, h = int(1100 * self.s), int(800 * self.s)
        self.geometry(f"{min(w, int(self.winfo_screenwidth() * .95))}x{min(h, int(self.winfo_screenheight() * .9))}")
        self.after(200, self.read_device)
        self.after(theme.POLL_MS, self.poll)
        self.after(theme.FRAME_MS, self.animate)
        threading.Thread(target=self._read_pad, daemon=True).start()

    def set_lang(self, lang):
        """Save the chosen interface language and restart the window so every text is rebuilt in it."""
        if lang == i18n.LANG:
            return
        save_settings({**load_settings(), "lang": lang})
        self.restart = True
        self.after_idle(self.destroy)           # let the chip traces of this change finish first

    def set_skin_pref(self, pref):
        """Drawing colour chosen on the Profile page: a skin, or "auto" to follow the controller's edition."""
        if pref == self.skin_pref:
            return
        self.skin_pref = pref
        save_settings({**load_settings(), "skin": pref})
        want = pref if pref in SKINS else EDITION_SKINS.get(self.edition, DEFAULT_SKIN)
        if want != self.skin:
            self.apply_skin(want)

    @property
    def buttons(self):
        """Physical buttons of the connected controller, in ``map_key`` order."""
        return self.model.buttons

    @property
    def display(self):
        """Names printed on the controller where they differ from the internal ones."""
        return DISPLAY_FOR[self.model.key]

    def set_model(self, model):
        """Adapt the window to the controller just read (a :class:`ultimate2.models.Model`): its drawing, buttons,
        pages and cards."""
        if model == self.model:
            return
        self.model = model
        self.title(f"8BitDo {model.short_name} — Linux")
        self.home_title.configure(text=model.name)
        keep = {k for _t, k in sections(model)}
        for t in self.tiles.values():
            t.pack_forget()
        for _t, k in SECTIONS:
            if k in keep:
                self.tiles[k].pack(side="left", padx=int(5 * self.s))
        if not model.xinput_rumble:
            self.xr_card.pack_forget()
        else:
            self.xr_card.pack(side="left", fill="both", expand=True, padx=int(6 * self.s), pady=int(6 * self.s))
        self.map_help.configure(text=self.map_help_text())
        self.build_map_chips()
        if self.sel_btn not in self.buttons:
            self.sel_btn = "A"
        self.apply_skin(self.skin)

    def destroy(self):
        self._closing = True
        if self.model.knock:                     # the GUI kept the controller in config mode: give it back
            device.leave_config_mode()
        for job in self.tk.splitlist(self.tk.call("after", "info")):   # timers would outlive the window
            self.after_cancel(job)
        super().destroy()

    font = staticmethod(theme.font)

    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=FG, font=theme.font(10))
        self._style_file_dialog(st)

    def _style_file_dialog(self, st):
        """Tk's file dialog (backups) in the window's colours: it is the only user of the ttk widgets besides the
        message boxes. Its file list is a plain canvas, white with black names whatever the theme: recoloured right
        after Tk builds the dialog. Hidden files are left out, behind its "show hidden" check box."""
        edge = dict(bordercolor=theme.LINE, lightcolor=TILE, darkcolor=TILE)
        st.configure("TEntry", fieldbackground=TILE, foreground=FG, insertcolor=FG, selectbackground=theme.SEL_FILL,
                     selectforeground=FG, **edge)
        st.map("TEntry", fieldbackground=[("disabled", BG)], foreground=[("disabled", MUTED)])
        for w in ("TButton", "TMenubutton"):
            st.configure(w, background=TILE, foreground=FG, arrowcolor=FG, padding=(10, 4), **edge)
            st.map(w, background=[("disabled", BG), ("active", theme.TILE_HI)], foreground=[("disabled", MUTED)])
        st.configure("TCheckbutton", indicatorbackground=TILE, indicatorforeground=FG)
        st.map("TCheckbutton", background=[("active", BG)], indicatorbackground=[("pressed", theme.TILE_HI)])
        st.configure("TScrollbar", background=TILE, troughcolor=BG, arrowcolor=FG, gripcount=0, **edge)
        st.map("TScrollbar", background=[("active", theme.TILE_HI)])
        for k, v in (("background", TILE), ("foreground", FG), ("activeBackground", theme.TILE_HI),
                     ("activeForeground", FG), ("font", theme.font(10))):
            self.option_add(f"*TkFDialog*Menu.{k}", v)        # the directory and file type drop-downs
        self.tk.eval("auto_load ::tk::dialog::file::")
        self.tk.eval("set ::tk::dialog::file::showHiddenBtn 1; set ::tk::dialog::file::showHiddenVar 0")
        self.tk.eval(f"""proc ::u2_file_dialog {{cmd args}} {{
            set icons [lindex $cmd 1].contents.icons
            $icons.cHull.canvas configure -background {TILE} -width 5.5i -height 2.5i
            set [info object namespace $icons]::fill {FG}
        }}""")
        self.tk.eval("trace add execution ::tk::dialog::file::Create leave ::u2_file_dialog")
        self.tk.eval("""namespace eval ::tk {
            ::msgcat::mcset pt "Show &Hidden Files and Directories" "Mostrar arquivos e pastas &ocultos"
            ::msgcat::mcset pt "Show &Hidden Directories" "Mostrar pastas &ocultas"
        }""")                                             # Tk's own Portuguese catalog lacks these two

    def _vars(self):
        V, I, B = tk.StringVar, tk.IntVar, tk.BooleanVar
        side = ("left_start", "left_end", "right_start", "right_end")
        self.v = {"name": V(), "enabled": B(), "keys": {b: V() for b in config.BUTTONS},
                  "sticks": {k: I() for k in side}, "triggers": {k: I() for k in side}, "xr": {k: I() for k in side},
                  "feat": {f: B() for f in config.FEATURES.values()},
                  "rumble_l": I(), "rumble_r": I(),
                  "gyro_type": I(), "gyro_mode": I(), "gyro_sens": I(), "gyro_dead": I(), "gyro_key": V(),
                  "hot_speed": I(), "theme": I()}
        self.colors = {}
        self.swatches = {}       # colour key -> (canvas, item)

    def _watch(self):
        """Every setting change schedules an automatic save (the official app also applies changes at once)."""
        def each(node):
            for var in node.values():
                if isinstance(var, dict):
                    each(var)
                elif var is not self.v["theme"]:
                    var.trace_add("write", lambda *_, var=var: self.changed(var))
        each(self.v)

    def _build(self):
        s = self.s
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=int(24 * s), pady=(int(16 * s), 0))
        tk.Label(head, text="8BitDo Ultimate Software · Linux", bg=BG, fg=MUTED, font=theme.font(9)).pack(side="left")
        self.slot_btns = []
        for i in range(3):
            b = Pill(head, _("Perfil {}").format(i + 1) + "  ●", s, cmd=lambda i=i: self.select_slot(i), fill=BG, fg=MUTED,
                     hover=TILE, padx=14, pady=6)
            self.slot_btns.append(b)
        for b in reversed(self.slot_btns):
            b.pack(side="right", padx=2)

        self.banner, banner_in = panel(self, s, fill="#2b2618", pady=10)
        self.banner_text = tk.Label(banner_in, bg="#2b2618", fg=WARN, font=theme.font(9), anchor="w", justify="left",
                                    wraplength=int(760 * s))
        self.banner_text.pack(side="left", fill="x", expand=True)
        self.banner_btn = self.button(banner_in, _("Editar o perfil ativo"), lambda: self.select_slot(self.active_slot))
        # Ultimate 2.4G on Bluetooth only: no config channel; shows the copy kept from the last cable read
        self.btinfo, btinfo_in = panel(self, s, fill="#2b2618", pady=10)
        self.btinfo_text = tk.Label(btinfo_in, bg="#2b2618", fg=WARN, font=theme.font(9), anchor="w", justify="left",
                                    wraplength=int(900 * s))
        self.btinfo_text.pack(side="left", fill="x", expand=True)
        # Ultimate 2.4G: editing the X configuration (receiver) while the pad plays on Bluetooth (D configuration)
        self.conflict, conflict_in = panel(self, s, fill="#3a1d1d", pady=10)
        tk.Label(conflict_in, text=_("Atenção: o controle está conectado pelo Bluetooth, mas você está editando a "
                                     "configuração do modo X (receptor). O Bluetooth usa a configuração do modo D, então "
                                     "estas mudanças NÃO valem nele. Para editar o que vale no Bluetooth, desconecte o "
                                     "receptor e ligue o cabo USB com a chave em D."),
                 bg="#3a1d1d", fg=DANGER, font=theme.font(9, "bold"), anchor="w", justify="left",
                 wraplength=int(900 * s)).pack(side="left", fill="x", expand=True)

        foot = tk.Frame(self, bg=BG)
        foot.pack(side="bottom", fill="x", padx=int(24 * s), pady=int(14 * s))
        self.fw_label = tk.Label(foot, text="", bg=BG, fg=MUTED, font=theme.font(8))      # bottom-right corner
        self.fw_label.pack(side="right", padx=(int(8 * s), 0))
        for text, cmd in ((_("Recarregar"), self.read_device), (_("Restaurar backup"), self.restore), (_("Backup"), self.backup)):
            self.button(foot, text, cmd).pack(side="right", padx=int(4 * s))
        self.lang_pick = tk.StringVar(value=i18n.LANG)                 # language selector, left of Backup
        Select(foot, self.lang_pick, list(i18n.LANGS.items()), s).pack(side="right", padx=int(4 * s))
        self.lang_pick.trace_add("write", lambda *_a: self.set_lang(self.lang_pick.get()))
        self.status = tk.Label(foot, text="", bg=BG, fg=MUTED, anchor="w", font=theme.font(9))
        self.status.pack(side="left", fill="x", expand=True)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        self.pages = {"home": self._p_home(body)}
        builders = {"buttons": self._p_buttons, "sticks": self._p_sticks, "triggers": self._p_triggers,
                    "rumble": self._p_rumble, "gyro": self._p_gyro, "leds": self._p_leds, "profile": self._p_profile}
        for title, key in SECTIONS:
            page = tk.Frame(body, bg=BG)
            top = tk.Frame(page, bg=BG, height=int(46 * s))
            top.pack(fill="x", padx=int(24 * s), pady=(int(10 * s), int(6 * s)))
            back = Pill(top, _("‹  Início"), s, cmd=lambda: self.show("home"), fill=BG, fg=MUTED, hover=TILE, padx=12, pady=6)
            back.place(relx=0, rely=.5, anchor="w")
            tk.Label(top, text=_(title), bg=BG, fg=FG, font=theme.font(17)).place(relx=.5, rely=.5, anchor="center")
            inner = tk.Frame(page, bg=BG)
            inner.pack(fill="both", expand=True, padx=int(24 * s), pady=int(8 * s))
            builders[key](inner)
            self.pages[key] = page
        for var in self.v["keys"].values():
            var.trace_add("write", lambda *_: self.refresh_mapping())
        self._watch()
        self.select_slot(0, gather=False)
        self.show("home")


WEB_URL = "https://miguelsanzbr.github.io/8bitdo-ultimate2-linux/"


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["web"]:
        # the web version (WebHID) is served by this repository's GitHub Pages
        print(WEB_URL)
        webbrowser.open(WEB_URL)
        return
    while True:
        app = App()
        app.mainloop()
        if not getattr(app, "restart", False):
            break
