"""Mixin: device I/O on a worker thread — initial read, auto-save, active-profile polling, LED theme, backups."""
import copy
import os
import sys
import threading
import time
from tkinter import filedialog, messagebox

from .. import battery, config, device, discovery, models, protocol
from . import theme
from .i18n import _
from .theme import ACCENT, DANGER, DEFAULT_SKIN, EDITION_SKINS, MUTED, SKINS, THEME_NAMES


def cache_path():
    """Copy of the Ultimate 2.4G's D configuration (the one Bluetooth uses), kept from the last cable read."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "ultimate2", "ultimate24g-d.bin")


class DeviceSync:
    # ------------------------------------------------------------ status line / connection pill
    def set_status(self, text, error=False):
        self.status.configure(text=text, fg=DANGER if error else MUTED)

    def set_connected(self, state):
        """Connection badge (Wi-Fi and battery; the firmware goes to the footer's corner). ``state``: ``(firmware,
        battery %)`` when connected (battery may be ``None``), ``None`` when the controller does not answer (grey Wi-Fi
        with a red X), ``False`` while still looking (grey Wi-Fi)."""
        c, s = self.pill, self.s
        c.delete("all")
        col, w = ACCENT if state else MUTED, max(1, round(2 * s))
        x, y = 11 * s, 17 * s                                  # Wi-Fi: three arcs over a dot
        for r in (5, 9.5, 14):
            c.create_arc(x - r * s, y - r * s, x + r * s, y + r * s, start=50, extent=80, style="arc", outline=col, width=w)
        c.create_oval(x - 2 * s, y - 2 * s, x + 2 * s, y + 2 * s, fill=col, outline="")
        if state is None:                                      # red X over the bottom-right of the arcs
            c.create_line(15 * s, 10 * s, 22 * s, 17 * s, fill=DANGER, width=w, capstyle="round")
            c.create_line(15 * s, 17 * s, 22 * s, 10 * s, fill=DANGER, width=w, capstyle="round")
        self.fw_label.configure(text=f"firmware {state[0]}" if state and state[0] else "")
        if state and state[1] is not None:                   # battery outline, fill to the level, then the %
            battery, px, bw, bh, top = state[1], 32 * s, 22 * s, 11 * s, 6 * s
            c.create_rectangle(px, top, px + bw, top + bh, outline=col, width=max(1, round(1.5 * s)))
            c.create_rectangle(px + bw, top + 3 * s, px + bw + 2.5 * s, top + bh - 3 * s, fill=col, outline="")
            level = min(max(battery, 0), 100) / 100
            if level:
                c.create_rectangle(px + 2 * s, top + 2 * s, px + 2 * s + (bw - 4 * s) * level, top + bh - 2 * s,
                                   fill=DANGER if battery <= 15 else col, outline="")
            c.create_text(px + bw + 6 * s, 11.5 * s, text=f"{battery}%", anchor="w", fill=col, font=theme.font(9),
                          tags="battery")
        c.configure(width=c.bbox("all")[2] + 2)

    # ------------------------------------------------------------ worker
    def run(self, label, job, done, quiet=False, fail=None, knock=False):
        """Run ``job(dev)`` on a worker thread; ``done(result)`` runs on the Tk thread.

        ``quiet`` (background polling): no status text and no error dialog, only the connection pill.
        ``fail(error, message)``, when given, handles errors instead (on the Tk thread).
        ``knock``: switch an Ultimate Bluetooth found in XInput mode to config mode first; it stays there until the
        window closes (switching takes a USB reconnect, too slow for every job).
        """
        if self.busy:
            return
        self.busy = True
        if not quiet:
            self.set_status(label)

        def work():
            dev = None
            try:
                dev = device.Device(knock=knock, stay=True)
                res = job(dev)
                self.after(0, lambda: done(res))
            except BaseException as e:     # Device uses sys.exit for user-facing errors
                msg = str(e) or e.__class__.__name__
                if fail:
                    self.after(0, lambda e=e: fail(e, msg))     # `e` is unbound once the except block ends
                elif quiet:
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
        if self.readonly:                          # Bluetooth: nothing can be written, put the shown values back
            self.after_idle(self.load)
            self.set_status(_("Somente leitura no Bluetooth: ligue o cabo USB (chave em D) para mudar."), True)
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
        layout = self.model.layout or None
        new = config.encode(copy.deepcopy(self.doc), self.base, layout)[0]
        span = config.changed_span(self.base, new)
        if not span:
            self.set_status("")
            return
        if self.model.whole_writes:       # its app always writes the whole record; partial writes are untested there
            span = (0, len(new))

        def job(dev):
            dev.write_config(new, *span)
            if not config.same(new, dev.read_config(), layout, span):
                raise IOError(_("verificação falhou: o controle não guardou o que foi enviado"))

        def done(_r):
            self.base = new
            self.profile_note.configure(text="")
            self.set_status(_("✓ Salvo no controle ({} bytes).").format(span[1] - span[0]))
        self.run(_("Salvando no controle…"), job, done)

    # ------------------------------------------------------------ live state
    def poll(self):
        """Follow the controller's active profile (the user switches it with the profile button)."""
        self.check_conflict()
        if self.readonly:                          # Bluetooth only: no config channel, keep the battery current
            bt = battery.bluetooth()
            self.set_connected((None, bt["capacity"]) if bt else None)
            self.after(theme.POLL_MS, self.poll)
            return
        # a pending re-read owns the device: polling now would postpone it forever (POLL_MS < RETRY_MS)
        if self.doc is not None and not self.busy and self._save_job is None and self._retry_job is None:
            wireless = bool(self.conn and self.conn[1] is not None)    # battery only exists through the dongle

            def done(r):
                slot, pad = r
                bt = battery.bluetooth() if self.model is models.ULTIMATE_24G and self.conn else None
                if pad or bt:
                    self.conn = (self.conn[0], pad["battery"] if pad else bt["capacity"])
                if slot is not None and self.conn:
                    self.set_connected(self.conn)          # recover the badge after a transient error
                if slot is not None and slot != self.active_slot:
                    self.active_slot = slot
                    self.refresh_slots()
            # a knocked controller that lost power or was replugged is back in XInput: read (and knock) it again
            fail = (lambda e, msg: (self.set_connected(None), self.read_device(True))) if self.model.knock else None
            self.run("", lambda dev: (dev.current_slot(), dev.pad_status() if wireless else None), done, quiet=True,
                     fail=fail)
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

    def read_device(self, retry=False):
        """Read everything from the controller and show it (skin, theme, active slot, config).

        A controller that does not answer (switched off, out of the dongle's range, unplugged) is not an error: the
        status says so and the read is tried again until it answers. Only a permission problem opens a dialog.
        """
        if self._retry_job:                     # Reload while waiting for the controller
            self.after_cancel(self._retry_job)
            self._retry_job = None
        if retry and self.busy:
            self._retry_job = self.after(theme.RETRY_MS, lambda: self.read_device(True))
            return

        def fail(e, msg):
            self.set_connected(None)
            if isinstance(e, SystemExit) and ("permission" in msg or "cannot switch" in msg):
                self.set_status(msg, True)
                messagebox.showerror(_("Erro"), msg, parent=self)
                return
            if "over Bluetooth" in msg:
                self.show_bluetooth()
            else:
                self.set_status(_("Controle desligado ou fora de alcance. Ligue-o: ele será lido automaticamente."))
            self._retry_job = self.after(theme.RETRY_MS, lambda: self.read_device(True))

        def job(dev):
            m = dev.model
            return (m, dev.path, dev.pid, dev.info(), dev.read_config(), dev.get_theme() if m.leds else None,
                    dev.edition(), dev.pad_status() if m.pad_status else None)

        def done(r):
            model, path, pid, info, cfg, led_theme, edition, pad = r
            self.set_model(model)
            if pad:                         # through the dongle, info() is the dongle's: use the controller's own
                edition, info = pad["edition"], pad
            self.edition = edition
            want = self.skin_pref if self.skin_pref in SKINS else EDITION_SKINS.get(edition, DEFAULT_SKIN)
            if want != self.skin:
                self.apply_skin(want)
            self.theme_dev = led_theme
            self.v["theme"].set(led_theme if led_theme in protocol.THEMES else 0)
            self.base = cfg
            self.doc = config.decode(cfg, model.layout or None)
            self.active_slot = self.doc["cur_slot"]
            fw = f"{info['firmware'] / 100:.2f}" if info else "?"
            bt = battery.bluetooth() if model is models.ULTIMATE_24G else None   # also on Bluetooth, configured
            self.conn = (fw, pad["battery"] if pad else bt and bt["capacity"])   # through the cable or the receiver
            self.set_connected(self.conn)
            modes = {0: "Switch", 1: "Android", 3: "Windows (XInput)"}
            mode = modes.get(self.doc["gamepad_mode"], self.doc["gamepad_mode"])
            self.info_label.configure(text=_("Dispositivo: {}\nModo: {}\nEdição: {} ({})").format(
                f"{path} · {protocol.PIDS.get(pid, hex(pid))}", mode, edition, _(SKINS[self.skin]["name"])))
            self.load()
            self.refresh_slots()
            self.set_status(_("Configuração lida do controle. As mudanças são salvas automaticamente."))
            self.readonly = False
            self.btinfo.pack_forget()
            self.check_conflict()
            if model is models.ULTIMATE_24G and self.doc["gamepad_mode"] == 1:
                self.keep_copy(cfg)
        self.run("" if retry else _("Lendo do controle…"), job, done, quiet=retry, fail=fail, knock=True)

    # ------------------------------------------------------------ Ultimate 2.4G on Bluetooth
    def check_conflict(self):
        """Warn when the X configuration (receiver, or cable on X) is being edited while the pad plays on Bluetooth,
        which uses the D one: the changes would not apply where the user is testing them."""
        on = bool(self.doc and self.model is models.ULTIMATE_24G and self.doc["gamepad_mode"] == 3
                  and discovery.bluetooth_24g())
        if on and not self.conflict.winfo_manager():
            self.conflict.pack(fill="x", padx=int(24 * self.s), pady=(int(10 * self.s), 0), after=self.slot_btns[0].master)
        elif not on and self.conflict.winfo_manager():
            self.conflict.pack_forget()
        return on

    def keep_copy(self, cfg):
        """Keep the D configuration read over the cable: shown read-only when the pad is only on Bluetooth."""
        try:
            os.makedirs(os.path.dirname(cache_path()), exist_ok=True)
            with open(cache_path(), "wb") as f:
                f.write(cfg)
        except OSError:
            pass                               # only a convenience

    def show_bluetooth(self):
        """Pad only on Bluetooth (no config channel): a banner up top, the battery in the badge and, when there is
        one, the copy kept from the last cable read, read-only (it is the configuration Bluetooth uses)."""
        bt = battery.bluetooth()
        self.set_connected((None, bt["capacity"]) if bt else None)
        if not self.readonly:
            try:
                with open(cache_path(), "rb") as f:
                    data = f.read()
                when = time.strftime("%d/%m/%Y %H:%M", time.localtime(os.path.getmtime(cache_path())))
            except OSError:
                data = None
            if data is not None and len(data) == models.ULTIMATE_24G.cfg_size:
                self.set_model(models.ULTIMATE_24G)
                self.base, self.doc, self.readonly, self.active_slot = data, config.decode(data, "ultimate_24g"), True, None
                self.cache_when = when
                self.load()
                self.refresh_slots()
        text = _("Controle conectado pelo Bluetooth, que não permite ler nem gravar a configuração.") + " "
        text += (_("Mostrando a última configuração lida pelo cabo, em {} (somente leitura); é a que vale no "
                   "Bluetooth. Para mudar, ligue o cabo USB com a chave em D.").format(self.cache_when)
                 if self.readonly else
                 _("Ligue o cabo USB (chave em D) uma vez para o programa guardar e mostrar a configuração."))
        if bt:
            text += " " + _("Bateria: {}%.").format(bt["capacity"])
        self.btinfo_text.configure(text=text)
        if not self.btinfo.winfo_manager():
            self.btinfo.pack(fill="x", padx=int(24 * self.s), pady=(int(10 * self.s), 0), after=self.slot_btns[0].master)
        self.set_status(_("Bluetooth: somente leitura."))

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
        size = self.model.cfg_size
        if len(data) != size:
            return messagebox.showerror(_("Erro"), _("Arquivo inválido ({} bytes, esperado {}).").format(len(data), size),
                                        parent=self)
        if not messagebox.askyesno(_("Restaurar"), _("Substituir toda a configuração do controle por este backup?"), parent=self):
            return

        def job(dev):
            dev.write_config(data)
            if not config.same(data, dev.read_config(), self.model.layout or None):
                raise IOError(_("verificação falhou"))

        def done(_r):
            self.base = data
            self.doc = config.decode(data, self.model.layout or None)
            self.load()
            self.set_status(_("Backup restaurado e verificado."))
        self.run(_("Restaurando…"), job, done)
