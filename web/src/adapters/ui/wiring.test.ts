import { describe, expect, it, vi } from 'vitest'
import { browserWiring } from './wiring'
import { DRAIN_MS } from '../gamepad-drain'
import type { LiveInput } from '../../domain/live-input'

const FAST = { timeoutMs: 15, commitTimeoutMs: 15, settleMs: 0 }

describe('browserWiring', () => {
  it('sabe se o navegador tem WebHID', () => {
    expect(browserWiring({} as Navigator).supported).toBe(false)
    expect(browserWiring({ hid: {} } as Navigator).supported).toBe(true)
  })

  it('demo liga a sessão no controle simulado', async () => {
    const opened = browserWiring({} as Navigator, FAST).openDemo()
    expect(opened.demo).toBe(true)
    const snap = await opened.session.connect()
    expect(snap.record.toDoc().slots[0].name).toBe('Demo')
    await opened.session.disconnect()
  })

  it('controle de verdade: null se a pessoa cancelar o seletor', async () => {
    const nav = { hid: { requestDevice: async () => [] } } as unknown as Navigator
    expect(await browserWiring(nav).openReal()).toBeNull()
  })

  it('controle de verdade: sessão com WebHID e o dreno lendo getGamepads', async () => {
    vi.useFakeTimers()
    const device = Object.assign(new EventTarget(), {
      opened: false, vendorId: 0x2dc8, collections: [{ usagePage: 0xff7a }],
      open: async () => {}, close: async () => {}, sendReport: async () => {},
    })
    const getGamepads = vi.fn(() => [])
    const nav = { hid: { requestDevice: async () => [device] }, getGamepads } as unknown as Navigator
    const opened = await browserWiring(nav, { ...FAST, timeoutMs: 50 }).openReal()
    expect(opened?.demo).toBe(false)
    const pending = opened?.session.connect().catch((e: Error) => e.name)
    await vi.advanceTimersByTimeAsync(100)
    // ninguém responde do outro lado, mas o dreno rodou durante a tentativa
    expect(await pending).toBe('NoAnswerError')
    expect(getGamepads).toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('tela inicial: acende com o gamepad q o Chrome já expõe, sem WebHID, e para de ler no fim', () => {
    vi.useFakeTimers()
    const a = { id: 'x 2dc8', mapping: 'standard', buttons: [{ pressed: true, value: 1 }], axes: [] }
    const getGamepads = vi.fn(() => [a])
    const seen: LiveInput[] = []
    const off = browserWiring({ getGamepads } as unknown as Navigator).onInput((i) => seen.push(i))
    vi.advanceTimersByTime(DRAIN_MS)
    expect(seen.map((i) => i.pressed)).toEqual([[], ['A']])
    off()
    const calls = getGamepads.mock.calls.length
    vi.advanceTimersByTime(DRAIN_MS * 3)
    expect(getGamepads).toHaveBeenCalledTimes(calls)
    vi.useRealTimers()
  })

  it('navegador sem Gamepad API: fica parado sem erro', () => {
    vi.useFakeTimers()
    const seen: LiveInput[] = []
    const off = browserWiring({} as Navigator).onInput((i) => seen.push(i))
    vi.advanceTimersByTime(DRAIN_MS * 2)
    off()
    expect(seen.map((i) => i.pressed)).toEqual([[]])
    vi.useRealTimers()
  })
})
