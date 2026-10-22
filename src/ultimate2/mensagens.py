"""Brazilian Portuguese for ``u2ctl``: its messages stay in English in the code (``u2gui`` matches some of the device
errors by their words) and are translated when shown, following the system language like ``u2gui`` does."""
import re

from .gui.i18n import system_lang

LANG = None                      # None = the system language; tests set "en" or "pt"

EXACT = {
    # parser
    "Configure the 8BitDo Ultimate 2 Wireless (and the 1st-gen Ultimate Bluetooth, on a USB cable, and the Ultimate "
    "2.4G) on Linux.":
        "Configura o 8BitDo Ultimate 2 Wireless (e o Ultimate Bluetooth de 1ª geração, no cabo USB, e o Ultimate 2.4G) "
        "no Linux.",
    "hidraw node (default: auto-detect)": "nó hidraw (padrão: detecção automática)",
    "list detected devices": "lista os controles detectados",
    "firmware version and active slot": "versão do firmware e perfil ativo",
    "read config as JSON": "lê a configuração em JSON",
    "write edited JSON back": "grava de volta um JSON editado",
    "turn slot 0-2 into a custom profile with app defaults": "cria no perfil 0-2 um perfil com os padrões do app",
    "show or set the active LED theme": "mostra ou muda o tema de LED ativo",
    "battery of the controller over Bluetooth (Ultimate 2.4G)": "bateria do controle no Bluetooth (Ultimate 2.4G)",
    "keep Ultimate 2.4G pads on X read so they stay connected (systemd user service)":
        "mantém o Ultimate 2.4G no modo X sendo lido para não desligar (serviço de usuário do systemd)",
    "save raw config record": "salva a configuração bruta num arquivo",
    "write raw config record": "grava no controle uma configuração bruta",
    # argparse's own words
    "usage: ": "uso: ",
    "positional arguments": "argumentos",
    "options": "opções",
    "show this help message and exit": "mostra esta ajuda e sai",
    "the following arguments are required: %s": "faltam os argumentos: %s",
    "%(prog)s: error: %(message)s\n": "%(prog)s: erro: %(message)s\n",
    "invalid choice: %(value)r (choose from %(choices)s)": "opção inválida: %(value)r (escolha entre %(choices)s)",
    "unrecognized arguments: %s": "argumentos não reconhecidos: %s",
    # messages
    "Ultimate 2.4G over Bluetooth: no configuration channel there (use the cable or the receiver)":
        "Ultimate 2.4G no Bluetooth: por ali não dá para configurar (use o cabo ou o receptor)",
    "no 8BitDo controller reporting its battery: it is only known over Bluetooth (the 2.4G receiver does not report "
    "it)":
        "nenhum controle 8BitDo informando a bateria: ela só é conhecida pelo Bluetooth (o receptor 2.4G não a informa)",
    "warning: the controller is also connected over Bluetooth, which uses the D-mode configuration: changes made "
    "here (X mode) do not apply there":
        "atenção: o controle também está conectado pelo Bluetooth, que usa a configuração do modo D: o que for mudado "
        "aqui (modo X) não vale nele",
    "no answer from controller": "o controle não respondeu",
    "changed:": "alterado:",
    "(nothing)": "(nada)",
    "saved and verified": "salvo e verificado",
    "verify failed: controller config differs from what was written":
        "verificação falhou: a configuração do controle difere do que foi gravado",
    "this controller has no LED themes": "este controle não tem temas de LED",
    "verify failed: controller config differs from the backup":
        "verificação falhou: a configuração do controle difere do backup",
    "restored": "restaurado",
    # device errors
    "the Ultimate 2.4G did not switch to config mode (is the controller on and connected?)":
        "o Ultimate 2.4G não entrou no modo de configuração (o controle está ligado e conectado?)",
    "the Ultimate Bluetooth did not switch to config mode (if it turned off, press Home and try again)":
        "o Ultimate Bluetooth não entrou no modo de configuração (se ele desligou, aperte Home e tente de novo)",
    "the Ultimate 2.4G is connected over Bluetooth, which has no configuration channel: connect it with the USB "
    "cable or the 2.4G receiver":
        "o Ultimate 2.4G está conectado pelo Bluetooth, que não permite configurar: conecte-o pelo cabo USB ou pelo "
        "receptor 2.4G",
    "no 8BitDo config interface found (is the controller plugged in / paired?)":
        "nenhum controle 8BitDo configurável encontrado (ele está conectado?)",
    "controller did not confirm the save": "o controle não confirmou a gravação",
    "controller did not confirm the LED theme": "o controle não confirmou o tema de LED",
}

STATUS = {"discharging": "descarregando", "charging": "carregando", "full": "carregada",
          "not charging": "sem carregar", "unknown": "desconhecido"}

PATTERNS = [(re.compile(rx), pt) for rx, pt in (
    (r"^battery     (\d+)% \((.+)\)$", "bateria     {0}% ({1:status})"),
    (r"^(.+): (\d+)% \((.+)\)$", "{0}: {1}% ({2:status})"),
    (r"^(.+)  \(switched to config mode on use\)$", "{0}  (passa ao modo de configuração ao ser usado)"),
    (r"^device      (.+)$", "dispositivo {0}"),
    (r"^report pid  (.+)$", "pid         {0}"),
    (r"^mode/slot   (.+)$", "modo/perfil {0}"),
    (r"^controller  firmware (\S+), battery (\d+)%, colorway (\S+)$", "controle    firmware {0}, bateria {1}%, cor {2}"),
    (r"^unknown \((.*)\)$", "desconhecido ({0})"),
    (r"^saved (\d+) bytes to (.+)$", "{0} bytes salvos em {1}"),
    (r"^(.+): expected (\d+) bytes, got (\d+)$", "{0}: esperados {1} bytes, mas tem {2}"),
    (r"^cannot switch the (.+) to config mode via (.+) \((.+)\): install udev/70-8bitdo-u2.rules \(see README\) and "
     r"replug it$", "não foi possível pôr o {0} no modo de configuração por {1} ({2}): instale a regra "
     "udev/70-8bitdo-u2.rules (veja o README) e reconecte-o"),
    (r"^cannot switch the (.+) to config mode via (.+) \((.+)\)$",
     "não foi possível pôr o {0} no modo de configuração por {1} ({2})"),
    (r"^permission denied on (.+): install udev/70-8bitdo-u2.rules \(see README\)$",
     "sem permissão em {0}: instale a regra udev/70-8bitdo-u2.rules (veja o README)"),
    (r"^read failed at offset (\d+)$", "a leitura falhou na posição {0}"),
    (r"^write failed at offset (\d+)$", "a gravação falhou na posição {0}"),
)]


def tr(text):
    """``text`` in the user's language (English unless the system is in Portuguese)."""
    if (LANG or system_lang()) != "pt":
        return text
    if text in EXACT:
        return EXACT[text]
    for rx, pt in PATTERNS:
        m = rx.match(text)
        if m:
            groups = list(m.groups())
            for i in range(len(groups)):                # a "{n:status}" slot takes the battery status word
                if "{%d:status}" % i in pt:
                    pt = pt.replace("{%d:status}" % i, "{%d}" % i)
                    groups[i] = STATUS.get(groups[i], groups[i])
            return pt.format(*groups)
    return text
