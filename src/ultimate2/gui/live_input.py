"""Mixin: live input from the controller's joystick node (pressed buttons, triggers, sticks, d-pad)."""
import os
import struct
import time

from .. import discovery

JS_BUTTONS = ["A", "B", "X", "Y", "LB", "RB", "Select", "Start", "Home", "L3", "R3"]   # xpad js button order
JS_EVENT = "<IhBB"       # struct js_event: u32 time, s16 value, u8 type, u8 number
JS_BUTTON, JS_AXIS, JS_INIT = 1, 2, 0x80


class PadInput:
    def _read_pad(self):
        """Background thread: follow the real controller's buttons/axes; reconnects every second."""
        while not self._closing:
            node = None
            try:
                dev = next(discovery.find_devices(), None)
                node = dev and discovery.find_input_node(dev[2])
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
