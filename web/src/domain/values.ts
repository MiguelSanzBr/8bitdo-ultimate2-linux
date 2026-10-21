// Value objects do controle. As faixas vêm do docs/PROTOCOL.md e do README do 8bitdo-ultimate2-linux;
// o Python não barra nada disso, aqui barra antes de qualquer byte mudar.
import { THEMES } from './packet'
import { KEYCODES } from './record'

export class InvariantError extends Error {
  name = 'InvariantError'
}

export type ProfileIndex = 0 | 1 | 2

export function profileIndex(n: number): ProfileIndex {
  if (n !== 0 && n !== 1 && n !== 2) throw new InvariantError(`perfil ${n + 1} não existe, só 1 a 3`)
  return n
}

export const profileLabel = (i: ProfileIndex) => `Perfil ${i + 1}`

export const GAMEPAD_MODES: Readonly<Record<number, string>> = { 0: 'Switch', 1: 'Android', 3: 'Windows (XInput)' }

export const gamepadModeName = (mode: number) => GAMEPAD_MODES[mode] ?? `desconhecido (${mode})`

export function ledTheme(n: number): number {
  if (!(n in THEMES)) throw new InvariantError(`tema de LED ${n} não existe`)
  return n
}

export const ledThemeName = (t: number | null) => THEMES[t ?? -1] ?? 'desconhecido'

const inRange = (v: unknown, max: number) => Number.isInteger(v) && (v as number) >= 0 && (v as number) <= max
const KEY_NAMES = new Set(Object.values(KEYCODES))

// Confere um campo editado (caminho do encode, ex. "slots/0/sticks/left_start"); null = ok.
export function changeProblem(path: string, value: unknown): string | null {
  const field = path.split('/').slice(2).join('/')
  if (/^sticks\/(left|right)_(start|end)$/.test(field)) return inRange(value, 128) ? null : `${path}: analógico vai de 0 a 128`
  if (/^triggers\/(left|right)_(start|end)$/.test(field)) return inRange(value, 255) ? null : `${path}: gatilho vai de 0 a 255`
  if (/^mapping\/(?!flag$)/.test(field)) {
    // código desconhecido lido do controle volta como hex e tem q continuar valendo
    return KEY_NAMES.has(value as string) || /^0x[0-9a-f]{8}$/.test(value as string) ? null : `${path}: função desconhecida`
  }
  if (/^led_\w+\/(bg_)?color$/.test(field)) return /^#[0-9a-f]{6}$/i.test(value as string) ? null : `${path}: cor tem q ser #rrggbb`
  return null
}
