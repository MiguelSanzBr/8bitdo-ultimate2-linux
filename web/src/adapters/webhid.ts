// Adapter do port ReportChannel: o canal de config via WebHID. Faz o papel do discovery.py + os.open
// do hidraw no Python. O dreno do joystick é outro port, quem liga é a ConfigSession.
import { PIDS, USAGE_PAGES, VID } from '../domain/packet'
import type { ReportChannel } from '../application/ports'

export const FILTERS: HIDDeviceFilter[] = Object.keys(PIDS).flatMap((pid) =>
  USAGE_PAGES.map((usagePage) => ({ vendorId: VID, productId: Number(pid), usagePage })))

export const webHidSupported = (nav: Navigator = navigator) => 'hid' in nav

export const isConfigInterface = (d: HIDDevice) =>
  d.vendorId === VID && d.collections.some((c) => USAGE_PAGES.includes(c.usagePage as number))

export async function requestController(hid: HID = navigator.hid): Promise<HIDDevice | null> {
  const devices = await hid.requestDevice({ filters: FILTERS })
  return devices.find(isConfigInterface) ?? null
}

export class WebHidTransport implements ReportChannel {
  readonly kind = 'webhid'
  readonly device: HIDDevice
  private listeners = new Set<(r: Uint8Array) => void>()

  constructor(device: HIDDevice) {
    this.device = device
  }

  private onInput = (e: HIDInputReportEvent) => {
    const r = new Uint8Array(1 + e.data.byteLength)
    r[0] = e.reportId
    r.set(new Uint8Array(e.data.buffer, e.data.byteOffset, e.data.byteLength), 1)
    this.listeners.forEach((l) => l(r))
  }

  async open(): Promise<void> {
    try {
      if (!this.device.opened) await this.device.open()
    } catch (e) {
      throw new Error('Não deu pra abrir o canal de config do controle. No Linux o Chrome precisa da regra udev 70-8bitdo-u2.rules pra abrir o hidraw.', { cause: e })
    }
    this.device.addEventListener('inputreport', this.onInput)
  }

  async close(): Promise<void> {
    this.device.removeEventListener('inputreport', this.onInput)
    if (this.device.opened) await this.device.close()
  }

  // o report id (0x81) vai separado no WebHID; o resto são os 63 bytes do pedido
  send(report: Uint8Array): Promise<void> {
    return this.device.sendReport(report[0] as number, report.slice(1))
  }

  onReport(cb: (r: Uint8Array) => void): () => void {
    this.listeners.add(cb)
    return () => this.listeners.delete(cb)
  }
}
