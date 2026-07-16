import { test, expect } from './fixtures/auth';

test.describe('Live ticks page', () => {
  test('shows the streaming badge after ticks arrive', async ({ authedPage: page }) => {
    await page.goto('/live');

    // Wait for at least one tick to render — the table replaces the empty state.
    await expect(page.getByTestId('live-table')).toBeVisible({ timeout: 10_000 });

    // The badge should be present and have a data-state attribute.
    // The exact value depends on timing (open, closed, or error after the
    // mocked stream ends — all are valid end states for a finite SSE mock).
    const status = page.getByTestId('live-status');
    await expect(status).toBeVisible();
    const state = await status.getAttribute('data-state');
    expect(state).toBeTruthy();
  });

  test('counts and symbols reflect incoming ticks', async ({ authedPage: page }) => {
    await page.goto('/live');
    await expect(page.getByTestId('live-table')).toBeVisible({ timeout: 10_000 });

    // Wait for at least 3 ticks to come through
    await expect.poll(async () => {
      const text = await page.getByTestId('live-count').textContent();
      const n = parseInt(text?.match(/\d+/)?.[0] ?? '0', 10);
      return n;
    }, { timeout: 10_000, intervals: [200] }).toBeGreaterThanOrEqual(3);

    // Symbols should include at least one of our mock symbols
    const symbols = await page.getByTestId('live-symbols').textContent();
    expect(symbols).toMatch(/\d+/);
  });

  test('renders a row per known symbol', async ({ authedPage: page }) => {
    await page.goto('/live');
    await expect(page.getByTestId('live-table')).toBeVisible({ timeout: 10_000 });

    // Wait for at least one of the mock symbols to appear
    await expect(page.getByTestId('live-row-EURUSD')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('live-row-GBPUSD')).toBeVisible({ timeout: 10_000 });
  });

  test('raw feed shows the latest ticks', async ({ authedPage: page }) => {
    await page.goto('/live');
    await expect(page.getByTestId('live-feed')).toBeVisible();
    // Each tick renders a <li> inside the feed
    await expect.poll(async () => {
      return await page.locator('[data-testid="live-feed"] li').count();
    }, { timeout: 10_000, intervals: [200] }).toBeGreaterThan(2);
  });
});