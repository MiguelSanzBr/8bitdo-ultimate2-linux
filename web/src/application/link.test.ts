import { describe, expect, it } from 'vitest'
import { ControllerLink, NoAnswerError, RETRIES } from './link'
import { DemoTransport } from '../adapters/demo'
import type { ReportChannel } from './ports'
import { CFG_SIZE, CHUNK, CMD_COMMIT, CMD_GET_THEME, CMD_INFO, CMD_READ, CMD_REPORT, CMD_WRITE, REPORT_SIZE } from '../domain/packet'

// timeouts curtos pros caminhos de falha (o equivalente do fixture `fast` do test_device.py)
const FAST = { timeoutMs: 15, commitTimeoutMs: 15, settleMs: 0 }
const DATA = Uint8Array.from({ length: CFG_SIZE }, (_, i) => i & 0xff)

function setup(opts = FAST) {
  const t = new DemoTransport()
  t.start()
  return { t, dev: new ControllerLink(t, opts) }
}

function answer(cmd: number, data: number[] = [], length = data.length) {
  const r = new Uint8Array(REPORT_SIZE)
  r.set([2, 4, 4, 0, cmd & 0xff, cmd >> 8, length & 0xff, length >> 8])
  r.set(data, 18)
  return r
}

// transporte roteirizado: a função decide o q responder pra cada pedido
function scripted(reply: (cmd: number) => Uint8Array[]): ReportChannel {
  const ls = new Set<(r: Uint8Array) => void>()
  return {
    kind: 'demo',
    open: async () => {},
    close: async () => {},
    onReport: (cb) => (ls.add(cb), () => ls.delete(cb)),
    send: async (pkt) => {
      const cmd = new DataView(pkt.buffer).getUint16(2, true)
      for (const r of reply(cmd)) queueMicrotask(() => ls.forEach((l) => l(r)))
    },
  }
}

describe('ControllerLink', () => {
  it('usa as 30 tentativas por pedaço do app', () => {
    // espelha test_device.test_retries
    expect(RETRIES).toBe(30)
  })

  it('info devolve firmware e PID, ou null sem resposta', async () => {
    // espelha test_device.test_query_and_info e test_info_none
    const { t, dev } = setup()
    expect(await dev.info()).toEqual({ firmware: 110, beta: 0, devicePid: 0x6012 })
    t.silent.add(CMD_INFO)
    expect(await dev.info()).toBeNull()
  })

  it('ignora report de outro comando enquanto espera', async () => {
    // espelha test_device.test_recv: resposta de outro cmd não conta
    const dev = new ControllerLink(scripted((cmd) => [answer(CMD_WRITE, [1]), new Uint8Array(3), answer(cmd, [5])]), FAST)
    expect(await dev.getTheme()).toBe(5)
  })

  it('liga e desliga os reports', async () => {
    // espelha test_device.test_report
    const { t, dev } = setup()
    await dev.report(true)
    await dev.report(false)
    expect(t.log.map(([c, s]) => [c, s])).toEqual([[CMD_REPORT, 1], [CMD_REPORT, 0]])
  })

  it('lê e troca o tema de LED', async () => {
    // espelha test_device.test_get_and_set_theme
    const { t, dev } = setup()
    expect(await dev.getTheme()).toBe(2)
    await dev.setTheme(3)
    expect(t.theme).toBe(3)
    expect(await dev.getTheme()).toBe(3)
  })

  it('tema sem resposta: get dá null, set estoura', async () => {
    // espelha test_get_theme_no_answer e test_set_theme_not_confirmed
    const { t, dev } = setup()
    t.silent = new Set([CMD_GET_THEME, 0x40])
    expect(await dev.getTheme()).toBeNull()
    await expect(dev.setTheme(4)).rejects.toThrow(NoAnswerError)
    const empty = new ControllerLink(scripted((cmd) => [answer(cmd)]), FAST)
    expect(await empty.getTheme()).toBeNull()
  })

  it('escreve e lê o registro inteiro', async () => {
    // espelha test_device.test_fake_roundtrip
    const { t, dev } = setup()
    await dev.writeConfig(DATA)
    const cmds = t.log.map(([c]) => c)
    expect(cmds.filter((c) => c === CMD_WRITE)).toHaveLength(Math.ceil(CFG_SIZE / CHUNK))
    expect([cmds[0], ...cmds.slice(-2)]).toEqual([CMD_REPORT, CMD_COMMIT, CMD_REPORT])
    expect(await dev.readConfig()).toEqual(DATA)
    expect(t.cfg).toEqual(DATA)
  })

  it('tenta de novo quando uma resposta se perde', async () => {
    // espelha test_read_retry_with_drop e test_write_retry_with_drop
    const { t, dev } = setup()
    t.cfg = DATA.slice()
    t.drop = 1
    expect(await dev.readConfig()).toEqual(DATA)
    t.drop = 2
    await dev.writeConfig(DATA.slice().reverse())
    expect(t.cfg).toEqual(DATA.slice().reverse())
  })

  it('resposta vazia também conta como tentativa', async () => {
    // espelha test_read_zero_length_and_none_retry e test_write_zero_length_then_ok
    let first = true
    const dev = new ControllerLink(scripted((cmd) => {
      if (first && (cmd === CMD_READ || cmd === CMD_WRITE)) {
        first = false
        return [answer(cmd)]
      }
      return cmd === CMD_READ ? [answer(cmd, Array(CHUNK).fill(7))] : cmd === CMD_WRITE ? [answer(cmd, [], CHUNK)] : [answer(cmd)]
    }), FAST)
    expect((await dev.readConfig()).every((b) => b === 7)).toBe(true)
    first = true
    await dev.writeConfig(DATA)
  })

  it('desiste depois de 30 tentativas', async () => {
    // espelha test_read_exhausted e test_write_exhausted
    const { t, dev } = setup()
    t.silent = new Set([CMD_READ, CMD_WRITE])
    await expect(dev.readConfig()).rejects.toThrow('leitura falhou no offset 0')
    expect(t.log.filter(([c]) => c === CMD_READ)).toHaveLength(RETRIES)
    await expect(dev.writeConfig(DATA)).rejects.toThrow(NoAnswerError)
    // diferente do Python: religa os reports mesmo se um pedaço falhar
    expect(t.log.at(-1)?.slice(0, 2)).toEqual([CMD_REPORT, 1])
  })

  it('commit sem confirmação estoura e religa os reports', async () => {
    // espelha test_device.test_commit_not_confirmed
    const { t, dev } = setup()
    t.silent.add(CMD_COMMIT)
    await expect(dev.writeConfig(DATA)).rejects.toThrow('o controle não confirmou a gravação')
    expect(t.log.at(-1)?.[0]).toBe(CMD_REPORT)
  })

  it('recusa registro de tamanho errado sem mandar nada', async () => {
    // espelha o assert len(data) == CFG_SIZE do write_config
    const { t, dev } = setup()
    await expect(dev.writeConfig(DATA.slice(1))).rejects.toThrow(/1592/)
    expect(t.log).toEqual([])
  })

  it('usa os timeouts do Python por padrão', async () => {
    const dev = new ControllerLink(new DemoTransport())
    expect(dev.opts).toEqual({ timeoutMs: 500, commitTimeoutMs: 3000, settleMs: 100 })
  })
})

describe('ControllerLink com transporte quebrado', () => {
  it('erro no envio sobe pra quem chamou', async () => {
    const t: ReportChannel = { kind: 'webhid', open: async () => {}, close: async () => {}, onReport: () => () => {}, send: () => Promise.reject(new Error('desconectado')) }
    await expect(new ControllerLink(t, FAST).getTheme()).rejects.toThrow('desconectado')
  })
})
