import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DRAIN_MS, GamepadDrain } from './gamepad-drain'
import { IDLE } from '../domain/live-input'
import type { LiveInput } from '../domain/live-input'

const pad = { id: '8BitDo Ultimate 2' } as Gamepad

// gamepad no layout standard com os índices dados apertados
const std = (...pressed: number[]) => ({
  id: '8BitDo Ultimate 2 (STANDARD GAMEPAD Vendor: 2dc8 Product: 6012)',
  mapping: 'standard',
  buttons: Array.from({ length: 17 }, (_, i) => ({ pressed: pressed.includes(i), value: pressed.includes(i) ? 1 : 0, touched: false })),
  axes: [0, 0, 0, 0],
}) as unknown as Gamepad

describe('GamepadDrain', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('fica chamando getGamepads enquanto tá ligado', () => {
    // equivale ao device.Device manter o /dev/input/js* aberto durante o I/O de config
    const get = vi.fn((): (Gamepad | null)[] => [null])
    const d = new GamepadDrain(get)
    expect(d.running).toBe(false)
    d.start()
    expect(d.running).toBe(true)
    vi.advanceTimersByTime(DRAIN_MS * 3)
    expect(get).toHaveBeenCalledTimes(3)
    expect(d.polls).toBe(3)
  })

  it('start repetido não cria um segundo timer', () => {
    const get = vi.fn((): (Gamepad | null)[] => [])
    const d = new GamepadDrain(get)
    d.start()
    d.start()
    vi.advanceTimersByTime(DRAIN_MS * 2)
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('stop para de ler', () => {
    const get = vi.fn((): (Gamepad | null)[] => [])
    const d = new GamepadDrain(get)
    d.start()
    vi.advanceTimersByTime(DRAIN_MS)
    d.stop()
    d.stop()
    vi.advanceTimersByTime(DRAIN_MS * 5)
    expect(get).toHaveBeenCalledTimes(1)
    expect(d.running).toBe(false)
  })


  it('usa navigator.getGamepads por padrão', () => {
    const get = vi.fn(() => [pad])
    vi.stubGlobal('navigator', { getGamepads: get })
    const d = new GamepadDrain()
    d.start()
    vi.advanceTimersByTime(DRAIN_MS)
    expect(get).toHaveBeenCalledTimes(1)
    d.stop()
  })

  it('entrega o estado do controle na hora e depois só quando muda', () => {
    let pads: (Gamepad | null)[] = [std()]
    const d = new GamepadDrain(() => pads)
    const seen: LiveInput[] = []
    const off = d.onInput((i) => seen.push(i))
    expect(seen).toEqual([IDLE])
    d.start()
    vi.advanceTimersByTime(DRAIN_MS * 2)
    expect(seen).toHaveLength(1)
    pads = [null, std(0)]
    vi.advanceTimersByTime(DRAIN_MS * 3)
    pads = [std()]
    vi.advanceTimersByTime(DRAIN_MS)
    expect(seen.map((i) => i.pressed)).toEqual([[], ['A'], []])
    off()
    pads = [std(1)]
    vi.advanceTimersByTime(DRAIN_MS)
    expect(seen).toHaveLength(3)
    d.stop()
  })

  it('quem chega depois recebe o estado atual; depois do stop volta pro parado', () => {
    const d = new GamepadDrain(() => [std(3)])
    d.start()
    vi.advanceTimersByTime(DRAIN_MS)
    const late: LiveInput[] = []
    d.onInput((i) => late.push(i))
    expect(late[0]?.pressed).toEqual(['Y'])
    d.stop()
    const after: LiveInput[] = []
    d.onInput((i) => after.push(i))
    expect(after).toEqual([IDLE])
  })
})
