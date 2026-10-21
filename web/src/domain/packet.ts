// Porta do ultimate2/protocol.py. Todo report tem 64 bytes contando o id: pedido começa com 81 04 e
// resposta com 02 04, cabeçalho = u16 cmd, u16 sub, u16 len, u16 crc16(data), u32 total, u32 offset.
// O detalhe tá no docs/PROTOCOL.md do 8bitdo-ultimate2-linux.

export const VID = 0x2dc8
export const PIDS: Readonly<Record<number, string>> = { 0x310b: 'wired (XInput)', 0x6012: 'Ultimate 2', 0x6013: '2.4G dongle' }
// canal de config: usage page 0xFF7A no controle, 0xFFA0 no dongle 2.4G
export const USAGE_PAGES = [0xff7a, 0xffa0]
export const CFG_SIZE = 1592
export const CHUNK = 45
export const REPORT_SIZE = 64

export const CMD_WRITE = 1
export const CMD_READ = 2
export const CMD_COMMIT = 6
export const CMD_REPORT = 7
export const CMD_SET_THEME = 0x40
export const CMD_GET_THEME = 0x41
export const CMD_INFO = 0x0100
// sub-comando do CMD_COMMIT q grava o registro na flash
export const COMMIT_KEY = 0x123
// tema de LED ativo, global, não é por perfil
export const THEMES: Readonly<Record<number, string>> = { 2: 'dynamic', 3: 'hotwheel', 4: 'custom', 5: 'off' }

export function crc16(data: Uint8Array): number {
  let c = 0xffff
  for (let b of data) {
    for (let i = 0; i < 8; i++) {
      c = (c >> 1) ^ ((c ^ b) & 1 ? 0xa001 : 0)
      b >>= 1
    }
  }
  return c
}

export interface RequestOpts {
  sub?: number
  data?: Uint8Array
  total?: number
  offset?: number
  length?: number
  withCrc?: boolean
}

export function buildRequest(cmd: number, { sub = 0, data = new Uint8Array(), total = 0, offset = 0, length = data.length, withCrc = true }: RequestOpts = {}): Uint8Array {
  // leitura manda len = tamanho pedido com payload zerado
  const body = new Uint8Array(length)
  body.set(data)
  const pkt = new Uint8Array(REPORT_SIZE)
  const v = new DataView(pkt.buffer)
  pkt.set([0x81, 0x04])
  v.setUint16(2, cmd, true)
  v.setUint16(4, sub, true)
  v.setUint16(6, length, true)
  v.setUint16(8, withCrc ? crc16(body) : 0, true)
  v.setUint32(10, total, true)
  v.setUint32(14, offset, true)
  pkt.set(body, 18)
  return pkt
}

export interface Reply {
  length: number
  data: Uint8Array
}

export function parseReply(report: Uint8Array, cmd: number): Reply | null {
  if (report.length < 18 || report[0] !== 2 || report[1] !== 4) return null
  const v = new DataView(report.buffer, report.byteOffset, report.byteLength)
  if (v.getUint16(2, true) !== 4 || v.getUint16(4, true) !== cmd) return null
  const length = v.getUint16(6, true)
  return { length, data: report.slice(18, 18 + length) }
}

export interface ControllerInfo {
  firmware: number
  beta: number
  devicePid: number
}

export function parseInfo(report: Uint8Array): ControllerInfo {
  const v = new DataView(report.buffer, report.byteOffset, report.byteLength)
  return { firmware: v.getUint16(18, true), beta: v.getUint8(20), devicePid: v.getUint16(22, true) }
}
