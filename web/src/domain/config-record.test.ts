import { describe, expect, it } from 'vitest'
import { ConfigRecord } from './config-record'
import { InvariantError } from './values'
import { encode } from './record'
import { DEFAULT_SLOT0_HEX, hex } from '../test/fixtures'

const base = () => ConfigRecord.fromBytes(hex(DEFAULT_SLOT0_HEX))

describe('ConfigRecord', () => {
  it('só nasce com 1592 bytes', () => {
    expect(() => ConfigRecord.fromBytes(new Uint8Array(100))).toThrow(InvariantError)
  })

  it('guarda cópia: mexer no array de fora não muda o agregado', () => {
    const bytes = hex(DEFAULT_SLOT0_HEX)
    const r = ConfigRecord.fromBytes(bytes)
    bytes[30] = 0x55
    const out = r.toBytes()
    out[31] = 0x55
    expect(r.toBytes()).toEqual(hex(DEFAULT_SLOT0_HEX))
  })

  it('expõe o documento e o crc_value', () => {
    // espelha config.encode(default_slot(...)): crc 0x8abc
    expect(base().crc).toBe(0x8abc)
    expect(base().toDoc().slots[0].name).toBe('Demo')
  })

  it('withChanges recalcula o crc e lista o q mudou', () => {
    const doc = base().toDoc()
    doc.slots[0].mapping.A = 'B'
    const { next, changed } = base().withChanges(doc)
    expect(changed).toEqual(['slots/0/mapping/A'])
    // espelha config.encode com mapping.A = "B": crc 0xc6f3
    expect(next.crc).toBe(0xc6f3)
    expect(next.equals(ConfigRecord.fromBytes(encode(doc, hex(DEFAULT_SLOT0_HEX)).record))).toBe(true)
    expect(next.equals(base())).toBe(false)
  })

  it('withChanges barra valor fora da faixa antes de virar byte', () => {
    const doc = base().toDoc()
    doc.slots[0].sticks.left_start = 200
    doc.slots[0].mapping.B = 'Voar'
    expect(() => base().withChanges(doc)).toThrow(/0 a 128.*\n.*função/s)
  })

  it('invariante de gravação: CRC tem q bater com o calculado sobre a base', () => {
    const doc = base().toDoc()
    doc.slots[0].name = 'Linux'
    const { next } = base().withChanges(doc)
    expect(() => next.assertWritableOver(base())).not.toThrow()
    const tampered = next.toBytes()
    tampered[300] = 0x55
    expect(() => ConfigRecord.fromBytes(tampered).assertWritableOver(base())).toThrow(/CRC/)
  })
})
