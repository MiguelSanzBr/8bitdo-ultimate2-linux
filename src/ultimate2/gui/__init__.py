"""``u2gui`` — Tk interface. :class:`ultimate2.gui.app.App` is assembled from small mixins:

* :mod:`.pages`       — layout helpers and the section pages
* :mod:`.controller`  — the controller drawing, its animation and the mapping highlight
* :mod:`.editor`      — config dict <-> widget values, LED colour targets
* :mod:`.sync`        — device I/O on a worker thread: read, auto-save, polling, theme, backup/restore
* :mod:`.live_input`  — live joystick input (pressed buttons, sticks, triggers)

Shared building blocks live in :mod:`.theme`, :mod:`.catalog`, :mod:`.geometry`, :mod:`.drawing` and
:mod:`.widgets`.
"""
