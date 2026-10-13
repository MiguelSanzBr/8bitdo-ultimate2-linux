"""app: construction, fonts, scaling, shutdown, the reader thread and main()."""
import tkinter as tk

from ultimate2.gui import app as app_mod, theme

from .conftest import badge, make_app, pump


def test_family_resolution(monkeypatch):
    a = make_app(monkeypatch, ["DejaVu Sans", "Inter"])
    try:
        assert theme.FAMILY == "Inter" and a.font(10)[0] == "Inter"
    finally:
        a.destroy()


def test_startup_timer_fires_read_and_pad_thread(fake, monkeypatch):
    monkeypatch.setattr(tk, "_default_root", None)   # a second Tk root must not borrow the shared app's default
    a = app_mod.App()                            # real startup: read timer, poll, animate, joystick thread
    a.withdraw()
    a.tk.willdispatch()
    try:
        pump(a, lambda: a.doc is not None and not a.busy)
        assert badge(a)[0] and a.active_slot == 0xFFFF       # blank config
    finally:
        a.destroy()
    assert a._closing


def test_construction_state_and_pages(app):
    assert set(app.pages) == {"home", "buttons", "sticks", "triggers", "rumble", "gyro", "leds", "profile"}
    assert len(app.slot_btns) == 3 and app.s >= 1.0
    assert set(app.v["keys"]) and "theme" in app.v and app.font is theme.font


def test_watch_schedules_autosave_for_every_setting_but_theme(eapp):
    eapp.v["theme"].set(3)
    assert eapp._save_job is None
    eapp.v["sticks"]["left_end"].set(100)
    assert eapp._save_job is not None




def test_main_runs_mainloop(monkeypatch):
    calls = []

    class Fake:
        def mainloop(self):
            calls.append("loop")
    monkeypatch.setattr(app_mod, "App", Fake)
    app_mod.main()
    assert calls == ["loop"]


# ---------------------------------------------------------------- drawing colour
def test_saved_drawing_colour_is_used_at_startup(monkeypatch):
    app_mod.save_settings({"skin": "lilac"})
    a = make_app(monkeypatch)
    try:
        assert a.skin == "lilac" and a.skin_pref == "lilac" and a.skin_var.get() == "lilac"
    finally:
        a.destroy()


def test_drawing_colour_choice_overrides_the_edition(app):
    assert app.skin_pref == "line" and app.edition == 3 and app.skin == "line"   # outline by default, even for pink
    assert app.skin_var.get() == "line"
    try:
        app.skin_var.set("dark")
        assert app.skin == "dark" and app_mod.load_settings() == {"skin": "dark"}
        app.skin_var.set("dark")                                       # same choice: nothing to do
        app.read_device()
        pump(app)
        assert app.skin == "dark"                                      # kept although the edition says pink
        app.skin_var.set("auto")
        assert app.skin == "lilac" and app_mod.load_settings() == {"skin": "auto"}
        app.skin_var.set("lilac")                                      # already drawn in that colour: saved only
        assert app.skin == "lilac" and app_mod.load_settings() == {"skin": "lilac"}
    finally:
        app.skin_var.set("line")
