import { defineConfig, devices } from '@playwright/test'

const url = 'http://localhost:4176/8bitdo-ultimate2-linux/'

export default defineConfig({
  testDir: 'e2e',
  forbidOnly: !!process.env.CI,
  reporter: 'list',
  use: { baseURL: url },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run build && npm run preview',
    url,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
