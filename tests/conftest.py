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


@pytest.fixture(autouse=True)
def no_real_hardware(request, monkeypatch, tmp_path):
    """Tests never see the controllers plugged into the machine running them (test_discovery sets its own roots):
    a switch to config mode must never reach a real pad."""
    from ultimate2 import discovery
    if request.module.__name__ != "test_discovery":
        monkeypatch.setattr(discovery, "SYS", str(tmp_path / "no-sys"))


@pytest.fixture(autouse=True)
def no_real_data_folder(monkeypatch, tmp_path):
    """u2gui keeps a copy of the Ultimate 2.4G's configuration in XDG_DATA_HOME: never the real one in tests."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
