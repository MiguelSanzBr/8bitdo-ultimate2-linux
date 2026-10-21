// Porta do ultimate2/config.py: o registro de 1592 bytes (custom_config_record_t_u2 do app oficial).
// Três perfis, alinhamento natural do MSVC, little endian. O encode só regrava o campo q mudou, assim
// byte desconhecido volta igualzinho pro controle.
import { CFG_SIZE, crc16 } from './packet'
import type { ConfigDoc, Slot } from './types'

export const FLAGS: Readonly<Record<number, string>> = { 0x20200911: 'enabled', 0x20190000: 'disabled', 0: 'off' }
// botões físicos na ordem do map_key.key[] (P1 = PR, P2 = PL atrás; P3 = L4, P4 = R4)
export const BUTTONS = ['A', 'B', 'X', 'Y', 'LB', 'RB', 'LT', 'RT', 'L3', 'R3', 'Select', 'Start', 'Star',
  'Home', 'Up', 'Down', 'Left', 'Right', 'P1', 'P2', 'P3', 'P4'] as const
// função q um botão pode receber
export const KEYCODES: Readonly<Record<number, string>> = {
  0: 'None', 0x1: 'Start', 0x2: 'L3', 0x4: 'R3', 0x8: 'Select', 0x10: 'X', 0x20: 'Y',
  0x40: 'Right', 0x80: 'Left', 0x100: 'Down', 0x200: 'Up', 0x400: 'LB', 0x800: 'RB',
  0x1000: 'B', 0x2000: 'A', 0x4000: 'LT', 0x8000: 'RT', 0x10000: 'Menu', 0x20000: 'Home',
  0x100000: 'P5', 0x200000: 'P3', 0x400000: 'Screenshot', 0x800000: 'TurboSingle',
  0x1000000: 'TurboAuto', 0x2000000: 'P1', 0x4000000: 'P2', 0x40000000: 'P4',
  0x08000001: 'RS_Up', 0x08000002: 'RS_Down', 0x08000004: 'RS_Left', 0x08000008: 'RS_Right',
  0x08000010: 'LS_Up', 0x08000020: 'LS_Down', 0x08000040: 'LS_Left', 0x08000080: 'LS_Right',
}
export const FEATURES: Readonly<Record<number, string>> = {
  0x1: 'invert_LS_X', 0x2: 'invert_LS_Y', 0x4: 'invert_RS_X', 0x8: 'invert_RS_Y',
  0x10: 'swap_sticks', 0x80: 'swap_triggers', 0x100: 'swap_LS_dpad', 0x8000: 'trigger_rumble',
}
export const CRC_FIELD = [12, 16] as const

// B/H/I inteiro sem sinal, f float, str32 nome UTF-16BE, F flag, K tecla, M máscara de features,
// X u32 em hex, C cor #rrggbb
export type Kind = 'B' | 'H' | 'I' | 'f' | 'str32' | 'F' | 'K' | 'M' | 'X' | 'C'
type Path = (string | number)[]
export interface Field { path: Path; off: number; kind: Kind }
type Value = string | number | null | string[]

const FEATURE_BITS = Object.keys(FEATURES).reduce((a, k) => a + Number(k), 0)
const hex8 = (v: number) => '0x' + v.toString(16).padStart(8, '0')

function buildFields(): Field[] {
  const f: Field[] = [
    { path: ['crc_value'], off: 12, kind: 'I' }, { path: ['gamepad_mode'], off: 16, kind: 'H' }, { path: ['cur_slot'], off: 18, kind: 'H' },
  ]
  const add = (path: Path, off: number, kind: Kind) => f.push({ path, off, kind })
  for (let s = 0; s < 3; s++) {
    const p = (...k: Path) => ['slots', s, ...k]
    add(p('flag'), 4 * s, 'F')
    add(p('name'), 20 + 32 * s, 'str32')
    let o = 116 + 12 * s
    add(p('rumble', 'flag'), o, 'F'); add(p('rumble', 'left'), o + 4, 'f'); add(p('rumble', 'right'), o + 8, 'f')
    for (const [sec, base] of [['sticks', 152], ['triggers', 176], ['xinput_rumble', 1148]] as const) {
      o = base + 8 * s
      add(p(sec, 'flag'), o, 'F'); add(p(sec, 'left_start'), o + 4, 'B'); add(p(sec, 'left_end'), o + 5, 'B')
      add(p(sec, 'right_start'), o + 6, 'B'); add(p(sec, 'right_end'), o + 7, 'B')
    }
    o = 200 + 8 * s
    add(p('special', 'flag'), o, 'F'); add(p('special', 'features'), o + 4, 'M')
    o = 224 + 92 * s
    add(p('mapping', 'flag'), o, 'F')
    BUTTONS.forEach((b, i) => add(p('mapping', b), o + 4 + 4 * i, 'K'))
    o = 500 + 216 * s
    add(p('macros', 'flag'), o, 'F'); add(p('macros', 'total_cnt'), o + 4, 'B')
    for (let r = 0; r < 4; r++) {
      const q = (k: string) => p('macros', 'records', r, k)
      const ro = o + 8 + 52 * r
      add(q('name'), ro, 'str32'); add(q('gamepad_mode'), ro + 32, 'B'); add(q('special_flag'), ro + 33, 'B')
      add(q('max_steps'), ro + 34, 'H'); add(q('offset'), ro + 36, 'H'); add(q('key_map'), ro + 40, 'X')
      add(q('cycles_num'), ro + 44, 'I'); add(q('interval_ms'), ro + 48, 'I')
    }
    o = 1172 + 12 * s
    add(p('sixaxis', 'flag'), o, 'F'); add(p('sixaxis', 'keys_map'), o + 4, 'X'); add(p('sixaxis', 'trigger_mode'), o + 8, 'B')
    add(p('sixaxis', 'sensitivity'), o + 9, 'B'); add(p('sixaxis', 'dead_compensate'), o + 10, 'B')
    add(p('sixaxis', 'mapping_type'), o + 11, 'B')
    o = 1208 + 12 * s
    add(p('led_dynamic', 'flag'), o, 'F'); add(p('led_dynamic', 'color'), o + 4, 'C'); add(p('led_dynamic', 'bg_color'), o + 8, 'C')
    o = 1244 + 16 * s
    add(p('led_hotwheel', 'flag'), o, 'F'); add(p('led_hotwheel', 'color'), o + 4, 'C')
    add(p('led_hotwheel', 'bg_color'), o + 8, 'C'); add(p('led_hotwheel', 'speed'), o + 12, 'B')
    o = 1292 + 100 * s
    add(p('led_single', 'flag'), o, 'F')
    for (let i = 0; i < 24; i++) add(p('led_single', 'colors', i), o + 4 + 4 * i, 'C')
  }
  return f
}

export const FIELDS = buildFields()

const view = (b: Uint8Array) => new DataView(b.buffer, b.byteOffset, b.byteLength)

export function getField(buf: Uint8Array, off: number, kind: Kind): Value {
  const v = view(buf)
  if (kind === 'str32') {
    // UTF-16BE, até 16 chars, termina em 0x0000; qualquer byte 0xFF = apagado
    const raw = buf.subarray(off, off + 32)
    if (raw.includes(0xff)) return ''
    let end = 0
    while (end < 32 && (raw[end] || raw[end + 1])) end += 2
    return new TextDecoder('utf-16be').decode(raw.subarray(0, end))
  }
  if (kind === 'f') {
    const f = v.getFloat32(off, true)
    // flash apagada (0xFFFFFFFF) é NaN. shortcut: toFixed arredonda empate exato pra cima e o round()
    // do Python pra par (0.03125 -> 0.0313 aqui, 0.0312 lá); só muda a exibição
    return Number.isFinite(f) ? Number(f.toFixed(4)) : null
  }
  if (kind === 'B') return v.getUint8(off)
  if (kind === 'H') return v.getUint16(off, true)
  const n = v.getUint32(off, true)
  if (kind === 'F') return FLAGS[n] ?? hex8(n)
  if (kind === 'K') return KEYCODES[n] ?? hex8(n)
  if (kind === 'M') {
    if (n === 0xffffffff) return hex8(n)
    const names = Object.entries(FEATURES).filter(([b]) => n & Number(b)).map(([, name]) => name)
    const rest = (n & ~FEATURE_BITS) >>> 0
    return rest ? [...names, hex8(rest)] : names
  }
  if (kind === 'X') return hex8(n)
  if (kind === 'C') return '#' + n.toString(16).padStart(6, '0')
  return n
}

function parseHex(val: unknown): number {
  if (typeof val !== 'string' || !/^(0x)?[0-9a-f]+$/i.test(val)) throw new Error(`valor não é hex: ${String(val)}`)
  return parseInt(val, 16)
}

function fromNames(table: Readonly<Record<number, string>>, val: unknown): number {
  if (typeof val === 'number') return val
  const hit = Object.entries(table).find(([, name]) => name === val)
  return hit ? Number(hit[0]) : parseHex(val)
}

function toInt(val: unknown, max: number): number {
  const n = typeof val === 'string' && val.trim() !== '' ? Number(val) : val
  // struct.pack_into estoura no Python; o DataView truncaria sem avisar
  if (typeof n !== 'number' || !Number.isInteger(n) || n < 0 || n > max) throw new RangeError(`fora da faixa 0..${max}: ${String(val)}`)
  return n
}

export function putField(buf: Uint8Array, off: number, kind: Kind, val: unknown): void {
  const v = view(buf)
  if (kind === 'str32') {
    if (typeof val !== 'string') throw new Error('nome tem q ser texto')
    const name = Array.from(val).slice(0, 16).join('')
    if (name.length > 16) throw new Error('nome não cabe nos 32 bytes')
    const out = new Uint8Array(32)
    for (let i = 0; i < name.length; i++) out.set([name.charCodeAt(i) >> 8, name.charCodeAt(i) & 0xff], 2 * i)
    buf.set(out, off)
  } else if (kind === 'f') {
    const f = val === null ? NaN : Number(val)
    if (val !== null && Number.isNaN(f)) throw new Error(`float inválido: ${String(val)}`)
    v.setFloat32(off, f, true)
  } else if (kind === 'B') {
    v.setUint8(off, toInt(val, 0xff))
  } else if (kind === 'H') {
    v.setUint16(off, toInt(val, 0xffff), true)
  } else {
    let n: number
    if (kind === 'F') n = fromNames(FLAGS, val)
    else if (kind === 'K') n = fromNames(KEYCODES, val)
    else if (kind === 'M') {
      if (typeof val === 'string') n = parseHex(val)
      else if (Array.isArray(val)) n = val.reduce((a: number, x) => a + fromNames(FEATURES, x), 0)
      else throw new Error('máscara tem q ser lista de nomes ou hex')
    } else if ((kind === 'X' || kind === 'C') && typeof val === 'string') n = parseHex(val.replace(/^#+/, ''))
    else n = val as number
    v.setUint32(off, toInt(n, 0xffffffff), true)
  }
}

export function decode(buf: Uint8Array): ConfigDoc {
  if (buf.length !== CFG_SIZE) throw new Error(`registro tem q ter ${CFG_SIZE} bytes, veio ${buf.length}`)
  const out: Record<string | number, unknown> = {}
  for (const { path, off, kind } of FIELDS) {
    let node = out
    for (let i = 0; i < path.length - 1; i++) {
      // chave numérica vira lista, igual o fix() do Python
      const k = path[i] as string | number
      node[k] ??= typeof path[i + 1] === 'number' ? [] : {}
      node = node[k] as Record<string | number, unknown>
    }
    node[path[path.length - 1] as string | number] = getField(buf, off, kind)
  }
  return out as unknown as ConfigDoc
}

function lookup(doc: unknown, path: Path): { found: boolean; value?: unknown } {
  let node = doc
  for (const k of path) {
    if (typeof node !== 'object' || node === null || !(k in node)) return { found: false }
    node = (node as Record<string | number, unknown>)[k]
  }
  return { found: true, value: node }
}

const same = (a: unknown, b: unknown) =>
  Array.isArray(a) && Array.isArray(b) ? a.length === b.length && a.every((x, i) => x === b[i]) : a === b

export interface Encoded { record: Uint8Array; changed: string[]; problems: string[] }

// Escreve doc por cima de base. Só regrava o campo q difere de decode(base) e recalcula o crc_value
// como o ANSI_CRC_16_Ultimate2 do app: sobre o buffer inteiro, com o crc antigo ainda dentro.
// check confere cada campo mudado antes de virar byte (o Python não tem isso).
export function encode(doc: unknown, base: Uint8Array, check: (path: string, value: unknown) => string | null = () => null): Encoded {
  const cur = decode(base)
  const record = base.slice()
  const changed: string[] = []
  const problems: string[] = []
  for (const { path, off, kind } of FIELDS) {
    if (path[0] === 'crc_value') continue
    const next = lookup(doc, path)
    if (next.found && !same(next.value, lookup(cur, path).value)) {
      const name = path.join('/')
      const problem = check(name, next.value)
      if (problem) problems.push(problem)
      else putField(record, off, kind, next.value)
      changed.push(name)
    }
  }
  view(record).setUint32(CRC_FIELD[0], crc16(record), true)
  return { record, changed, problems }
}

// Barreira antes de gravar: tamanho certo e crc_value batendo com o q o encode calcularia sobre base.
export function recordProblem(record: Uint8Array, base: Uint8Array): string | null {
  if (record.length !== CFG_SIZE) return `registro com ${record.length} bytes, esperado ${CFG_SIZE}`
  const probe = record.slice()
  probe.set(base.subarray(CRC_FIELD[0], CRC_FIELD[1]), CRC_FIELD[0])
  return crc16(probe) === view(record).getUint32(CRC_FIELD[0], true) ? null : 'CRC do registro não confere'
}

// Preenche o perfil n com os padrões q o app do Windows usa num perfil novo (devolve cópia).
export function defaultSlot(doc: ConfigDoc, n: 0 | 1 | 2, name: string): ConfigDoc {
  const out = structuredClone(doc)
  const mode = out.gamepad_mode
  const s = out.slots[n]
  const on = 'enabled'
  const ident = mode === 0 ? ['B', 'A', 'Y', 'X'] : ['A', 'B', 'X', 'Y']
  const keys = [...ident, 'LB', 'RB', 'LT', 'RT', 'L3', 'R3', 'Select', 'Start',
    mode === 0 ? 'Screenshot' : 'Menu', 'Home', 'Up', 'Down', 'Left', 'Right', 'None', 'None', 'None', 'None']
  const tstart = mode === 0 ? 77 : 0
  const slot: Slot = {
    ...s, flag: on, name,
    rumble: { flag: on, left: 1.0, right: 1.0 },
    sticks: { flag: on, left_start: 17, left_end: 128, right_start: 17, right_end: 128 },
    triggers: { flag: on, left_start: tstart, left_end: 255, right_start: tstart, right_end: 255 },
    xinput_rumble: { flag: on, left_start: 1, left_end: 100, right_start: 1, right_end: 100 },
    special: { flag: on, features: [] },
    mapping: { flag: on, ...Object.fromEntries(BUTTONS.map((b, i) => [b, keys[i] as string])) },
    sixaxis: { ...s.sixaxis, flag: 'disabled', sensitivity: 10, dead_compensate: 40 },
    led_dynamic: { flag: on, color: '#260032', bg_color: '#084e50' },
    led_hotwheel: { flag: on, color: '#cc6200', bg_color: '#cc0000', speed: 7 },
    led_single: { flag: on, colors: Array<string>(24).fill('#7e3200') },
    macros: {
      ...s.macros, flag: on, total_cnt: 0,
      records: Array.from({ length: 4 }, () => ({ name: '', gamepad_mode: mode, special_flag: 0, max_steps: 0, offset: 0, key_map: '0x00000000', cycles_num: 0, interval_ms: 0 })),
    },
  }
  out.slots[n] = slot
  return out
}
