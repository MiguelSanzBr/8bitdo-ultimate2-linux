import { describe, expect, it } from 'vitest'
import {
  BUTTONS, CRC_FIELD, FEATURES, FIELDS, FLAGS, KEYCODES, decode, defaultSlot, encode, getField, putField, recordProblem,
} from './record'
import { CFG_SIZE, crc16 } from './packet'
import { DEFAULT_SLOT0_HEX, blankRecord, hex } from '../test/fixtures'

const u32 = (n: number) => {
  const b = new Uint8Array(4)
  new DataView(b.buffer).setUint32(0, n, true)
  return b
}
const g = (raw: Uint8Array, kind: Parameters<typeof getField>[2]) => {
  const b = new Uint8Array(64)
  b.set(raw)
  return getField(b, 0, kind)
}
const p = (kind: Parameters<typeof putField>[2], val: unknown) => {
  const b = new Uint8Array(64)
  putField(b, 0, kind, val)
  return b
}
const rd = (b: Uint8Array) => new DataView(b.buffer).getUint32(0, true)

// PRNG fixo pra rodar sempre os mesmos registros aleatórios
function rng(seed: number) {
  return () => {
    seed = (seed * 1103515245 + 12345) >>> 0
    return seed >>> 24
  }
}

describe('tabelas', () => {
  it('batem com o config.py', () => {
    // espelha test_config.test_tables e test_rt_and_home_codes_match_the_app
    expect(FLAGS[0x20200911]).toBe('enabled')
    expect(BUTTONS).toHaveLength(22)
    expect(CRC_FIELD).toEqual([12, 16])
    expect([KEYCODES[0x2000], KEYCODES[0x8000], KEYCODES[0x20000], FEATURES[0x1]]).toEqual(['A', 'RT', 'Home', 'invert_LS_X'])
  })

  it('os campos cobrem os 1592 bytes', () => {
    // espelha test_config.test_layout_covers_record
    const size = { str32: 32, H: 2, B: 1 } as Record<string, number>
    expect(Math.max(...FIELDS.map((f) => f.off + (size[f.kind] ?? 4)))).toBe(CFG_SIZE)
  })
})

describe('getField', () => {
  it('str32 em UTF-16BE, 0xFF = apagado', () => {
    // espelha test_config.test_get_str32
    expect(g(new Uint8Array(32).fill(0xff), 'str32')).toBe('')
    expect(g(Uint8Array.of(0, 0x48, 0, 0x69), 'str32')).toBe('Hi')
    const full = Uint8Array.from('ABCDEFGHIJKLMNOP', (c) => c.charCodeAt(0))
    expect(g(Uint8Array.from([...full].flatMap((c) => [0, c])), 'str32')).toBe('ABCDEFGHIJKLMNOP')
  })

  it('float arredondado em 4 casas, NaN vira null', () => {
    // espelha test_config.test_get_float
    const f = new Uint8Array(4)
    new DataView(f.buffer).setFloat32(0, 1.23456, true)
    expect(g(f, 'f')).toBe(1.2346)
    expect(g(new Uint8Array(4).fill(0xff), 'f')).toBeNull()
  })

  it('flag e código de tecla por nome, senão hex', () => {
    // espelha test_config.test_get_flag_key
    expect(g(u32(0x20200911), 'F')).toBe('enabled')
    expect(g(u32(0x12345678), 'F')).toBe('0x12345678')
    expect(g(u32(0x2000), 'K')).toBe('A')
    expect(g(u32(0x77777), 'K')).toBe('0x00077777')
  })

  it('máscara de features com bits desconhecidos preservados', () => {
    // espelha test_config.test_get_mask e config._get(0x10000081, "M")
    expect(g(new Uint8Array(4).fill(0xff), 'M')).toBe('0xffffffff')
    expect(g(u32(0x11), 'M')).toEqual(['invert_LS_X', 'swap_sticks'])
    expect(g(u32(0x10000081), 'M')).toEqual(['invert_LS_X', 'swap_triggers', '0x10000000'])
    expect(g(u32(0), 'M')).toEqual([])
  })

  it('hex, cor e inteiros', () => {
    // espelha test_config.test_get_plain
    expect(g(u32(0xab), 'X')).toBe('0x000000ab')
    expect(g(u32(0x260032), 'C')).toBe('#260032')
    expect(g(Uint8Array.of(7), 'B')).toBe(7)
    expect(g(Uint8Array.of(0x34, 0x12), 'H')).toBe(0x1234)
    expect(g(u32(99), 'I')).toBe(99)
  })
})

describe('putField', () => {
  it('str32 corta em 16 caracteres e completa com zero', () => {
    // espelha test_config.test_put_str32
    const b = p('str32', 'A'.repeat(20))
    expect(b.slice(0, 32)).toEqual(Uint8Array.from({ length: 32 }, (_, i) => (i % 2 ? 0x41 : 0)))
    expect(b[32]).toBe(0)
    expect(p('str32', 'Hi').slice(0, 6)).toEqual(Uint8Array.of(0, 0x48, 0, 0x69, 0, 0))
    expect(g(p('str32', 'Ωmega'), 'str32')).toBe('Ωmega')
  })

  it('recusa nome q não cabe em 32 bytes ou q não é texto', () => {
    // no Python isso aumentaria o bytearray e o write_config barraria no assert de tamanho
    expect(() => p('str32', '😀'.repeat(16))).toThrow(/32 bytes/)
    expect(() => p('str32', 5)).toThrow(/texto/)
  })

  it('float, null vira NaN', () => {
    // espelha test_config.test_put_float
    expect(new DataView(p('f', 0.5).buffer).getFloat32(0, true)).toBe(0.5)
    expect(p('f', null).slice(0, 4)).toEqual(Uint8Array.of(0, 0, 0xc0, 0x7f))
    expect(() => p('f', 'abc')).toThrow(/float/)
  })

  it('flag e tecla aceitam nome, número ou hex', () => {
    // espelha test_config.test_put_flag_key_names
    expect(rd(p('F', 'enabled'))).toBe(0x20200911)
    expect(rd(p('F', 5))).toBe(5)
    expect(rd(p('F', '0x20190000'))).toBe(0x20190000)
    expect(rd(p('K', 'A'))).toBe(0x2000)
    expect(rd(p('K', '0x1234'))).toBe(0x1234)
    expect(() => p('K', 'Nada')).toThrow(/hex/)
    expect(() => p('K', true)).toThrow(/hex/)
  })

  it('máscara soma os nomes ou lê hex', () => {
    // espelha test_config.test_put_mask
    expect(rd(p('M', ['invert_LS_X', 0x10, '0x80']))).toBe(0x91)
    expect(rd(p('M', '0x1f'))).toBe(0x1f)
    expect(rd(p('M', []))).toBe(0)
    expect(() => p('M', 7)).toThrow(/máscara/)
  })

  it('hex, cor e inteiros com faixa conferida', () => {
    // espelha test_config.test_put_x_c_and_ints
    expect(rd(p('C', '#7e3200'))).toBe(0x7e3200)
    expect(rd(p('X', '0x00000010'))).toBe(0x10)
    expect(rd(p('X', 5))).toBe(5)
    expect(p('B', '7')[0]).toBe(7)
    expect(new DataView(p('H', 513).buffer).getUint16(0, true)).toBe(513)
    expect(rd(p('I', 70000))).toBe(70000)
    // struct.pack_into estoura com struct.error no Python; DataView truncaria calado
    expect(() => p('B', 256)).toThrow(RangeError)
    expect(() => p('H', -1)).toThrow(RangeError)
    expect(() => p('I', 2 ** 32)).toThrow(RangeError)
    expect(() => p('B', 1.5)).toThrow(RangeError)
    expect(() => p('B', '')).toThrow(RangeError)
  })
})

describe('decode', () => {
  it('monta 3 perfis, 4 macros e 24 LEDs', () => {
    // espelha test_config.test_decode_shape
    const d = decode(new Uint8Array(CFG_SIZE))
    expect(d.slots).toHaveLength(3)
    expect(d.slots[0].macros.records).toHaveLength(4)
    expect(d.slots[2].led_single.colors).toHaveLength(24)
  })

  it('lê o registro em branco igual ao Python', () => {
    // espelha config.decode(blank_config.bin)
    const d = decode(blankRecord())
    expect([d.crc_value, d.gamepad_mode, d.cur_slot]).toEqual([0xffffffff, 3, 3])
    const s = d.slots[0]
    expect([s.flag, s.name, s.rumble.left, s.sticks.left_start, s.special.features]).toEqual(['0xffffffff', '', null, 255, '0xffffffff'])
    expect([s.mapping.A, s.led_dynamic.color, s.sixaxis.trigger_mode]).toEqual(['0xffffffff', '#ffffffff', 255])
  })

  it('recusa registro com tamanho errado', () => {
    expect(() => decode(new Uint8Array(10))).toThrow(/1592/)
  })
})

describe('encode', () => {
  it('sem edição devolve os mesmos bytes; editar só mexe no campo', () => {
    // espelha test_config.test_roundtrip_and_edit
    const next = rng(0)
    for (let n = 0; n < 20; n++) {
      const b = Uint8Array.from({ length: CFG_SIZE }, next)
      const doc = JSON.parse(JSON.stringify(decode(b)))
      const same = encode(doc, b)
      expect(same.record.slice(16)).toEqual(b.slice(16))
      expect(same.changed).toEqual([])
      const s = doc.slots[1].sticks
      s.left_start = (s.left_start + 1) % 256
      doc.slots[2].name = doc.slots[2].name !== 'Teste' ? 'Teste' : 'X'
      const { record, changed } = encode(doc, b)
      const d2 = decode(record)
      expect(d2.slots[1].sticks.left_start).toBe(s.left_start)
      expect(d2.slots[2].name).toBe(doc.slots[2].name)
      expect(changed).toHaveLength(2)
    }
  })

  it('perfil novo com os padrões do app sai igual ao Python', () => {
    // espelha config.encode(config.default_slot(decode(blank), 0, "Demo"), blank)
    const blank = blankRecord()
    const { record, changed } = encode(defaultSlot(decode(blank), 0, 'Demo'), blank)
    expect(record).toEqual(hex(DEFAULT_SLOT0_HEX))
    expect(changed).toHaveLength(108)
    expect(changed.slice(0, 3)).toEqual(['slots/0/flag', 'slots/0/name', 'slots/0/rumble/flag'])
    expect(changed.at(-1)).toBe('slots/0/led_single/colors/23')
  })

  it('remapear um botão regrava só ele e o crc', () => {
    // espelha config.encode com slots[0].mapping.A = "B" sobre o registro acima: crc 0xc6f3
    const base = hex(DEFAULT_SLOT0_HEX)
    const doc = decode(base)
    doc.slots[0].mapping.A = 'B'
    const { record, changed } = encode(doc, base)
    expect(changed).toEqual(['slots/0/mapping/A'])
    expect(record.slice(228, 232)).toEqual(Uint8Array.of(0, 0x10, 0, 0))
    expect(new DataView(record.buffer).getUint32(12, true)).toBe(0xc6f3)
  })

  it('nome, analógico, features e cor batem com o Python', () => {
    // espelha config.encode com name/sticks.left_start/special.features/led_dynamic.color: crc 0x6779
    const base = hex(DEFAULT_SLOT0_HEX)
    const doc = decode(base)
    const s = doc.slots[0]
    s.name = 'Linux'
    s.sticks.left_start = 20
    s.special.features = ['invert_LS_Y', 'swap_triggers']
    s.led_dynamic.color = '#ff0000'
    const { record, changed } = encode(doc, base)
    expect(changed).toEqual(['slots/0/name', 'slots/0/sticks/left_start', 'slots/0/special/features', 'slots/0/led_dynamic/color'])
    expect(record.slice(20, 52)).toEqual(hex('004c0069006e0075007800000000000000000000000000000000000000000000'))
    expect(record.slice(156, 160)).toEqual(hex('14801180'))
    expect(record.slice(204, 208)).toEqual(hex('82000000'))
    expect(record.slice(1212, 1216)).toEqual(hex('0000ff00'))
    expect(new DataView(record.buffer).getUint32(12, true)).toBe(0x6779)
  })

  it('pula caminho ausente e ignora crc_value do documento', () => {
    // espelha test_config.test_encode_skips_missing_paths
    const base = blankRecord()
    base.set([0, 0, 0, 0], 16)
    for (const doc of [{}, { slots: [{}] }, { slots: 5 }, { gamepad_mode: 1, slots: null }]) {
      const { record, changed } = encode(doc, base)
      expect(record.slice(0, 12)).toEqual(base.slice(0, 12))
      expect(record.slice(20)).toEqual(base.slice(20))
      expect(changed).toEqual('gamepad_mode' in doc ? ['gamepad_mode'] : [])
    }
    const { record, changed } = encode({ crc_value: 1, gamepad_mode: 2 }, base)
    expect(changed).toEqual(['gamepad_mode'])
    const chk = record.slice()
    chk.set(base.slice(12, 16), 12)
    // o crc é calculado com o crc_value antigo ainda no buffer, igual ao Python
    expect(new DataView(record.buffer).getUint32(12, true)).toBe(crc16(chk))
  })
})

describe('defaultSlot', () => {
  it('usa os padrões de cada modo sem mexer no documento original', () => {
    // espelha test_config.test_default_slot_modes
    for (const [mode, ident, star, tstart] of [[0, ['B', 'A', 'Y', 'X'], 'Screenshot', 77], [3, ['A', 'B', 'X', 'Y'], 'Menu', 0]] as const) {
      const base = blankRecord()
      base.set([mode, 0], 16)
      const before = decode(base)
      const doc = defaultSlot(before, 1, 'N')
      const s = doc.slots[1]
      expect(['A', 'B', 'X', 'Y'].map((k) => s.mapping[k])).toEqual(ident)
      expect(s.mapping.Star).toBe(star)
      expect([s.triggers.left_start, s.name]).toEqual([tstart, 'N'])
      expect(s.macros.records.every((r) => r.gamepad_mode === mode)).toBe(true)
      expect(before.slots[1].flag).toBe('0xffffffff')
    }
  })
})

describe('recordProblem', () => {
  const base = hex(DEFAULT_SLOT0_HEX)
  const doc = decode(base)
  doc.slots[0].mapping.A = 'B'
  const { record } = encode(doc, base)

  it('aceita registro q saiu do encode', () => {
    expect(recordProblem(record, base)).toBeNull()
  })

  it('barra crc errado e tamanho errado', () => {
    const bad = record.slice()
    bad[12] = 0
    expect(recordProblem(bad, base)).toMatch(/CRC/)
    const edited = record.slice()
    edited[300] = 0x55
    expect(recordProblem(edited, base)).toMatch(/CRC/)
    expect(recordProblem(record.slice(0, 100), base)).toMatch(/1592/)
  })
})
