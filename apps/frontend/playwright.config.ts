import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for the TNSVT V2 frontend.
 *
 * - Runs `npm run dev` on port 5180
 * - Spins up Chromium + Firefox (WebKit disabled for speed)
 * - Spins a mock /api backend for tests that don't need the real stack
 *
 * For tests requiring the full backend (Postgres/Redis/NATS/etc.), set
 * TNSVT_USE_REAL_BACKEND=1 — they will use whatever is reachable on
 * localhost instead of the mock.
 */
const PORT = 5180;
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',

  timeout: 30_000,
  expect: { timeout: 5_000 },

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox',  use: { ...devices['Desktop Firefox'] } },
  ],

  webServer: {
    // Use `vite preview` against the production build for stability;
    // falls back to `npm run dev` if no build is present.
    command: process.env.PW_DEV === '1' ? 'npm run dev' : 'npm run preview -- --port 5180',
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});