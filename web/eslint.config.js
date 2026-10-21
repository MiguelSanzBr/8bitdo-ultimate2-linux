import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'

// regra de dependência da arquitetura hexagonal: o núcleo não conhece adapter, React nem DOM
const ui = ['react', 'react-dom', 'react-dom/*']
const browser = ['window', 'document', 'navigator'].map((name) => ({ name, message: 'DOM/navigator só nos adapters' }))
const layer = (forbidden) => ({
  'no-restricted-imports': ['error', { patterns: [{ group: forbidden, message: 'quebra a regra de dependência entre camadas' }] }],
  'no-restricted-globals': ['error', ...browser],
})

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'playwright-report', 'test-results'] },
  {
    files: ['**/*.{ts,tsx,js}'],
    extends: [js.configs.recommended, ...tseslint.configs.strict],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    plugins: { 'react-hooks': reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  },
  {
    files: ['src/domain/**'],
    ignores: ['src/**/*.test.*'],
    rules: layer([...ui, '**/application/**', '**/adapters/**']),
  },
  {
    files: ['src/application/**'],
    ignores: ['src/**/*.test.*'],
    rules: layer([...ui, '**/adapters/**']),
  },
)
