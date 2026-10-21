// Ports do núcleo. Os adapters (WebHID, demo, GamepadDrain) implementam; a application só conhece isso.
import type { LiveInput } from '../domain/live-input'

// Canal cru de reports de 64 bytes, contando o report id (81 = pedido, 02 = resposta), igual ao q o
// Python lê e escreve no /dev/hidraw.
export interface ReportChannel {
  readonly kind: 'webhid' | 'demo'
  open(): Promise<void>
  close(): Promise<void>
  send(report: Uint8Array): Promise<void>
  onReport(cb: (report: Uint8Array) => void): () => void
}

// Quem mantém o host lendo os reports de joystick do controle. Sem isso o firmware ignora o
// endpoint de config (no Python é o /dev/input/js* aberto durante o I/O).
export interface InputDrain {
  start(): void
  stop(): void
  readonly running: boolean
  // já q tá lendo o joystick, entrega o q tá apertado pro desenho acender: o estado atual na hora e depois cada mudança
  onInput(cb: (input: LiveInput) => void): () => void
}
