# Contributing

Thanks for helping! Issues and pull requests are welcome, especially:

* reports from other controller editions (run `u2ctl info` and say which colour your controller is) and from the
  2.4G dongle;
* protocol findings, such as macro step data or unknown feature bits.

## Setup

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/python -m coverage run -m pytest && .venv/bin/python -m coverage report
```

GUI tests need an X display. On a headless machine, run them through `xvfb-run`.

## Rules

* Keep the standard-library-only runtime (Tk is part of Python).
* Every change keeps the test suite green at **100% line and branch coverage**. Use `tests/fake_device.py` instead of
  hardware, and extend it when you add a protocol command.
* Protocol knowledge goes into `docs/PROTOCOL.md` together with the code.
* Before writing to a real controller, back it up first with `u2ctl backup file.bin`.
* Commit messages: imperative mood, short subject line.
