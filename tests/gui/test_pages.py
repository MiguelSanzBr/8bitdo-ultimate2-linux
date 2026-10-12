"""pages mixin: layout helpers, the home page, navigation and the profile chips/banner."""
import tkinter as tk

from ultimate2.gui import catalog, theme, widgets

from .conftest import cfg_with, click, slot_states, walk


# ---------------------------------------------------------------- helpers
def test_font(app):
    assert app.font(10) == (theme.FAMILY, 10, "normal")
    assert app.font(9, "bold")[2] == "bold"


def test_row(app, scratch):
    r = app.row(scratch)
    assert r.winfo_manager() == "pack"


def test_button_click_hover_and_primary(app, scratch):
    hits = []
    b = app.button(scratch, "x", lambda: hits.append(1))
    click(app, b)
    assert hits == [1]
    assert isinstance(b, widgets.Pill)
    click(app, b, "<Enter>")
    assert b.fill == theme.LINE
    click(app, b, "<Leave>")
    assert b.fill == theme.TILE_HI
    p = app.button(scratch, "p", lambda: None, primary=True)
    assert p.fill == theme.ACCENT and p.fg == theme.BG and p.hover == "#62e07a"


def test_card_variants(app, scratch):
    f1 = app.card(scratch)
    f2 = app.card(scratch, "T", side="left")
    assert isinstance(f1.master, tk.Canvas)                  # the inner frame lives in the rounded panel canvas
    assert f1.master.pack_info()["fill"] == "x" and not f1.winfo_children()
    assert f2.master.pack_info()["side"] == "left" and f2.winfo_children()[0].cget("text") == "T"


def test_slider_helper_label(app, scratch):
    var = tk.IntVar(master=app, value=3)
    app.slider(scratch, "lbl", var, 0, 10, lambda v: f"<{v}>")
    assert any(isinstance(w, widgets.Slider) for w in walk(scratch))
    var.set(7)
    vals = [w for w in walk(scratch) if isinstance(w, tk.Label) and w.cget("text").startswith("<")]
    assert vals[0].cget("text") == "<7>"
    app.slider(scratch, "default fmt", var, 0, 10)      # fmt=str default
    var.set(2)


def test_toggle_helper(app, scratch):
    var = tk.BooleanVar(master=app)
    app.toggle(scratch, "lbl", var)
    t = next(w for w in walk(scratch) if isinstance(w, widgets.Toggle))
    click(app, t)
    assert var.get()


def test_chips_click_and_paint(app, scratch):
    var = tk.StringVar(master=app, value="b")
    app.chips(scratch, var, [("a", "A"), ("b", "B"), ("c", "C")], 2)
    chips = [w for w in walk(scratch) if isinstance(w, widgets.Pill)]
    assert [c.fill for c in chips] == [theme.TILE_HI, theme.ACCENT, theme.TILE_HI]
    assert [c.fg for c in chips] == [theme.FG, theme.BG, theme.FG]
    click(app, chips[2])
    assert var.get() == "c"
    assert chips[2].fill == theme.ACCENT and chips[1].fill == theme.TILE_HI


# ---------------------------------------------------------------- pages
def test_home_tiles_click_and_hover(app):
    tiles = list(app.pages["home"].winfo_children()[-1].winfo_children())
    assert len(tiles) == len(catalog.SECTIONS)
    for t, (_, key) in zip(tiles, catalog.SECTIONS):
        click(app, t, "<Enter>")
        assert t.itemcget("bg", "fill") == theme.TILE_HI
        click(app, t, "<Leave>")
        assert t.itemcget("bg", "fill") == theme.TILE
        click(app, t)
        assert app.pages[key].winfo_manager() == "pack" and app.page == key
        assert app.pages["home"].winfo_manager() == ""


def test_back_link_and_show(app):
    app.show("sticks")
    back = next(w for w in walk(app.pages["sticks"]) if isinstance(w, widgets.Pill) and "Início" in w.text)
    click(app, back)
    assert app.pages["home"].winfo_manager() == "pack" and app.pages["sticks"].winfo_manager() == ""
    assert app.page == "home"


def test_map_choice_sets_selected_key(eapp):
    eapp.select_button("B")
    eapp.map_choice.set("RT")
    assert eapp.v["keys"]["B"].get() == "RT"


def test_reset_mapping_button(eapp):
    btns = [w for w in walk(eapp.pages["buttons"]) if isinstance(w, widgets.Pill) and "Restaurar" in w.text]
    eapp.v["keys"]["A"].set("B")
    click(eapp, btns[0])
    assert eapp.v["keys"]["A"].get() == "A"


def test_reset_slot_button(eapp):
    btn = next(w for w in walk(eapp.pages["profile"]) if isinstance(w, widgets.Pill) and "Restaurar" in w.text)
    eapp.v["keys"]["A"].set("B")
    click(eapp, btn)
    assert eapp.v["keys"]["A"].get() == "A" and "Padrões" in eapp.status.cget("text")


def test_page_widgets_follow_variables(eapp):
    sw = [w for w in walk(eapp.pages["sticks"]) if isinstance(w, widgets.Toggle)]
    assert len(sw) == 6
    eapp.v["sticks"]["left_start"].set(64)
    labels = [w.cget("text") for w in walk(eapp.pages["sticks"]) if isinstance(w, tk.Label)]
    assert "50%" in labels


# ---------------------------------------------------------------- slots
def test_slot_buttons(eapp):
    eapp.v["name"].set("changed")
    click(eapp, eapp.slot_btns[1])
    assert eapp.slot == 1
    assert eapp.doc["slots"][0]["name"] == "changed"          # gathered before switching
    assert eapp.slot_btns[1].fg == theme.ACCENT and eapp.slot_btns[1].fill == theme.TILE
    click(eapp, eapp.slot_btns[0])
    assert eapp.v["name"].get() == "changed"


def test_select_slot_variants(mk):
    a = mk(cfg_with(0))
    a.doc = None
    a.select_slot(2)                       # doc None: no gather, no load
    assert a.slot == 2
    a = mk(cfg_with(0))
    a.select_slot(1, gather=False)
    assert a.slot == 1 and a.profile_note.cget("text")


def test_refresh_slots_cases(app):
    doc = app.doc
    app.doc, app.slot = None, 0
    app.active_slot = 1
    app.refresh_slots()                                     # no doc: no banner, but chips and subtitle
    assert slot_states(app) == ("", "") and app.slot_btns[1].text == "Perfil 2  ●"
    assert app.home_sub.cget("text") == "Perfil ativo no controle: 2"
    app.doc = doc
    app.active_slot = None
    app.refresh_slots()
    assert slot_states(app) == ("", "") and app.home_sub.cget("text") == "" and "●" not in app.slot_btns[0].text
    app.active_slot = 0                                     # editing the active profile
    app.refresh_slots()
    assert slot_states(app) == ("", "") and app.slot_btns[0].fg == theme.ACCENT
    app.active_slot = 2                                     # another custom profile is active
    app.refresh_slots()
    assert slot_states(app) == ("pack", "pack")
    assert "no Perfil 3" in app.banner_text.cget("text") and "Perfil 1" in app.banner_text.cget("text")
    app.active_slot = 3                                     # default profile: no button to switch to
    app.refresh_slots()
    assert slot_states(app) == ("pack", "")
    assert "padrão" in app.banner_text.cget("text") and app.home_sub.cget("text").endswith("padrão")
    app.active_slot = 1
    app.refresh_slots()
    assert slot_states(app) == ("pack", "pack")
    click(app, app.banner_btn)                              # "Editar o perfil ativo"
    assert app.slot == 1 and app.banner.winfo_manager() == ""
