// Driving adapter: a tela só chama os casos de uso da ConfigSession e guarda edição no reducer.
import { useEffect, useReducer, useState } from 'react'
import { NoAnswerError } from '../../application/link'
import type { ConfigSession, Plan, Snapshot } from '../../application/config-session'
import type { ConfigDoc } from '../../domain/types'
import { profileLabel } from '../../domain/values'
import type { ProfileIndex } from '../../domain/values'
import { Editor, activeProfile, firmware } from './Editor'
import { ICONS } from './icons'
import { LivePad } from './Pad'
import type { Callout, PanelKey } from './pad-geometry'
import { Review } from './Review'
import { initial, reducer } from './state'
import type { Wiring } from './wiring'
import './styles.css'

const UDEV = 'KERNEL=="hidraw*", ATTRS{idVendor}=="2dc8", TAG+="uaccess"'
const PROFILES: ProfileIndex[] = [0, 1, 2]

function message(e: unknown): string {
  if (e instanceof NoAnswerError) {
    return 'O controle não respondeu. Mexa um analógico ou aperte um botão e tente de novo; se continuar, desconecte e reconecte o controle.'
  }
  return (e as Error).message
}

// mesmo --bg do styles.css, pra barra do navegador no celular acompanhar a página
const THEME_COLOR = { light: '#f5f4f8', dark: '#141416' }

// sem escolha a página segue o prefers-color-scheme; o botão fixa o oposto do q tá na tela
function flipTheme() {
  const root = document.documentElement
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches
  const next = dark ? 'light' : 'dark'
  root.dataset.theme = next
  // tema fixo: as duas metas (uma por media) passam a ter a mesma cor
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.setAttribute('content', THEME_COLOR[next]))
}

function Landing({ wiring, busy, onConnect }: { wiring: Wiring; busy: boolean; onConnect: (demo: boolean) => void }) {
  const { supported } = wiring
  return (
    <section className="hero">
      <div className="hero-art" translate="no"><LivePad source={wiring} /></div>
      <div className="hero-copy">
        <p className="eyebrow"><span translate="no">WebHID</span> · nada pra instalar</p>
        <h1><span translate="no">8BitDo Ultimate 2</span> no navegador</h1>
        <p className="lead">
          Remapeia botões, ajusta analógicos, gatilhos e LEDs do controle direto no Chrome ou Edge. Toda edição fica na
          tela até você revisar a lista de mudanças e confirmar.
        </p>
        {!supported && (
          <p role="alert" id="no-webhid" className="warn">
            {ICONS.alert}
            <span>Seu navegador não tem WebHID. Use Chrome ou Edge no desktop pra falar com o controle, ou abra o modo demo.</span>
          </p>
        )}
        <div className="cta">
          <button type="button" className="primary big" disabled={busy || !supported} aria-describedby={supported ? undefined : 'no-webhid'}
            onClick={() => onConnect(false)}>
            {ICONS.link}Conectar controle
          </button>
          <button type="button" className="big" disabled={busy} onClick={() => onConnect(true)}>{ICONS.flask}Abrir modo demo</button>
        </div>
        <details className="udev">
          <summary>Linux: o Chrome precisa da regra udev</summary>
          <p>Sem ela o Chrome não consegue abrir o hidraw do controle. É a mesma regra do 8bitdo-ultimate2-linux:</p>
          <pre translate="no"><code>{UDEV}</code></pre>
          <p>Salve em <code translate="no">/etc/udev/rules.d/70-8bitdo-u2.rules</code>, rode <code translate="no">sudo udevadm control --reload</code> e reconecte o controle.</p>
        </details>
      </div>
    </section>
  )
}

export function App({ wiring }: { wiring: Wiring }) {
  const [s, dispatch] = useReducer(reducer, initial)
  const [session, setSession] = useState<ConfigSession | null>(null)
  const [panel, setPanel] = useState<PanelKey>('buttons')
  const [jump, setJump] = useState<{ field: string } | null>(null)
  const busy = s.phase === 'busy'
  const snap = s.snap

  // foco depois do painel montar; perfil vazio não tem o campo
  useEffect(() => {
    if (jump) document.getElementById(jump.field)?.focus()
  }, [jump])

  async function run(text: string, job: () => Promise<void>) {
    dispatch({ type: 'busy', text })
    try {
      await job()
    } catch (e) {
      dispatch({ type: 'failed', text: message(e) })
    }
  }

  const connect = (demo: boolean) => run('Conectando e lendo a configuração…', async () => {
    const opened = demo ? wiring.openDemo() : await wiring.openReal()
    if (!opened) return dispatch({ type: 'failed', text: 'Nenhum controle escolhido. Clique em Conectar controle de novo e escolha o 8BitDo na lista.' })
    const read = await opened.session.connect()
    setSession(opened.session)
    dispatch({ type: 'loaded', snap: read, demo: opened.demo, text: 'Configuração lida do controle.' })
  })

  const reread = () => run('Relendo do controle…', async () => {
    const read = await (session as ConfigSession).readConfig()
    dispatch({ type: 'loaded', snap: read, demo: s.demo, text: 'Configuração relida, edições locais descartadas.' })
  })

  // o plano é puro (só compara registro), dá pra montar a cada render e contar o q tá staged
  function draft(): { plan: Plan; count: number } | { problem: string } | null {
    if (!snap || !session) return null
    try {
      const plan = session.planChanges(snap.record, s.doc as ConfigDoc, snap.theme, s.theme)
      return { plan, count: plan.changed.length + (plan.theme === null ? 0 : 1) }
    } catch (e) {
      return { problem: message(e) }
    }
  }
  const pending = draft()
  const changed = new Set(pending && 'plan' in pending ? pending.plan.changed : [])

  const confirm = () => run('Gravando, salvando na flash e relendo pra conferir…', async () => {
    const sess = session as ConfigSession
    const out = await sess.applyChanges(sess.confirm(s.plan as Plan))
    dispatch({ type: 'written', ...out })
  })

  const disconnect = () => run('Desconectando…', async () => {
    await (session as ConfigSession).disconnect()
    setSession(null)
    dispatch({ type: 'disconnected' })
  })

  function backup() {
    const url = URL.createObjectURL(new Blob([(snap as Snapshot).record.toBytes().buffer as ArrayBuffer]))
    const a = document.createElement('a')
    a.href = url
    // mesmo formato do `u2ctl backup`, dá pra restaurar com `u2ctl restore`
    a.download = 'ultimate2-backup.bin'
    a.click()
    URL.revokeObjectURL(url)
  }

  function onJump(c: Callout) {
    setPanel(c.panel)
    setJump({ field: c.field })
  }

  const doc = s.doc as ConfigDoc
  const show = pending && ('problem' in pending || pending.count > 0)
  const unsaved = !!show
  // o diálogo de revisão não tem focus trap próprio: o resto da página sai do Tab e do leitor de tela
  const review = s.phase === 'review'

  // staged só existe na tela, recarregar ou fechar a aba perde tudo
  useEffect(() => {
    if (!unsaved) return
    const stop = (e: Event) => e.preventDefault()
    addEventListener('beforeunload', stop)
    return () => removeEventListener('beforeunload', stop)
  }, [unsaved])

  return (
    <div className="app">
      <a className="skip" href="#conteudo" inert={review}>Pular pro conteúdo</a>
      <header className="topbar" inert={review}>
        <div className="brand">
          <span className="logo" aria-hidden="true">{ICONS.buttons}</span>
          <span translate="no">8BitDo Ultimate 2</span>
          <span className="tag">Web</span>
        </div>
        {snap && (
          <div className="profiles" role="group" aria-label="Perfis">
            {PROFILES.map((i) => (
              <button key={i} type="button" aria-pressed={i === s.profile} onClick={() => dispatch({ type: 'profile', index: i })}>
                {profileLabel(i)}
                {i === doc.cur_slot && <span className="dot" aria-hidden="true" title="Ativo no controle" />}
              </button>
            ))}
          </div>
        )}
        <button type="button" className="icon-btn theme-toggle" aria-label="Mudar tema" title="Mudar tema claro/escuro" onClick={flipTheme}>
          {ICONS.theme}
        </button>
      </header>

      {s.demo && (
        <p className="demo" inert={review}>{ICONS.flask}<span><strong>Modo demo:</strong> controle simulado, nada vai pro hardware.</span></p>
      )}

      <main id="conteudo" inert={review}>
        {!snap ? (
          <Landing wiring={wiring} busy={busy} onConnect={connect} />
        ) : (
          <>
            <section className="device" aria-labelledby="device-title">
              <h1 id="device-title" translate="no">Ultimate 2</h1>
              <p className="sub">{`Perfil ativo no controle: ${activeProfile(snap.record.toDoc())}`}</p>
              <LivePad source={session as ConfigSession} demo={s.demo} onJump={onJump} />
              <p className="hint">{s.demo ? 'Clique numa parte do desenho: ela acende como se fosse o controle.' : 'Aperte os botões do controle: eles acendem aqui.'}</p>
              <p className="link-pill">
                {s.demo ? ICONS.flask : ICONS.link}
                <span>{s.demo ? 'Controle simulado' : 'Conectado via WebHID'}</span>
              </p>
            </section>
            <Editor state={s} dispatch={dispatch} panel={panel} onPanel={setPanel} changed={changed} />
          </>
        )}
      </main>

      <footer className="statusbar" inert={review}>
        {show && (
          <section className="actionbar" aria-label="Alterações pendentes" data-problem={'problem' in pending || undefined}>
            <p aria-live="polite">
              {'problem' in pending ? pending.problem : `${pending.count} ${pending.count === 1 ? 'alteração' : 'alterações'}`}
              <small>{'problem' in pending ? 'Corrija o valor pra poder gravar.' : 'Só na tela até você confirmar.'}</small>
            </p>
            <div className="actionbar-buttons">
              <button type="button" disabled={busy} onClick={() => dispatch({ type: 'discard' })}>Descartar</button>
              <button type="button" className="primary" disabled={busy || 'problem' in pending}
                onClick={() => dispatch({ type: 'review', plan: (pending as { plan: Plan }).plan })}>
                Revisar e gravar
              </button>
            </div>
          </section>
        )}
        <div className="statusrow">
          <p role="status" aria-live="polite" className={`status ${s.status?.tone ?? ''} ${busy ? 'busy' : ''}`}>{s.status?.text}</p>
          {snap && (
            <div className="session">
              <button type="button" disabled={busy} onClick={backup} title="Baixa o registro de 1592 bytes (.bin)">{ICONS.download}Backup</button>
              <button type="button" disabled={busy} onClick={reread} title="Relê do controle e descarta as edições">{ICONS.reload}Reler</button>
              <button type="button" disabled={busy} onClick={disconnect}>{ICONS.power}Desconectar</button>
            </div>
          )}
          {snap && <span className="fw">{`firmware ${firmware(snap)}`}</span>}
        </div>
      </footer>

      {s.phase === 'review' && (
        <Review plan={s.plan as Plan} doc={doc} theme={(snap as Snapshot).theme} onConfirm={confirm} onCancel={() => dispatch({ type: 'cancel' })} />
      )}
    </div>
  )
}
