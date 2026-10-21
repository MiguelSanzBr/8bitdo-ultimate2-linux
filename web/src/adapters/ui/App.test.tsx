import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from './App'
import type { Wiring } from './wiring'
import { ConfigSession } from '../../application/config-session'
import type { InputDrain } from '../../application/ports'
import { DemoTransport } from '../demo'
import { decode, encode } from '../../domain/record'
import { CMD_GET_THEME, CMD_WRITE } from '../../domain/packet'
import { IDLE } from '../../domain/live-input'
import type { LiveInput } from '../../domain/live-input'

const FAST = { timeoutMs: 15, commitTimeoutMs: 15, settleMs: 0 }

function setup(over: Partial<Wiring> = {}, t = new DemoTransport()) {
  const wiring: Wiring = {
    supported: true,
    openDemo: () => ({ session: new ConfigSession(t, t, FAST), demo: true }),
    openReal: async () => null,
    onInput: () => () => {},
    ...over,
  }
  const user = userEvent.setup()
  render(<App wiring={wiring} />)
  return { t, user }
}

async function demo(t = new DemoTransport()) {
  const ctx = setup({}, t)
  await ctx.user.click(screen.getByRole('button', { name: 'Abrir modo demo' }))
  await screen.findByText('Configuração lida do controle.')
  return ctx
}

const status = () => screen.getByRole('status')
const wrote = (t: DemoTransport) => t.log.some(([c]) => c === CMD_WRITE)
const tile = (name: string) => screen.getByRole('button', { name })
const bar = () => screen.queryByRole('region', { name: 'Alterações pendentes' })
const changes = () => within(screen.getByRole('dialog')).getAllByRole('listitem').map((li) => (li.textContent as string).replace(/\s+/g, ' ').trim())

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  delete document.documentElement.dataset.theme
})

describe('tela inicial', () => {
  it('navegador sem WebHID: aviso, conectar desabilitado apontando pro aviso, demo disponível', () => {
    setup({ supported: false })
    expect(screen.getByRole('alert')).toHaveTextContent(/Chrome ou Edge/)
    const connect = screen.getByRole('button', { name: 'Conectar controle' })
    expect(connect).toBeDisabled()
    expect(connect).toHaveAccessibleDescription(/Chrome ou Edge/)
    expect(screen.getByRole('button', { name: 'Abrir modo demo' })).toBeEnabled()
  })

  it('mostra o desenho do controle e explica a regra udev do Linux', () => {
    setup()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('8BitDo Ultimate 2 no navegador')
    expect(document.querySelector('svg.pad')).not.toBeNull()
    expect(screen.getByText(/ATTRS\{idVendor\}=="2dc8"/)).toBeInTheDocument()
  })

  it('cancelar o seletor do Chrome só avisa', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: 'Conectar controle' }))
    expect(await screen.findByText('Nenhum controle escolhido. Clique em Conectar controle de novo e escolha o 8BitDo na lista.')).toBeInTheDocument()
  })

  it('controle mudo: pede pra mexer um analógico ou reconectar', async () => {
    const t = new DemoTransport()
    const dead: InputDrain = { start: () => {}, stop: () => {}, running: false, onInput: () => () => {} }
    const { user } = setup({ openReal: async () => ({ session: new ConfigSession(t, dead, FAST), demo: false }) })
    await user.click(screen.getByRole('button', { name: 'Conectar controle' }))
    expect(await screen.findByText(/Mexa um analógico/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Conectar controle' })).toBeEnabled()
  })

  it('erro ao abrir aparece como veio (ex. falta da regra udev)', async () => {
    const t = new DemoTransport()
    t.open = () => Promise.reject(new Error('precisa da regra udev'))
    const { user } = setup({ openReal: async () => ({ session: new ConfigSession(t, t, FAST), demo: false }) })
    await user.click(screen.getByRole('button', { name: 'Conectar controle' }))
    expect(await screen.findByText('precisa da regra udev')).toBeInTheDocument()
  })

  it('controle de verdade conectado não mostra a faixa de demo', async () => {
    const t = new DemoTransport()
    const { user } = setup({ openReal: async () => ({ session: new ConfigSession(t, t, FAST), demo: false }) })
    await user.click(screen.getByRole('button', { name: 'Conectar controle' }))
    await screen.findByText('Configuração lida do controle.')
    expect(screen.queryByText(/Modo demo/)).toBeNull()
    expect(screen.getByText('Conectado via WebHID')).toBeInTheDocument()
    await user.click(tile('Perfil'))
    expect(screen.getByText(/lendo o joystick/)).toBeInTheDocument()
  })
})

describe('tema claro e escuro', () => {
  it('a cor da barra do navegador (theme-color) acompanha o botão', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    document.head.innerHTML = '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#f5f4f8"><meta name="theme-color" media="(prefers-color-scheme: dark)" content="#141416">'
    const metas = () => [...document.querySelectorAll('meta[name="theme-color"]')].map((m) => m.getAttribute('content'))
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: 'Mudar tema' }))
    expect(metas()).toEqual(['#141416', '#141416'])
    await user.click(screen.getByRole('button', { name: 'Mudar tema' }))
    expect(metas()).toEqual(['#f5f4f8', '#f5f4f8'])
    document.head.innerHTML = ''
  })

  it('segue o sistema até a pessoa trocar no botão', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q === '(prefers-color-scheme: dark)' }))
    const { user } = setup()
    const toggle = screen.getByRole('button', { name: 'Mudar tema' })
    expect(document.documentElement.dataset.theme).toBeUndefined()
    await user.click(toggle)
    expect(document.documentElement.dataset.theme).toBe('light')
    await user.click(toggle)
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})

describe('modo demo', () => {
  it('deixa claro q é simulado e mostra as infos do controle', async () => {
    const { user } = await demo()
    expect(screen.getByText(/Modo demo/)).toBeInTheDocument()
    expect(screen.getByText('Perfil ativo no controle: Perfil 1')).toBeInTheDocument()
    expect(screen.getByText('Controle simulado')).toBeInTheDocument()
    expect(screen.getByText('firmware 1.10')).toBeInTheDocument()
    await user.click(tile('Perfil'))
    const info = within(screen.getByRole('region', { name: 'Controle' }))
    expect(info.getByText('1.10')).toBeInTheDocument()
    expect(info.getByText('0x6012 (Ultimate 2)')).toBeInTheDocument()
    expect(info.getByText('Windows (XInput)')).toBeInTheDocument()
    expect(info.getByText('Perfil 1')).toBeInTheDocument()
    expect(info.getByText('Dinâmico')).toBeInTheDocument()
  })

  it('firmware beta, perfil padrão e tema desconhecido', async () => {
    const t = new DemoTransport()
    t.beta = 2
    t.theme = 9
    t.reportPid = 0x1234
    t.cfg[18] = 3
    const { user } = await demo(t)
    expect(screen.getByText('Perfil ativo no controle: padrão (sem perfil custom)')).toBeInTheDocument()
    await user.click(tile('Perfil'))
    const info = within(screen.getByRole('region', { name: 'Controle' }))
    expect(info.getByText('1.10 beta 2')).toBeInTheDocument()
    expect(info.getByText('0x1234 (?)')).toBeInTheDocument()
    expect(info.getByText('padrão (sem perfil custom)')).toBeInTheDocument()
    expect(info.getByText('desconhecido')).toBeInTheDocument()
  })

  it('tema q o controle não informa aparece como desconhecido', async () => {
    const t = new DemoTransport()
    t.silent.add(CMD_GET_THEME)
    const { user } = await demo(t)
    await user.click(tile('Perfil'))
    expect(within(screen.getByRole('region', { name: 'Controle' })).getByText('desconhecido')).toBeInTheDocument()
  })
})

describe('categorias e desenho', () => {
  it('abre em Botões e cada bloco troca o painel', async () => {
    const { user } = await demo()
    expect(tile('Botões')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('region', { name: 'Botões' })).toBeInTheDocument()
    for (const name of ['Analógicos', 'Gatilhos', 'LEDs', 'Perfil']) {
      await user.click(tile(name))
      expect(tile(name)).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByRole('region', { name })).toBeInTheDocument()
    }
    expect(tile('Botões')).toHaveAttribute('aria-pressed', 'false')
  })

  it('só mostra categoria q a versão web edita (sem giroscópio nem macro)', async () => {
    await demo()
    const names = within(screen.getByRole('group', { name: 'Categorias' })).getAllByRole('button').map((b) => b.textContent)
    expect(names).toEqual(['Botões', 'Analógicos', 'Gatilhos', 'LEDs', 'Perfil'])
  })

  it.each([
    ['Botões ABXY', 'Botões', 'A'], ['LB', 'Botões', 'LB'], ['L4', 'Botões', 'L4 (P3)'], ['R4', 'Botões', 'R4 (P4)'],
    ['D-pad', 'Botões', 'Up'], ['Traseiros PL / PR', 'Botões', 'PR (P1)'], ['Analógico esquerdo', 'Analógicos', 'LS zona morta'],
    ['Analógico direito', 'Analógicos', 'RS zona morta'], ['LT', 'Gatilhos', 'LT início'], ['RT', 'Gatilhos', 'RT início'],
  ])('legenda %s leva pro campo certo', async (callout, panel, field) => {
    const { user } = await demo()
    await user.click(tile('LEDs'))
    await user.click(screen.getByRole('button', { name: callout }))
    expect(tile(panel)).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText(field)).toHaveFocus()
  })

  it('legenda num perfil vazio só abre o painel', async () => {
    const { user } = await demo()
    await user.click(screen.getByRole('button', { name: 'Perfil 2' }))
    await user.click(screen.getByRole('button', { name: 'LT' }))
    expect(within(screen.getByRole('region', { name: 'Gatilhos' })).getByText(/perfil tá vazio/)).toBeInTheDocument()
  })
})

describe('remapear e gravar', () => {
  it('nada sai pro controle antes da confirmação; depois grava e confere', async () => {
    const { t, user } = await demo()
    await user.selectOptions(screen.getByLabelText('A'), 'B')
    await user.click(screen.getByRole('button', { name: 'Revisar e gravar' }))
    const dialog = screen.getByRole('dialog', { name: 'Confirmar gravação' })
    expect(changes()).toEqual(['Perfil 1 · mapping/A A → B'])
    expect(wrote(t)).toBe(false)
    await user.click(within(dialog).getByRole('button', { name: 'Gravar no controle' }))
    expect(await screen.findByText('Gravado na flash e conferido na releitura.')).toBeInTheDocument()
    expect(decode(t.cfg).slots[0].mapping.A).toBe('B')
    expect(screen.getByLabelText('A')).toHaveValue('B')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(bar()).toBeNull()
  })

  it('cancelar ou Esc fecha a revisão sem gravar', async () => {
    const { t, user } = await demo()
    await user.selectOptions(screen.getByLabelText('B'), 'A')
    await user.click(screen.getByRole('button', { name: 'Revisar e gravar' }))
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Revisar e gravar' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(wrote(t)).toBe(false)
  })

  it('barra de alterações conta o q tá staged e some quando volta pro lido', async () => {
    const { user } = await demo()
    expect(bar()).toBeNull()
    expect(screen.queryByRole('button', { name: 'Revisar e gravar' })).toBeNull()
    await user.selectOptions(screen.getByLabelText('A'), 'B')
    expect(bar()).toHaveTextContent('1 alteração')
    expect(screen.getByLabelText('A').closest('.remap')).toHaveAttribute('data-changed')
    expect(screen.getByLabelText('B').closest('.remap')).not.toHaveAttribute('data-changed')
    await user.selectOptions(screen.getByLabelText('B'), 'A')
    await user.click(tile('LEDs'))
    await user.click(screen.getByLabelText('Desligado'))
    expect(bar()).toHaveTextContent('3 alterações')
    await user.click(tile('Botões'))
    await user.selectOptions(screen.getByLabelText('A'), 'A')
    await user.selectOptions(screen.getByLabelText('B'), 'B')
    await user.click(tile('LEDs'))
    await user.click(screen.getByLabelText('Dinâmico'))
    expect(bar()).toBeNull()
  })

  it('releitura diferente vira erro na tela', async () => {
    const { t, user } = await demo()
    t.corruptCommit = true
    await user.selectOptions(screen.getByLabelText('X'), 'Y')
    await user.click(screen.getByRole('button', { name: 'Revisar e gravar' }))
    await user.click(screen.getByRole('button', { name: 'Gravar no controle' }))
    expect(await screen.findByText(/Conferência falhou/)).toBeInTheDocument()
  })

  it('código desconhecido lido do controle continua como opção', async () => {
    const t = new DemoTransport()
    const doc = decode(t.cfg)
    doc.slots[0].mapping.P1 = '0x00077777'
    t.cfg = encode(doc, t.cfg).record
    await demo(t)
    expect(screen.getByLabelText('PR (P1)')).toHaveValue('0x00077777')
  })
})

describe('perfis', () => {
  it('abas no topo, ponto no perfil ativo do controle', async () => {
    await demo()
    const tabs = within(screen.getByRole('group', { name: 'Perfis' }))
    expect(tabs.getByRole('button', { name: 'Perfil 1' })).toHaveAttribute('aria-pressed', 'true')
    expect(tabs.getByRole('button', { name: 'Perfil 1' }).querySelector('.dot')).not.toBeNull()
    expect(tabs.getByRole('button', { name: 'Perfil 2' }).querySelector('.dot')).toBeNull()
  })

  it('perfil vazio: cria com os padrões do app e renomeia', async () => {
    const { user } = await demo()
    await user.click(screen.getByRole('button', { name: 'Perfil 2' }))
    expect(screen.getByRole('button', { name: 'Perfil 2' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByLabelText('A')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Criar com os padrões do app' }))
    expect(screen.getByLabelText('A')).toBeInTheDocument()
    await user.click(tile('Perfil'))
    const name = screen.getByLabelText('Nome do perfil')
    expect(name).toHaveValue('Perfil 2')
    await user.clear(name)
    await user.type(name, 'Linux')
    await user.click(screen.getByRole('button', { name: 'Revisar e gravar' }))
    expect(changes()).toContain('Perfil 2 · name → Linux')
  })
})

describe('analógicos, gatilhos e LED', () => {
  it('valor fora da faixa trava a gravação e mostra o problema', async () => {
    const { t, user } = await demo()
    await user.click(tile('Analógicos'))
    const dz = screen.getByLabelText('LS zona morta (valor)')
    await user.clear(dz)
    await user.type(dz, '200')
    expect(bar()).toHaveTextContent('0 a 128')
    expect(screen.getByRole('button', { name: 'Revisar e gravar' })).toBeDisabled()
    expect(wrote(t)).toBe(false)
  })

  it('deslizante e caixa de número mexem no mesmo valor', async () => {
    const { user } = await demo()
    await user.click(tile('Analógicos'))
    fireEvent.change(screen.getByLabelText('RS alcance'), { target: { value: '100' } })
    expect(screen.getByLabelText('RS alcance (valor)')).toHaveValue(100)
  })

  it('gatilho e features entram no plano', async () => {
    const { user } = await demo()
    await user.click(tile('Gatilhos'))
    const lt = screen.getByLabelText('LT fim (valor)')
    await user.clear(lt)
    await user.type(lt, '200')
    await user.click(screen.getByRole('switch', { name: 'Trocar gatilhos' }))
    await user.click(screen.getByRole('switch', { name: 'Trocar gatilhos' }))
    await user.click(tile('Analógicos'))
    await user.click(screen.getByRole('switch', { name: 'Inverter LS Y' }))
    await user.click(screen.getByRole('button', { name: 'Revisar e gravar' }))
    expect(changes()).toContain('Perfil 1 · triggers/left_end 255 → 200')
    expect(changes()).toContain('Perfil 1 · special/features → invert_LS_Y')
  })

  it('features em formato desconhecido não ficam editáveis', async () => {
    const t = new DemoTransport()
    const doc = decode(t.cfg)
    doc.slots[0].special.features = '0xffffffff'
    t.cfg = encode(doc, t.cfg).record
    const { user } = await demo(t)
    await user.click(tile('Analógicos'))
    expect(screen.queryByRole('switch')).toBeNull()
    expect(screen.getByText(/0xffffffff/)).toBeInTheDocument()
    await user.click(tile('Gatilhos'))
    expect(screen.queryByRole('switch')).toBeNull()
  })

  it('tema e cor dynamic entram na revisão e são aplicados', async () => {
    const { t, user } = await demo()
    await user.click(tile('LEDs'))
    expect(screen.getByLabelText('Dinâmico')).toBeChecked()
    await user.click(screen.getByLabelText('Desligado'))
    // input type=color não aceita digitação no jsdom, vai pelo evento
    fireEvent.input(screen.getByLabelText('Cor do efeito'), { target: { value: '#00ff00' } })
    await user.click(screen.getByRole('button', { name: 'Fundo do efeito: #0a84ff' }))
    expect(screen.getByLabelText('Fundo do efeito')).toHaveValue('#0a84ff')
    await user.click(screen.getByRole('button', { name: 'Revisar e gravar' }))
    expect(changes()).toContain('Tema de LED Dinâmico → Desligado')
    expect(changes()).toContain('Perfil 1 · led_dynamic/color #260032 → #00ff00')
    expect(changes()).toContain('Perfil 1 · led_dynamic/bg_color #084e50 → #0a84ff')
    await user.click(screen.getByRole('button', { name: 'Gravar no controle' }))
    await screen.findByText('Gravado na flash e conferido na releitura.')
    expect(t.theme).toBe(5)
  })
})

describe('ações da sessão', () => {
  it('descartar volta pro q foi lido', async () => {
    const { user } = await demo()
    await user.selectOptions(screen.getByLabelText('A'), 'Home')
    await user.click(screen.getByRole('button', { name: 'Descartar' }))
    expect(screen.getByLabelText('A')).toHaveValue('A')
    expect(bar()).toBeNull()
  })

  it('reler pega o q tá no controle agora', async () => {
    const { t, user } = await demo()
    const doc = decode(t.cfg)
    doc.slots[0].mapping.Y = 'LB'
    t.cfg = encode(doc, t.cfg).record
    await user.click(screen.getByRole('button', { name: 'Reler' }))
    await waitFor(() => expect(screen.getByLabelText('Y')).toHaveValue('LB'))
  })

  it('reler sem resposta mostra o erro e mantém a tela', async () => {
    const { t, user } = await demo()
    t.silent.add(0x0100)
    await user.click(screen.getByRole('button', { name: 'Reler' }))
    expect(await screen.findByText(/Mexa um analógico/)).toBeInTheDocument()
    expect(screen.getByLabelText('A')).toBeInTheDocument()
  })

  it('backup baixa os 1592 bytes lidos', async () => {
    const { t, user } = await demo()
    const blobs: Blob[] = []
    URL.createObjectURL = vi.fn((b: Blob) => (blobs.push(b), 'blob:x'))
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await user.click(screen.getByRole('button', { name: 'Backup' }))
    expect(click).toHaveBeenCalled()
    expect(new Uint8Array(await (blobs[0] as Blob).arrayBuffer())).toEqual(t.cfg)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:x')
  })

  it('desconectar volta pra tela inicial e desliga o dreno', async () => {
    const { t, user } = await demo()
    await user.click(screen.getByRole('button', { name: 'Desconectar' }))
    expect(screen.getByRole('button', { name: 'Abrir modo demo' })).toBeInTheDocument()
    expect(status()).toHaveTextContent('Desconectado.')
    expect(t.running).toBe(false)
  })
})

describe('botões acendendo ao vivo', () => {
  const part = (name: string) => document.querySelector(`svg.pad [data-part="${name}"]`) as Element
  const lit = (name: string) => part(name).classList.contains('lit')
  const HINT = 'Aperte os botões do controle: eles acendem aqui.'

  // fonte de input falsa: guarda quem assinou e deixa o teste empurrar estados
  function source() {
    const src: { push: (i: LiveInput) => void; offs: number } = { push: () => {}, offs: 0 }
    const onInput = (cb: (i: LiveInput) => void) => {
      src.push = cb
      cb(IDLE)
      return () => void src.offs++
    }
    return { src, onInput }
  }

  it('tela inicial: o desenho do hero acende com o gamepad q o navegador já expõe', async () => {
    const { src, onInput } = source()
    const { user } = setup({ onInput })
    expect(lit('A')).toBe(false)
    act(() => src.push({ ...IDLE, pressed: ['A'] }))
    await waitFor(() => expect(lit('A')).toBe(true))
    // ao sair da tela inicial para de ler
    await user.click(screen.getByRole('button', { name: 'Abrir modo demo' }))
    await screen.findByText('Configuração lida do controle.')
    expect(src.offs).toBe(1)
  })

  it('controle conectado: botões, d-pad, gatilho proporcional e analógico deslocado, com a dica embaixo', async () => {
    const t = new DemoTransport()
    const { src, onInput } = source()
    const drain: InputDrain = { start: () => t.start(), stop: () => t.stop(), get running() { return t.running }, onInput }
    const { user } = setup({ openReal: async () => ({ session: new ConfigSession(t, drain, FAST), demo: false }) })
    await user.click(screen.getByRole('button', { name: 'Conectar controle' }))
    await screen.findByText('Configuração lida do controle.')
    expect(screen.getByText(HINT)).toBeInTheDocument()
    // vários estados no mesmo quadro: só o último chega na tela
    act(() => {
      src.push({ ...IDLE, pressed: ['B'] })
      src.push({ pressed: ['Up', 'R3', 'Home', 'RB'], lt: 0.5, rt: 0, left: [1, -0.5], right: [0, 0] })
    })
    await waitFor(() => expect(lit('Up')).toBe(true))
    expect(['B', 'A', 'Down', 'RB', 'Home', 'R3'].map(lit)).toEqual([false, false, false, true, true, true])
    expect(lit('LT')).toBe(true)
    expect(lit('RT')).toBe(false)
    expect(part('LT').querySelector('clipPath rect')?.getAttribute('height')).toBe('17')
    expect(part('RT').querySelector('clipPath rect')?.getAttribute('height')).toBe('0')
    // analógico mexido acende e mostra pra onde o dedão foi; o outro fica no centro
    expect(lit('L3')).toBe(true)
    expect((part('L3').querySelector('.thumb') as HTMLElement).style.transform).toBe('translate(8px, -4px)')
    expect((part('R3').querySelector('.thumb') as HTMLElement).style.transform).toBe('translate(0px, 0px)')
    // fora do demo o ponteiro não finge aperto
    fireEvent.pointerDown(part('A'))
    expect(lit('A')).toBe(false)
    act(() => src.push(IDLE))
    await waitFor(() => expect(lit('Up')).toBe(false))
    expect(lit('LT')).toBe(false)
  })

  it('modo demo: apertar uma parte do desenho com o ponteiro acende até soltar', async () => {
    await demo()
    expect(screen.queryByText(HINT)).toBeNull()
    expect(screen.getByText(/Clique numa parte do desenho/)).toBeInTheDocument()
    fireEvent.pointerDown(part('A'))
    expect(lit('A')).toBe(true)
    fireEvent.pointerUp(part('A'))
    expect(lit('A')).toBe(false)
    fireEvent.pointerDown(part('RT'))
    expect(part('RT').querySelector('clipPath rect')?.getAttribute('height')).toBe('34')
    fireEvent.pointerLeave(part('RT'))
    expect(lit('RT')).toBe(false)
    fireEvent.pointerDown(part('L3'))
    expect(lit('L3')).toBe(true)
  })

  it('traseiros, L4/R4 e o botão estrela não acendem: o Gamepad API não entrega eles', () => {
    setup()
    for (const name of ['PL', 'PR', 'L4', 'R4', 'Star']) expect(part(name)).toBeNull()
  })
})

describe('acabamento da interface', () => {
  const noTranslate = (el: Element | null) => el?.closest('[translate="no"]') ?? null

  it('enquanto conecta o status termina em reticências', async () => {
    const { user } = setup({ openReal: () => new Promise(() => {}) })
    await user.click(screen.getByRole('button', { name: 'Conectar controle' }))
    expect(status()).toHaveTextContent(/^Conectando e lendo a configuração…$/)
  })

  it('nome do controle, WebHID e teclas não passam pelo tradutor do navegador', async () => {
    setup()
    expect(noTranslate(screen.getByText('8BitDo Ultimate 2', { selector: '.brand *' }))).not.toBeNull()
    expect(noTranslate(screen.getByText('8BitDo Ultimate 2', { selector: 'h1 *' }))).not.toBeNull()
    expect(noTranslate(screen.getByText('WebHID', { selector: '.eyebrow *' }))).not.toBeNull()
    expect(noTranslate(screen.getByText(/ATTRS/))).not.toBeNull()
    expect(noTranslate(document.querySelector('svg.pad'))).not.toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Abrir modo demo' }))
    await screen.findByText('Configuração lida do controle.')
    expect(noTranslate(screen.getByRole('heading', { level: 1 }))).not.toBeNull()
    expect(noTranslate(screen.getByLabelText('A'))).not.toBeNull()
    expect(noTranslate(screen.getByText('A', { selector: 'label' }))).not.toBeNull()
  })

  it('link pra pular direto pro conteúdo', () => {
    setup()
    expect(screen.getByRole('link', { name: 'Pular pro conteúdo' })).toHaveAttribute('href', '#conteudo')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'conteudo')
  })

  it('problema de validação é anunciado sem roubar o foco', async () => {
    const { user } = await demo()
    await user.click(tile('Analógicos'))
    const dz = screen.getByLabelText('LS zona morta (valor)')
    await user.clear(dz)
    await user.type(dz, '200')
    expect(within(bar() as HTMLElement).getByText(/0 a 128/)).toHaveAttribute('aria-live', 'polite')
  })

  it('com a revisão aberta o resto da página fica inerte', async () => {
    const { user } = await demo()
    await user.selectOptions(screen.getByLabelText('A'), 'B')
    await user.click(screen.getByRole('button', { name: 'Revisar e gravar' }))
    for (const el of document.querySelectorAll('.topbar, main, .statusbar')) expect(el).toHaveAttribute('inert')
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    for (const el of document.querySelectorAll('.topbar, main, .statusbar')) expect(el).not.toHaveAttribute('inert')
  })

  it('sair da página com alteração staged pede confirmação', async () => {
    const { user } = await demo()
    const leave = () => {
      const e = new Event('beforeunload', { cancelable: true })
      window.dispatchEvent(e)
      return e.defaultPrevented
    }
    expect(leave()).toBe(false)
    await user.selectOptions(screen.getByLabelText('A'), 'B')
    expect(leave()).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Descartar' }))
    expect(leave()).toBe(false)
  })

  it('nome do perfil não chama o gerenciador de senha nem o corretor', async () => {
    const { user } = await demo()
    await user.click(tile('Perfil'))
    const name = screen.getByLabelText('Nome do perfil')
    expect(name).toHaveAttribute('autocomplete', 'off')
    expect(name).toHaveAttribute('spellcheck', 'false')
    expect(name).toHaveAttribute('name', 'profile-name')
  })
})
