// Porta do ultimate2/device.py em cima de um ReportChannel: info, tema de LED, leitura e escrita do
// registro em pedaços de 45 bytes com retry e commit na flash.
import { CFG_SIZE, CHUNK, CMD_COMMIT, CMD_GET_THEME, CMD_INFO, CMD_READ, CMD_REPORT, CMD_SET_THEME, CMD_WRITE, COMMIT_KEY, buildRequest, parseInfo, parseReply } from '../domain/packet'
import type { ControllerInfo, Reply, RequestOpts } from '../domain/packet'
import type { ReportChannel } from './ports'

// quantas vezes o app tenta cada pedaço
export const RETRIES = 30

// controle mudo: no Linux é quase sempre o joystick sem ninguém drenando (ver drain.ts)
export class NoAnswerError extends Error {
  name = 'NoAnswerError'
}

export interface LinkOpts {
  timeoutMs: number
  commitTimeoutMs: number
  // pausa antes do commit, o time.sleep(0.1) do Python
  settleMs: number
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export class ControllerLink {
  readonly opts: LinkOpts
  private readonly t: ReportChannel

  constructor(t: ReportChannel, opts: Partial<LinkOpts> = {}) {
    this.t = t
    this.opts = { timeoutMs: 500, commitTimeoutMs: 3000, settleMs: 100, ...opts }
  }

  // manda o pedido e espera o report q responde o mesmo cmd; o resto é ignorado, igual o recv()
  private exchange(cmd: number, req: RequestOpts, timeout = this.opts.timeoutMs): Promise<Uint8Array | null> {
    return new Promise((resolve, reject) => {
      const finish = () => {
        clearTimeout(timer)
        off()
      }
      const off = this.t.onReport((r) => {
        if (parseReply(r, cmd)) {
          finish()
          resolve(r)
        }
      })
      const timer = setTimeout(() => {
        finish()
        resolve(null)
      }, timeout)
      this.t.send(buildRequest(cmd, req)).catch((e: unknown) => {
        finish()
        reject(e)
      })
    })
  }

  private async call(cmd: number, req: RequestOpts = {}, timeout?: number): Promise<Reply | null> {
    const r = await this.exchange(cmd, req, timeout)
    return r && parseReply(r, cmd)
  }

  async info(): Promise<ControllerInfo | null> {
    const r = await this.exchange(CMD_INFO, { withCrc: false })
    return r && parseInfo(r)
  }

  // liga/desliga os input reports em volta da escrita, como o app
  async report(on: boolean): Promise<void> {
    await this.call(CMD_REPORT, { sub: on ? 1 : 0, withCrc: false })
  }

  async getTheme(): Promise<number | null> {
    const r = await this.call(CMD_GET_THEME)
    return r?.length ? (r.data[0] as number) : null
  }

  async setTheme(theme: number): Promise<void> {
    if (!(await this.call(CMD_SET_THEME, { sub: theme }))) throw new NoAnswerError('o controle não confirmou o tema de LED')
  }

  async readConfig(): Promise<Uint8Array> {
    const buf = new Uint8Array(CFG_SIZE)
    let got = 0
    let tries = 0
    while (got < CFG_SIZE) {
      const r = await this.call(CMD_READ, { total: CFG_SIZE, offset: got, length: Math.min(CHUNK, CFG_SIZE - got) })
      if (!r?.length) {
        if (++tries >= RETRIES) throw new NoAnswerError(`leitura falhou no offset ${got}`)
        continue
      }
      tries = 0
      buf.set(r.data.subarray(0, CFG_SIZE - got), got)
      got += r.data.length
    }
    return buf
  }

  // Escreve o registro inteiro e manda o commit pra flash.
  async writeConfig(data: Uint8Array): Promise<void> {
    if (data.length !== CFG_SIZE) throw new Error(`registro tem q ter ${CFG_SIZE} bytes, veio ${data.length}`)
    await this.report(false)
    try {
      let off = 0
      let tries = 0
      while (off < CFG_SIZE) {
        const r = await this.call(CMD_WRITE, { data: data.subarray(off, off + CHUNK), total: CFG_SIZE, offset: off })
        if (!r?.length) {
          if (++tries >= RETRIES) throw new NoAnswerError(`escrita falhou no offset ${off}`)
          continue
        }
        tries = 0
        off += r.length
      }
      await sleep(this.opts.settleMs)
      const ok = await this.call(CMD_COMMIT, { sub: COMMIT_KEY, withCrc: false }, this.opts.commitTimeoutMs)
      if (!ok) throw new NoAnswerError('o controle não confirmou a gravação')
    } finally {
      // o Python só religa no caminho do commit; aqui religa sempre pra não largar o controle sem report
      await this.report(true)
    }
  }
}
