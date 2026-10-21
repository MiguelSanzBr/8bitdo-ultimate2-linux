// @vitest-environment node
import { ESLint } from 'eslint'
import { describe, expect, it } from 'vitest'

// A regra de dependência mora no eslint.config.js; aqui garanto q ela existe e pega cada violação.
const eslint = new ESLint()

async function errors(file: string, code: string) {
  const [r] = await eslint.lintText(code, { filePath: file })
  return (r?.messages ?? []).map((m) => m.ruleId)
}

describe('regra de dependência entre camadas', () => {
  it.each([
    ['src/domain/x.ts', "import { useState } from 'react'\nexport const a = useState"],
    ['src/domain/x.ts', "import { DemoTransport } from '../adapters/demo'\nexport const a = DemoTransport"],
    ['src/domain/x.ts', "import type { ReportChannel } from '../application/ports'\nexport type A = ReportChannel"],
    ['src/application/x.ts', "import { WebHidTransport } from '../adapters/webhid'\nexport const a = WebHidTransport"],
    ['src/application/x.ts', "import { createRoot } from 'react-dom/client'\nexport const a = createRoot"],
  ])('%s não pode importar isso: %s', async (file, code) => {
    expect(await errors(file, code)).toContain('no-restricted-imports')
  })

  it.each([
    ['src/domain/x.ts', 'export const a = navigator.hid'],
    ['src/application/x.ts', 'export const a = document.title'],
    ['src/application/x.ts', 'export const a = window.location'],
  ])('%s não pode tocar em DOM/navigator: %s', async (file, code) => {
    expect(await errors(file, code)).toContain('no-restricted-globals')
  })

  it('adapter pode usar domain e application, e teste de application pode usar o demo', async () => {
    expect(await errors('src/adapters/x.ts', "import { crc16 } from '../domain/packet'\nexport const a = crc16")).toEqual([])
    expect(await errors('src/application/x.test.ts', "import { DemoTransport } from '../adapters/demo'\nexport const a = DemoTransport")).toEqual([])
  })
})
