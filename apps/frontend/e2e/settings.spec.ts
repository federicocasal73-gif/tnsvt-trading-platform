import { test, expect } from './fixtures/auth';

test.describe('Settings page', () => {
  test('shows account info from the decoded JWT', async ({ authedPage: page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
    await expect(page.getByText('demo@tnsvt.com')).toBeVisible();
    // Username 'demo' appears in the topbar (right side) AND in the settings main.
    // Use main scope to disambiguate.
    await expect(page.getByRole('main').getByText('demo', { exact: true })).toBeVisible();
    await expect(page.getByRole('main').getByText(/admin/i)).toBeVisible();
  });

  test('shows the JWT copy button', async ({ authedPage: page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('button', { name: /copy jwt/i })).toBeVisible();
  });
});

test.describe('Empty states', () => {
  test('positions shows empty state when no data', async ({ authedPage: page }) => {
    await page.goto('/positions');
    await expect(page.getByText(/no positions/i).first()).toBeVisible();
  });

  test('signals shows empty state when no data', async ({ authedPage: page }) => {
    await page.goto('/signals');
    await expect(page.getByText(/no signals/i).first()).toBeVisible();
  });

  test('history shows empty state when no data', async ({ authedPage: page }) => {
    await page.goto('/history');
    await expect(page.getByText(/no closed trades/i)).toBeVisible();
  });
});