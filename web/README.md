# 8BitDo Ultimate 2 no navegador

*English: [README.en.md](README.en.md)*

Configurador do controle **8BitDo Ultimate 2** direto no navegador, via WebHID. Lê a configuração, remapeia botões
(inclusive as borboletas de trás e o L4/R4), ajusta analógicos e gatilhos, troca o tema e a cor dos LEDs e grava na
flash do controle, conferindo tudo numa releitura.

## Por quê

O *8BitDo Ultimate Software* só existe pra Windows e macOS. Pra usar o controle no Linux eu fiz engenharia reversa do
protocolo e escrevi o [8bitdo-ultimate2-linux](https://github.com/MiguelSanzBr/8bitdo-ultimate2-linux) (CLI `u2ctl` e
interface gráfica `u2gui`, em Python). Esse projeto é a mesma coisa no navegador: nada pra instalar além da regra udev,
e o protocolo é uma porta fiel do código Python.

Sem vínculo com a 8BitDo. O protocolo foi obtido por engenharia reversa pra interoperabilidade.

## Arquitetura

DDD + hexagonal, sem cerimônia: o núcleo não sabe q existe React, DOM, `navigator` ou WebHID.

```
adapters/      ui/ (React)   webhid.ts   gamepad-drain.ts   demo.ts
                    │ chama caso de uso       │ implementa os ports
                    ▼                         ▼
application/   ConfigSession, ControllerLink    ports: ReportChannel, InputDrain
                    │
                    ▼
domain/        ConfigRecord, value objects, packet.ts, record.ts   (puro, sem I/O)
```

- **domain/**: funções puras. `packet.ts` é o framing (porta do `protocol.py`), `record.ts` é o codec do registro de
  1592 bytes (porta do `config.py`), `config-record.ts` é o agregado com as invariantes (sempre 1592 bytes, CRC tem q
  bater antes de qualquer escrita), `values.ts` tem as faixas e nomes e `live-input.ts` traduz o Gamepad API pro desenho.
- **application/**: os casos de uso e os ports. `ControllerLink` é a porta do `device.py` (pedido/resposta, pedaços de
  45 bytes, 30 tentativas, commit) em cima do port `ReportChannel`. O dreno do joystick também é port (`InputDrain`),
  quem liga e desliga é a `ConfigSession`.
- **adapters/**: WebHID, o `GamepadDrain`, o controle simulado do modo demo e a tela React, q só chama caso de uso.

Por quê: o protocolo é a parte cara de acertar e a q não pode quebrar. Deixando ele puro dá pra testar byte a byte
contra o Python sem navegador, e trocar o transporte (WebHID, demo, quem sabe WebUSB) sem encostar no núcleo.
A regra de dependência é cobrada pelo ESLint (`no-restricted-imports` e `no-restricted-globals` por pasta) e por um
teste (`src/architecture.test.ts`) q confere q a regra pega cada violação.

## Como funciona

O canal de config é uma coleção HID vendor (usage page `0xFF7A` no controle, `0xFFA0` no dongle 2.4G) com report de
saída `0x81` e de entrada `0x02`, 64 bytes contando o id. Pedido `81 04` + cabeçalho (`cmd`, `sub`, `len`,
CRC-16/MODBUS dos dados, `total`, `offset`), resposta `02 04` ecoando o comando. O registro inteiro tem 1592 bytes
(3 perfis, mapeamento, analógicos, gatilhos, giroscópio, LEDs, macros) e trafega em pedaços de 45. O detalhe tá no
[docs/PROTOCOL.md](https://github.com/MiguelSanzBr/8bitdo-ultimate2-linux/blob/main/docs/PROTOCOL.md) do repo Linux.

IDs filtrados no seletor do Chrome: VID `0x2DC8`, PIDs `0x310B` (cabo, XInput), `0x6012` (Ultimate 2) e `0x6013`
(dongle 2.4G), nas duas usage pages de config.

### A pegadinha do XInput

O firmware só atende o endpoint de config enquanto o host vai drenando os reports de joystick do controle. No Windows
o driver XInput faz isso sozinho. No Linux o `xpad` só faz polling se alguém tá com o `/dev/input/js*` aberto, então o
Python abre esse nó durante todo o I/O de config (`discovery.find_input_node`). Sem isso a escrita trava e só
reconectando o cabo volta.

No navegador não tem como abrir o `js*`. A aposta aqui: enquanto a sessão de config tá aberta, a página fica chamando
`navigator.getGamepads()` a cada 16 ms (`GamepadDrain`, com `setInterval` pq `requestAnimationFrame` para com a aba em
segundo plano), e o Chrome, pra responder isso, mantém o joystick aberto e lido. O dreno liga **antes** de abrir o canal
e desliga no disconnect. Se o controle não responder, a tela pede pra mexer um analógico ou apertar um botão e, se
continuar, reconectar o controle.

**Isso é hipótese.** Não foi validado com o controle de verdade. No Windows a expectativa é q o próprio driver XInput
já faça o polling e o dreno nem seja necessário, mas isso também não foi conferido.

### Botões acendendo ao vivo

Igual o app desktop: aperte os botões do controle e eles acendem no desenho. O botão fica roxo e afunda rápido, apaga
devagar ao soltar; o gatilho enche conforme a pressão e o analógico mostra pra onde o dedão foi. Com
`prefers-reduced-motion` só muda a cor.

Reaproveita o polling do dreno: o `GamepadDrain` passa o `getGamepads()` pelo `readPad` do domain (`live-input.ts`,
layout `standard` do W3C, q é por posição e por isso vale pro XInput e pro Switch) e só avisa quando algo muda. A tela
redesenha só o controle, no máximo uma vez por quadro (`requestAnimationFrame`). Na tela inicial o desenho também acende
se o navegador já enxerga o controle, mesmo sem WebHID. No modo demo, segurar o clique numa parte do desenho simula o
aperto.

Limites do Gamepad API:

- PL/PR, L4/R4 e o ★ não aparecem no Gamepad API, então não acendem. Não tem simulação disso.
- O Chrome só expõe o gamepad depois do primeiro botão apertado com a página aberta, daí a dica embaixo do desenho.
- Acende o q o controle manda, já com o remapeamento do perfil: com A mapeado pra B, o esperado é apertar o A e acender o B.
- Sem o mapping `standard` (driver q o Chrome não reconhece) nada acende, melhor q acender o botão errado.
- O 8BitDo é achado pelo vendor `2dc8` no `id`; sem ele vale o primeiro gamepad conectado.

### Segurança da gravação

1. Conectar já lê tudo primeiro (info, registro, tema). Dá pra baixar o backup `.bin` (mesmo formato do `u2ctl backup`,
   restaura com `u2ctl restore`).
2. Edição fica só na tela. Nada vai pro controle até a revisão.
3. "Revisar e gravar" monta o plano: o encode só regrava o campo q mudou (byte desconhecido volta igual), confere as
   faixas (analógico 0 a 128, gatilho 0 a 255, função de botão conhecida, cor `#rrggbb`) e recalcula o `crc_value`.
4. Um diálogo lista cada mudança (antes → depois). Só o botão "Gravar no controle" confirma o plano, e a confirmação
   vale uma vez.
5. Antes de escrever, o agregado confere tamanho e CRC. Registro q não valida não sai.
6. Escreve, manda o commit `0x123` pra flash, relê os 1592 bytes e compara. Diferente vira erro e o tema nem é mexido.

## Testes

Vitest + Testing Library (unitário e tela) e Playwright (E2E do modo demo). TDD de verdade: no histórico cada unidade
tem o commit `Teste: ...` com o teste falhando antes do commit da implementação, e as mudanças de estrutura estão em
commits `Refatoração: ...` com tudo verde antes e depois. Os bytes esperados vieram de rodar o código Python
(commit `af02fde`) e estão colados como literal, cada um com um comentário dizendo qual função ele espelha.

| Garantia | Teste |
|---|---|
| CRC-16/MODBUS, montagem de pedido e leitura de resposta batem byte a byte com o Python | `src/domain/packet.test.ts` |
| decode/encode do registro igual ao Python (perfil novo, remapeamento, nome, features, cor, CRC) | `src/domain/record.test.ts` |
| encode sem edição devolve os mesmos bytes; editar só mexe no campo | `record.test.ts` (20 registros aleatórios) |
| registro com CRC ou tamanho errado nunca é gravado | `config-record.test.ts`, `config-session.test.ts` "nunca grava registro com CRC errado" |
| valor fora da faixa é barrado antes de virar byte | `values.test.ts`, `config-record.test.ts`, `App.test.tsx` |
| nada é gravado sem confirmação; confirmação vale uma vez | `config-session.test.ts` "sem confirmação não grava nada", `App.test.tsx` "nada sai pro controle antes da confirmação" |
| releitura diferente do q foi gravado vira erro | `config-session.test.ts` (`corruptCommit`), `App.test.tsx` |
| dreno liga antes do canal, fica ligado a sessão toda e desliga no fim | `config-session.test.ts` "Connect", `gamepad-drain.test.ts` com `getGamepads` falso |
| sem dreno o controle simulado fica mudo e a tela explica o q fazer | `demo.test.ts`, `App.test.tsx` "controle mudo" |
| retry de 30 tentativas, timeout e commit, igual o `device.py` | `src/application/link.test.ts` |
| WebHID: filtros VID/PID/usage page, report id separado, erro de abertura cita a regra udev | `src/adapters/webhid.test.ts` |
| Gamepad API vira o desenho aceso: layout standard por posição, gatilho analógico, zona morta, vendor 2dc8 | `src/domain/live-input.test.ts` |
| dreno só avisa quando muda; tela acende no hero, conectada e no demo com o ponteiro | `gamepad-drain.test.ts`, `App.test.tsx` "botões acendendo ao vivo", `e2e/demo.spec.ts` |
| domain e application não importam adapter, React nem DOM | `src/architecture.test.ts` + ESLint |
| fluxo completo no Chrome: demo, ler, remapear, confirmar, ver aplicado; 375px sem rolagem lateral | `e2e/demo.spec.ts` |

### Cobertura

Cobertura v8 com threshold de 100% em statements, branches, functions e lines sobre `src/`; abaixo disso o
`npm run coverage` falha e o CI cai. Resultado atual: 182 testes, statements 871/871, branches 464/464,
functions 258/258, lines 703/703.

Fora da cobertura, cada um com o motivo no `vite.config.ts`:

- `src/main.tsx`: bootstrap, só monta o `<App/>` no `#root`; quem cobre é o E2E.
- `src/application/ports.ts` e `src/domain/types.ts`: só declaram tipo, não sobra JS pra medir.
- `src/vite-env.d.ts`: referência de tipos do Vite.
- `src/test/**` e os próprios `*.test.*`.

### Teste de mutação (manual)

Quebrei de propósito as proteções principais, rodei a suíte e restaurei:

| Mutação | Resultado |
|---|---|
| `recordProblem` aceita qualquer CRC | 3 testes falharam (`record`, `config-record`, `config-session`) |
| `applyChanges` ignora a confirmação | 2 testes falharam (`config-session`) |
| tela grava direto no "Revisar e gravar", sem o diálogo | 6 testes falharam (`App.test.tsx`) |
| `ConfigSession.connect` não liga o dreno | 35 testes falharam (sessão, tela, composição) |
| import de adapter dentro de `domain/` | ESLint acusou `no-restricted-imports` |

## Rodando

Precisa de Node 24.

```bash
npm install
npm run dev          # http://localhost:5176/8bitdo-ultimate2-linux/
npm run lint && npm run typecheck
npm run coverage     # falha abaixo de 100%
npm run e2e          # build + preview na 4176 + Playwright (chromium)
npm run build
docker compose up --build   # site buildado no nginx em http://localhost:8090/8bitdo-ultimate2-linux/
```

O deploy no GitHub Pages tá em `../.github/workflows/pages.yml` (base `/8bitdo-ultimate2-linux/`).

### Linux: regra udev

O Chrome abre o controle pelo hidraw, e sem permissão o `open()` falha. Instale a mesma regra do repo Linux e
reconecte o controle:

```bash
echo 'KERNEL=="hidraw*", ATTRS{idVendor}=="2dc8", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/70-8bitdo-u2.rules
sudo udevadm control --reload && sudo udevadm trigger --action=add --subsystem-match=hidraw
```

O nome começa com `70-` pq tem q vir antes do `73-seat-late.rules`, q transforma o `uaccess` em ACL.

## O q foi portado e o q não foi

Portado: framing e CRC, codec completo do registro (todos os campos decodificam e voltam iguais, inclusive macro e
giroscópio), padrões de perfil novo do app, info (firmware, beta, PID), tema de LED, leitura e escrita com retry e
commit, verificação por releitura, backup `.bin`.

Editável na tela: perfis (criar com os padrões do app, renomear), os 22 botões, zona morta e alcance dos analógicos,
faixas dos gatilhos, as 8 opções (inverter eixos, trocar analógicos/gatilhos/d-pad, vibração nos gatilhos), tema de LED
e as cores do tema dynamic.

A tela segue o layout do app desktop: o mesmo desenho do controle (portado do `geometry.py` pra SVG) com legendas
clicáveis q levam pro campo, um bloco por categoria (Botões, Analógicos, Gatilhos, LEDs, Perfil), abas de perfil no
topo e uma barra com o número de alterações staged. Tema claro e escuro, segue o sistema e tem botão pra trocar.
Com alteração staged o navegador pergunta antes de fechar ou recarregar a aba, e dá pra usar tudo pelo teclado (Tab
mostra o foco, tem link pra pular pro conteúdo e a revisão prende o foco no diálogo).

Não portado (o byte é preservado, só não tem tela): editor de macros, giroscópio (six-axis), força da vibração,
faixa da vibração dos gatilhos, cores do hotwheel e dos 24 LEDs do custom, troca do `gamepad_mode`. Também ficaram de
fora: consulta de edição/cor (`81 05`), status do controle atrás do dongle (bateria), polling do perfil ativo, restaurar
backup (use o `u2ctl restore`), escrita parcial (`changed_span`, aqui grava o registro
inteiro como o `u2ctl apply`) e interface em inglês.

## Limitações conhecidas

- Só Chrome e Edge no desktop (WebHID). Nos outros a página avisa e oferece o modo demo.
- O dreno via `getGamepads()` é hipótese e **não foi validado no hardware**. O Chrome pode só expor o gamepad depois de
  um botão apertado, e com a aba em segundo plano o `setInterval` é limitado a 1 vez por segundo. Se travar, reconecte.
- **Essa versão web ainda não rodou contra o controle de verdade.** Tudo foi testado contra o controle simulado, q é
  porta do `tests/fake_device.py` do Python. O protocolo em si foi verificado no hardware (firmware 1.10, cabo) pelo
  projeto Linux.
- Os botões acendendo ao vivo só foram testados com `getGamepads()` falso (unitário e E2E), **não com o controle de
  verdade**. O mapping `standard` no modo Switch e o índice do Home dependem do Chrome reconhecer o controle.
- Dongle 2.4G: nem o projeto Linux testou ainda.
- Como no Python, a resposta é casada só pelo comando, não pelo offset. Uma resposta atrasada de outro pedaço pode
  entrar no lugar errado; a releitura final pega isso na gravação, mas não na leitura inicial.
- Diferenças em relação ao Python, de propósito: faixas conferidas antes do encode, nome q não cabe em 32 bytes é
  recusado (no Python o `bytearray` cresceria e o `assert` do `write_config` barraria), e os reports são religados mesmo
  quando um pedaço da escrita falha.
- Arredondamento do float da vibração em empate exato (ex. `0.03125`) dá `0.0313` aqui e `0.0312` no `round()` do
  Python. Só afeta a exibição; byte não editado volta igual.

## Licença

[MIT](LICENSE), Copyright (c) 2026 Miguel Sanz Boragan.
