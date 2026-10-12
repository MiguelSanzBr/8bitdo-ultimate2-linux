#!/usr/bin/env python3
"""Run ``u2gui`` from a source checkout (after ``pip install .`` just use the ``u2gui`` command)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from ultimate2.gui.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
