"""Mixin: live input from the controller's joystick node (pressed buttons, triggers, sticks, d-pad)."""
import os
import struct
import time

from .. import device, discovery, models
from .catalog import LIVE_BITS

LIVE_POLL = 0.05         # live-state polling interval for live_by_query models (the Ultimate Bluetooth app asks ~20/s)
JS_BUTTONS = ["A", "B", "X", "Y", "LB", "RB", "Select", "Start", "Home", "L3", "R3"]   # xpad js button order
JS_EVENT = "<IhBB"       # struct js_event: u32 time, s16 value, u8 type, u8 number
JS_BUTTON, JS_AXIS, JS_INIT = 1, 2, 0x80


class PadInput:
    def _read_pad(self):
        """Background thread: follow the real controller's buttons/axes; reconnects every second."""
        while not self._closing:
            if self.model.live_by_query:
                self._poll_live()
                continue
            node = None
            try:
                dev = next(discovery.find_devices(), None)
                # a live_by_query controller sends no js events: wait for the read to set self.model
                node = dev and not models.for_pid(dev[1]).live_by_query and discovery.find_input_node(dev[2])
            except OSError:
                pass
            fd = None
            if node:
                try:
                    fd = os.open(node, os.O_RDONLY)
                except OSError:
                    fd = None
            if fd is None:
                time.sleep(1)
                continue
            try:
                while not self._closing:
                    ev = os.read(fd, 8)
                    if len(ev) < 8:
                        break
                    self.pad_event(*struct.unpack(JS_EVENT, ev)[1:])
            except OSError:
                pass
            finally:
                os.close(fd)
            self.pad_down.clear()
            self.pad_axes.clear()
            time.sleep(1)

    def _poll_live(self):
        """Controllers without gamepad reports in config mode (``live_by_query``): ask for the live state between jobs."""
        try:
            dev = device.Device()
        except SystemExit:
            time.sleep(1)
            return
        try:
            while self.model.live_by_query and not self._closing:
                if not self.busy:
                    state = dev.live()
                    if state is None:
                        break
                    self.live_state(*state)
                time.sleep(LIVE_POLL)
        except OSError:
            pass
        finally:
            dev.close()
        self.pad_down.clear()
        self.pad_axes.clear()
        time.sleep(1)

    def live_state(self, bits, axes):
        """One polled live state, mapped onto the js axes and button names the drawing uses."""
        lx, ly, rx, ry, rt, lt = axes
        stick = lambda v: max(-32767, min(32767, (v - 128) * 256))
        trig = lambda v: round(v / 255 * 65534) - 32767
        self.pad_axes.update({0: stick(lx), 1: stick(ly), 2: trig(lt), 3: stick(rx), 4: stick(ry), 5: trig(rt)})
        for bit, name in LIVE_BITS[self.model.key].items():
            self._pad_set(name, bool(bits & bit), False)

    def pad_event(self, value, kind, number):
        """One js_event: kind 1 = button, 2 = axis; bit 0x80 marks the initial-state burst (no ripple).

        Axes: 0/1 left stick, 2 LT, 3/4 right stick, 5 RT, 6/7 d-pad.
        """
        init = kind & JS_INIT
        kind &= ~JS_INIT & 0xFF
        if kind == JS_BUTTON and number < len(JS_BUTTONS):
            self._pad_set(JS_BUTTONS[number], value != 0, init)
        elif kind == JS_AXIS:
            self.pad_axes[number] = value
            if number == 6:
                self._pad_set("Left", value < 0, init)
                self._pad_set("Right", value > 0, init)
            elif number == 7:
                self._pad_set("Up", value < 0, init)
                self._pad_set("Down", value > 0, init)
            elif number in (2, 5):
                self._pad_set("LT" if number == 2 else "RT", value > 0, init)

    def _pad_set(self, name, down, init):
        if down and name not in self.pad_down and not init:
            self.press_t[name] = time.time()
        (self.pad_down.add if down else self.pad_down.discard)(name)
