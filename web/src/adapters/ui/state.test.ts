import { describe, expect, it } from 'vitest'
import { initial, reducer } from './state'
import type { State } from './state'
import { ConfigRecord } from '../../domain/config-record'
import { demoRecord } from '../demo'

const snap = { info: { firmware: 110, beta: 0, devicePid: 0x6012 }, record: ConfigRecord.fromBytes(demoRecord()), theme: 2 }
const loaded = (): State => reducer(initial, { type: 'loaded', snap, demo: true, text: 'lido' })

describe('reducer', () => {
  it('começa desconectado e parado', () => {
    expect(initial).toMatchObject({ phase: 'idle', snap: null, doc: null, plan: null, profile: 0 })
  })

  it('busy guarda a mensagem e trava a tela', () => {
    expect(reducer(initial, { type: 'busy', text: 'lendo' })).toMatchObject({ phase: 'busy', status: { tone: 'info', text: 'lendo' } })
  })

  it('loaded copia o documento do registro e o tema', () => {
    const s = loaded()
    expect(s).toMatchObject({ phase: 'ready', demo: true, theme: 2, status: { tone: 'ok', text: 'lido' } })
    expect(s.doc?.slots[0].name).toBe('Demo')
  })

  it('failed volta pra tela anterior com o erro', () => {
    expect(reducer(initial, { type: 'failed', text: 'x' })).toMatchObject({ phase: 'idle', status: { tone: 'error' } })
    expect(reducer(loaded(), { type: 'failed', text: 'x' }).phase).toBe('ready')
  })

  it('edit mexe numa cópia do documento', () => {
    const s = loaded()
    const next = reducer(s, { type: 'edit', fn: (d) => void (d.slots[0].name = 'X') })
    expect(next.doc?.slots[0].name).toBe('X')
    expect(s.doc?.slots[0].name).toBe('Demo')
    expect(reducer(initial, { type: 'edit', fn: () => {} })).toBe(initial)
  })

  it('perfil, tema, descarte e revisão', () => {
    let s = reducer(loaded(), { type: 'profile', index: 2 })
    expect(s.profile).toBe(2)
    s = reducer(s, { type: 'theme', theme: 5 })
    s = reducer(s, { type: 'edit', fn: (d) => void (d.slots[0].name = 'X') })
    s = reducer(s, { type: 'discard' })
    expect([s.theme, s.doc?.slots[0].name, s.status?.text]).toEqual([2, 'Demo', 'Edições descartadas.'])
    const plan = { base: snap.record, next: snap.record, changed: ['x'], theme: null }
    s = reducer(s, { type: 'review', plan })
    expect([s.phase, s.plan]).toEqual(['review', plan])
    s = reducer(s, { type: 'cancel' })
    expect([s.phase, s.plan]).toEqual(['ready', null])
    expect(reducer(initial, { type: 'discard' })).toBe(initial)
  })

  it('written troca a base pelo q foi relido do controle', () => {
    const doc = snap.record.toDoc()
    doc.slots[0].name = 'Gravado'
    const record = snap.record.withChanges(doc).next
    const s = reducer(loaded(), { type: 'written', record, theme: 4 })
    expect([s.phase, s.theme, s.snap?.theme, s.doc?.slots[0].name, s.status?.tone]).toEqual(['ready', 4, 4, 'Gravado', 'ok'])
    expect(reducer(initial, { type: 'written', record, theme: 4 })).toBe(initial)
  })

  it('disconnected zera tudo', () => {
    expect(reducer(loaded(), { type: 'disconnected' })).toMatchObject({ ...initial, status: { tone: 'info', text: 'Desconectado.' } })
  })
})
