"""sync mixin: worker thread, auto-save, polling, LED theme, read, backup/restore."""
import threading

import pytest

from ultimate2 import config, device, discovery, protocol
from ultimate2.gui import theme

from .conftest import BACKUP, cfg_with, pump, slot_states


def saved(a):
    return "Salvo" in a.status.cget("text") and not a.busy


def test_set_status_and_connected(app):
    app.set_status("oops", True)
    assert app.status.cget("fg") == theme.DANGER
    app.set_status("ok")
    assert app.status.cget("fg") == theme.MUTED
    app.set_connected("hi")
    assert app.pill.cget("text") == "●  hi"
    app.set_connected(None)
    assert "não encontrado" in app.pill.cget("text")


# ---------------------------------------------------------------- run
def test_run_while_busy_is_ignored(app):
    gate = threading.Event()
    seen = []
    app.run("a", lambda d: gate.wait(5), lambda r: seen.append("a"))
    assert app.busy and app.status.cget("text") == "a"
    app.run("b", lambda d: seen.append("b"), lambda r: seen.append("b"))
    gate.set()
    pump(app)
    assert seen == ["a"]


def test_run_success(app):
    out = []
    app.run("lbl", lambda d: d.pid, out.append)
    pump(app)
    assert out == [0x310B]


def test_run_no_device_systemexit(app, dlg, monkeypatch):
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([]))
    app.run("lbl", lambda d: None, lambda r: pytest.fail("done"))
    pump(app)
    assert "no 8BitDo" in app.status.cget("text") and app.status.cget("fg") == theme.DANGER
    assert "não encontrado" in app.pill.cget("text") and dlg.errors


def test_run_job_ioerror_with_device_and_empty_message(app, dlg):
    def job(dev):
        raise IOError()
    app.run("lbl", job, lambda r: pytest.fail("done"))
    pump(app)
    assert app.status.cget("text") == "OSError" and dlg.errors


# ---------------------------------------------------------------- read_device
def test_read_device_controller_off_is_not_an_error(app, dlg, monkeypatch):
    def off(self):
        raise OSError(5, "Input/output error")
    real = device.Device.read_config
    monkeypatch.setattr(device.Device, "read_config", off)
    app.read_device()
    pump(app)
    assert not dlg.errors and "desligado" in app.status.cget("text") and app.status.cget("fg") != theme.DANGER
    assert "não encontrado" in app.pill.cget("text") and app._retry_job
    app.busy = True                                         # a retry while busy waits for the next turn
    job = app._retry_job
    app.read_device(True)
    assert app._retry_job and app._retry_job != job
    app.busy = False
    monkeypatch.setattr(device.Device, "read_config", real)  # switched on: the retry reads it quietly
    app.read_device(True)
    pump(app)
    assert app._retry_job is None and "salvas automaticamente" in app.status.cget("text") and not dlg.errors


def test_read_device_unplugged_retries_and_permission_opens_dialog(app, dlg, monkeypatch):
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([]))
    app.read_device()
    pump(app)
    assert not dlg.errors and app._retry_job
    def denied(self, path=None):
        raise SystemExit("permission denied on /dev/hidraw0")
    monkeypatch.setattr(device.Device, "__init__", denied)
    app.read_device()                                       # Reload cancels the pending retry
    pump(app)
    assert dlg.errors and app._retry_job is None and app.status.cget("fg") == theme.DANGER


def test_read_device(app):
    assert app.doc["gamepad_mode"] == 3 and app.active_slot == 3 and app.base == BACKUP
    assert "Windows (XInput)" in app.info_label.cget("text") and "/dev/hidraw-fake" in app.info_label.cget("text")
    assert "wired (XInput)" in app.pill.cget("text") and "firmware 1.10" in app.pill.cget("text")
    assert "salvas automaticamente" in app.status.cget("text")
    assert app.home_sub.cget("text") == "Perfil ativo no controle: padrão"


def test_read_device_unknown_mode_and_info_none(mk, monkeypatch, fake):
    cfg = bytearray(BACKUP)
    cfg[16:18] = (7).to_bytes(2, "little")
    monkeypatch.setattr(device.Device, "info", lambda self: None)
    monkeypatch.setattr(protocol, "PIDS", {})
    a = mk(bytes(cfg))
    assert "Modo: 7" in a.info_label.cget("text")
    assert "firmware ?" in a.pill.cget("text") and hex(fake.usb_pid) in a.pill.cget("text")


def test_read_device_loads_theme(app, fake):
    assert app.theme_dev == 2 and app.v["theme"].get() == 2


def test_read_device_unknown_theme(mk, fake, monkeypatch):
    monkeypatch.setattr(device.Device, "get_theme", lambda self: None)
    a = mk()
    assert a.theme_dev is None and a.v["theme"].get() == 0


@pytest.mark.parametrize("start,edition,end,switches", [
    ("dark", 3, "lilac", True), ("lilac", 3, "lilac", False),
    ("lilac", 0, "line", True), ("line", 0, "line", False),
    ("lilac", 9, "line", True),                                          # unknown edition: the outline drawing
    ("lilac", None, "line", True), ("line", None, "line", False)])      # no answer to the colorway query
def test_read_device_picks_skin_from_edition(mk, fake, monkeypatch, start, edition, end, switches):
    a = mk(BACKUP, read=False)
    old = a.skin
    a.apply_skin(start)
    calls = []
    real = a.apply_skin
    monkeypatch.setattr(a, "apply_skin", lambda n: calls.append(n) or real(n))
    if edition is None:
        monkeypatch.setattr(device.Device, "edition", lambda self: None)
    else:
        fake.edition = edition
    a.read_device()
    pump(a)
    assert a.skin == end and calls == ([end] if switches else [])
    assert f"Edição: {edition} ({theme.SKINS[end]['name']})" in a.info_label.cget("text")
    assert a.doc is not None and a.map_items is a.ctrl[a.map_canvas][0]
    monkeypatch.undo()
    a.apply_skin(old)


# ---------------------------------------------------------------- auto-save
def test_changed_ignored_without_doc_or_while_loading(app):
    doc = app.doc
    app.doc = None
    app.v["name"].set("x")
    assert app._save_job is None
    app.doc = doc
    app._loading = True
    try:
        app.v["name"].set("y")
    finally:
        app._loading = False
    assert app._save_job is None


def test_changed_auto_enables_empty_profile_and_debounces(app):
    assert not app.v["enabled"].get()
    app.v["name"].set("novo")                              # empty profile becomes a custom one
    assert app.v["enabled"].get() and app._save_job and "pendentes" in app.status.cget("text")
    first = app._save_job
    app.v["gyro_sens"].set(3)                              # reschedules: the old job is cancelled
    assert app._save_job != first and first not in app.tk.splitlist(app.tk.call("after", "info"))
    app.v["enabled"].set(False)                            # the toggle itself never re-enables
    assert not app.v["enabled"].get()


def test_changed_without_var(eapp):
    eapp.changed()
    assert eapp._save_job and "pendentes" in eapp.status.cget("text")


def test_autosave_writes_changed_range(eapp, fake, fast):
    before = bytes(fake.cfg)
    eapp.v["name"].set("Novo")
    eapp.v["keys"]["A"].set("RT")
    pump(eapp, lambda: saved(eapp))
    assert bytes(fake.cfg) != before and eapp._save_job is None
    doc = config.decode(bytes(fake.cfg))
    assert doc["slots"][0]["name"] == "Novo" and doc["slots"][0]["mapping"]["A"] == "RT"
    assert config.changed_span(eapp.base, bytes(fake.cfg)) is None      # base follows what was written
    assert "bytes)" in eapp.status.cget("text") and eapp.profile_note.cget("text") == ""
    wr = [e for e in fake.log if e[0] == protocol.CMD_WRITE]
    assert wr and sum(e[2] for e in wr) < protocol.CFG_SIZE                # a partial write, not the whole record


def test_autosave_creates_profile_from_empty(app, fake, fast):
    app.v["gyro_sens"].set(2)
    pump(app, lambda: saved(app))
    assert config.decode(bytes(fake.cfg))["slots"][0]["flag"] == "enabled"


def test_autosave_no_changes_clears_status(app, fake):
    before = bytes(fake.cfg)
    app.set_status("Alterações pendentes…")
    app.autosave()                                          # empty profile, nothing enabled: nothing to write
    assert app.status.cget("text") == "" and not app.busy and bytes(fake.cfg) == before


def test_autosave_second_run_has_nothing_left(eapp, fake, fast):
    eapp.v["name"].set("Uma vez")
    pump(eapp, lambda: saved(eapp))
    log = len(fake.log)
    eapp.set_status("Alterações pendentes…")
    eapp.autosave()
    assert eapp.status.cget("text") == "" and len(fake.log) == log


def test_autosave_waits_while_busy(eapp, fake):
    eapp.v["name"].set("Espera")
    eapp.busy = True
    eapp.autosave()
    assert eapp._save_job is not None and "Salvo" not in eapp.status.cget("text")
    eapp.busy = False
    pump(eapp, lambda: saved(eapp))
    assert config.decode(bytes(fake.cfg))["slots"][0]["name"] == "Espera"


def test_autosave_verify_failure(eapp, fake, dlg, monkeypatch):
    stale = bytes(fake.cfg)
    monkeypatch.setattr(device.Device, "read_config", lambda self: b"\xa5" * protocol.CFG_SIZE)
    base = eapp.base
    eapp.v["name"].set("Falha")
    eapp.autosave()
    pump(eapp)
    assert "verificação falhou" in eapp.status.cget("text") and dlg.errors
    assert eapp.base is base and config.decode(bytes(fake.cfg))["slots"][0]["name"] == "Falha" and stale != bytes(fake.cfg)


# ---------------------------------------------------------------- poll / active slot
def set_cur_slot(fake, n):
    fake.cfg[18:20] = n.to_bytes(2, "little")


def test_poll_follows_active_slot(eapp, fake):
    set_cur_slot(fake, 1)
    eapp.poll()
    assert eapp.busy and eapp.status.cget("text") != ""     # quiet: no status change of its own
    pump(eapp)
    assert eapp.active_slot == 1 and "●" in eapp.slot_btns[1].text
    assert slot_states(eapp)[0] == "pack"                    # slot 0 is edited, slot 1 active: banner shown
    eapp.poll()                                              # unchanged: nothing to refresh
    pump(eapp)
    assert eapp.active_slot == 1
    assert eapp.tk.splitlist(eapp.tk.call("after", "info"))  # poll re-arms itself


def test_poll_is_quiet(eapp, fake):
    eapp.set_status("marker")
    eapp.poll()
    assert eapp.status.cget("text") == "marker"
    pump(eapp)
    assert eapp.status.cget("text") == "marker"


def test_poll_skipped_without_doc_busy_or_pending_save(eapp, fake):
    log = len(fake.log)
    doc = eapp.doc
    eapp.doc = None
    eapp.poll()
    eapp.doc = doc
    eapp.busy = True
    eapp.poll()
    eapp.busy = False
    eapp._save_job = "pending"
    eapp.poll()
    eapp._save_job = None
    assert len(fake.log) == log and not eapp.busy


def test_poll_no_answer_keeps_active_slot(eapp, monkeypatch):
    monkeypatch.setattr(device.Device, "current_slot", lambda self: None)
    eapp.active_slot = 2
    eapp.poll()
    pump(eapp)
    assert eapp.active_slot == 2


def test_poll_error_is_silent_but_marks_disconnected(eapp, dlg, monkeypatch):
    def boom(self):
        raise IOError("gone")
    monkeypatch.setattr(device.Device, "current_slot", boom)
    eapp.set_status("marker")
    eapp.poll()
    pump(eapp)
    assert not dlg.errors and eapp.status.cget("text") == "marker"
    assert "não encontrado" in eapp.pill.cget("text")


def test_poll_recovers_pill_after_transient_error(eapp):
    assert eapp.conn_text and "Conectado" in eapp.conn_text
    eapp.set_connected(None)                     # e.g. controller was unplugged for a moment
    eapp.poll()
    pump(eapp)
    assert eapp.pill.cget("text") == f"●  {eapp.conn_text}"
    eapp.conn_text = None                        # never read successfully: nothing to restore
    eapp.set_connected(None)
    eapp.poll()
    pump(eapp)
    assert "não encontrado" in eapp.pill.cget("text")


# ---------------------------------------------------------------- LED theme (cmd 0x40/0x41)
def test_theme_chip_applies_immediately(app, fake):
    fake.theme = 2
    app.v["theme"].set(4)
    pump(app)
    assert fake.theme == 4 and app.theme_dev == 4
    assert "Personalizado" in app.status.cget("text")
    assert app._save_job is None                            # a theme change is not a profile edit


def test_theme_same_or_invalid_is_noop(app, fake):
    log = len(fake.log)
    app.v["theme"].set(app.theme_dev)        # unchanged
    app.v["theme"].set(0)                    # not a theme value
    app.doc = None
    app.apply_theme()                        # no document yet
    app.v["theme"].set(5)
    pump(app)
    assert not any(c == protocol.CMD_SET_THEME for c, *_ in fake.log[log:])


def test_apply_theme_retries_while_busy(app, fake):
    app.busy = True
    app.v["theme"].set(5)                    # busy: retried 300 ms later
    assert fake.theme == 2
    app.busy = False
    pump(app, lambda: app.theme_dev == 5 and not app.busy)
    assert fake.theme == 5


# ---------------------------------------------------------------- backup / restore
def test_backup_and_cancel(app, fake, dlg, tmp_path):
    dlg.save = ""
    app.backup()
    assert not app.busy
    dlg.save = str(tmp_path / "b.bin")
    app.backup()
    pump(app)
    assert (tmp_path / "b.bin").read_bytes() == bytes(fake.cfg)
    assert "Backup salvo" in app.status.cget("text")


def test_restore_cancel_wrong_size_no_success_and_verify_fail(app, fake, dlg, tmp_path):
    before = bytes(fake.cfg)
    app.restore()                                           # cancel
    assert not dlg.errors and not dlg.asked
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"123")
    dlg.open = str(bad)
    app.restore()                                           # wrong size
    assert "Arquivo inválido" in dlg.errors[-1][1] and not dlg.asked
    good = tmp_path / "good.bin"
    good.write_bytes(cfg_with(1))
    dlg.open, dlg.yes = str(good), False
    app.restore()                                           # user says no
    assert len(dlg.asked) == 1 and not app.busy and bytes(fake.cfg) == before
    dlg.yes = True
    app.restore()                                           # success
    pump(app)
    assert bytes(fake.cfg) == good.read_bytes() and "restaurado" in app.status.cget("text")
    assert app.doc["slots"][1]["flag"] == "enabled" and app.base == good.read_bytes()
    fake.corrupt_commit = True
    other = tmp_path / "other.bin"
    other.write_bytes(cfg_with(2))
    dlg.open = str(other)
    app.restore()                                           # verify failure
    pump(app)
    assert "verificação falhou" in app.status.cget("text")
