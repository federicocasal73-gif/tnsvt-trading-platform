import { test, expect } from './fixtures/auth';

test.describe('Login flow', () => {
  test('shows the login page when unauthenticated', async ({ page }) => {
    await page.goto('/');
    // ProtectedShell redirects to /login
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByTestId('login-card')).toBeVisible();
    await expect(page.getByRole('heading', { name: /TNSVT Terminal/i })).toBeVisible();
  });

  test('rejects empty submission', async ({ page }) => {
    await page.goto('/login');
    await page.getByTestId('login-submit').click();
    await expect(page.getByTestId('login-error')).toContainText(/required/i);
  });

  test('redirects to dashboard after successful login', async ({ page }) => {
    await page.goto('/login');
    await page.getByTestId('login-email').fill('demo@tnsvt.com');
    await page.getByTestId('login-password').fill('Secret123!');
    await page.getByTestId('login-submit').click();

    // Should land on dashboard
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });

  test('preserves the JWT in localStorage after login', async ({ page }) => {
    await page.goto('/login');
    await page.getByTestId('login-email').fill('demo@tnsvt.com');
    await page.getByTestId('login-password').fill('Secret123!');
    await page.getByTestId('login-submit').click();
    await expect(page).toHaveURL('/');

    const token = await page.evaluate(() => localStorage.getItem('tnsvt_token'));
    expect(token).toBeTruthy();
    expect(token!.split('.').length).toBe(3); // valid JWT shape
  });
});

test.describe('Auth gate', () => {
  test('unauthenticated user is redirected away from protected routes', async ({ page }) => {
    await page.goto('/positions');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('authenticated user with stored token lands on dashboard', async ({ authedPage: page }) => {
    await page.goto('/');
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });
});