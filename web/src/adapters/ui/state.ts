// Estado da tela. Edição fica só aqui (staged) até a confirmação; o controle só vê o plano confirmado.
import type { Plan, Snapshot } from '../../application/config-session'
import type { ConfigRecord } from '../../domain/config-record'
import type { ConfigDoc } from '../../domain/types'
import type { ProfileIndex } from '../../domain/values'

export interface Status {
  tone: 'info' | 'ok' | 'error'
  text: string
}

export interface State {
  phase: 'idle' | 'busy' | 'ready' | 'review'
  demo: boolean
  snap: Snapshot | null
  doc: ConfigDoc | null
  theme: number | null
  profile: ProfileIndex
  plan: Plan | null
  status: Status | null
}

export type Action =
  | { type: 'busy'; text: string }
  | { type: 'loaded'; snap: Snapshot; demo: boolean; text: string }
  | { type: 'failed'; text: string }
  | { type: 'disconnected' }
  | { type: 'profile'; index: ProfileIndex }
  | { type: 'edit'; fn: (doc: ConfigDoc) => void }
  | { type: 'theme'; theme: number }
  | { type: 'discard' }
  | { type: 'review'; plan: Plan }
  | { type: 'cancel' }
  | { type: 'written'; record: ConfigRecord; theme: number | null }

export const initial: State = { phase: 'idle', demo: false, snap: null, doc: null, theme: null, profile: 0, plan: null, status: null }

export function reducer(s: State, a: Action): State {
  switch (a.type) {
    case 'busy':
      return { ...s, phase: 'busy', status: { tone: 'info', text: a.text } }
    case 'loaded':
      return { ...s, phase: 'ready', demo: a.demo, snap: a.snap, doc: a.snap.record.toDoc(), theme: a.snap.theme, plan: null, status: { tone: 'ok', text: a.text } }
    case 'failed':
      return { ...s, phase: s.snap ? 'ready' : 'idle', plan: null, status: { tone: 'error', text: a.text } }
    case 'disconnected':
      return { ...initial, status: { tone: 'info', text: 'Desconectado.' } }
    case 'profile':
      return { ...s, profile: a.index }
    case 'edit': {
      if (!s.doc) return s
      // cópia nova a cada edição: o reducer continua puro (StrictMode roda duas vezes)
      const doc = structuredClone(s.doc)
      a.fn(doc)
      return { ...s, doc }
    }
    case 'theme':
      return { ...s, theme: a.theme }
    case 'discard':
      return s.snap ? { ...s, doc: s.snap.record.toDoc(), theme: s.snap.theme, status: { tone: 'info', text: 'Edições descartadas.' } } : s
    case 'review':
      return { ...s, phase: 'review', plan: a.plan }
    case 'cancel':
      return { ...s, phase: 'ready', plan: null }
    case 'written':
      if (!s.snap) return s
      return {
        ...s, phase: 'ready', plan: null, snap: { ...s.snap, record: a.record, theme: a.theme }, doc: a.record.toDoc(), theme: a.theme,
        status: { tone: 'ok', text: 'Gravado na flash e conferido na releitura.' },
      }
  }
}
