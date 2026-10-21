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
    knock: str = ""                  # how it is reached from XInput and handed back afterwards: "rumble" (xpad force
                                     # feedback) or "usb" (the Windows connect sequence over usbfs); "" = never
    live_by_query: bool = False      # no gamepad reports in config mode: the live state is polled with CMD_LIVE
    whole_writes: bool = False       # always save the whole record (its app never writes a part of it)
    leds: bool = True
    gyro: bool = True
    xinput_rumble: bool = True
    pad_status: bool = True          # a 2.4G dongle can report the controller behind it
    header_crc: bool = True          # requests carry the CRC of their data (else that u16 is 0: a u32 length)
    reports: bool = True             # understands CMD_REPORT (input reports off/on)
    colorway: bool = True            # byte 6 of the version answer is the colorway (else it is the PID)
    echo_offset: bool = False        # answers echo the offset: late answers to a request that timed out are skipped
    own_slot: bool = False           # the firmware keeps its own cur_slot and stores a save counter in crc_value:
                                     # cur_slot is refreshed before writing and neither is compared after it
    save_wait: float = 3.0           # seconds for the CMD_COMMIT answer
    layout: str = ""                 # config record layout (config.LAYOUTS); "" picks it from the record size


ULTIMATE2 = Model("ultimate2", "Ultimate 2 Wireless", "Ultimate 2", protocol.CFG_SIZE, protocol.COMMIT_KEY,
                  tuple(config.BUTTONS))
ULTIMATE_BT = Model("ultimate_bt", "Ultimate Bluetooth", "Ultimate Bluetooth", protocol.CFG_SIZE_BT,
                    protocol.COMMIT_KEY_BT, tuple(config.BUTTONS_BT), prefixed=True, session=True,
                    info_by_version=True, knock="rumble", live_by_query=True, whole_writes=True, leds=False, gyro=False,
                    xinput_rumble=False, pad_status=False)
# its sibling, the Ultimate 2.4G: same record size and commit key, but no CRC in the request header, no CMD_REPORT
# and its own record details (see docs/ULTIMATE_24G.md)
ULTIMATE_24G = Model("ultimate_24g", "Ultimate 2.4G", "Ultimate 2.4G", protocol.CFG_SIZE_BT, protocol.COMMIT_KEY_BT,
                     tuple(config.BUTTONS_BT), prefixed=True, info_by_version=True, knock="usb", whole_writes=True,
                     leds=False, gyro=False, xinput_rumble=False, pad_status=False, header_crc=False, reports=False,
                     colorway=False, echo_offset=True, own_slot=True, save_wait=4.0, layout="ultimate_24g")
MODELS = (ULTIMATE2, ULTIMATE_BT, ULTIMATE_24G)


def for_pid(pid):
    """The model behind a config interface: the Ultimate Bluetooth's config-mode PID, the Ultimate 2.4G's PIDs, else
    the Ultimate 2 family."""
    if pid == protocol.PID_BT_CONFIG:
        return ULTIMATE_BT
    return ULTIMATE_24G if pid in protocol.PIDS_24G else ULTIMATE2
