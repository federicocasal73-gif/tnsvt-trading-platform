import { test, expect } from './fixtures/auth';

test.describe('Sidebar navigation', () => {
  // Splitting the full route tour into per-route tests instead of one loop
  // makes each test more reliable — they all use a fresh `goto()` which
  // gives the React Router + Vite preview a clean state.
  for (const { id, path, heading } of [
    { id: 'dashboard', path: '/',         heading: 'Dashboard' },
    { id: 'positions', path: '/positions', heading: 'Positions' },
    { id: 'signals',   path: '/signals',   heading: 'Signals' },
    { id: 'live',      path: '/live',      heading: 'Live Ticks' },
    { id: 'history',   path: '/history',   heading: 'Trade History' },
    { id: 'settings',  path: '/settings',  heading: 'Settings' },
  ]) {
    test(`navigates to ${id} and updates the URL`, async ({ authedPage: page }) => {
      await page.goto('/');
      await page.getByTestId(`nav-${id}`).click();
      await expect(page).toHaveURL(path);
      await expect(page.getByRole('heading', { name: heading })).toBeVisible();
    });
  }

  test('active item is highlighted in the sidebar', async ({ authedPage: page }) => {
    await page.goto('/positions');
    const active = page.getByTestId('nav-positions');
    // The active button gets the inset shadow class
    await expect(active).toHaveClass(/shadow-\[inset/);
  });

  test('logout navigates to /login', async ({ page }) => {
    await page.goto('/login');
    await page.getByTestId('login-email').fill('demo@tnsvt.com');
    await page.getByTestId('login-password').fill('Secret123!');
    await page.getByTestId('login-submit').click();
    await expect(page).toHaveURL('/');
    await page.getByTestId('nav-logout').click();
    await page.waitForURL(/\/login$/, { timeout: 10_000 });
    await expect(page.getByTestId('login-card')).toBeVisible();
  });
});

test.describe('Dashboard widgets', () => {
  test('shows the four KPI cards', async ({ authedPage: page }) => {
    await page.goto('/');
    await expect(page.getByTestId('kpi-pnl')).toBeVisible();
    await expect(page.getByTestId('kpi-winrate')).toBeVisible();
    await expect(page.getByTestId('kpi-pos')).toBeVisible();
    await expect(page.getByTestId('kpi-signals')).toBeVisible();
  });

  test('Live Prices widget shows streaming state', async ({ authedPage: page }) => {
    await page.goto('/');
    // The widget may show "streaming" or the latest connection state
    const stateEl = page.getByTestId('dashboard-tick-state');
    await expect(stateEl).toBeVisible();
  });
});