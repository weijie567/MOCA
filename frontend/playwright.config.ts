import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.MOCA_E2E_BASE_URL ?? 'http://127.0.0.1:3100'
const apiURL = process.env.MOCA_E2E_API_URL ?? 'http://127.0.0.1:8000'
const browserChannel = process.env.PLAYWRIGHT_CHANNEL ?? 'chrome'
const basePort = new URL(baseURL).port || '3100'

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${basePort}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      VITE_API_URL: apiURL,
    },
  },
  projects: [
    {
      name: 'mocked',
      grepInvert: /@live/,
      use: { ...devices['Desktop Chrome'], channel: browserChannel },
    },
    {
      name: 'mocked-mobile',
      grepInvert: /@live/,
      use: { ...devices['Pixel 5'], channel: browserChannel },
    },
    {
      name: 'live',
      grep: /@live/,
      use: { ...devices['Desktop Chrome'], channel: browserChannel },
    },
  ],
})
