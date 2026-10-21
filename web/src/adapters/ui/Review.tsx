// Confirmação explícita: lista cada campo q vai mudar (antes -> depois) antes de qualquer escrita.
import type { Plan } from '../../application/config-session'
import type { ConfigDoc } from '../../domain/types'
import { themeLabel } from './Editor'
import { ICONS } from './icons'

const at = (doc: unknown, path: string) => String(path.split('/').reduce((n, k) => (n as Record<string, unknown>)[k], doc))
const label = (path: string) => path.replace(/^slots\/(\d)\//, (_, i: string) => `Perfil ${Number(i) + 1} · `)

interface Props {
  plan: Plan
  doc: ConfigDoc
  theme: number | null
  onConfirm: () => void
  onCancel: () => void
}

function Change({ what, before, after }: { what: string; before: string; after: string }) {
  return (
    <li>
      <span className="what">{what}</span>{' '}
      <span className="diff"><span className="before">{before}</span> → <span className="after">{after}</span></span>
    </li>
  )
}

export function Review({ plan, doc, theme, onConfirm, onCancel }: Props) {
  const before = plan.base.toDoc()
  return (
    <div className="backdrop">
      <div role="dialog" aria-modal="true" aria-labelledby="review-title" aria-describedby="review-text" className="dialog"
        onKeyDown={(e) => e.key === 'Escape' && onCancel()}>
        <div className="dialog-head">
          {ICONS.alert}
          <h2 id="review-title">Confirmar gravação</h2>
        </div>
        <p id="review-text">Isso grava no controle e salva na flash. Depois a página relê tudo pra conferir.</p>
        <ul className="changes">
          {plan.changed.map((p) => <Change key={p} what={label(p)} before={at(before, p)} after={at(doc, p)} />)}
          {plan.theme !== null && <Change what="Tema de LED" before={themeLabel(theme)} after={themeLabel(plan.theme)} />}
        </ul>
        <div className="dialog-actions">
          <button type="button" autoFocus onClick={onCancel}>Cancelar</button>
          <button type="button" className="primary" onClick={onConfirm}>Gravar no controle</button>
        </div>
      </div>
    </div>
  )
}
