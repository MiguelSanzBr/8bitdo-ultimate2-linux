import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

async function demo(page: Page) {
  await page.goto('./')
  await page.getByRole('button', { name: 'Abrir modo demo' }).click()
  await expect(page.getByRole('status')).toHaveText('Configuração lida do controle.')
}

test('modo demo: lê, remapeia um botão, confirma e vê aplicado', async ({ page }) => {
  await demo(page)
  await expect(page.getByText(/Modo demo/)).toBeVisible()

  await page.getByRole('button', { name: 'Botões ABXY' }).click()
  await expect(page.getByLabel('A', { exact: true })).toBeFocused()
  await page.getByLabel('A', { exact: true }).selectOption('B')
  await expect(page.getByRole('region', { name: 'Alterações pendentes' })).toContainText('1 alteração')
  await page.getByRole('button', { name: 'Revisar e gravar' }).click()
  const dialog = page.getByRole('dialog', { name: 'Confirmar gravação' })
  await expect(dialog.getByRole('listitem')).toHaveText(/Perfil 1 · mapping\/A\s*A → B/)
  await dialog.getByRole('button', { name: 'Gravar no controle' }).click()

  await expect(page.getByRole('status')).toHaveText('Gravado na flash e conferido na releitura.')
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('region', { name: 'Alterações pendentes' })).toBeHidden()
  await expect(page.getByLabel('A', { exact: true })).toHaveValue('B')
})

test('cabe em 375px sem rolagem horizontal', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 })
  await page.goto('./')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  await page.getByRole('button', { name: 'Abrir modo demo' }).click()
  await expect(page.getByRole('status')).toHaveText('Configuração lida do controle.')
  for (const name of ['Botões', 'Analógicos', 'Gatilhos', 'LEDs', 'Perfil']) {
    await page.getByRole('button', { name, exact: true }).click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  }
})

const luminance = (page: Page) => page.evaluate(() => {
  const [r, g, b] = (getComputedStyle(document.body).backgroundColor.match(/\d+/g) ?? []).map(Number) as [number, number, number]
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
})

for (const scheme of ['dark', 'light'] as const) {
  test(`tema ${scheme}: segue o sistema e o botão troca`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme })
    await demo(page)
    const dark = scheme === 'dark'
    expect(await luminance(page) < 0.5).toBe(dark)
    await expect(page.locator('svg.pad .body')).toBeVisible()
    await page.getByRole('button', { name: 'Mudar tema' }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', dark ? 'light' : 'dark')
    expect(await luminance(page) < 0.5).toBe(!dark)
  })
}

const LIT = /\blit\b/

test('modo demo: segurar o A no desenho acende até soltar', async ({ page }) => {
  await demo(page)
  const a = page.locator('svg.pad [data-part="A"]')
  const box = await a.boundingBox()
  if (!box) throw new Error('A fora da tela')
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await expect(a).toHaveClass(LIT)
  await page.mouse.up()
  await expect(a).not.toHaveClass(LIT)
})

test('gamepad com o A apertado acende o A no desenho da tela inicial', async ({ page }) => {
  // o Chrome só expõe o gamepad depois do primeiro aperto; aqui ele já vem apertado
  await page.addInitScript(() => {
    const buttons = Array.from({ length: 17 }, (_, i) => ({ pressed: i === 0, touched: i === 0, value: i === 0 ? 1 : 0 }))
    const pad = { id: '8BitDo Ultimate 2 (STANDARD GAMEPAD Vendor: 2dc8 Product: 6012)', index: 0, connected: true, mapping: 'standard', timestamp: 0, axes: [0, 0, 0, 0], buttons }
    Object.defineProperty(Navigator.prototype, 'getGamepads', { configurable: true, value: () => [pad, null, null, null] })
  })
  await page.goto('./')
  await expect(page.locator('svg.pad [data-part="A"]')).toHaveClass(LIT)
  await expect(page.locator('svg.pad [data-part="B"]')).not.toHaveClass(LIT)
})
