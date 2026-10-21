import { describe, expect, it } from 'vitest'
import { InvariantError, changeProblem, gamepadModeName, ledTheme, ledThemeName, profileIndex, profileLabel } from './values'

describe('Profile', () => {
  it('só existem os perfis 1 a 3 (índice 0 a 2 no registro)', () => {
    expect(profileIndex(2)).toBe(2)
    expect(profileLabel(0)).toBe('Perfil 1')
    expect(() => profileIndex(3)).toThrow(InvariantError)
    expect(() => profileIndex(-1)).toThrow(InvariantError)
  })
})

describe('GamepadMode', () => {
  it('nomeia os modos do docs/PROTOCOL.md', () => {
    expect([0, 1, 3].map(gamepadModeName)).toEqual(['Switch', 'Android', 'Windows (XInput)'])
    expect(gamepadModeName(7)).toBe('desconhecido (7)')
  })
})

describe('LedTheme', () => {
  it('aceita só dynamic, hotwheel, custom e off', () => {
    expect(ledTheme(2)).toBe(2)
    expect(ledTheme(5)).toBe(5)
    expect(() => ledTheme(1)).toThrow(InvariantError)
    expect(() => ledTheme(6)).toThrow(InvariantError)
  })

  it('nomeia o tema, ou desconhecido', () => {
    expect([ledThemeName(3), ledThemeName(9), ledThemeName(null)]).toEqual(['hotwheel', 'desconhecido', 'desconhecido'])
  })
})

describe('changeProblem', () => {
  it('StickSettings: zona morta e alcance vão de 0 a 128', () => {
    expect(changeProblem('slots/0/sticks/left_start', 128)).toBeNull()
    expect(changeProblem('slots/2/sticks/right_end', 129)).toMatch(/0 a 128/)
    expect(changeProblem('slots/0/sticks/left_end', -1)).toMatch(/0 a 128/)
  })

  it('TriggerRange: acionamento e fim de curso vão de 0 a 255', () => {
    expect(changeProblem('slots/1/triggers/right_start', 255)).toBeNull()
    expect(changeProblem('slots/1/triggers/left_start', 256)).toMatch(/0 a 255/)
    expect(changeProblem('slots/1/triggers/left_start', 1.5)).toMatch(/0 a 255/)
  })

  it('ButtonMapping: função conhecida ou código hex preservado', () => {
    expect(changeProblem('slots/0/mapping/A', 'B')).toBeNull()
    expect(changeProblem('slots/0/mapping/P1', '0x00077777')).toBeNull()
    expect(changeProblem('slots/0/mapping/A', 'Pular')).toMatch(/função/)
    expect(changeProblem('slots/0/mapping/flag', 'enabled')).toBeNull()
  })

  it('cor de LED é #rrggbb', () => {
    expect(changeProblem('slots/0/led_dynamic/color', '#00ff7f')).toBeNull()
    expect(changeProblem('slots/0/led_dynamic/bg_color', 'red')).toMatch(/#rrggbb/)
  })

  it('o resto passa direto pro codec, q confere o tipo', () => {
    expect(changeProblem('slots/0/name', 'Linux')).toBeNull()
  })
})
