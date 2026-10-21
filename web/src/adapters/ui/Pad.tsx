// Controle em SVG no traço do app desktop. Com onJump ganha as legendas, cada uma leva pro campo dela.
// Com input acende o q tá apertado; com onPress (demo) o ponteiro aperta.
import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { IDLE } from '../../domain/live-input'
import type { LiveInput, LivePart } from '../../domain/live-input'
import type { InputDrain } from '../../application/ports'
import {
  CALLOUTS, DECOR, DECOR_SQUARE, DETAILS, DPAD, DPAD_ARMS, DPAD_CROSS, DPAD_X, H, HEART_PATH, OX, PADDLES, ROUND, SHOULDERS,
  SHOULDER_TEXT, STICKS, TRIGGERS, TRIGGER_BOTTOM, TRIGGER_SPAN, W, arc, closedPath, openPath, BODY,
} from './pad-geometry'
import type { Callout } from './pad-geometry'

const FULL = W + 2 * OX
const TOP = -4
const TALL = H + 8
// a ponta da legenda fica 14 unidades antes do desenho, igual o app
const EDGE = OX - 14
// quanto o miolo do analógico anda com o eixo no fim, em unidades do desenho
const THROW = 8

type Part = LivePart | 'LT' | 'RT'
const TRIGGER_PARTS = ['LT', 'RT'] as const
const STICK_PARTS = ['L3', 'R3'] as const
const SHOULDER_PARTS = ['LB', 'RB'] as const

interface Live {
  input: LiveInput
  held: Part | null
  onPress?: (part: Part | null) => void
}

function Drawing({ input, held, onPress }: Live) {
  const on = (p: Part) => p === held || (input.pressed as readonly Part[]).includes(p)
  const key = (p: Part, lit: boolean, cls = '') => ({
    'data-part': p,
    className: `${cls} key${lit ? ' lit' : ''}`.trim(),
    ...(onPress && { onPointerDown: () => onPress(p), onPointerUp: () => onPress(null), onPointerLeave: () => onPress(null) }),
  })
  return (
    <g transform={`translate(${OX} 0)`}>
      {TRIGGERS.map((p, i) => {
        const part = TRIGGER_PARTS[i] as Part
        const v = held === part ? 1 : i ? input.rt : input.lt
        // id fixo: só tem um desenho na tela por vez
        const clip = `pad-fill-${part}`
        return (
          <g key={part} {...key(part, v > 0, 'trigger')}>
            <path className="part" d={closedPath(p)} />
            <clipPath id={clip}><rect x={0} y={TRIGGER_BOTTOM - TRIGGER_SPAN * v} width={W} height={TRIGGER_SPAN * v} /></clipPath>
            <path className="fill" d={closedPath(p)} clipPath={`url(#${clip})`} />
          </g>
        )
      })}
      <path className="body" d={closedPath(BODY)} />
      {DETAILS.map((p, i) => <path key={i} className="detail" d={openPath(p)} />)}
      {STICKS.map(([x, y], i) => {
        const part = STICK_PARTS[i] as Part
        const [dx, dy] = i ? input.right : input.left
        return (
          <g key={x} {...key(part, on(part) || dx !== 0 || dy !== 0, 'stick')}>
            <circle className="ring" cx={x} cy={y} r={37} />
            <g className="thumb" style={{ transform: `translate(${dx * THROW}px, ${dy * THROW}px)` }}>
              <circle className="part" cx={x} cy={y} r={32} />
              <circle className="part" cx={x} cy={y} r={25} />
              <circle className="part dot" cx={x} cy={y} r={7} />
              <path className="shine" d={arc(x, y, 15, 100, 80)} />
            </g>
          </g>
        )
      })}
      {SHOULDERS.map((p, i) => {
        const part = SHOULDER_PARTS[i]
        // L4/R4 não chegam pelo Gamepad API
        return part ? <path key={i} {...key(part, on(part), 'part')} d={closedPath(p)} /> : <path key={i} className="part" d={closedPath(p)} />
      })}
      {ROUND.map(([x, y, r, t, part]) => (
        <g key={`${x},${y}`} {...(part && key(part, on(part)))}>
          <circle className="part" cx={x} cy={y} r={r} />
          {t && <text x={x} y={y} className={r > 12 ? 'face' : 'mini'}>{t}</text>}
          {part === 'Home' && <path className="ink" d={HEART_PATH} />}
        </g>
      ))}
      {DECOR.map(([x1, y1, x2, y2]) => (
        <rect key={`${x1},${y1}`} className="part" x={x1} y={y1} width={x2 - x1} height={y2 - y1} rx={Math.min(x2 - x1, y2 - y1) / 2} />
      ))}
      <rect className="part thin" x={DECOR_SQUARE[0]} y={DECOR_SQUARE[1]} width={8} height={8} rx={1.5} />
      <path className="part" d={closedPath(DPAD_CROSS)} />
      <path className="part" d={`M${DPAD[0] - DPAD_X} ${DPAD[1] - DPAD_X}l${2 * DPAD_X} ${2 * DPAD_X}M${DPAD[0] - DPAD_X} ${DPAD[1] + DPAD_X}l${2 * DPAD_X} ${-2 * DPAD_X}`} />
      {DPAD_ARMS.map(([part, x, y, w, h]) => <rect key={part} {...key(part, on(part), 'part arm')} x={x} y={y} width={w} height={h} rx={4} />)}
      {PADDLES.map(([x1, y1, x2, y2, t]) => (
        <g key={t}>
          <rect className="part" x={x1} y={y1} width={x2 - x1} height={y2 - y1} rx={7} />
          <text x={(x1 + x2) / 2} y={(y1 + y2) / 2} className="mini">{t}</text>
        </g>
      ))}
      {SHOULDER_TEXT.map(([x, y, t]) => <text key={t} x={x} y={y} className="mini">{t}</text>)}
    </g>
  )
}

const pct = (v: number, of: number) => `${(v / of) * 100}%`

export function Pad({ onJump, input = IDLE, held = null, onPress }: Partial<Live> & { onJump?: (c: Callout) => void }) {
  const live = { input, held, onPress }
  const cls = onPress ? 'pad press' : 'pad'
  if (!onJump) {
    return (
      <svg className={cls} viewBox={`${OX} ${TOP} ${W} ${TALL}`} aria-hidden="true">
        <Drawing {...live} />
      </svg>
    )
  }
  return (
    <div className="stage-clip" translate="no">
      <div className="stage">
        <svg className={cls} viewBox={`0 ${TOP} ${FULL} ${TALL}`} aria-hidden="true">
          <Drawing {...live} />
          <g className="callout-lines">
            {CALLOUTS.map(({ label, side, y, to }) => {
              const edge = side === 'l' ? EDGE : FULL - EDGE
              const bend = side === 'l' ? OX : FULL - OX
              return (
                <g key={label}>
                  <path d={`M${edge} ${y}H${bend}L${to[0] + OX} ${to[1]}`} />
                  <circle cx={to[0] + OX} cy={to[1]} r={3} />
                </g>
              )
            })}
          </g>
        </svg>
        {CALLOUTS.map((c) => {
          const style: CSSProperties = { top: pct(c.y - TOP, TALL), [c.side === 'l' ? 'right' : 'left']: pct(FULL - EDGE, FULL) }
          return <button key={c.label} type="button" className={`callout ${c.side}`} style={style} onClick={() => onJump(c)}>{c.label}</button>
        })}
      </div>
    </div>
  )
}

// Só esse pedaço re-renderiza com o controle, e no máximo uma vez por quadro: o dreno lê a cada 16 ms.
export function LivePad({ source, demo = false, onJump }: { source: Pick<InputDrain, 'onInput'>; demo?: boolean; onJump?: (c: Callout) => void }) {
  const [input, setInput] = useState(IDLE)
  const [held, setHeld] = useState<Part | null>(null)

  useEffect(() => {
    let frame = 0
    let next = IDLE
    const off = source.onInput((i) => {
      next = i
      frame ||= requestAnimationFrame(() => {
        frame = 0
        setInput(next)
      })
    })
    return () => {
      off()
      cancelAnimationFrame(frame)
    }
  }, [source])

  return <Pad onJump={onJump} input={input} held={held} onPress={demo ? setHeld : undefined} />
}
