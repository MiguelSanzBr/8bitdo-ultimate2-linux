// Raiz de composição: liga os adapters de verdade (ou o demo) nos casos de uso.
import { ConfigSession } from '../../application/config-session'
import type { LinkOpts } from '../../application/link'
import { DemoTransport } from '../demo'
import { GamepadDrain } from '../gamepad-drain'
import { WebHidTransport, requestController, webHidSupported } from '../webhid'
import type { InputDrain } from '../../application/ports'

export interface Opened {
  session: ConfigSession
  demo: boolean
}

export interface Wiring {
  supported: boolean
  openDemo(): Opened
  openReal(): Promise<Opened | null>
  // tela inicial, antes de qualquer sessão: só o gamepad q o navegador já enxerga
  onInput: InputDrain['onInput']
}

export function browserWiring(nav: Navigator = navigator, opts: Partial<LinkOpts> = {}): Wiring {
  return {
    supported: webHidSupported(nav),
    openDemo() {
      const t = new DemoTransport()
      return { session: new ConfigSession(t, t, opts), demo: true }
    },
    async openReal() {
      const device = await requestController(nav.hid)
      return device && { session: new ConfigSession(new WebHidTransport(device), new GamepadDrain(() => nav.getGamepads()), opts), demo: false }
    },
    onInput(cb) {
      const d = new GamepadDrain(() => nav.getGamepads?.() ?? [])
      const off = d.onInput(cb)
      d.start()
      return () => {
        off()
        d.stop()
      }
    },
  }
}
