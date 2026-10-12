#!/usr/bin/env python3
"""Run ``u2ctl`` from a source checkout (after ``pip install .`` just use the ``u2ctl`` command)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from ultimate2.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
