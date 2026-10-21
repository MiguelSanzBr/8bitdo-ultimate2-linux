import { afterEach, describe, expect, it, vi } from 'vitest'
import { FILTERS, WebHidTransport, isConfigInterface, requestController, webHidSupported } from './webhid'

class FakeHid extends EventTarget {
  opened = false
  vendorId = 0x2dc8
  productId = 0x310b
  productName = 'Ultimate 2'
  collections: { usagePage?: number }[] = [{ usagePage: 0xff7a }]
  sent: [number, Uint8Array][] = []
  failOpen = false
  async open() {
    if (this.failOpen) throw new DOMException('Failed to open the device.', 'NotAllowedError')
    this.opened = true
  }
  async close() {
    this.opened = false
  }
  async sendReport(id: number, data: BufferSource) {
    this.sent.push([id, new Uint8Array(data as ArrayBuffer)])
  }
  input(reportId: number, bytes: number[]) {
    const e = new Event('inputreport') as HIDInputReportEvent
    Object.assign(e, { reportId, data: new DataView(Uint8Array.from([0xee, ...bytes]).buffer, 1) })
    this.dispatchEvent(e)
  }
}

const hid = (over: Partial<FakeHid> = {}) => Object.assign(new FakeHid(), over) as unknown as HIDDevice & FakeHid

afterEach(() => vi.unstubAllGlobals())

describe('filtros', () => {
  it('cobrem os 3 PIDs nas duas usage pages de config', () => {
    // espelha protocol.PIDS x discovery.CONFIG_DESCRIPTORS
    expect(FILTERS).toHaveLength(6)
    expect(FILTERS).toContainEqual({ vendorId: 0x2dc8, productId: 0x6013, usagePage: 0xffa0 })
    expect(FILTERS).toContainEqual({ vendorId: 0x2dc8, productId: 0x310b, usagePage: 0xff7a })
  })

  it('só aceita interface 8BitDo com usage page de config', () => {
    expect(isConfigInterface(hid())).toBe(true)
    expect(isConfigInterface(hid({ collections: [{ usagePage: 0xffa0 }] }))).toBe(true)
    expect(isConfigInterface(hid({ collections: [{ usagePage: 1 }, {}] }))).toBe(false)
    expect(isConfigInterface(hid({ vendorId: 0x1234 }))).toBe(false)
  })
})

describe('webHidSupported', () => {
  it('olha se navigator.hid existe', () => {
    expect(webHidSupported({} as Navigator)).toBe(false)
    expect(webHidSupported({ hid: {} } as Navigator)).toBe(true)
    vi.stubGlobal('navigator', {})
    expect(webHidSupported()).toBe(false)
  })
})

describe('requestController', () => {
  it('pede o dispositivo com os filtros e pega a interface de config', async () => {
    const good = hid()
    const requestDevice = vi.fn(async () => [hid({ collections: [{ usagePage: 1 }] }), good])
    vi.stubGlobal('navigator', { hid: { requestDevice } })
    expect(await requestController()).toBe(good)
    expect(requestDevice).toHaveBeenCalledWith({ filters: FILTERS })
  })

  it('devolve null quando a pessoa cancela', async () => {
    expect(await requestController({ requestDevice: async () => [] } as unknown as HID)).toBeNull()
  })
})

describe('WebHidTransport', () => {
  it('abre e fecha o dispositivo', async () => {
    // o dreno do joystick saiu daqui: quem liga é o caso de uso (ConfigSession)
    const d = hid()
    const t = new WebHidTransport(d)
    expect(t.kind).toBe('webhid')
    await t.open()
    expect(d.opened).toBe(true)
    await t.close()
    expect(d.opened).toBe(false)
  })

  it('não reabre dispositivo já aberto nem fecha o q já tá fechado', async () => {
    const d = hid({ opened: true })
    const open = vi.spyOn(d, 'open')
    const t = new WebHidTransport(d)
    await t.open()
    expect(open).not.toHaveBeenCalled()
    d.opened = false
    const close = vi.spyOn(d, 'close')
    await t.close()
    expect(close).not.toHaveBeenCalled()
  })

  it('falha ao abrir explica a regra udev', async () => {
    await expect(new WebHidTransport(hid({ failOpen: true })).open()).rejects.toThrow(/udev/)
  })

  it('separa o report id no envio', async () => {
    const d = hid()
    const t = new WebHidTransport(d)
    const pkt = new Uint8Array(64)
    pkt.set([0x81, 4, 0x41])
    await t.send(pkt)
    expect(d.sent).toEqual([[0x81, pkt.slice(1)]])
  })

  it('junta report id e dados na recepção', async () => {
    const d = hid()
    const t = new WebHidTransport(d)
    const got: Uint8Array[] = []
    const off = t.onReport((r) => got.push(r))
    await t.open()
    d.input(2, [4, 4, 0])
    off()
    d.input(2, [9])
    await t.close()
    d.input(2, [8])
    expect(got).toEqual([Uint8Array.of(2, 4, 4, 0)])
  })

})
