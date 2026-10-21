// Desenho do controle portado do gui/geometry.py do 8bitdo-ultimate2-linux: mesmas coordenadas (caixa de 440x330)
// e o mesmo alisamento dos polígonos do Tk, pra web e desktop terem o mesmo controle.
import type { LivePart } from '../../domain/live-input'

export type Pt = readonly [number, number]

export const W = 440
export const H = 330
// espaço das legendas de cada lado do desenho, igual o HOME_OFFSET do app
export const OX = 160

export const BODY: Pt[] = [[105, 18], [132, 20], [138, 26], [171, 24], [301, 26], [305, 21], [310, 19], [340, 18], [368, 25],
  [395, 43], [396, 52], [406, 60], [417, 82], [428, 128], [439, 227], [439, 260], [435, 285], [428, 301], [418, 313],
  [403, 321], [388, 326], [367, 304], [333, 248], [320, 235], [299, 229], [131, 230], [120, 234], [111, 241], [74, 303],
  [52, 326], [49, 326], [29, 318], [15, 306], [7, 293], [2, 275], [0, 229], [10, 136], [20, 88], [30, 66], [36, 57],
  [44, 52], [44, 43], [49, 39], [75, 24]]

const mirror = (pts: readonly Pt[]): Pt[] => pts.map(([x, y]) => [W - x, y])

const LB: Pt[] = [[44, 48], [44, 43], [49, 39], [75, 24], [105, 18], [132, 20], [138, 26], [112, 28], [82, 33], [60, 40]]
const LT: Pt[] = [[52, 36], [62, 22], [84, 8], [116, 3], [140, 8], [146, 22], [120, 22], [80, 26]]
// ponto repetido mantém a quina viva no alisamento do Tk
const L4: Pt[] = [[138, 26], [138, 26], [139, 17], [145, 11], [154, 11], [162, 15], [167, 21], [169, 26], [169, 26]]

export const TRIGGERS = [LT, mirror(LT)]
// faixa em y q o preenchimento do gatilho cobre, de baixo pra cima
export const TRIGGER_BOTTOM = 37
export const TRIGGER_SPAN = 34
export const SHOULDERS = [LB, mirror(LB), L4, mirror(L4)]

export const DPAD: Pt = [159, 175]
const ARM = 38
const HALF = 14
const DIRS: Pt[] = [[0, -1], [1, 0], [0, 1], [-1, 0]]
export const DPAD_CROSS: Pt[] = DIRS.flatMap(([dx, dy]) =>
  ([[-HALF, -ARM], [HALF, -ARM], [HALF, -HALF], [HALF, -HALF]] as Pt[]).map(([x, y]): Pt => [DPAD[0] - y * dx - x * dy, DPAD[1] + x * dx - y * dy]))
export const DPAD_X = HALF
// braço de cada direção (x, y, largura, altura), pra acender só o lado apertado; recuado pra não comer o contorno
const IN = 3
export const DPAD_ARMS = (['Up', 'Right', 'Down', 'Left'] as const).map((part, i): [LivePart, number, number, number, number] => {
  const [dx, dy] = DIRS[i] as Pt
  const w = (dx ? ARM - HALF : 2 * HALF) - 2 * IN
  const h = (dy ? ARM - HALF : 2 * HALF) - 2 * IN
  return [part, DPAD[0] + (dx * (HALF + ARM)) / 2 - w / 2, DPAD[1] + (dy * (HALF + ARM)) / 2 - h / 2, w, h]
})

export const STICKS: Pt[] = [[93, 106], [281, 177]]
// botões redondos: x, y, raio, legenda e o botão q acende (o ★ não aparece no Gamepad API)
export const ROUND: [number, number, number, string, LivePart | null][] = [
  [347, 73, 15, 'Y', 'Y'], [347, 136, 15, 'A', 'A'], [316, 104, 15, 'X', 'X'], [379, 104, 15, 'B', 'B'],
  [162, 67, 10, '−', 'Select'], [277, 67, 10, '+', 'Start'], [220, 67, 14, '', 'Home'], [250, 99, 10, '★', null],
]
// partes q não são configuráveis (botão redondo, botão de perfil, ponto central e LEDs de jogador)
export const DECOR: [number, number, number, number][] = [[180, 89, 200, 109], [207, 113, 233, 125], [219, 98, 221, 100],
  ...[147, 156, 165].map((y): [number, number, number, number] => [219, y - 1, 221, y + 1])]
export const DECOR_SQUARE = [186, 95, 194, 103] as const
export const PADDLES: [number, number, number, number, string][] = [[176, 300, 210, 316, 'PL'], [230, 300, 264, 316, 'PR']]
// texto dos ombros: x, y, legenda
export const SHOULDER_TEXT: [number, number, string][] = [[112, 13, 'LT'], [328, 13, 'RT'], [96, 27, 'LB'], [344, 27, 'RB'],
  [152, 19, 'L4'], [288, 19, 'R4']]
export const DETAILS: Pt[][] = [[[60, 168], [36, 233], [26, 280], [34, 318]], [[380, 168], [404, 233], [414, 280], [406, 318]],
  [[84, 306], [118, 250], [136, 240], [304, 240], [322, 250], [356, 306]]]

const HEART = ['..XX...XX..', '.X..X.X..X.', 'X....X....X', 'X.........X', '.X.......X.', '..X.....X..', '...X...X...',
  '....X.X....', '.....X.....']
const PX = 1.8
// coração em pixel art no Home, um quadradinho por X
export const HEART_PATH = HEART.flatMap((row, j) => [...row].map((c, i) => c === 'X'
  ? `M${num(220 - 5.5 * PX + i * PX)} ${num(67 - 4.5 * PX + j * PX)}h${PX}v${PX}h-${PX}z` : '')).join('')

function num(v: number): string {
  return String(Math.round(v * 10) / 10)
}

const mid = (a: Pt, b: Pt): Pt => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
const xy = (p: Pt) => `${num(p[0])} ${num(p[1])}`

// polígono smooth=True do Tk: curvas quadráticas pelos pontos médios das arestas
export function closedPath(pts: readonly Pt[]): string {
  const at = (i: number) => pts[(i + pts.length) % pts.length] as Pt
  return `M${xy(mid(at(-1), at(0)))}${pts.map((p, i) => `Q${xy(p)} ${xy(mid(p, at(i + 1)))}`).join('')}Z`
}

// linha smooth=True do Tk: começa e termina nas pontas
export function openPath(pts: readonly Pt[]): string {
  const inner = pts.slice(1, -1)
  return `M${xy(pts[0] as Pt)}${inner.map((p, i) => `Q${xy(p)} ${xy(i === inner.length - 1 ? pts[pts.length - 1] as Pt : mid(p, pts[i + 2] as Pt))}`).join('')}`
}

// arco no sentido do Tk (graus anti-horário a partir das 3h, y pra baixo)
export function arc(cx: number, cy: number, r: number, start: number, extent: number): string {
  const p = (a: number): Pt => [cx + r * Math.cos((a * Math.PI) / 180), cy - r * Math.sin((a * Math.PI) / 180)]
  return `M${xy(p(start))}A${r} ${r} 0 0 0 ${xy(p(start + extent))}`
}

export type PanelKey = 'buttons' | 'sticks' | 'triggers' | 'leds' | 'profile'

export interface Callout {
  label: string
  side: 'l' | 'r'
  y: number
  to: Pt
  panel: PanelKey
  // id do campo q recebe o foco
  field: string
}

// legendas da tela inicial do app, na mesma altura e apontando pro mesmo lugar
export const CALLOUTS: Callout[] = [
  { label: 'LT', side: 'l', y: 13, to: [96, 12], panel: 'triggers', field: 'triggers-left_start' },
  { label: 'L4', side: 'l', y: 36, to: [142, 21], panel: 'buttons', field: 'map-P3' },
  { label: 'LB', side: 'l', y: 59, to: [54, 42], panel: 'buttons', field: 'map-LB' },
  { label: 'Analógico esquerdo', side: 'l', y: 106, to: [61, 106], panel: 'sticks', field: 'sticks-left_start' },
  { label: 'D-pad', side: 'l', y: 175, to: [121, 175], panel: 'buttons', field: 'map-Up' },
  { label: 'RT', side: 'r', y: 13, to: [344, 12], panel: 'triggers', field: 'triggers-right_start' },
  { label: 'R4', side: 'r', y: 36, to: [298, 21], panel: 'buttons', field: 'map-P4' },
  { label: 'RB', side: 'r', y: 59, to: [386, 42], panel: 'buttons', field: 'map-RB' },
  { label: 'Botões ABXY', side: 'r', y: 104, to: [394, 104], panel: 'buttons', field: 'map-A' },
  { label: 'Analógico direito', side: 'r', y: 177, to: [313, 177], panel: 'sticks', field: 'sticks-right_start' },
  { label: 'Traseiros PL / PR', side: 'r', y: 308, to: [264, 308], panel: 'buttons', field: 'map-P1' },
]
