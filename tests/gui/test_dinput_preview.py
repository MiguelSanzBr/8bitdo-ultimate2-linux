"""DInput preview has live highlighting but never uses a stale config or enables editing."""
import tkinter as tk

import pytest

from ultimate2 import discovery, models, protocol
from ultimate2.gui import app as app_mod, live_input, sync, theme, widgets

from .conftest import badge, cfg_with, click, fire, make_app, pump, walk


def test_wireless_dinput_without_config_keeps_input_preview(monkeypatch, fake, dlg):
    # The window runs its real read worker, but never opens a joystick or actual controller.
    thread = app_mod.threading.Thread
    a = make_app(monkeypatch)
    monkeypatch.setattr(app_mod.threading, "Thread", thread)
    monkeypatch.setattr(discovery, "find_devices", lambda: iter(()))
    monkeypatch.setattr(discovery, "find_dinput_wireless", lambda: object())
    dialogs = []
    for name in ("asksaveasfilename", "askopenfilename"):
        monkeypatch.setattr(sync.filedialog, name, lambda **_kw: dialogs.append(True))
    try:
        a.read_device()
        pump(a)
        assert badge(a) == (None, False)
        assert "DInput" in a.status.cget("text")
        assert a.dinput_info.winfo_manager() == "pack"
        assert a.doc is None and a.base is None and a._retry_job
        a.select_slot(2)
        a.autosave()
        a.backup()
        a.restore()

        # Neutral receiver reports captured while the physical profile lights cycled.
        # Changing battery/IMU bytes must not resurrect a previously known slot.
        for packet, capacity in (
            ("010f7f7f7f7f00000000000000005a6dfe0100ad0f04000800efff00000000000000", 90),
            ("010f7f7f7f7f00000000000000005839feefffee0f03000a00f2ff00000000000000", 88),
            ("010f7f7f7f7f00000000000000005726fedaffba0f01000900eeff00000000000000", 87),
        ):
            buttons, _, a.dinput_battery = live_input.decode_dinput(bytes.fromhex(packet))
            assert not buttons and a.dinput_battery == capacity
            a.show_dinput()
            assert a.active_slot is None and a.home_sub.cget("text") == ""

        click(a, a.tiles["sticks"])
        fire(a, a.home_canvas, "co:Botões_ABXY")
        click(a, a.slot_btns[1])
        for button in a.backup_buttons:
            click(a, button)
        assert a.page == "home" and a.slot == 0
        assert not dialogs and not dlg.errors

        a.pad_down.add("A")
        a.animate()
        body = a.home_items["A"]["body"]
        assert a.home_canvas.itemcget(body, "fill") == theme.ACCENT
        assert not any(c in {protocol.CMD_WRITE, protocol.CMD_COMMIT, protocol.CMD_SET_THEME} for c, *_ in fake.log)
    finally:
        a.destroy()


def test_poll_switches_to_preview_and_retry_restores_config_controls(mk, fake, monkeypatch):
    a = mk(cfg_with(0, lambda s: s["mapping"].update(P1="A"), name="Old config"))
    a.show("buttons")
    find_devices = discovery.find_devices
    link = {"dinput": True, "config": False}
    monkeypatch.setattr(discovery, "find_devices", lambda: find_devices() if link["config"] else iter(()))
    monkeypatch.setattr(discovery, "find_dinput_wireless", lambda: link["dinput"])
    try:
        a.poll()
        pump(a)
        assert a.page == "home" and a.doc is None and a.base is None
        assert a.home_sub.cget("text") == "" and not a.pill.find_withtag("battery")
        assert a.tiles["buttons"].cget("state") == "disabled"
        assert all(not b.enabled for b in (*a.slot_btns, *a.backup_buttons))
        a.pad_down.add("A")
        a.animate()
        paddle = a.home_items["P1"]
        assert a.home_canvas.itemcget(paddle["body"], "fill") == paddle["base"][0]

        # Losing the input node removes the connected badge, not the config guard.
        link["dinput"] = False
        a.read_device(True)
        pump(a)
        assert badge(a) == (None, True) and not a.dinput_info.winfo_manager()
        assert a.tiles["buttons"].cget("state") == "disabled"

        # Drive the actual retry timer once after the supported config endpoint comes back.
        link["config"] = True
        fake.cfg[:] = fake.pending[:] = cfg_with(0, name="New config")
        a.after_cancel(a._retry_job)
        monkeypatch.setattr(theme, "RETRY_MS", 1)
        a.schedule_retry()
        pump(a, lambda: a.doc is not None and not a.busy)
        assert a.v["name"].get() == "New config" and a._retry_job is None
        assert a.tiles["buttons"].cget("state") == "normal"
        assert all(b.enabled for b in (*a.slot_btns, *a.backup_buttons))
        click(a, a.tiles["buttons"])
        assert a.page == "buttons"
    finally:
        link["config"] = True
        a.pad_down.clear()
        a.read_device()
        pump(a)


def test_successful_config_read_wins_over_dinput_discovery(mk, monkeypatch):
    monkeypatch.setattr(discovery, "find_dinput_wireless", lambda: True)
    a = mk()
    assert a.doc is not None and not a.dinput_info.winfo_manager()
    assert a.tiles["buttons"].cget("state") == "normal"


def test_pending_edits_cancelled_when_other_model_replaced_by_dinput(mk, monkeypatch):
    a = mk()
    a.set_model(models.ULTIMATE_BT)
    a._save_job = a.after(60000, lambda: pytest.fail("stale save"))
    job = a._save_job
    monkeypatch.setattr(discovery, "find_dinput_wireless", lambda: True)
    assert a.show_dinput()
    assert a.model is models.ULTIMATE2 and job not in a.tk.call("after", "info")
    a.read_device()
    pump(a)


def test_no_slot_reply_with_dinput_retries_in_preview(mk, monkeypatch):
    a = mk()
    monkeypatch.setattr(sync.device.Device, "current_slot", lambda _: None)
    monkeypatch.setattr(discovery, "find_dinput_wireless", lambda: True)
    a.poll()
    pump(a)
    assert a.preview_only and a._retry_job
    a.read_device()
    pump(a)


def test_restore_aborts_if_controller_switches_during_confirmation(mk, tmp_path, monkeypatch):
    a = mk()
    path = tmp_path / "backup"
    path.write_bytes(a.base)
    monkeypatch.setattr(discovery, "find_dinput_wireless", lambda: True)
    monkeypatch.setattr(sync.filedialog, "askopenfilename", lambda **_: str(path))
    monkeypatch.setattr(sync.messagebox, "askyesno", lambda *args, **kw: a.show_dinput())
    a.restore()
    assert a.preview_only and not a.busy
    a.read_device()
    pump(a)


@pytest.mark.parametrize("lang,words", [
    ("pt", ("configurações", "perfil", "backups", "analógicos")),
    ("en", ("Settings", "Profile", "restore", "sticks")),
])
def test_preview_hover_help_and_reload(monkeypatch, fake, lang, words):
    monkeypatch.setenv("LANGUAGE", lang)
    monkeypatch.setattr(theme, "TOOLTIP_MS", 1)
    monkeypatch.setattr(discovery, "find_dinput_wireless", lambda: True)
    thread = app_mod.threading.Thread
    a = make_app(monkeypatch)
    monkeypatch.setattr(app_mod.threading, "Thread", thread)

    def tip_text():
        return [w.cget("text") for popup in a.winfo_children() if isinstance(popup, tk.Toplevel)
                and popup.winfo_viewable() for w in popup.winfo_children() if isinstance(w, tk.Label)]

    try:
        a.deiconify()
        a.show_dinput()
        a.update()
        tile, profile, backup = a.tiles["sticks"], a.slot_btns[0], a.backup_buttons[0]
        # A tooltip for a control at the bottom of the screen must fit above it.
        bottom = a.winfo_screenheight() - 2
        with monkeypatch.context() as patch:
            patch.setattr(backup, "winfo_rooty", lambda: bottom)
            a.preview_tip.hide()
            a.preview_tip._show(backup, "Backup", 0)
            popup = a.preview_tip.window
            popup.update_idletasks()
            assert popup.winfo_rooty() + popup.winfo_reqheight() <= bottom
            a.preview_tip.hide()
        # Moving away before the hover delay must cancel the pending popup.
        monkeypatch.setattr(theme, "TOOLTIP_MS", 60000)
        tile.event_generate("<Enter>")
        pending = a.preview_tip.job
        tile.event_generate("<Leave>")
        assert pending and pending not in a.tk.call("after", "info") and not tip_text()
        monkeypatch.setattr(theme, "TOOLTIP_MS", 1)
        assert tile.itemcget("bg", "disabledfill") != tile.itemcget("bg", "fill")
        assert a.home_canvas.itemcget("co:LT", "state") == "disabled"
        for pill in (*a.slot_btns, *a.backup_buttons):
            assert pill.itemcget(pill.find_all()[0], "fill") == theme.DISABLED_FILL
        for widget, word in zip((tile, profile, backup, a.home_canvas), words):
            widget.event_generate("<Enter>", x=5, y=5)
            pump(a, tip_text)
            text, = tip_text()
            assert word in text and "USB" in text and "XInput" in text
            widget.event_generate("<Leave>")
            a.update()
            assert not tip_text()

        profile.event_generate("<Enter>")
        pump(a, tip_text)
        reload = next(w for w in walk(a) if isinstance(w, widgets.Pill) and w.text in ("Reload", "Recarregar"))
        assert reload.enabled
        click(a, reload)
        pump(a)
        assert a.doc is not None and not a.preview_only and not tip_text()
        a.preview_tip._show(tile, "stale hover", 0)
        assert not tip_text()
        assert a.home_canvas.itemcget("co:LT", "state") == "normal"
        tile.event_generate("<Enter>")
        pump(a, lambda: tile.itemcget("bg", "fill") == theme.TILE_HI)
        tile.event_generate("<Button-1>")
        assert a.page == "sticks" and not tip_text()
    finally:
        a.destroy()
