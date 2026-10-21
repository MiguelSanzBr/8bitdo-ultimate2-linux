// Controle simulado pro modo demo e pros testes. Porta do tests/fake_device.py: responde os mesmos
// comandos, com escrita pendente até o commit, e tem os mesmos ganchos de falha (drop, silent, corruptCommit).
// Implementa os dois ports: canal e dreno. Igual o firmware, fica mudo enquanto ninguém drena o joystick.
import { decode, defaultSlot, encode } from '../domain/record'
import {
  CFG_SIZE, CMD_COMMIT, CMD_GET_THEME, CMD_INFO, CMD_READ, CMD_REPORT, CMD_SET_THEME, CMD_WRITE, REPORT_SIZE, crc16,
} from '../domain/packet'
import type { InputDrain, ReportChannel } from '../application/ports'
import { IDLE } from '../domain/live-input'
import type { LiveInput } from '../domain/live-input'

// flash apagada com o perfil 1 criado pelos padrões do app e ativo
export function demoRecord(): Uint8Array {
  const blank = new Uint8Array(CFG_SIZE).fill(0xff)
  blank.set([3, 0, 3, 0], 16)
  const doc = defaultSlot(decode(blank), 0, 'Demo')
  doc.cur_slot = 0
  return encode(doc, blank).record
}

export class DemoTransport implements ReportChannel, InputDrain {
  readonly kind = 'demo'
  cfg: Uint8Array
  pending: Uint8Array
  firmware = 110
  beta = 0
  reportPid = 0x6012
  theme = 2
  drop = 0
  silent = new Set<number>()
  corruptCommit = false
  running = false
  log: [cmd: number, sub: number, length: number, offset: number][] = []
  private listeners = new Set<(r: Uint8Array) => void>()

  constructor(cfg = demoRecord()) {
    this.cfg = cfg.slice()
    this.pending = cfg.slice()
  }

  start(): void {
    this.running = true
  }

  stop(): void {
    this.running = false
  }

  // no demo quem aperta é o ponteiro no desenho, isso fica na tela
  onInput(cb: (input: LiveInput) => void): () => void {
    cb(IDLE)
    return () => {}
  }

  async open(): Promise<void> {}

  async close(): Promise<void> {
    this.listeners.clear()
  }

  onReport(cb: (r: Uint8Array) => void): () => void {
    this.listeners.add(cb)
    return () => this.listeners.delete(cb)
  }

  async send(pkt: Uint8Array): Promise<void> {
    if (pkt.length < 18 || pkt[0] !== 0x81 || pkt[1] !== 4) return
    const v = new DataView(pkt.buffer, pkt.byteOffset, pkt.byteLength)
    const [cmd, sub, length, total, off] = [v.getUint16(2, true), v.getUint16(4, true), v.getUint16(6, true), v.getUint32(10, true), v.getUint32(14, true)]
    this.log.push([cmd, sub, length, off])
    if (this.drop) {
      this.drop--
      return
    }
    if (this.silent.has(cmd) || !this.running) return
    if (cmd === CMD_INFO) {
      const body = new Uint8Array(8)
      const b = new DataView(body.buffer)
      b.setUint16(0, this.firmware, true)
      b.setUint8(2, this.beta)
      b.setUint16(4, this.reportPid, true)
      this.reply(cmd, body)
    } else if (cmd === CMD_READ) {
      this.reply(cmd, this.cfg.slice(off, off + length), total, off)
    } else if (cmd === CMD_WRITE) {
      this.pending.set(pkt.subarray(18, 18 + length), off)
      this.reply(cmd, new Uint8Array(), total, off, length)
    } else if (cmd === CMD_COMMIT) {
      this.cfg = this.pending.slice()
      if (this.corruptCommit) this.cfg[100] = (this.cfg[100] as number) ^ 0xff
      this.reply(cmd)
    } else if (cmd === CMD_REPORT) {
      this.reply(cmd)
    } else if (cmd === CMD_SET_THEME) {
      this.theme = sub
      this.reply(cmd)
    } else if (cmd === CMD_GET_THEME) {
      this.reply(cmd, Uint8Array.of(this.theme))
    }
  }

  private reply(cmd: number, data = new Uint8Array(), total = 0, offset = 0, length = data.length): void {
    const r = new Uint8Array(REPORT_SIZE)
    const v = new DataView(r.buffer)
    r.set([2, 4])
    v.setUint16(2, 4, true)
    v.setUint16(4, cmd, true)
    v.setUint16(6, length, true)
    v.setUint16(8, crc16(data), true)
    v.setUint32(10, total, true)
    v.setUint32(14, offset, true)
    r.set(data, 18)
    // resposta chega depois, como um inputreport de verdade
    queueMicrotask(() => this.listeners.forEach((l) => l(r)))
  }
}
