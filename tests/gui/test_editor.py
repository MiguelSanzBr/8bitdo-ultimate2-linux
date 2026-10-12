"""editor mixin: config dict <-> widget variables, LED colour targets, resets."""
import pytest

from ultimate2 import config
from ultimate2.gui import catalog, theme, widgets

from .conftest import cfg_with, click, pump


# ---------------------------------------------------------------- load
def test_load_fresh_controller(mk):
    app = mk()                          # cfg all 0xFF
    v = app.v
    assert not v["enabled"].get() and v["name"].get() == "Perfil 1"
    assert "vazio" in app.profile_note.cget("text")
    assert v["rumble_l"].get() == 5 and v["gyro_type"].get() == 0 and v["gyro_mode"].get() == 1
    assert v["gyro_sens"].get() == 10 and v["gyro_dead"].get() == 40 and v["gyro_key"].get() == "RT"
    assert v["keys"]["A"].get() == "A"
    assert app.colors["dyn_color"] == "#260032"
    assert app._loading is False and app._save_job is None      # loading never schedules a save


def test_load_enabled_custom_values(mk):
    def edit(s):
        s["name"] = "Meu"
        s["mapping"]["A"] = "0xdeadbeef"           # not in KEY_NAMES -> default
        s["mapping"]["B"] = "X"
        s["special"]["features"] = ["invert_LS_X", "swap_triggers", "0x00000020"]
        s["rumble"] = dict(flag="enabled", left=0.4, right=0.0)
        s["sixaxis"] = dict(s["sixaxis"], flag="enabled", mapping_type=2, trigger_mode=2,
                            keys_map="0x00004000", sensitivity=4, dead_compensate=30)
        s["sticks"]["left_start"] = 40
        s["led_dynamic"]["color"] = "#010203"
        s["led_single"]["colors"][3] = "#aabbcc"
        s["led_hotwheel"]["speed"] = 3
    a = mk(cfg_with(0, edit))
    v = a.v
    assert v["enabled"].get() and v["name"].get() == "Meu"
    assert v["keys"]["A"].get() == "A" and v["keys"]["B"].get() == "X"
    assert v["feat"]["invert_LS_X"].get() and v["feat"]["swap_triggers"].get() and not v["feat"]["swap_sticks"].get()
    assert v["rumble_l"].get() == 2 and v["rumble_r"].get() == 0
    assert (v["gyro_type"].get(), v["gyro_mode"].get(), v["gyro_key"].get(), v["gyro_sens"].get(), v["gyro_dead"].get()) == (2, 2, "LT", 4, 30)
    assert v["sticks"]["left_start"].get() == 40
    assert a.colors["dyn_color"] == "#010203" and a.colors["single3"] == "#aabbcc" and v["hot_speed"].get() == 3
    assert a.profile_note.cget("text") == ""
    assert a.swatches["dyn_color"][0].itemcget(a.swatches["dyn_color"][1], "fill") == "#010203"


def test_load_disabled_sections_and_odd_values(mk):
    def edit(s):
        for k in ("sticks", "triggers", "xinput_rumble", "led_dynamic", "led_hotwheel", "led_single"):
            s[k]["flag"] = "disabled"
        s["sticks"]["left_start"] = 99
        s["sixaxis"] = dict(s["sixaxis"], flag="enabled", mapping_type=1, trigger_mode=0, keys_map="0x00000001")
        s["sixaxis"]["sensitivity"] = 0
        s["sixaxis"]["dead_compensate"] = 200
    a = mk(cfg_with(0, edit))
    assert a.v["sticks"]["left_start"].get() == 17          # default, not 99
    assert a.v["gyro_type"].get() == 1 and a.v["gyro_mode"].get() == 1
    assert a.v["gyro_key"].get() == "RT" and a.v["gyro_sens"].get() == 1 and a.v["gyro_dead"].get() == 100
    assert a.colors["dyn_color"] == "#260032"


def test_load_sixaxis_enabled_but_type_out_of_range(mk):
    a = mk(cfg_with(0, lambda s: s.update(sixaxis=dict(s["sixaxis"], flag="enabled", mapping_type=7))))
    assert a.v["gyro_type"].get() == 0


def test_load_with_explicit_slot_dict(eapp):
    eapp.load(eapp._defaults(0))
    assert eapp.v["name"].get() == "Perfil 1"


# ---------------------------------------------------------------- gather
def test_gather_disabled_slot_enabled_goes_off(eapp):
    eapp.v["enabled"].set(False)
    eapp.gather()
    assert eapp.doc["slots"][0]["flag"] == "off"


def test_gather_disabled_slot_not_enabled_noop(app):
    before = repr(app.doc["slots"][0])
    app.gather()
    assert repr(app.doc["slots"][0]) == before


def test_gather_empty_slot_defaults_path(app):
    app.v["enabled"].set(True)
    app.v["name"].set("x" * 30)
    app.v["gyro_type"].set(1)
    app.v["gyro_key"].set("LB")
    app.v["rumble_l"].set(5)
    app.gather()
    s = app.doc["slots"][0]
    assert s["flag"] == "enabled" and s["name"] == "x" * 16
    assert s["sixaxis"]["flag"] == "enabled" and s["sixaxis"]["keys_map"] == "0x00000400" and s["sixaxis"]["mapping_type"] == 1
    assert s["rumble"]["left"] == 1.0
    assert s["led_single"]["colors"][0] == app.colors["single0"]


def test_gather_enabled_slot_keeps_unknown_features_and_gyro_off(mk):
    a = mk(cfg_with(0, lambda s: s["special"].update(features=["invert_LS_Y", "0x00000020"])))
    a.v["feat"]["swap_sticks"].set(True)
    a.v["gyro_type"].set(0)
    a.gather()
    s = a.doc["slots"][0]
    assert sorted(s["special"]["features"]) == sorted(["0x00000020", "invert_LS_Y", "swap_sticks"])
    assert s["sixaxis"]["flag"] == "disabled" and s["sixaxis"]["mapping_type"] == 0


# ---------------------------------------------------------------- LED colors
def test_color_of_paint_and_missing(app):
    app.colors["hot_bg"] = "#123456ff"
    app.paint("hot_bg")
    cv, item = app.swatches["hot_bg"]
    assert cv.itemcget(item, "fill") == "#123456" and app._color_of("hot_bg") == "#123456"
    app.colors["single0"] = "#abcdef"
    assert app._color_of("single_all") == "#abcdef"
    app.colors.pop("hot_bg")
    assert app._color_of("hot_bg") == "#000000"
    app.paint("hot_bg")
    assert cv.itemcget(item, "fill") == "#000000"


def test_paint_stores_dot_color_on_pills(app):
    app.colors["dyn_bg"] = "#123456ff"
    app.paint("dyn_bg")
    cell, item = app.swatches["dyn_bg"]
    assert item == "dot" and cell.dot_fill == "#123456" and cell.itemcget("dot", "fill") == "#123456"
    app.refresh_targets()                                       # set(...) redraws without losing it
    assert cell.itemcget("dot", "fill") == "#123456"
    cv, it = app.swatches["single3"]                            # plain canvas swatch: no dot_fill involved
    app.paint("single3")
    assert not isinstance(cv, widgets.Pill) and cv.type(it) == "arc"      # LED swatches are arcs, colored by outline
    app.colors["single3"] = "#abcdef"
    app.paint("single3")
    assert cv.itemcget(it, "outline") == "#abcdef"


@pytest.mark.parametrize("key,led_theme", [("dyn_color", 2), ("dyn_bg", 2), ("hot_color", 3), ("hot_bg", 3),
                                           ("single_all", 4), ("single7", 4)])
def test_pick_color_selects_target_and_theme(app, fake, key, led_theme):
    app.colors["dyn_bg"] = "#102030"
    app.pick_color(key)
    pump(app)
    assert app.color_target == key and app.v["theme"].get() == led_theme and fake.theme == led_theme
    assert app.picker.color() == app._color_of(key)
    label = next((l for k, l, _ in catalog.LED_TARGETS if k == key), "LED 8 (personalizado)")
    assert app.target_title.cget("text") == f"Editando: {label}"
    for k, cell in app.target_labels.items():       # only the selected target is highlighted
        assert (cell.fill == theme.LINE) == (k == key) and (cell.fg == theme.ACCENT) == (k == key)


def test_pick_color_target_cells_click(app):
    cell = app.target_labels["dyn_bg"]
    assert isinstance(cell, widgets.Pill) and app.swatches["dyn_bg"] == (cell, "dot")
    click(app, cell)
    pump(app)
    assert app.color_target == "dyn_bg" and app.v["theme"].get() == 2
    click(app, app.target_labels["hot_color"])
    assert app.color_target == "hot_color"


def test_on_pick_single_target_and_all(eapp, fast):
    eapp.pick_color("hot_bg")
    eapp.on_pick("#112233")
    assert eapp.colors["hot_bg"] == "#112233" and eapp.colors["hot_color"] != "#112233"
    assert eapp.swatches["hot_bg"][0].itemcget(eapp.swatches["hot_bg"][1], "fill") == "#112233"
    eapp.pick_color("single_all")
    eapp.on_pick("#445566")
    assert all(eapp.colors[f"single{i}"] == "#445566" for i in range(24))
    cv, item = eapp.swatches["single_all"]
    assert cv.itemcget(item, "fill") == "#445566"
    pump(eapp, lambda: "Salvo" in eapp.status.cget("text") and not eapp.busy)


def test_color_picker_to_controller(eapp, fake, fast):
    eapp.pick_color("single3")
    pump(eapp)
    eapp.picker.choose("#ff0000")
    pump(eapp, lambda: "Salvo" in eapp.status.cget("text") and not eapp.busy)
    doc = config.decode(bytes(fake.cfg))
    assert doc["slots"][0]["led_single"]["colors"][3].startswith("#ff0000")


# ---------------------------------------------------------------- resets
def test_reset_slot(mk):
    a = mk(cfg_with(0))
    a.doc = None
    a.reset_slot()                         # doc None: no-op
    assert "Padrões" not in a.status.cget("text")
    a = mk(cfg_with(0))
    a.v["keys"]["A"].set("B")
    a.reset_slot()
    assert a.v["keys"]["A"].get() == "A" and a.v["enabled"].get()
    assert "Padrões" in a.status.cget("text") or "pendentes" in a.status.cget("text")


def test_reset_mapping(mk):
    a = mk(cfg_with(0))
    a.doc = None
    a.v["keys"]["A"].set("B")
    a.reset_mapping()                      # doc None: no-op
    assert a.v["keys"]["A"].get() == "B"
    a = mk(cfg_with(0))
    a.v["keys"]["A"].set("B")
    a.reset_mapping()
    assert a.v["keys"]["A"].get() == "A"
