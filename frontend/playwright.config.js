import { defineConfig, devices } from '@playwright/test'

// E2E tests run against the real docker-compose backend stack (postgres,
// redis, web, worker, beat — see ../docker-compose.yml) plus the Vite dev
// server for the frontend, started automatically below. The backend stack
// itself is NOT started here: run `docker compose up -d` from the repo root
// first (the CI "e2e" job does this — see .github/workflows/ci.yml).
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev -- --port 5173',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
