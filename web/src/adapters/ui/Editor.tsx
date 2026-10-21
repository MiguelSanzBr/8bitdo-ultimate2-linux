// Edição staged do perfil escolhido, um painel por categoria: nada aqui fala com o controle, só despacha pro reducer.
import type { CSSProperties, Dispatch, ReactNode } from 'react'
import type { Snapshot } from '../../application/config-session'
import { PIDS, THEMES } from '../../domain/packet'
import { KEYCODES, defaultSlot } from '../../domain/record'
import type { BUTTONS } from '../../domain/record'
import type { ConfigDoc, Slot } from '../../domain/types'
import { gamepadModeName, profileIndex, profileLabel } from '../../domain/values'
import { ICONS } from './icons'
import type { PanelKey } from './pad-geometry'
import type { Action, State } from './state'

export const PANELS: [PanelKey, string][] = [['buttons', 'Botões'], ['sticks', 'Analógicos'], ['triggers', 'Gatilhos'], ['leds', 'LEDs'], ['profile', 'Perfil']]
export const THEME_LABEL: Readonly<Record<number, string>> = { 2: 'Dinâmico', 3: 'Roda', 4: 'Personalizado', 5: 'Desligado' }
export const themeLabel = (t: number | null) => THEME_LABEL[t ?? -1] ?? 'desconhecido'
export const firmware = ({ info }: Snapshot) => `${(info.firmware / 100).toFixed(2)}${info.beta ? ` beta ${info.beta}` : ''}`

const KEY_NAMES = [...new Set(Object.values(KEYCODES))]
type Button = (typeof BUTTONS)[number]
// P1/P2 são as borboletas de trás, P3/P4 os botões pequenos do lado do LB/RB (docs/PROTOCOL.md)
const GROUPS: [string, Button[]][] = [
  ['Frente', ['A', 'B', 'X', 'Y']], ['Ombros e gatilhos', ['LB', 'RB', 'LT', 'RT', 'P3', 'P4']], ['D-pad', ['Up', 'Down', 'Left', 'Right']],
  ['Centro', ['Select', 'Start', 'Star', 'Home']], ['Clique dos analógicos', ['L3', 'R3']], ['Traseiros', ['P1', 'P2']],
]
const ALIAS: Partial<Record<Button, [string, string]>> = { P1: ['PR', 'P1'], P2: ['PL', 'P2'], P3: ['L4', 'P3'], P4: ['R4', 'P4'] }
const PRESETS = ['#7c3aed', '#ff2d75', '#ff8a00', '#ffd60a', '#30d158', '#00c7be', '#0a84ff', '#ffffff']

interface Props {
  state: State
  dispatch: Dispatch<Action>
  panel: PanelKey
  onPanel: (p: PanelKey) => void
  changed: ReadonlySet<string>
}

export function Editor({ state, dispatch, panel, onPanel, changed }: Props) {
  const doc = state.doc as ConfigDoc
  const n = state.profile
  const slot = doc.slots[n]
  const edit = (fn: (s: Slot) => void) => dispatch({ type: 'edit', fn: (d) => fn(d.slots[n]) })
  const ctx: Ctx = { slot, edit, dirty: (path) => changed.has(`slots/${n}/${path}`) }
  const title = (PANELS.find(([k]) => k === panel) as [PanelKey, string])[1]
  const empty = (
    <div className="empty">
      <p>Esse perfil tá vazio no controle.</p>
      <button type="button" className="primary" onClick={() => dispatch({ type: 'edit', fn: (d) => void (d.slots[n] = defaultSlot(d, n, profileLabel(n)).slots[n]) })}>
        Criar com os padrões do app
      </button>
    </div>
  )
  const body: Record<PanelKey, () => ReactNode> = {
    buttons: () => <Buttons {...ctx} />,
    sticks: () => <Ranges {...ctx} sec="sticks" />,
    triggers: () => <Ranges {...ctx} sec="triggers" />,
    leds: () => <Leds {...ctx} theme={state.theme} onTheme={(t) => dispatch({ type: 'theme', theme: t })} />,
    profile: () => <Profile {...ctx} state={state} />,
  }

  return (
    <>
      <div className="tiles" role="group" aria-label="Categorias">
        {PANELS.map(([key, name]) => (
          <button key={key} type="button" className="tile" aria-pressed={key === panel} onClick={() => onPanel(key)}>
            {ICONS[key]}<span>{name}</span>
          </button>
        ))}
      </div>
      <section className="panel" aria-labelledby="panel-title">
        <h2 id="panel-title">{title}</h2>
        {slot.flag !== 'enabled' && empty}
        {(slot.flag === 'enabled' || panel === 'profile') && body[panel]()}
      </section>
    </>
  )
}

interface Ctx {
  slot: Slot
  edit: (fn: (s: Slot) => void) => void
  dirty: (path: string) => boolean
}

const mark = (on: boolean) => (on ? { 'data-changed': '' } : {})

function Buttons({ slot, edit, dirty }: Ctx) {
  return (
    <div className="groups">
      {GROUPS.map(([group, buttons]) => (
        <fieldset key={group} className="card">
          <legend>{group}</legend>
          {buttons.map((b) => {
            const value = slot.mapping[b] as string
            const alias = ALIAS[b]
            return (
              <div key={b} className="remap" translate="no" {...mark(dirty(`mapping/${b}`))}>
                <label htmlFor={`map-${b}`} className="key">{alias ? <>{alias[0]} <small>({alias[1]})</small></> : b}</label>
                <span className="to" aria-hidden="true">{ICONS.arrow}</span>
                <select id={`map-${b}`} value={value} onChange={(e) => edit((s) => void (s.mapping[b] = e.target.value))}>
                  {(KEY_NAMES.includes(value) ? KEY_NAMES : [value, ...KEY_NAMES]).map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
              </div>
            )
          })}
        </fieldset>
      ))}
    </div>
  )
}

interface SliderProps {
  id: string
  label: string
  max: number
  value: number
  changed: boolean
  onChange: (v: number) => void
}

function Slider({ id, label, max, value, changed, onChange }: SliderProps) {
  const set = (e: { target: { value: string } }) => onChange(Number(e.target.value))
  return (
    <div className="slider" {...mark(changed)}>
      <label htmlFor={id}>{label}</label>
      <input id={id} type="range" min={0} max={max} value={value} onChange={set} style={{ '--p': `${(Math.min(value, max) / max) * 100}%` } as CSSProperties} />
      <input type="number" aria-label={`${label} (valor)`} min={0} max={max} value={value} onChange={set} />
    </div>
  )
}

function Switch({ label, checked, onChange }: { label: string; checked: boolean; onChange: (on: boolean) => void }) {
  return (
    <label className="switch">
      <input type="checkbox" role="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  )
}

// features fica num campo só (máscara); formato desconhecido não vira toggle pra não estragar o q tá lá
function Features({ slot, edit, list }: Ctx & { list: [string, string][] }) {
  const features = slot.special.features
  if (!Array.isArray(features)) return null
  return (
    <div className="switches">
      {list.map(([f, label]) => (
        <Switch key={f} label={label} checked={features.includes(f)}
          onChange={(on) => edit((s) => void (s.special.features = on ? [...features, f] : features.filter((x) => x !== f)))} />
      ))}
    </div>
  )
}

function UnknownFeatures({ slot }: Ctx) {
  const features = slot.special.features
  return Array.isArray(features) ? null : <p className="hint">Opções extras em formato desconhecido ({features}), ficam como estão.</p>
}

type Side = 'left' | 'right'
type Sec = 'sticks' | 'triggers'
const SIDES: [Side, string, string][] = [['left', 'L', 'esquerdo'], ['right', 'R', 'direito']]
const RANGES: Record<Sec, { max: number; unit: string; start: string; end: string; both: [string, string][] }> = {
  sticks: { max: 128, unit: 'S', start: 'zona morta', end: 'alcance', both: [['swap_sticks', 'Trocar analógicos'], ['swap_LS_dpad', 'Trocar LS com d-pad']] },
  triggers: { max: 255, unit: 'T', start: 'início', end: 'fim', both: [['swap_triggers', 'Trocar gatilhos'], ['trigger_rumble', 'Vibração nos gatilhos']] },
}

// analógicos e gatilhos têm a mesma forma: início/fim por lado, mais as features dos dois
function Ranges({ sec, ...ctx }: Ctx & { sec: Sec }) {
  const { slot, edit, dirty } = ctx
  const { max, unit, both } = RANGES[sec]
  const pct = (v: number) => (Math.min(v, max) / max) * 100
  return (
    <div className="cards">
      {SIDES.map(([side, k, name]) => {
        const short = `${k}${unit}`
        const value = (end: 'start' | 'end') => slot[sec][`${side}_${end}`]
        return (
          <div key={side} className="card">
            <h3>{sec === 'sticks' ? `Analógico ${name}` : short}</h3>
            {sec === 'sticks' ? (
              <svg className="preview-stick" viewBox="-50 -50 100 100" aria-hidden="true">
                <circle className="outer" r={46} />
                <circle className="reach" r={(pct(value('end')) * 46) / 100} />
                <circle className="dead" r={(pct(value('start')) * 46) / 100} />
              </svg>
            ) : (
              <div className="preview-trigger" aria-hidden="true">
                <span style={{ left: `${pct(value('start'))}%`, right: `${100 - pct(value('end'))}%` }} />
              </div>
            )}
            {(['start', 'end'] as const).map((end) => (
              <Slider key={end} id={`${sec}-${side}_${end}`} label={`${short} ${RANGES[sec][end]}`} max={max} value={value(end)}
                changed={dirty(`${sec}/${side}_${end}`)} onChange={(v) => edit((s) => void (s[sec][`${side}_${end}`] = v))} />
            ))}
            {sec === 'sticks' && <Features {...ctx} list={[[`invert_${short}_X`, `Inverter ${short} X`], [`invert_${short}_Y`, `Inverter ${short} Y`]]} />}
          </div>
        )
      })}
      <div className="card wide">
        <h3>Os dois</h3>
        <Features {...ctx} list={both} />
        <UnknownFeatures {...ctx} />
      </div>
    </div>
  )
}

type ColorKey = 'color' | 'bg_color'

function Leds({ slot, edit, dirty, theme, onTheme }: Ctx & { theme: number | null; onTheme: (t: number) => void }) {
  const { color, bg_color: bg } = slot.led_dynamic
  const fields: [ColorKey, string][] = [['color', 'Cor do efeito'], ['bg_color', 'Fundo do efeito']]
  return (
    <div className="cards">
      <fieldset className="card wide">
        <legend>Tema de LED (global)</legend>
        <div className="segmented">
          {Object.keys(THEMES).map(Number).map((t) => (
            <label key={t}>
              <input type="radio" name="led-theme" checked={theme === t} onChange={() => onTheme(t)} />
              <span>{THEME_LABEL[t]}</span>
            </label>
          ))}
        </div>
        <p className="hint">Vale pros três perfis. As cores abaixo são do tema Dinâmico.</p>
      </fieldset>
      <div className="card">
        <h3>Dinâmico</h3>
        <div className="led-preview" aria-hidden="true" style={{ '--c': color, '--bg': bg } as CSSProperties}><span /><span /></div>
      </div>
      <div className="card">
        {fields.map(([key, label]) => (
          <div key={key} className="color" {...mark(dirty(`led_dynamic/${key}`))}>
            <label htmlFor={`led-${key}`}>{label}</label>
            <div className="color-row">
              <input id={`led-${key}`} type="color" value={slot.led_dynamic[key]} onChange={(e) => edit((s) => void (s.led_dynamic[key] = e.target.value))} />
              <code translate="no">{slot.led_dynamic[key]}</code>
            </div>
            <div className="presets">
              {PRESETS.map((c) => (
                <button key={c} type="button" aria-label={`${label}: ${c}`} style={{ background: c }} onClick={() => edit((s) => void (s.led_dynamic[key] = c))} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Profile({ slot, edit, state }: Ctx & { state: State }) {
  const snap = state.snap as Snapshot
  const read = snap.record.toDoc()
  const pid = snap.info.devicePid
  return (
    <div className="cards">
      {slot.flag === 'enabled' && (
        <div className="card">
          <label htmlFor="profile-name">Nome do perfil</label>
          <input id="profile-name" name="profile-name" className="text" autoComplete="off" spellCheck={false} value={slot.name} maxLength={16} onChange={(e) => edit((s) => void (s.name = e.target.value))} />
          <p className="hint">Até 16 caracteres, aparece no app oficial.</p>
        </div>
      )}
      <section className="card" aria-labelledby="info-title">
        <h3 id="info-title">Controle</h3>
        <dl className="info">
          <dt>Firmware</dt>
          <dd>{firmware(snap)}</dd>
          <dt>PID reportado</dt>
          <dd translate="no">{`0x${pid.toString(16).padStart(4, '0')} (${PIDS[pid] ?? '?'})`}</dd>
          <dt>Modo</dt>
          <dd>{gamepadModeName(read.gamepad_mode)}</dd>
          <dt>Perfil ativo</dt>
          <dd>{activeProfile(read)}</dd>
          <dt>Tema de LED</dt>
          <dd>{themeLabel(snap.theme)}</dd>
        </dl>
        {!state.demo && <p className="hint">Enquanto a sessão tá aberta a página fica lendo o joystick (getGamepads) pro firmware atender o canal de config.</p>}
      </section>
    </div>
  )
}

export const activeProfile = (doc: ConfigDoc) => (doc.cur_slot < 3 ? profileLabel(profileIndex(doc.cur_slot)) : 'padrão (sem perfil custom)')
