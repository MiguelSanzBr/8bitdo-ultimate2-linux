// O firmware só atende o endpoint de config enquanto o host vai drenando os reports de joystick do
// controle. No Linux o xpad só faz polling com alguém segurando o /dev/input/js* aberto, por isso o
// Python abre esse nó junto (discovery.find_input_node). Aqui a aposta é q o Chrome abre o joystick
// e mantém a leitura enquanto a página fica chamando getGamepads(). Hipótese, falta validar no hardware.

import type { InputDrain } from '../application/ports'
import { IDLE, pickPad, readPad } from '../domain/live-input'
import type { LiveInput } from '../domain/live-input'

export const DRAIN_MS = 16

// adapter do port InputDrain no navegador
export class GamepadDrain implements InputDrain {
  polls = 0
  private timer: ReturnType<typeof setInterval> | undefined
  private readonly getGamepads: () => readonly (Gamepad | null)[]
  private last = IDLE
  private readonly listeners = new Set<(input: LiveInput) => void>()

  constructor(getGamepads = () => navigator.getGamepads()) {
    this.getGamepads = getGamepads
  }

  get running(): boolean {
    return this.timer !== undefined
  }

  start(): void {
    // setInterval e não requestAnimationFrame: rAF para de vez com a aba em segundo plano
    this.timer ??= setInterval(() => {
      this.polls++
      const input = readPad(pickPad(this.getGamepads()))
      // o poll é a 16 ms, só avisa quando muda pra não redesenhar à toa
      if (JSON.stringify(input) === JSON.stringify(this.last)) return
      this.last = input
      this.listeners.forEach((cb) => cb(input))
    }, DRAIN_MS)
  }

  stop(): void {
    clearInterval(this.timer)
    this.timer = undefined
    this.last = IDLE
  }

  onInput(cb: (input: LiveInput) => void): () => void {
    this.listeners.add(cb)
    cb(this.last)
    return () => this.listeners.delete(cb)
  }
}
