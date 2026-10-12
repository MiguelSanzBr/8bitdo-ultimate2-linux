"""ultimate2 — open-source Linux configurator for the 8BitDo Ultimate 2 Wireless controller.

Package layout:

* :mod:`ultimate2.protocol`  — constants, CRC and the HID frame format (pure functions).
* :mod:`ultimate2.discovery` — finds the controller's config ``hidraw`` node and its joystick node.
* :mod:`ultimate2.device`    — :class:`~ultimate2.device.Device`, the transport (read/write/save, theme, slot).
* :mod:`ultimate2.config`    — the 1592-byte configuration record: decode to a dict, encode back.
* :mod:`ultimate2.cli`       — the ``u2ctl`` command.
* :mod:`ultimate2.gui`       — the ``u2gui`` Tk interface.
"""

__version__ = "0.1.0b2"
