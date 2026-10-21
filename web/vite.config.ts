/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // GitHub Pages serve o projeto em /8bitdo-ultimate2-linux/
  base: '/8bitdo-ultimate2-linux/',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        // bootstrap: só monta o <App/> no #root, quem cobre isso é o e2e
        'src/main.tsx',
        // só declara tipos, não sobra linha de JS pra medir
        'src/application/ports.ts',
        'src/domain/types.ts',
        // referência de tipos do Vite (import de .css), não tem código
        'src/vite-env.d.ts',
        'src/test/**',
        'src/**/*.test.{ts,tsx}',
      ],
      thresholds: { statements: 100, branches: 100, functions: 100, lines: 100 },
    },
  },
})
