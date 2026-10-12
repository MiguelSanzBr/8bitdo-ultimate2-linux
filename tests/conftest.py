import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fake_device import FakeController  # noqa: E402

BLANK_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "blank_config.bin")


@pytest.fixture
def fake(monkeypatch):
    f = FakeController().install(monkeypatch)
    yield f
    f.close()
