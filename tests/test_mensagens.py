"""u2ctl in Brazilian Portuguese: its English messages translated when shown."""
import argparse
import os
import re

import pytest

from ultimate2 import cli, discovery, mensagens

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "ultimate2")


@pytest.fixture
def pt(monkeypatch):
    monkeypatch.setattr(mensagens, "LANG", "pt")


def test_follows_the_system_language(monkeypatch):
    monkeypatch.setattr(mensagens, "LANG", None)
    monkeypatch.setenv("LANGUAGE", "pt_BR:pt")
    assert mensagens.tr("restored") == "restaurado"
    monkeypatch.setenv("LANGUAGE", "en_US")
    assert mensagens.tr("restored") == "restored"


def test_exact_patterns_and_unknown(pt):
    t = mensagens.tr
    assert t("battery     91% (discharging)") == "bateria     91% (descarregando)"
    assert t("8BitDo Ultimate wireless: 80% (charging)") == "8BitDo Ultimate wireless: 80% (carregando)"
    assert t("8BitDo: 5% (odd state)") == "8BitDo: 5% (odd state)"          # unknown status word kept
    assert t("saved 1652 bytes to /x.bin") == "1652 bytes salvos em /x.bin"
    assert t("write failed at offset 45") == "a gravação falhou na posição 45"
    assert t("x.bin: expected 1652 bytes, got 1592") == "x.bin: esperados 1652 bytes, mas tem 1592"
    assert t("cannot switch the Ultimate 2.4G to config mode via /dev/bus/usb/003/009 ([Errno 13] Permission denied): "
             "install udev/70-8bitdo-u2.rules (see README) and replug it").startswith(
        "não foi possível pôr o Ultimate 2.4G no modo de configuração por /dev/bus/usb/003/009 ([Errno 13]")
    assert t("cannot switch the Ultimate Bluetooth to config mode via /dev/input/event7 (x)") == \
        "não foi possível pôr o Ultimate Bluetooth no modo de configuração por /dev/input/event7 (x)"
    assert t("something new") == "something new"
    assert t("controller  firmware 2.04, battery 50%, colorway 3") == "controle    firmware 2.04, bateria 50%, cor 3"


def test_every_exact_text_is_still_used():
    code = "".join(open(os.path.join(d, f)).read() for d, _s, fs in os.walk(SRC) for f in fs if f.endswith(".py")
                   and f != "mensagens.py")
    code = re.sub(r'"\s*\n\s*(?:f?)"', "", code)                # join implicitly concatenated literals
    stale = [k for k in mensagens.EXACT if k not in code and not k.startswith(("%", "usage", "positional", "options",
             "show this", "the following", "invalid choice", "unrecognized"))]
    assert stale == []


def test_cli_speaks_portuguese(pt, monkeypatch, capsys):
    monkeypatch.setattr(discovery, "find_devices", lambda: iter([]))
    monkeypatch.setattr(discovery, "find_bt_xinput", lambda: None)
    monkeypatch.setattr(discovery, "find_24g_xinput", lambda: "/dev/bus/usb/003/009")
    monkeypatch.setattr(discovery, "bluetooth_24g", lambda: True)
    cli.main(["list"])
    out = capsys.readouterr().out
    assert "(passa ao modo de configuração ao ser usado)" in out and "Ultimate 2.4G no Bluetooth" in out
    monkeypatch.setattr(discovery, "find_24g_xinput", lambda: None)
    with pytest.raises(SystemExit, match="está conectado pelo Bluetooth"):   # a device error, translated on the way out
        cli.main(["info"])
    with pytest.raises(SystemExit):
        cli.main(["restore"])
    assert "faltam os argumentos: file" in capsys.readouterr().err


def test_device_io_errors_translated_others_left_alone(pt, monkeypatch, tmp_path):
    def broken(argv):
        raise IOError("controller did not confirm the save")
    monkeypatch.setattr(cli, "_main", broken)
    with pytest.raises(SystemExit, match="o controle não confirmou a gravação"):
        cli.main([])

    def missing(argv):
        open(tmp_path / "nope")
    monkeypatch.setattr(cli, "_main", missing)
    with pytest.raises(FileNotFoundError):
        cli.main([])

    def numeric(argv):
        raise SystemExit(3)
    monkeypatch.setattr(cli, "_main", numeric)
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 3


def test_help_is_translated(pt, capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert out.startswith("uso: u2ctl") and "mostra esta ajuda e sai" in out and "opções:" in out
    assert "Configura o 8BitDo Ultimate 2 Wireless" in out and "bateria do controle no Bluetooth" in out
    assert argparse._ is mensagens.tr
