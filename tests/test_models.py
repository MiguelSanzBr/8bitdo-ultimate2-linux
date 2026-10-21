"""models: one Model per controller, picked from the config interface PID."""
import pytest

from ultimate2 import config, models
from ultimate2.protocol import PID_BT_CONFIG, PIDS, PIDS_24G


@pytest.mark.parametrize("pid", [p for p in PIDS if p != PID_BT_CONFIG and p not in PIDS_24G])
def test_every_other_pid_is_the_ultimate2_family(pid):
    assert models.for_pid(pid) is models.ULTIMATE2


def test_the_config_mode_pid_is_the_ultimate_bluetooth():
    assert models.for_pid(PID_BT_CONFIG) is models.ULTIMATE_BT


@pytest.mark.parametrize("pid", PIDS_24G)
def test_the_cable_and_receiver_pids_are_the_ultimate_24g(pid):
    assert models.for_pid(pid) is models.ULTIMATE_24G


@pytest.mark.parametrize("m", models.MODELS, ids=lambda m: m.key)
def test_each_model_matches_its_record_layout(m):
    doc = config.decode(bytes(m.cfg_size), m.layout or None)
    assert tuple(b for b in doc["slots"][0]["mapping"] if b != "flag") == m.buttons
    assert m.leds == m.gyro == m.xinput_rumble == m.pad_status == ("sixaxis" in doc["slots"][0])
