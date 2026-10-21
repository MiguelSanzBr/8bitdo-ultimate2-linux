import { describe, expect, it } from 'vitest'
import { IDLE, pickPad, readPad } from './live-input'
import type { PadReading } from './live-input'

// layout standard do W3C: 17 botões, 6 e 7 são os gatilhos analógicos, eixos 0-1 esquerdo e 2-3 direito
function pad(over: { pressed?: number[]; values?: Record<number, number>; axes?: number[]; id?: string; mapping?: string } = {}): PadReading {
  return {
    id: over.id ?? '8BitDo Ultimate 2 (STANDARD GAMEPAD Vendor: 2dc8 Product: 6012)',
    mapping: over.mapping ?? 'standard',
    buttons: Array.from({ length: 17 }, (_, i) => ({ pressed: over.pressed?.includes(i) ?? false, value: over.values?.[i] ?? (over.pressed?.includes(i) ? 1 : 0) })),
    axes: over.axes ?? [0, 0, 0, 0],
  }
}

describe('readPad', () => {
  it('sem controle ou parado não acende nada', () => {
    expect(readPad(null)).toEqual(IDLE)
    expect(readPad(pad())).toEqual(IDLE)
  })

  it('cada índice do layout standard vira a parte do desenho na mesma posição', () => {
    const all = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    expect(readPad(pad({ pressed: all })).pressed).toEqual(['A', 'B', 'X', 'Y', 'LB', 'RB', 'Select', 'Start', 'L3', 'R3', 'Up', 'Down', 'Left', 'Right', 'Home'])
    expect(readPad(pad({ pressed: [0] })).pressed).toEqual(['A'])
  })

  it('gatilho é analógico e não entra na lista de apertados', () => {
    const r = readPad(pad({ pressed: [7], values: { 6: 0.333, 7: 1 } }))
    expect(r.pressed).toEqual([])
    expect([r.lt, r.rt]).toEqual([0.33, 1])
  })

  it('gatilho digital (pressed sem value) conta como cheio', () => {
    expect(readPad(pad({ pressed: [6], values: { 6: 0 } })).lt).toBe(1)
  })

  it('analógico com ruído de repouso fica no centro, mexido vira deslocamento', () => {
    expect(readPad(pad({ axes: [0.05, -0.08, 0.1, 0] })).left).toEqual([0, 0])
    const r = readPad(pad({ axes: [-1, 0.504, 0.7, -0.3] }))
    expect(r.left).toEqual([-1, 0.5])
    expect(r.right).toEqual([0.7, -0.3])
  })

  it('eixos ou botões faltando não quebram', () => {
    expect(readPad({ id: 'x', mapping: 'standard', buttons: [{ pressed: true, value: 1 }], axes: [] })).toEqual({ ...IDLE, pressed: ['A'] })
  })

  it('sem o layout standard não acende nada, os índices dependem do driver', () => {
    expect(readPad(pad({ mapping: '', pressed: [0], axes: [1, 1, 1, 1] }))).toEqual(IDLE)
  })
})

describe('pickPad', () => {
  const other = pad({ id: 'Xbox 360 Controller (Vendor: 045e Product: 028e)' })
  const ours = pad({ id: '8BitDo Ultimate 2 (Vendor: 2DC8 Product: 310b)' })

  it('prefere o 8BitDo pelo vendor 2dc8', () => {
    expect(pickPad([other, null, ours])).toBe(ours)
  })

  it('sem 8BitDo pega o primeiro conectado; sem nenhum, null', () => {
    expect(pickPad([null, other])).toBe(other)
    expect(pickPad([null, null])).toBeNull()
    expect(pickPad([])).toBeNull()
  })
})
