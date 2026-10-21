// Casos de uso da sessão de config, o fluxo do `u2ctl apply`: liga o dreno, lê primeiro, planeja,
// só grava plano confirmado e validado, manda commit pra flash e relê pra conferir.
import { ConfigRecord } from '../domain/config-record'
import type { ControllerInfo } from '../domain/packet'
import type { ConfigDoc } from '../domain/types'
import { ledTheme } from '../domain/values'
import { ControllerLink, NoAnswerError } from './link'
import type { LinkOpts } from './link'
import type { InputDrain, ReportChannel } from './ports'
import type { LiveInput } from '../domain/live-input'

export class VerifyError extends Error {
  name = 'VerifyError'
}

export interface Snapshot {
  info: ControllerInfo
  record: ConfigRecord
  theme: number | null
}

export interface Plan {
  base: ConfigRecord
  next: ConfigRecord
  changed: string[]
  // null = tema não muda
  theme: number | null
}

declare const confirmedBrand: unique symbol
export type ConfirmedPlan = Plan & { readonly [confirmedBrand]: true }

export class ConfigSession {
  private readonly link: ControllerLink
  // plano só vale uma vez e só se passou pelo confirm()
  private readonly confirmed = new WeakSet<Plan>()

  constructor(private readonly channel: ReportChannel, private readonly drain: InputDrain, opts: Partial<LinkOpts> = {}) {
    this.link = new ControllerLink(channel, opts)
  }

  async connect(): Promise<Snapshot> {
    // dreno antes do primeiro pedido: sem ele o firmware não atende o canal de config
    this.drain.start()
    try {
      await this.channel.open()
      return await this.readConfig()
    } catch (e) {
      await this.disconnect()
      throw e
    }
  }

  async disconnect(): Promise<void> {
    this.drain.stop()
    await this.channel.close()
  }

  onInput(cb: (input: LiveInput) => void): () => void {
    return this.drain.onInput(cb)
  }

  async readConfig(): Promise<Snapshot> {
    const info = await this.link.info()
    if (!info) throw new NoAnswerError('o controle não respondeu ao pedido de info')
    const record = ConfigRecord.fromBytes(await this.link.readConfig())
    return { info, record, theme: await this.link.getTheme() }
  }

  planChanges(base: ConfigRecord, doc: ConfigDoc, theme: number | null, nextTheme: number | null): Plan {
    const { next, changed } = base.withChanges(doc)
    const t = nextTheme === theme ? null : nextTheme
    return { base, next, changed, theme: t === null ? null : ledTheme(t) }
  }

  // chamado só pelo botão de confirmação da tela, depois de listar as mudanças
  confirm(plan: Plan): ConfirmedPlan {
    this.confirmed.add(plan)
    return plan as ConfirmedPlan
  }

  async applyChanges(plan: ConfirmedPlan): Promise<{ record: ConfigRecord; theme: number | null }> {
    if (!this.confirmed.delete(plan)) throw new Error('plano sem confirmação, nada foi gravado')
    let record = plan.base
    if (plan.changed.length) {
      plan.next.assertWritableOver(plan.base)
      await this.link.writeConfig(plan.next.toBytes())
      record = ConfigRecord.fromBytes(await this.link.readConfig())
      if (!record.equals(plan.next)) throw new VerifyError('Conferência falhou: o controle devolveu outra configuração. O tema não foi mexido.')
    }
    const theme = plan.theme === null ? await this.link.getTheme() : await this.setTheme(plan.theme)
    return { record, theme }
  }

  async setTheme(theme: number): Promise<number | null> {
    await this.link.setTheme(ledTheme(theme))
    return this.link.getTheme()
  }
}
