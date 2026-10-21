"""i18n: language detection, the _() lookup, catalogue completeness, the language chips and the restart loop."""
import ast
import glob
import json
import os

import pytest

from ultimate2 import models
from ultimate2.gui import app as app_mod, catalog, geometry, i18n, theme, widgets

from .conftest import click, make_app, texts, walk

GUI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "ultimate2", "gui")
NEUTRAL = {"LT", "LB", "RT", "RB", "L4", "R4", "D-pad", "LEDs"}      # constant labels that read the same in English


# ---------------------------------------------------------------- detection and lookup
@pytest.mark.parametrize("env, lang", [
    ({}, "en"),
    ({"LANG": "pt_BR.UTF-8"}, "pt"),
    ({"LANG": "en_US.UTF-8"}, "en"),
    ({"LC_MESSAGES": "pt_PT", "LANG": "en_US"}, "pt"),
    ({"LC_ALL": "en_GB", "LC_MESSAGES": "pt_BR", "LANG": "pt_BR"}, "en"),
    ({"LANGUAGE": "pt_BR:en", "LC_ALL": "en_US"}, "pt"),
    ({"LANGUAGE": "en:pt_BR", "LANG": "pt_BR"}, "en"),
    ({"LANGUAGE": "", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "pt_BR"}, "pt"),
    ({"LANG": "C"}, "en"),
])
def test_system_lang(env, lang):
    assert i18n.system_lang(env) == lang


def test_system_lang_default_environ(monkeypatch):
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", "pt_BR.UTF-8")
    assert i18n.system_lang() == "pt"


def test_translate_both_languages_and_fallback(monkeypatch):
    monkeypatch.setattr(i18n, "LANG", "pt")
    assert i18n._("Recarregar") == "Recarregar"
    monkeypatch.setattr(i18n, "LANG", "en")
    assert i18n._("Recarregar") == "Reload"
    assert i18n._("texto desconhecido") == "texto desconhecido"
    assert i18n._("Perfil {}").format(2) == "Profile 2"
    assert set(i18n.LANGS) == {"pt", "en"}


# ---------------------------------------------------------------- completeness
def _literals():
    found = set()
    for path in glob.glob(os.path.join(GUI, "*.py")):
        for node in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" \
                    and isinstance(node.args[0], ast.Constant):
                found.add(node.args[0].value)
    return found


def _constants():
    """Portuguese labels of the module-level constants that are translated where they are displayed."""
    return ({t for t, _k in catalog.SECTIONS} | set(theme.THEME_NAMES.values()) | {sk["name"] for sk in theme.SKINS.values()}
            | {label for _k, label, _t in catalog.LED_TARGETS}
            | {c[0] for m in models.MODELS for c in geometry.drawing(m.key)[2]}) - NEUTRAL


def test_every_wrapped_literal_is_in_en_and_en_has_no_unused_keys():
    literals = _literals()
    assert literals and not literals - set(i18n.EN)
    assert not set(i18n.EN) - literals - _constants()
    assert _constants() <= set(i18n.EN)
    assert all(i18n.EN.values()) and all(isinstance(k, str) for k in i18n.EN)


def test_placeholders_match_between_languages():
    for pt, en in i18n.EN.items():
        assert pt.count("{}") == en.count("{}"), pt


# ---------------------------------------------------------------- settings
def test_settings_roundtrip_missing_and_broken(settings_file, monkeypatch, tmp_path):
    assert app_mod.load_settings() == {}
    app_mod.save_settings({"lang": "en"})
    assert json.load(open(settings_file)) == {"lang": "en"} and app_mod.load_settings() == {"lang": "en"}
    open(settings_file, "w").write("{not json")
    assert app_mod.load_settings() == {}
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(app_mod, "SETTINGS", str(blocker / "sub" / "gui.json"))
    app_mod.save_settings({"lang": "pt"})                # OSError is ignored
    assert app_mod.load_settings() == {}


# ---------------------------------------------------------------- language chips and restart
def _chip(app, text):
    return next(w for w in walk(app.pages["profile"]) if isinstance(w, widgets.Pill) and w.text == text)


def test_language_chips_show_both_languages_untranslated(app):
    assert {_chip(app, n).text for n in i18n.LANGS.values()} == {"Português (Brasil)", "English"}
    assert app.lang_var.get() == "pt"


def test_choosing_a_language_saves_and_restarts(app, settings_file, monkeypatch):
    app_mod.save_settings({"skin": "x"})
    destroyed = []
    monkeypatch.setattr(app, "destroy", lambda: destroyed.append(1))
    click(app, _chip(app, "Português (Brasil)"))        # same language: nothing happens
    assert not destroyed and not app.restart and app_mod.load_settings() == {"skin": "x"}
    click(app, _chip(app, "English"))
    assert destroyed == [1] and app.restart is True
    assert app_mod.load_settings() == {"skin": "x", "lang": "en"}
    app.restart = False
    app.lang_var.set("pt")


def test_main_restarts_once_then_exits(monkeypatch):
    made = []

    class Stub:
        def __init__(self):
            made.append(self)
            self.restart = len(made) == 1

        def mainloop(self):
            pass
    monkeypatch.setattr(app_mod, "App", Stub)
    app_mod.main()
    assert len(made) == 2


def test_main_exits_when_app_has_no_restart_flag(monkeypatch):
    class Bare:
        def mainloop(self):
            pass
    monkeypatch.setattr(app_mod, "App", Bare)
    app_mod.main()


# ---------------------------------------------------------------- startup language
@pytest.mark.parametrize("saved, env, expected", [
    ("en", "pt_BR", "en"), ("pt", "en_US", "pt"), (None, "pt_BR", "pt"), (None, "en_US", "en"), ("fr", "pt_BR", "pt"),
])
def test_startup_language(monkeypatch, saved, env, expected):
    monkeypatch.setenv("LANGUAGE", env)
    if saved:
        app_mod.save_settings({"lang": saved})
    a = make_app(monkeypatch)
    try:
        assert i18n.LANG == expected and a.lang_var.get() == expected
    finally:
        a.destroy()


def test_app_in_english_shows_english_texts(monkeypatch):
    app_mod.save_settings({"lang": "en"})
    a = make_app(monkeypatch)
    try:
        labels = {w.text for w in walk(a) if isinstance(w, widgets.Pill)}
        assert {"Reload", "Restore backup", "Backup", "‹  Home", "Profile 1", "Profile 2", "Edit the active profile"} <= labels
        tiles = [t for w in walk(a.pages["home"]) if w.winfo_class() == "Canvas" for t in texts(w)]
        assert {"Buttons", "Sticks", "Triggers", "Gyroscope", "Profile"} <= set(tiles)
        assert {"Left stick", "ABXY buttons", "D-pad"} <= set(texts(a.home_canvas))
        assert a.home_canvas.find_withtag("co:Botões_ABXY")            # tags still come from the Portuguese text
        titles = [w.cget("text") for p in a.pages.values() for w in walk(p) if w.winfo_class() == "Label"]
        assert "Interface language" in titles and "Selected profile" in titles and "Theme active on the controller" in titles
        a.set_status(i18n._("Alterações pendentes…"))
        assert a.status.cget("text") == "Pending changes…"
    finally:
        a.destroy()


def test_footer_selector_left_of_backup_switches_language(app, settings_file, monkeypatch):
    foot = app.status.master
    order = [getattr(w, "text", None) for w in foot.pack_slaves()]
    assert foot.pack_slaves()[0] is app.fw_label                            # firmware in the corner, rightmost
    assert order[1:5] == ["Recarregar", "Restaurar backup", "Backup", "Português (Brasil)  ▾"]   # packed right to left
    destroyed = []
    monkeypatch.setattr(app, "destroy", lambda: destroyed.append(1))
    foot.pack_slaves()[4].menu.invoke(1)
    app.update()
    assert destroyed == [1] and app.restart is True and app_mod.load_settings() == {"lang": "en"}
    app.restart = False
    app.lang_pick.set("pt")
