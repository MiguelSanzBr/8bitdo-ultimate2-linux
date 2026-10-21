import { describe, expect, it } from 'vitest'
import {
  CFG_SIZE, CHUNK, CMD_COMMIT, CMD_GET_THEME, CMD_INFO, CMD_READ, CMD_REPORT, CMD_SET_THEME, CMD_WRITE,
  COMMIT_KEY, PIDS, REPORT_SIZE, THEMES, USAGE_PAGES, VID, buildRequest, crc16, parseInfo, parseReply,
} from './packet'

import { hex } from '../test/fixtures'
const pad = (b: number[]) => {
  const r = new Uint8Array(REPORT_SIZE)
  r.set(b)
  return r
}

describe('constantes', () => {
  it('batem com o protocol.py', () => {
    // espelha test_protocol.test_constants
    expect([VID, CFG_SIZE, CHUNK, REPORT_SIZE]).toEqual([0x2dc8, 1592, 45, 64])
    expect(PIDS[0x6012]).toBe('Ultimate 2')
    expect(Object.keys(PIDS).map(Number)).toEqual([0x310b, 0x6012, 0x6013])
    expect([CMD_WRITE, CMD_READ, CMD_COMMIT, CMD_REPORT]).toEqual([1, 2, 6, 7])
    expect([CMD_SET_THEME, CMD_GET_THEME, CMD_INFO, COMMIT_KEY]).toEqual([0x40, 0x41, 0x0100, 0x123])
    expect(THEMES).toEqual({ 2: 'dynamic', 3: 'hotwheel', 4: 'custom', 5: 'off' })
    // espelha discovery.CONFIG_DESCRIPTORS (06 7a ff / 06 a0 ff)
    expect(USAGE_PAGES).toEqual([0xff7a, 0xffa0])
  })
})

describe('crc16', () => {
  it('é CRC-16/MODBUS', () => {
    // espelha protocol.crc16(b"123456789") e crc16(bytes(45)) (test_crc_known_value)
    expect(crc16(new TextEncoder().encode('123456789'))).toBe(0x4b37)
    expect(crc16(new Uint8Array(45))).toBe(0xcf30)
    expect(crc16(new Uint8Array())).toBe(0xffff)
  })
})

describe('buildRequest', () => {
  it('monta escrita com dados, total e offset', () => {
    // espelha protocol.build_request(CMD_WRITE, data=b"abc", total=10, offset=4)
    expect(buildRequest(CMD_WRITE, { data: Uint8Array.of(0x61, 0x62, 0x63), total: 10, offset: 4 })).toEqual(
      hex('810401000000030049570a0000000400000061626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000'),
    )
  })

  it('leitura manda payload zerado do tamanho pedido', () => {
    // espelha protocol.build_request(CMD_READ, total=1592, offset=45, length=45)
    expect(buildRequest(CMD_READ, { total: CFG_SIZE, offset: 45, length: 45 })).toEqual(
      hex('8104020000002d0030cf380600002d00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'),
    )
  })

  it('commit e report vão sem crc', () => {
    // espelha protocol.build_request(CMD_COMMIT, sub=COMMIT_KEY, with_crc=False)
    expect(buildRequest(CMD_COMMIT, { sub: COMMIT_KEY, withCrc: false })).toEqual(pad([0x81, 4, 6, 0, 0x23, 1]))
    // espelha protocol.build_request(CMD_SET_THEME, sub=3): crc de dado vazio = 0xffff
    expect(buildRequest(CMD_SET_THEME, { sub: 3 })).toEqual(pad([0x81, 4, 0x40, 0, 3, 0, 0, 0, 0xff, 0xff]))
  })

  it('pedido de info é o 81 04 00 01 fixo do device.info', () => {
    // espelha device.Device.info: b"\x81\x04\x00\x01" completado com zero até 64 bytes
    expect(buildRequest(CMD_INFO, { withCrc: false })).toEqual(pad([0x81, 4, 0, 1]))
  })
})

const answer = (cmd: number, data: number[] = [], length = data.length) =>
  pad([2, 4, 4, 0, cmd & 0xff, cmd >> 8, length & 0xff, length >> 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ...data])

describe('parseReply', () => {
  it('devolve tamanho e dados da resposta ao comando', () => {
    // espelha test_protocol.test_parse_reply
    expect(parseReply(answer(CMD_READ, [0x61, 0x62, 0x63]), CMD_READ)).toEqual({ length: 3, data: Uint8Array.of(0x61, 0x62, 0x63) })
    expect(parseReply(answer(CMD_READ), CMD_READ)).toEqual({ length: 0, data: new Uint8Array() })
    expect(parseReply(answer(CMD_INFO), CMD_INFO)?.length).toBe(0)
  })

  it('ignora outro comando, report curto ou cabeçalho errado', () => {
    expect(parseReply(answer(CMD_WRITE, [1]), CMD_READ)).toBeNull()
    expect(parseReply(Uint8Array.of(2, 4), CMD_READ)).toBeNull()
    expect(parseReply(new Uint8Array(64).fill(3), CMD_READ)).toBeNull()
    expect(parseReply(pad([2, 5]), CMD_READ)).toBeNull()
    expect(parseReply(pad([2, 4, 5, 0, CMD_READ, 0]), CMD_READ)).toBeNull()
  })
})

describe('parseInfo', () => {
  it('lê firmware x100, beta e PID', () => {
    // espelha test_protocol.test_parse_info
    const r = new Uint8Array(64)
    r.set([0x6e, 0x01, 3, 0, 0x12, 0x60], 18)
    expect(parseInfo(r)).toEqual({ firmware: 0x16e, beta: 3, devicePid: 0x6012 })
  })
})
