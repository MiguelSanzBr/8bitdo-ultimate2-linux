import { describe, expect, it } from 'vitest'
import { DemoTransport, demoRecord } from './demo'
import { decode } from '../domain/record'
import { IDLE } from '../domain/live-input'
import {
  CFG_SIZE, CMD_COMMIT, CMD_GET_THEME, CMD_INFO, CMD_READ, CMD_REPORT, CMD_SET_THEME, CMD_WRITE, COMMIT_KEY,
  buildRequest, crc16, parseInfo, parseReply,
} from '../domain/packet'

const tick = () => new Promise((r) => setTimeout(r, 0))

// controle com o dreno ligado, senão o firmware simulado fica mudo
function demo() {
  const t = new DemoTransport()
  t.start()
  return t
}

async function talk(t: DemoTransport, req: Uint8Array) {
  const got: Uint8Array[] = []
  const off = t.onReport((r) => got.push(r))
  await t.send(req)
  await tick()
  off()
  return got
}

describe('demoRecord', () => {
  it('é um controle com o perfil 1 criado e ativo', () => {
    const d = decode(demoRecord())
    expect([d.gamepad_mode, d.cur_slot, d.slots[0].flag, d.slots[0].name]).toEqual([3, 0, 'enabled', 'Demo'])
    expect(d.slots[1].flag).toBe('0xffffffff')
  })
})

describe('DemoTransport', () => {
  // espelha tests/fake_device.FakeController._serve
  it('responde info com firmware, beta e PID', async () => {
    const t = demo()
    expect(t.kind).toBe('demo')
    await t.open()
    const [r] = await talk(t, buildRequest(CMD_INFO, { withCrc: false }))
    expect(r?.slice(0, 6)).toEqual(Uint8Array.of(2, 4, 4, 0, 0, 1))
    expect(parseInfo(r as Uint8Array)).toEqual({ firmware: 110, beta: 0, devicePid: 0x6012 })
  })

  it('lê pedaço do registro com crc certo na resposta', async () => {
    const t = demo()
    const [r] = await talk(t, buildRequest(CMD_READ, { total: CFG_SIZE, offset: 45, length: 45 }))
    const reply = parseReply(r as Uint8Array, CMD_READ)
    expect(reply?.data).toEqual(t.cfg.slice(45, 90))
    expect(new DataView((r as Uint8Array).buffer).getUint16(8, true)).toBe(crc16(t.cfg.slice(45, 90)))
  })

  it('escrita só vale depois do commit', async () => {
    const t = demo()
    const [w] = await talk(t, buildRequest(CMD_WRITE, { data: Uint8Array.of(9, 9), total: CFG_SIZE, offset: 100 }))
    expect(parseReply(w as Uint8Array, CMD_WRITE)?.length).toBe(2)
    expect(t.cfg.slice(100, 102)).not.toEqual(Uint8Array.of(9, 9))
    const [c] = await talk(t, buildRequest(CMD_COMMIT, { sub: COMMIT_KEY, withCrc: false }))
    expect(parseReply(c as Uint8Array, CMD_COMMIT)).not.toBeNull()
    expect(t.cfg.slice(100, 102)).toEqual(Uint8Array.of(9, 9))
    expect(t.log.map(([cmd]) => cmd)).toEqual([CMD_WRITE, CMD_COMMIT])
  })

  it('commit corrompido grava outra coisa', async () => {
    const t = demo()
    t.corruptCommit = true
    const before = t.cfg[100]
    await talk(t, buildRequest(CMD_COMMIT, { sub: COMMIT_KEY, withCrc: false }))
    expect(t.cfg[100]).toBe((before as number) ^ 0xff)
  })

  it('tema de LED e liga/desliga dos reports', async () => {
    const t = demo()
    const [g] = await talk(t, buildRequest(CMD_GET_THEME))
    expect(parseReply(g as Uint8Array, CMD_GET_THEME)?.data).toEqual(Uint8Array.of(2))
    await talk(t, buildRequest(CMD_SET_THEME, { sub: 4 }))
    expect(t.theme).toBe(4)
    expect(await talk(t, buildRequest(CMD_REPORT, { sub: 0, withCrc: false }))).toHaveLength(1)
  })

  it('ignora o q não é pedido 81 04 e comando desconhecido', async () => {
    const t = demo()
    expect(await talk(t, Uint8Array.of(0x81, 5, 0, 0x21, 1))).toEqual([])
    expect(await talk(t, Uint8Array.of(0x81, 4, 1))).toEqual([])
    expect(await talk(t, new Uint8Array(64))).toEqual([])
    expect(await talk(t, buildRequest(0x77))).toEqual([])
  })

  it('drop e silent simulam resposta perdida', async () => {
    const t = demo()
    t.drop = 1
    expect(await talk(t, buildRequest(CMD_GET_THEME))).toEqual([])
    expect(await talk(t, buildRequest(CMD_GET_THEME))).toHaveLength(1)
    t.silent.add(CMD_GET_THEME)
    expect(await talk(t, buildRequest(CMD_GET_THEME))).toEqual([])
  })

  it('sem dreno fica mudo, igual o firmware com o joystick parado', async () => {
    const t = demo()
    t.stop()
    expect(t.running).toBe(false)
    expect(await talk(t, buildRequest(CMD_GET_THEME))).toEqual([])
    t.start()
    expect(await talk(t, buildRequest(CMD_GET_THEME))).toHaveLength(1)
  })

  it('fechado não entrega mais nada', async () => {
    const t = demo()
    const got: Uint8Array[] = []
    t.onReport((r) => got.push(r))
    await t.close()
    await t.send(buildRequest(CMD_GET_THEME))
    await tick()
    expect(got).toEqual([])
  })
})

describe('DemoTransport como fonte de input', () => {
  it('não tem botão físico: entrega o controle parado e nada mais', () => {
    const t = new DemoTransport()
    const seen: unknown[] = []
    const off = t.onInput((i) => seen.push(i))
    t.start()
    off()
    expect(seen).toEqual([IDLE])
  })
})
