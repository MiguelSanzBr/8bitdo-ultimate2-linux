"""Shared fixtures and helpers of the GUI tests. They need a real X display and the in-process FakeController."""
import re
import time
import tkinter as tk
from types import SimpleNamespace

import pytest

from conftest import BLANK_CONFIG
from ultimate2 import config, device
from ultimate2.gui import app as app_mod, sync, theme

BACKUP = open(BLANK_CONFIG, "rb").read()


# ---------------------------------------------------------------- helpers
def cfg_with(slot=0, edit=None, mode=None, name="Perfil X"):
    """Config bytes with `slot` turned into an enabled custom profile (app defaults), optionally edited."""
    doc = config.decode(BACKUP)
    if mode is not None:
        doc["gamepad_mode"] = mode
    config.default_slot(doc, slot, name)
    if edit:
        edit(doc["slots"][slot])
    return config.encode(doc, BACKUP)[0]


def pump(app, cond=None, timeout=5.0):
    """Run the Tk event loop until cond() (default: worker finished and its after-callbacks ran)."""
    cond = cond or (lambda: not app.busy)
    end = time.time() + timeout
    while time.time() < end:
        app.update()
        if cond():
            app.update()
            return
        time.sleep(0.003)
    raise AssertionError("pump timeout")


def fire(app, widget, tag, seq="<Button-1>"):
    """Invoke the Python callback bound to a canvas item tag (hit-testing needs a mapped window)."""
    script = widget.tag_bind(tag, seq)
    app.tk.eval(re.sub(r"%.", "0", script))
    app.update()


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def click(app, w, seq="<Button-1>"):
    """Run the handler bound to `seq` (event_generate does not reach widgets of a withdrawn window)."""
    app.tk.eval(re.sub(r"%.", "0", w.bind(seq)))
    app.update()


def clear_timers(a):
    """Cancel every pending after() timer (debounced saves, polls, retries) and the autosave job."""
    for i in a.tk.splitlist(a.tk.call("after", "info")):
        a.after_cancel(i)
    a._save_job = None


def xy(x, y):
    return SimpleNamespace(x=x, y=y)


def px(img, x, y):
    """RGB of a PhotoImage pixel, or None if transparent."""
    return None if img.transparency_get(x, y) else tuple(img.get(x, y))


def texts(cv):
    return [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]


def leds_canvas(app):
    return next(c for c, (_, mode) in app.ctrl.items() if mode == "leds")


def slot_states(a):
    return a.banner.winfo_manager(), a.banner_btn.winfo_manager()


def no_thread(*a, **kw):
    """Stand-in for threading.Thread that never runs its target."""
    return SimpleNamespace(start=lambda: None)


def make_app(monkeypatch, families=None):
    """A fresh App (own Tk root, no threads/timers); optionally with tkfont.families() faked."""
    monkeypatch.setattr(theme, "FAMILY", theme.FAMILY)          # undo the global assignment made by App.__init__
    monkeypatch.setattr(tk, "_default_root", None)
    if families is not None:
        monkeypatch.setattr(theme.tkfont, "families", lambda root=None: families)
    monkeypatch.setattr(app_mod.threading, "Thread", no_thread)
    a = app_mod.App()
    a.withdraw()
    a.tk.willdispatch()
    clear_timers(a)
    return a


# ---------------------------------------------------------------- fixtures
@pytest.fixture(autouse=True)
def dlg(monkeypatch):
    d = SimpleNamespace(save="", open="", yes=True, errors=[], asked=[])
    monkeypatch.setattr(sync.filedialog, "asksaveasfilename", lambda **kw: d.save)
    monkeypatch.setattr(sync.filedialog, "askopenfilename", lambda **kw: d.open)
    monkeypatch.setattr(sync.messagebox, "showerror", lambda *a, **kw: d.errors.append(a))
    monkeypatch.setattr(sync.messagebox, "askyesno", lambda *a, **kw: d.asked.append(a) or d.yes)
    # timers the tests do not drive explicitly must not fire behind their back
    monkeypatch.setattr(theme, "POLL_MS", 10 ** 7)
    monkeypatch.setattr(theme, "FRAME_MS", 10 ** 7)
    return d


@pytest.fixture(scope="session")
def shared_app():
    """One App for the whole run (building the Tk widget tree costs ~0.5 s); mk() resets it per test.
    No joystick reader thread and no startup timers: those are exercised explicitly."""
    with pytest.MonkeyPatch.context() as mp:
        def boom(*a, **k):
            raise AssertionError("real device access")
        mp.setattr(device, "Device", boom)
        mp.setattr(app_mod.threading, "Thread", no_thread)
        mp.setattr(theme, "POLL_MS", 10 ** 7)
        mp.setattr(theme, "FRAME_MS", 10 ** 7)
        a = app_mod.App()
    a.withdraw()
    a.tk.willdispatch()             # worker thread may call app.after without a running mainloop()
    clear_timers(a)
    yield a
    a.destroy()


@pytest.fixture
def mk(shared_app, fake):
    """Factory: reset the shared App, optionally preload cfg into the fake controller, read it."""
    a = shared_app

    def make(cfg=None, read=True):
        pump(a)
        clear_timers(a)
        if cfg is not None:
            fake.cfg[:] = cfg
            fake.pending[:] = cfg
        a.doc, a.base, a.sel_btn, a.color_target = None, None, "A", "hot_color"
        a.active_slot, a.theme_dev, a._remapped = None, None, set()
        a.pad_down.clear(), a.pad_axes.clear(), a.press_t.clear()
        a.show("home")
        a.select_slot(0, gather=False)
        if read:
            a.read_device()
            pump(a)
        return a
    yield make
    pump(a)
    clear_timers(a)


@pytest.fixture
def scratch(shared_app):
    f = tk.Frame(shared_app, bg=theme.BG)
    yield f
    f.destroy()


@pytest.fixture
def app(mk):
    return mk(BACKUP)


@pytest.fixture
def eapp(mk):
    """App with slot 0 enabled (custom profile)."""
    return mk(cfg_with(0))


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(theme, "AUTOSAVE_MS", 5)
