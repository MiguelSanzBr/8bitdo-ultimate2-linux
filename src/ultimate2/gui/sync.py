"""Mixin: device I/O on a worker thread — initial read, auto-save, active-profile polling, LED theme, backups."""
import copy
import threading
import time
from tkinter import filedialog, messagebox

from .. import config, device, protocol
from . import theme
from .i18n import _
from .theme import ACCENT, DANGER, EDITION_SKINS, MUTED, SKINS, THEME_NAMES


class DeviceSync:
    # ------------------------------------------------------------ status line / connection pill
    def set_status(self, text, error=False):
        self.status.configure(text=text, fg=DANGER if error else MUTED)

    def set_connected(self, text):
        self.pill.configure(text=f"●  {text}" if text else "○  " + _("controle não encontrado"), fg=ACCENT if text else MUTED)

    # ------------------------------------------------------------ worker
    def run(self, label, job, done, quiet=False):
        """Run ``job(dev)`` on a worker thread; ``done(result)`` runs on the Tk thread.

        ``quiet`` (background polling): no status text and no error dialog, only the connection pill.
        """
        if self.busy:
            return
        self.busy = True
        if not quiet:
            self.set_status(label)

        def work():
            dev = None
            try:
                dev = device.Device()
                res = job(dev)
                self.after(0, lambda: done(res))
            except BaseException as e:     # Device uses sys.exit for user-facing errors
                msg = str(e) or e.__class__.__name__
                if quiet:
                    self.after(0, lambda: self.set_connected(None))
                else:
                    self.after(0, lambda: (self.set_status(msg, True), self.set_connected(None),
                                           messagebox.showerror(_("Erro"), msg, parent=self)))
            finally:
                if dev:
                    dev.close()
                self.after(0, self._idle)
        threading.Thread(target=work, daemon=True).start()

    def _idle(self):
        self.busy = False

    # ------------------------------------------------------------ auto-save
    def changed(self, var=None):
        """A setting changed: an empty profile becomes a custom one, then save shortly (debounced)."""
        if self._loading or self.doc is None:
            return
        if var is not self.v["enabled"] and not self.v["enabled"].get():
            self.v["enabled"].set(True)       # re-enters changed(); the second call just reschedules
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(theme.AUTOSAVE_MS, self.autosave)
        self.set_status(_("Alterações pendentes…"))

    def autosave(self):
        """Write only the changed byte range (like the app's per-setting writes) and verify it."""
        self._save_job = None
        if self.busy:
            self._save_job = self.after(300, self.autosave)
            return
        self.gather()
        new = config.encode(copy.deepcopy(self.doc), self.base)[0]
        span = config.changed_span(self.base, new)
        if not span:
            self.set_status("")
            return

        def job(dev):
            dev.write_config(new, *span)
            if dev.read_config()[span[0]:span[1]] != new[span[0]:span[1]]:
                raise IOError(_("verificação falhou: o controle não guardou o que foi enviado"))

        def done(_r):
            self.base = new
            self.profile_note.configure(text="")
            self.set_status(_("✓ Salvo no controle ({} bytes).").format(span[1] - span[0]))
        self.run(_("Salvando no controle…"), job, done)

    # ------------------------------------------------------------ live state
    def poll(self):
        """Follow the controller's active profile (the user switches it with the profile button)."""
        if self.doc is not None and not self.busy and self._save_job is None:
            def done(slot):
                if slot is not None and self.conn_text:
                    self.set_connected(self.conn_text)     # recover the pill after a transient error
                if slot is not None and slot != self.active_slot:
                    self.active_slot = slot
                    self.refresh_slots()
            self.run("", lambda dev: dev.current_slot(), done, quiet=True)
        self.after(theme.POLL_MS, self.poll)

    def apply_theme(self):
        """Send the LED theme chosen in ``v["theme"]`` (applies at once, for every profile)."""
        t = self.v["theme"].get()
        if t == self.theme_dev or t not in protocol.THEMES or self.doc is None:
            return
        if self.busy:
            self.after(300, self.apply_theme)
            return

        def done(_r):
            self.theme_dev = t
            self.set_status(_("✓ Tema de LED aplicado: {}.").format(_(THEME_NAMES[t])))
        self.run(_("Aplicando tema de LED…"), lambda dev: dev.set_theme(t), done)

    def read_device(self):
        """Read everything from the controller and show it (skin, theme, active slot, config)."""
        def job(dev):
            return dev.path, dev.pid, dev.info(), dev.read_config(), dev.get_theme(), dev.edition()

        def done(r):
            path, pid, info, cfg, led_theme, edition = r
            self.edition = edition
            want = self.skin_pref if self.skin_pref in SKINS else EDITION_SKINS.get(edition, "dark")
            if want != self.skin:
                self.apply_skin(want)
            self.theme_dev = led_theme
            self.v["theme"].set(led_theme if led_theme in protocol.THEMES else 0)
            self.base = cfg
            self.doc = config.decode(cfg)
            self.active_slot = self.doc["cur_slot"]
            fw = f"{info['firmware'] / 100:.2f}" if info else "?"
            self.conn_text = _("Conectado · {} · firmware {}").format(protocol.PIDS.get(pid, hex(pid)), fw)
            self.set_connected(self.conn_text)
            modes = {0: "Switch", 1: "Android", 3: "Windows (XInput)"}
            self.info_label.configure(text=_("Dispositivo: {}\nModo: {}\nEdição: {} ({})").format(
                path, modes.get(self.doc["gamepad_mode"], self.doc["gamepad_mode"]), edition, _(SKINS[self.skin]["name"])))
            self.load()
            self.refresh_slots()
            self.set_status(_("Configuração lida do controle. As mudanças são salvas automaticamente."))
        self.run(_("Lendo do controle…"), job, done)

    # ------------------------------------------------------------ backups
    def backup(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".bin",
                                            initialfile=f"u2-backup-{time.strftime('%Y%m%d-%H%M')}.bin")
        if path:
            def job(dev):
                with open(path, "wb") as f:
                    f.write(dev.read_config())
            self.run(_("Fazendo backup…"), job, lambda r: self.set_status(_("Backup salvo em {}").format(path)))

    def restore(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[(_("Backup"), "*.bin")])
        if not path:
            return
        with open(path, "rb") as f:
            data = f.read()
        if len(data) != protocol.CFG_SIZE:
            return messagebox.showerror(_("Erro"), _("Arquivo inválido ({} bytes, esperado {}).").format(len(data), protocol.CFG_SIZE),
                                        parent=self)
        if not messagebox.askyesno(_("Restaurar"), _("Substituir toda a configuração do controle por este backup?"), parent=self):
            return

        def job(dev):
            dev.write_config(data)
            if dev.read_config() != data:
                raise IOError(_("verificação falhou"))

        def done(_r):
            self.base = data
            self.doc = config.decode(data)
            self.load()
            self.set_status(_("Backup restaurado e verificado."))
        self.run(_("Restaurando…"), job, done)
