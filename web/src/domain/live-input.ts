// O q o controle tá apertando agora, pro desenho acender. Vem do Gamepad API no layout "standard" do W3C, q é por
// posição (0 = botão de baixo), igual o desenho, então vale pro XInput e pro Switch sem tabela por gamepad_mode.
import type { BUTTONS } from './record'

export type LivePart = Extract<(typeof BUTTONS)[number], 'A' | 'B' | 'X' | 'Y' | 'LB' | 'RB' | 'Select' | 'Start' | 'L3' | 'R3' | 'Up' | 'Down' | 'Left' | 'Right' | 'Home'>
export type Stick = readonly [x: number, y: number]

export interface LiveInput {
  pressed: readonly LivePart[]
  // 0 a 1
  lt: number
  rt: number
  // -1 a 1, y pra baixo
  left: Stick
  right: Stick
}

// o mesmo formato do Gamepad do navegador, sem depender do DOM
export interface PadReading {
  readonly id: string
  readonly mapping: string
  readonly buttons: readonly { readonly pressed: boolean; readonly value: number }[]
  readonly axes: readonly number[]
}

export const IDLE: LiveInput = { pressed: [], lt: 0, rt: 0, left: [0, 0], right: [0, 0] }

// PL/PR e L4/R4 não aparecem no Gamepad API, por isso nem entram
const STANDARD = ['A', 'B', 'X', 'Y', 'LB', 'RB', null, null, 'Select', 'Start', 'L3', 'R3', 'Up', 'Down', 'Left', 'Right', 'Home'] as const
// analógico parado nunca volta pro zero exato
const DEAD = 0.12

const round = (v: number) => Math.round(v * 100) / 100
const axis = (v = 0) => (Math.abs(v) < DEAD ? 0 : round(v))
const trigger = (b?: PadReading['buttons'][number]) => (b ? round(b.value || (b.pressed ? 1 : 0)) : 0)

export function readPad(pad: PadReading | null): LiveInput {
  // sem o standard os índices dependem do driver, melhor não acender nada q acender o botão errado
  if (pad?.mapping !== 'standard') return IDLE
  const { buttons: b, axes: a } = pad
  return {
    pressed: STANDARD.filter((p, i): p is LivePart => p !== null && !!b[i]?.pressed),
    lt: trigger(b[6]),
    rt: trigger(b[7]),
    left: [axis(a[0]), axis(a[1])],
    right: [axis(a[2]), axis(a[3])],
  }
}

export function pickPad(pads: readonly (PadReading | null)[]): PadReading | null {
  const on = pads.filter((p): p is PadReading => p !== null)
  return on.find((p) => /2dc8/i.test(p.id)) ?? on[0] ?? null
}
