"""Mixin: layout helpers (cards, sliders, chips…), the home page, the section pages and navigation."""
import tkinter as tk

from . import i18n, theme
from .catalog import GYRO_KEYS, KEY_NAMES_FOR, LED_TARGETS, SECTIONS
from .drawing import rounded
from .geometry import HEIGHT, HOME_OFFSET, WIDTH
from .i18n import LANGS, _
from .theme import ACCENT, BG, FG, LINE, MUTED, SKINS, THEME_NAMES, TILE, TILE_HI
from .widgets import ColorPicker, Pill, Select, Slider, Toggle, field, panel


class Pages:
    """Builds the widgets bound to ``self.v`` (see :class:`ultimate2.gui.app.App`)."""

    # ------------------------------------------------------------ helpers
    def button(self, parent, text, cmd, primary=False):
        return Pill(parent, text, self.s, cmd=cmd, fill=ACCENT if primary else TILE_HI, fg=BG if primary else FG,
                    hover="#62e07a" if primary else LINE, font=theme.font(10, "bold" if primary else "normal"))

    def card(self, parent, title=None, side=None):
        """Rounded card; returns the inner frame to fill."""
        s = self.s
        c, f = panel(parent, s)
        if side:
            c.pack(side=side, fill="both", expand=True, padx=int(6 * s), pady=int(6 * s))
        else:
            c.pack(fill="x", padx=int(6 * s), pady=int(6 * s))
        if title:
            tk.Label(f, text=title, bg=TILE, fg=FG, font=theme.font(11, "bold")).pack(anchor="w", pady=(0, int(8 * s)))
        return f

    @staticmethod
    def row(parent):
        r = tk.Frame(parent, bg=parent["bg"])
        r.pack(fill="x")
        return r

    def slider(self, parent, label, var, lo, hi, fmt=str):
        bg = parent["bg"]
        r = tk.Frame(parent, bg=bg)
        r.pack(fill="x", pady=int(5 * self.s))
        top = tk.Frame(r, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=bg, fg=MUTED, font=theme.font(9)).pack(side="left")
        val = tk.Label(top, bg=bg, fg=FG, font=theme.font(9, "bold"))
        val.pack(side="right")
        Slider(r, var, lo, hi, self.s).pack(fill="x", pady=(int(2 * self.s), 0))
        var.trace_add("write", lambda *_: val.configure(text=fmt(var.get())))

    def toggle(self, parent, label, var):
        r = tk.Frame(parent, bg=parent["bg"])
        r.pack(fill="x", pady=int(5 * self.s))
        tk.Label(r, text=label, bg=parent["bg"], fg=FG, font=theme.font(10)).pack(side="left")
        Toggle(r, var, self.s).pack(side="right")

    def chips(self, parent, var, options, cols):
        """Grid of selectable chips bound to a variable (options: list of ``(value, label)``); returns ``(grid, trace)``
        so a grid can be rebuilt."""
        s = self.s
        grid = tk.Frame(parent, bg=parent["bg"])
        grid.pack(fill="x", pady=int(4 * s))
        labels = []
        for i, (value, text) in enumerate(options):
            c = Pill(grid, text, s, cmd=lambda v=value: var.set(v), font=theme.font(9), radius=10, padx=10, pady=6)
            c.grid(row=i // cols, column=i % cols, sticky="ew", padx=int(3 * s), pady=int(3 * s))
            labels.append((value, c))
        for col in range(cols):
            grid.columnconfigure(col, weight=1)

        def paint(*_):
            for value, c in labels:
                on = str(var.get()) == str(value)
                c.set(fill=ACCENT if on else TILE_HI, fg=BG if on else FG)
        trace = var.trace_add("write", paint)
        paint()
        return grid, trace

    # ------------------------------------------------------------ pages
    def _p_home(self, parent):
        s = self.s
        page = tk.Frame(parent, bg=BG)
        self.home_title = tk.Label(page, text="Ultimate 2 Wireless", bg=BG, fg=FG, font=theme.font(18))
        self.home_title.pack(pady=(int(14 * s), 0))
        self.home_sub = tk.Label(page, text="", bg=BG, fg=MUTED, font=theme.font(10))
        self.home_sub.pack(pady=(int(2 * s), int(6 * s)))
        self.home_canvas = tk.Canvas(page, width=int((WIDTH + 2 * HOME_OFFSET) * s), height=int(HEIGHT * s), bg=BG,
                                     highlightthickness=0)
        self.home_canvas.pack()
        self.home_items = self.draw_controller(self.home_canvas, "home", ox=HOME_OFFSET)
        tk.Label(page, text=_("Aperte os botões do controle: eles acendem aqui."), bg=BG, fg=MUTED,
                 font=theme.font(8)).pack()
        self.pill = tk.Canvas(page, height=int(22 * s), bg=BG, highlightthickness=0)      # connection badge
        self.pill.pack(pady=int(8 * s))
        self.set_connected(False)
        tiles = tk.Frame(page, bg=BG)
        tiles.pack(pady=int(10 * s))
        self.tiles = {}
        for title, key in SECTIONS:
            t = tk.Canvas(tiles, width=int(104 * s), height=int(96 * s), bg=BG, highlightthickness=0, cursor="hand2")
            t.pack(side="left", padx=int(5 * s))
            self.tiles[key] = t
            rounded(t, 1, 1, 103 * s, 95 * s, 16 * s, fill=TILE, outline="", tags="bg")
            self.icon(t, key, 52, 36)
            t.create_text(52 * s, 74 * s, text=_(title), fill=FG, font=theme.font(9))
            t.bind("<Button-1>", lambda e, k=key: self.show(k))
            t.bind("<Enter>", lambda e, t=t: t.itemconfigure("bg", fill=TILE_HI))
            t.bind("<Leave>", lambda e, t=t: t.itemconfigure("bg", fill=TILE))
        return page

    def _p_buttons(self, p):
        s = self.s
        left = tk.Frame(p, bg=BG)
        left.pack(side="left", fill="y", padx=(0, int(16 * s)))
        self.map_canvas = tk.Canvas(left, width=int(WIDTH * s), height=int(HEIGHT * s), bg=BG, highlightthickness=0)
        self.map_canvas.pack(pady=int(20 * s))
        self.map_items = self.draw_controller(self.map_canvas, "map")
        self.map_help = tk.Label(left, text=self.map_help_text(), bg=BG, fg=MUTED, font=theme.font(9), justify="left")
        self.map_help.pack(anchor="w")
        right = self.card(p, side="left")
        self.map_title = tk.Label(right, bg=TILE, fg=FG, font=theme.font(13, "bold"))
        self.map_title.pack(anchor="w")
        self.map_sub = tk.Label(right, bg=TILE, fg=MUTED, font=theme.font(9))
        self.map_sub.pack(anchor="w", pady=(0, int(8 * s)))
        self.map_choice = tk.StringVar()
        self.map_choice.trace_add("write", lambda *_: self.v["keys"][self.sel_btn].get() != self.map_choice.get()
                                  and self.v["keys"][self.sel_btn].set(self.map_choice.get()))
        self.map_chips = (tk.Frame(right, bg=TILE), None)
        self.map_chips[0].pack(fill="x")
        self.build_map_chips()
        self.button(right, _("Restaurar todos os botões"), self.reset_mapping).pack(anchor="w", pady=(int(10 * s), 0))

    def build_map_chips(self):
        """The output functions the connected controller can assign (rebuilt when another model is read)."""
        holder, trace = self.map_chips
        if trace:
            self.map_choice.trace_remove("write", trace)
        for w in holder.winfo_children():
            w.destroy()
        self.map_chips = (holder, self.chips(holder, self.map_choice, [(k, self.display.get(k, k)) for k in
                                                                       KEY_NAMES_FOR[self.model.key]], 4)[1])

    def map_help_text(self):
        if "P3" not in self.model.buttons:                # no L4/R4: only the back paddles
            return _("Clique num botão do controle para escolher a função dele.\nP1/P2: botões traseiros · ★: estrela/turbo.")
        return _("Clique num botão do controle para escolher a função dele.\n"
                 "L4/R4: botões extras do ombro · PL/PR: botões traseiros · ★: estrela/turbo.")

    def _p_sticks(self, p):
        pct = lambda v: f"{v * 100 // 128}%"
        cols = self.row(p)
        for side, lbl in (("left", _("Analógico esquerdo")), ("right", _("Analógico direito"))):
            c = self.card(cols, lbl, side="left")
            self.slider(c, _("Zona morta interna"), self.v["sticks"][f"{side}_start"], 0, 128, pct)
            self.slider(c, _("Alcance externo"), self.v["sticks"][f"{side}_end"], 0, 128, pct)
        c = self.card(p, _("Opções"))
        for f, t in (("invert_LS_X", _("Inverter eixo X esquerdo")), ("invert_LS_Y", _("Inverter eixo Y esquerdo")),
                     ("invert_RS_X", _("Inverter eixo X direito")), ("invert_RS_Y", _("Inverter eixo Y direito")),
                     ("swap_sticks", _("Trocar analógicos esquerdo/direito")),
                     ("swap_LS_dpad", _("Trocar analógico esquerdo com D-pad"))):
            self.toggle(c, t, self.v["feat"][f])

    def _p_triggers(self, p):
        pct = lambda v: f"{v * 100 // 255}%"
        cols = self.row(p)
        for side, lbl in (("left", _("Gatilho LT")), ("right", _("Gatilho RT"))):
            c = self.card(cols, lbl, side="left")
            self.slider(c, _("Início (zona morta)"), self.v["triggers"][f"{side}_start"], 0, 255, pct)
            self.slider(c, _("Fim (pressão total)"), self.v["triggers"][f"{side}_end"], 0, 255, pct)
        c = self.card(p, _("Opções"))
        self.toggle(c, _("Trocar LT/RT"), self.v["feat"]["swap_triggers"])

    def _p_rumble(self, p):
        pc = lambda v: f"{v}%"
        cols = self.row(p)
        c = self.card(cols, _("Motores"), side="left")
        self.slider(c, _("Motor esquerdo"), self.v["rumble_l"], 0, 5, lambda v: f"{v * 20}%")
        self.slider(c, _("Motor direito"), self.v["rumble_r"], 0, 5, lambda v: f"{v * 20}%")
        c = self.card(cols, _("Vibração nos gatilhos"), side="left")
        self.xr_card = c.master                         # hidden for controllers without trigger rumble
        self.toggle(c, _("Ativar"), self.v["feat"]["trigger_rumble"])
        self.slider(c, _("LT início"), self.v["xr"]["left_start"], 1, 91, pc)
        self.slider(c, _("LT fim"), self.v["xr"]["left_end"], 9, 100, pc)
        self.slider(c, _("RT início"), self.v["xr"]["right_start"], 1, 91, pc)
        self.slider(c, _("RT fim"), self.v["xr"]["right_end"], 9, 100, pc)

    def _p_gyro(self, p):
        cols = self.row(p)
        c = self.card(cols, _("Giroscópio (6 eixos)"), side="left")
        self.chips(c, self.v["gyro_type"], [(0, _("Desligado")), (1, _("→ Analógico direito")), (2, _("→ Analógico esquerdo"))], 1)
        c = self.card(cols, _("Ativação"), side="left")
        self.chips(c, self.v["gyro_mode"], [(1, _("Segurar o botão")), (2, _("Apertar liga/desliga"))], 2)
        tk.Label(c, text=_("Botão de ativação"), bg=TILE, fg=MUTED, font=theme.font(9)).pack(anchor="w", pady=(int(8 * self.s), 0))
        self.chips(c, self.v["gyro_key"], [(k, k) for k in GYRO_KEYS], 3)
        c = self.card(p, _("Ajustes"))
        self.slider(c, _("Sensibilidade"), self.v["gyro_sens"], 1, 10)
        self.slider(c, _("Compensação de zona morta"), self.v["gyro_dead"], 0, 100, lambda v: f"{v}%")

    def _p_leds(self, p):
        s = self.s
        left = tk.Frame(p, bg=BG)
        left.pack(side="left", fill="y", padx=(0, int(16 * s)))
        cv = tk.Canvas(left, width=int(WIDTH * s), height=int(HEIGHT * s), bg=BG, highlightthickness=0)
        cv.pack(pady=int(10 * s))
        self.draw_controller(cv, "leds")
        tk.Label(left, text=_("Prévia ao vivo dos anéis de LED.\nClique num LED do desenho para pintar só ele."),
                 bg=BG, fg=MUTED, font=theme.font(9), justify="left").pack(anchor="w")
        right = tk.Frame(p, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        c = self.card(right, _("Tema ativo no controle"))
        self.chips(c, self.v["theme"], [(k, _(n)) for k, n in THEME_NAMES.items()], 4)
        self.v["theme"].trace_add("write", lambda *_: self.apply_theme())
        c = self.card(right, _("Cor"))
        grid = tk.Frame(c, bg=TILE)
        grid.pack(fill="x")
        self.target_labels = {}
        for i, (key, label, _t) in enumerate(LED_TARGETS):
            cell = Pill(grid, _(label), s, cmd=lambda k=key: self.pick_color(k), font=theme.font(9), radius=10,
                        padx=10, pady=7, dot=True)
            cell.grid(row=i // 3, column=i % 3, sticky="ew", padx=int(3 * s), pady=int(3 * s))
            self.swatches[key] = (cell, "dot")
            self.target_labels[key] = cell
        for col in range(3):
            grid.columnconfigure(col, weight=1)
        self.target_title = tk.Label(c, bg=TILE, fg=MUTED, font=theme.font(9))
        self.target_title.pack(anchor="w", pady=(int(8 * s), int(6 * s)))
        self.picker = ColorPicker(c, s, self.on_pick)
        self.picker.pack(anchor="w")
        self.slider(c, _("Velocidade da roda"), self.v["hot_speed"], 1, 15)

    def _p_profile(self, p):
        s = self.s
        c = self.card(p, _("Perfil selecionado"))
        r = self.row(c)
        tk.Label(r, text=_("Nome"), bg=TILE, fg=MUTED, font=theme.font(9)).pack(side="left", padx=(0, int(10 * s)))
        field(r, self.v["name"], 20, theme.font(10), s).master.pack(side="left")
        self.toggle(c, _("Perfil custom ativo neste slot"), self.v["enabled"])
        self.profile_note = tk.Label(c, bg=TILE, fg=MUTED, font=theme.font(9), wraplength=int(600 * s), justify="left")
        self.profile_note.pack(anchor="w", pady=(int(6 * s), 0))
        self.button(c, _("Restaurar padrões deste perfil"), self.reset_slot).pack(anchor="w", pady=(int(10 * s), 0))
        c = self.card(p, _("Controle"))
        self.info_label = tk.Label(c, bg=TILE, fg=MUTED, font=theme.font(9), justify="left")
        self.info_label.pack(anchor="w")
        tk.Label(c, text=_("Cor do desenho"), bg=TILE, fg=MUTED, font=theme.font(9)).pack(anchor="w", pady=(int(8 * s), 0))
        self.skin_var = tk.StringVar(value=self.skin_pref)
        Select(c, self.skin_var, [(k, _(v["name"])) for k, v in SKINS.items()] + [("auto", _("Automática (pela edição)"))],
               s, fill=TILE_HI).pack(anchor="w", pady=(int(4 * s), 0))
        self.skin_var.trace_add("write", lambda *_a: self.set_skin_pref(self.skin_var.get()))
        c = self.card(p, _("Idioma da interface"))
        self.lang_var = tk.StringVar(value=i18n.LANG)
        self.chips(c, self.lang_var, list(LANGS.items()), 2)
        self.lang_var.trace_add("write", lambda *_a: self.set_lang(self.lang_var.get()))

    # ------------------------------------------------------------ navigation
    def show(self, name):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        self.page = name

    def select_slot(self, i, gather=True):
        if gather and self.doc:
            self.gather()
        self.slot = i
        if self.doc:
            self.load()
        self.refresh_slots()

    def refresh_slots(self):
        """Profile chips (● = active on the controller) and the 'not active' banner."""
        for j, b in enumerate(self.slot_btns):
            b.set(text=_("Perfil {}").format(j + 1) + ("  ●" if j == self.active_slot else ""),
                  fill=TILE if j == self.slot else BG, fg=ACCENT if j == self.slot else MUTED)
        act = self.active_slot
        self.home_sub.configure(text="" if act is None else
                                _("Perfil ativo no controle: {}").format(_("padrão") if act not in (0, 1, 2) else act + 1))
        if self.doc is None or act is None or act == self.slot:
            self.banner.pack_forget()
            return
        where = _("no perfil padrão (sem perfil custom)") if act not in (0, 1, 2) else _("no Perfil {}").format(act + 1)
        self.banner_text.configure(text=_("O controle está {}. As mudanças do Perfil {} são salvas, "
                                          "mas só aparecem quando você ativa esse perfil no botão de perfil do controle.")
                                 .format(where, self.slot + 1))
        if act in (0, 1, 2):
            self.banner_btn.pack(side="right", padx=(int(10 * self.s), 0))
        else:
            self.banner_btn.pack_forget()
        self.banner.pack(fill="x", padx=int(24 * self.s), pady=(int(10 * self.s), 0), after=self.slot_btns[0].master)
