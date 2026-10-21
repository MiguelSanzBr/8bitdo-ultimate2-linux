import { describe, expect, it } from 'vitest'
import { ConfigSession, VerifyError } from './config-session'
import type { ConfirmedPlan } from './config-session'
import type { InputDrain, ReportChannel } from './ports'
import { NoAnswerError } from './link'
import { DemoTransport } from '../adapters/demo'
import { ConfigRecord } from '../domain/config-record'
import { InvariantError } from '../domain/values'
import { CMD_SET_THEME, CMD_WRITE } from '../domain/packet'
import { IDLE } from '../domain/live-input'
import type { LiveInput } from '../domain/live-input'

const FAST = { timeoutMs: 15, commitTimeoutMs: 15, settleMs: 0 }

// o demo implementa os dois ports e, como o firmware, fica mudo sem o dreno ligado
function setup() {
  const t = new DemoTransport()
  return { t, s: new ConfigSession(t, t, FAST) }
}

async function connected() {
  const ctx = setup()
  const snap = await ctx.s.connect()
  ctx.t.log.length = 0
  return { ...ctx, snap }
}

describe('Connect', () => {
  it('liga o dreno antes de abrir o canal e lê tudo', async () => {
    const t = new DemoTransport()
    const order: string[] = []
    const drain: InputDrain = { start: () => (order.push('drain'), t.start()), stop: () => t.stop(), get running() { return t.running }, onInput: (cb) => t.onInput(cb) }
    const channel: ReportChannel = { kind: 'demo', open: async () => void order.push('open'), close: () => t.close(), send: (r) => t.send(r), onReport: (cb) => t.onReport(cb) }
    const snap = await new ConfigSession(channel, drain, FAST).connect()
    expect(order).toEqual(['drain', 'open'])
    expect(snap.info).toEqual({ firmware: 110, beta: 0, devicePid: 0x6012 })
    expect(snap.record.toBytes()).toEqual(t.cfg)
    expect(snap.theme).toBe(2)
  })

  it('o dreno fica ligado a sessão inteira e desliga no disconnect', async () => {
    const { t, s } = await connected()
    expect(t.running).toBe(true)
    await s.disconnect()
    expect(t.running).toBe(false)
  })

  it('sem dreno o controle não responde e a sessão avisa', async () => {
    const t = new DemoTransport()
    const dead: InputDrain = { start: () => {}, stop: () => {}, running: false, onInput: () => () => {} }
    await expect(new ConfigSession(t, dead, FAST).connect()).rejects.toThrow(NoAnswerError)
  })

  it('falha ao abrir desliga o dreno e repassa o erro', async () => {
    const { t } = setup()
    const channel: ReportChannel = { kind: 'webhid', open: () => Promise.reject(new Error('udev')), close: async () => {}, send: (r) => t.send(r), onReport: (cb) => t.onReport(cb) }
    await expect(new ConfigSession(channel, t, FAST).connect()).rejects.toThrow('udev')
    expect(t.running).toBe(false)
  })
})

describe('ReadConfig', () => {
  it('relê o controle', async () => {
    const { t, s } = await connected()
    t.cfg[30] = 0x41
    const snap = await s.readConfig()
    expect(snap.record.toBytes()[30]).toBe(0x41)
  })
})

describe('PlanChanges', () => {
  it('lista campos e troca de tema sem tocar no controle', async () => {
    const { t, s, snap } = await connected()
    const doc = snap.record.toDoc()
    doc.slots[0].mapping.A = 'B'
    const plan = s.planChanges(snap.record, doc, 2, 3)
    expect(plan.changed).toEqual(['slots/0/mapping/A'])
    expect(plan.theme).toBe(3)
    expect(plan.next.crc).not.toBe(snap.record.crc)
    expect(t.log).toEqual([])
  })

  it('sem mudança, tema null', async () => {
    const { s, snap } = await connected()
    const plan = s.planChanges(snap.record, snap.record.toDoc(), 2, 2)
    expect([plan.changed, plan.theme]).toEqual([[], null])
  })

  it('barra tema inexistente e valor fora da faixa', async () => {
    const { s, snap } = await connected()
    expect(() => s.planChanges(snap.record, snap.record.toDoc(), 2, 9)).toThrow(InvariantError)
    const doc = snap.record.toDoc()
    doc.slots[0].triggers.left_end = 300
    expect(() => s.planChanges(snap.record, doc, 2, 2)).toThrow(/0 a 255/)
  })
})

describe('ApplyChanges', () => {
  it('sem confirmação não grava nada', async () => {
    const { t, s, snap } = await connected()
    const doc = snap.record.toDoc()
    doc.slots[0].mapping.A = 'B'
    // tipo forçado de propósito: a barreira em runtime tem q pegar mesmo assim
    await expect(s.applyChanges(s.planChanges(snap.record, doc, 2, 3) as ConfirmedPlan)).rejects.toThrow(/confirma/)
    expect(t.log).toEqual([])
  })

  it('confirmado: grava, commit na flash, relê pra conferir e troca o tema', async () => {
    // espelha cli.main "apply": write_config, depois read_config tem q bater
    const { t, s, snap } = await connected()
    const doc = snap.record.toDoc()
    doc.slots[0].mapping.A = 'B'
    const plan = s.planChanges(snap.record, doc, 2, 5)
    const out = await s.applyChanges(s.confirm(plan))
    expect(out.record.equals(plan.next)).toBe(true)
    expect(t.cfg).toEqual(plan.next.toBytes())
    expect(out.theme).toBe(5)
  })

  it('confirmação vale uma vez só', async () => {
    const { s, snap } = await connected()
    const confirmed = s.confirm(s.planChanges(snap.record, snap.record.toDoc(), 2, 4))
    await s.applyChanges(confirmed)
    await expect(s.applyChanges(confirmed)).rejects.toThrow(/confirma/)
  })

  it('só tema: não encosta no registro', async () => {
    const { t, s, snap } = await connected()
    const out = await s.applyChanges(s.confirm(s.planChanges(snap.record, snap.record.toDoc(), 2, 4)))
    expect(t.log.some(([c]) => c === CMD_WRITE)).toBe(false)
    expect(out.record).toBe(snap.record)
    expect(out.theme).toBe(4)
  })

  it('sem troca de tema não manda CMD_SET_THEME', async () => {
    const { t, s, snap } = await connected()
    const doc = snap.record.toDoc()
    doc.slots[0].name = 'Outro'
    const out = await s.applyChanges(s.confirm(s.planChanges(snap.record, doc, 2, 2)))
    expect(out.theme).toBe(2)
    expect(t.log.some(([c]) => c === CMD_SET_THEME)).toBe(false)
  })

  it('nunca grava registro com CRC errado', async () => {
    const { t, s, snap } = await connected()
    const doc = snap.record.toDoc()
    doc.slots[0].mapping.A = 'B'
    const plan = s.planChanges(snap.record, doc, 2, 2)
    const bad = plan.next.toBytes()
    bad[12] = bad[12] === 0 ? 1 : 0
    await expect(s.applyChanges(s.confirm({ ...plan, next: ConfigRecord.fromBytes(bad) }))).rejects.toThrow(/CRC/)
    expect(t.log).toEqual([])
  })

  it('releitura diferente do q foi gravado vira VerifyError e o tema fica', async () => {
    // espelha o "verify failed" do cli com FakeController.corrupt_commit
    const { t, s, snap } = await connected()
    t.corruptCommit = true
    const doc = snap.record.toDoc()
    doc.slots[0].name = 'Outro'
    await expect(s.applyChanges(s.confirm(s.planChanges(snap.record, doc, 2, 3)))).rejects.toThrow(VerifyError)
    expect(t.log.some(([c]) => c === CMD_SET_THEME)).toBe(false)
  })
})

describe('SetTheme', () => {
  it('troca o tema e devolve o q o controle reporta', async () => {
    const { t, s } = await connected()
    expect(await s.setTheme(3)).toBe(3)
    expect(t.theme).toBe(3)
    await expect(s.setTheme(1)).rejects.toThrow(InvariantError)
  })
})

describe('Input ao vivo', () => {
  it('a sessão repassa o estado do controle q vem do dreno', () => {
    const { t } = setup()
    let push: (i: LiveInput) => void = () => {}
    const off = () => {}
    const drain: InputDrain = { start: () => {}, stop: () => {}, running: true, onInput: (cb) => ((push = cb), off) }
    const seen: LiveInput[] = []
    expect(new ConfigSession(t, drain, FAST).onInput((i) => seen.push(i))).toBe(off)
    push({ ...IDLE, pressed: ['A'] })
    expect(seen).toEqual([{ ...IDLE, pressed: ['A'] }])
  })
})
