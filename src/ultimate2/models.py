"""The controllers this tool speaks to. Everything that differs between them is a field here, so the rest of the
code asks ``model.leds`` (say) instead of which controller it is talking to. See ``docs/ULTIMATE_BT.md``."""
from dataclasses import dataclass

from . import config, protocol


@dataclass(frozen=True)
class Model:
    key: str                         # picks the drawing and the live-button map in the GUI
    name: str                        # on the home page
    short_name: str                  # in the window title
    cfg_size: int
    commit_key: int                  # sub-command of CMD_COMMIT that saves the record to flash
    buttons: tuple                   # physical buttons, in map_key order
    prefixed: bool = False           # frames carry their length after the report ID
    session: bool = False            # config requests are answered only while reports are off: opened before
                                     # reads, kept open after writes, closed by Device.leave()
    info_by_version: bool = False    # CMD_INFO goes unanswered: the firmware comes from the version query
    knock: bool = False              # reached from XInput with a rumble knock and handed back to XInput afterwards
    live_by_query: bool = False      # no gamepad reports in config mode: the live state is polled with CMD_LIVE
    whole_writes: bool = False       # always save the whole record (its app never writes a part of it)
    leds: bool = True
    gyro: bool = True
    xinput_rumble: bool = True
    pad_status: bool = True          # a 2.4G dongle can report the controller behind it


ULTIMATE2 = Model("ultimate2", "Ultimate 2 Wireless", "Ultimate 2", protocol.CFG_SIZE, protocol.COMMIT_KEY,
                  tuple(config.BUTTONS))
ULTIMATE_BT = Model("ultimate_bt", "Ultimate Bluetooth", "Ultimate Bluetooth", protocol.CFG_SIZE_BT,
                    protocol.COMMIT_KEY_BT, tuple(config.BUTTONS_BT), prefixed=True, session=True,
                    info_by_version=True, knock=True, live_by_query=True, whole_writes=True, leds=False, gyro=False,
                    xinput_rumble=False, pad_status=False)
MODELS = (ULTIMATE2, ULTIMATE_BT)


def for_pid(pid):
    """The model behind a config interface: the Ultimate Bluetooth's config-mode PID, else the Ultimate 2 family."""
    return ULTIMATE_BT if pid == protocol.PID_BT_CONFIG else ULTIMATE2
