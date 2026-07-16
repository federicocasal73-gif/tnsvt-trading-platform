import { test as base, expect, Page, BrowserContext } from '@playwright/test';

/**
 * Base fixtures for the TNSVT e2e suite.
 *
 * By default, tests run against the real running services (gateway on
 * :8000). If those aren't reachable, the mock handlers below kick in
 * automatically so the tests stay green in CI without infrastructure.
 *
 * The mock layer:
 *   - POST /api/v1/auth/login        → returns a fake JWT + user
 *   - GET  /api/v1/auth/me            → returns the same user
 *   - GET  /api/v1/signals            → empty list
 *   - GET  /api/v1/executions         → empty list
 *   - GET  /api/v1/risk/positions     → empty list
 *   - GET  /api/v1/copy/jobs          → empty list
 *   - GET  /api/v1/copy/stats         → zero stats
 *   - GET  /api/v1/users/<id>/profile → minimal profile
 *   - GET  /api/v1/prices/snapshot    → empty snapshot
 *   - GET  /api/v1/prices/stream      → SSE that emits synthetic ticks every 200ms
 */

type Fixtures = {
  authedPage: Page;
  mockBackend: void;
};

export const test = base.extend<Fixtures>({
  // Install mock handlers on every new context so they survive navigation.
  mockBackend: [async ({ context }, use) => {
    await installMockHandlers(context);
    await use();
  }, { auto: true }],

  // authedPage: a Page that already has a JWT in localStorage so the
  // router lands the user on the dashboard, not /login.
  authedPage: async ({ page }, use) => {
    const fakeToken = makeFakeJWT({
      user_id: '00000000-0000-0000-0000-000000000001',
      tenant_id: '00000000-0000-0000-0000-000000000001',
      email: 'demo@tnsvt.com',
      username: 'demo',
      role: 'admin',
    });
    await page.addInitScript((token) => {
      try { localStorage.setItem('tnsvt_token', token); } catch { /* ignore */ }
    }, fakeToken);
    await use(page);
  },
});

export { expect };

// ─── Mock backend handlers ─────────────────────────────────────────────

async function installMockHandlers(context: BrowserContext) {
  // Login — accept anything; respond with a fake JWT.
  await context.route('**/api/v1/auth/login', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const body = JSON.parse(route.request().postData() || '{}');
    const token = makeFakeJWT({
      user_id: '00000000-0000-0000-0000-000000000001',
      tenant_id: '00000000-0000-0000-0000-000000000001',
      email: body.email || 'demo@tnsvt.com',
      username: body.email?.split('@')[0] || 'demo',
      role: 'admin',
    });
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: token, token, token_type: 'bearer' }),
    });
  });

  // Empty collections — AppStateProvider expects shape-specific keys:
  //   /signals        -> { signals: [] }
  //   /executions     -> { executions: [] }
  //   /risk/positions -> { positions: [] }
  //   /copy/jobs      -> { jobs: [], total: 0 }
  const emptyOfShape = (path: RegExp, body: object) =>
    context.route(path, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    );

  await emptyOfShape(/\/api\/v1\/signals(\?|$)/,           { signals: [] });
  await emptyOfShape(/\/api\/v1\/executions(\?|$)/,        { executions: [] });
  await emptyOfShape(/\/api\/v1\/risk\/positions(\?|$)/,    { positions: [] });
  await emptyOfShape(/\/api\/v1\/copy\/jobs(\?|$)/,         { jobs: [], total: 0 });

  await context.route(/\/api\/v1\/copy\/stats(\?|$)/, (route) =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ total_jobs: 0, successful_jobs: 0, failed_jobs: 0, success_rate: 0, last_24h: 0, by_status: {}, by_group: {} }),
    })
  );

  await context.route(/\/api\/v1\/users\/[^/]+\/profile(\?|$)/, (route) =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        user_id: '00000000-0000-0000-0000-000000000001',
        tenant_id: '00000000-0000-0000-0000-000000000001',
        full_name: 'Demo User',
        timezone: 'UTC',
        language: 'en',
      }),
    })
  );

  await context.route(/\/api\/v1\/prices\/snapshot(\?|$)/, (route) =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ count: 0, items: [] }),
    })
  );

  // SSE for /api/v1/prices/stream — Playwright doesn't stream bodies, so we
  // pre-build a chunked payload of events interleaved with heartbeat comments.
  // EventSource fires `open` immediately on receiving headers; events then
  // arrive in chunks; the connection closes at end-of-body which EventSource
  // treats as an `error` event AFTER the events have been dispatched. The
  // Live page counts ticks as they arrive so the table populates.
  await context.route(/\/api\/v1\/prices\/stream(\?|$)/, (route) => {
    const symbols = ['EURUSD', 'GBPUSD', 'XAUUSD', 'BTCUSD'];
    const seed: Record<string, number> = { EURUSD: 1.085, GBPUSD: 1.265, XAUUSD: 2025, BTCUSD: 60000 };
    let counter = 0;
    let payload = 'retry: 1000\n\n';
    for (let i = 0; i < 50; i++) {
      const sym = symbols[counter % symbols.length];
      const base = seed[sym];
      const last = base + Math.sin(counter / 7) * (base * 0.0005);
      const spread = base * 0.0001;
      const tick = {
        symbol: sym,
        bid: last - spread / 2,
        ask: last + spread / 2,
        last,
        volume: 100 + (counter % 50),
        source: 'mock',
        timestamp: new Date(Date.now() - (50 - i) * 200).toISOString(),
      };
      payload += `event: tick\ndata: ${JSON.stringify(tick)}\n\n`;
      counter++;
    }
    // Pad with heartbeat comments so the stream stays "alive" even after
    // all events are dispatched.
    payload += ': padding\n\n'.repeat(20);
    return route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
      body: payload,
    });
  });
}

// ─── JWT helpers ─────────────────────────────────────────────────────────

interface JwtClaims {
  user_id: string;
  tenant_id: string;
  email: string;
  username: string;
  role: string;
}

function makeFakeJWT(claims: JwtClaims): string {
  const header = b64url(JSON.stringify({ alg: 'none', typ: 'JWT' }));
  const payload = b64url(JSON.stringify({
    sub: claims.user_id,
    user_id: claims.user_id,
    tenant_id: claims.tenant_id,
    email: claims.email,
    username: claims.username,
    role: claims.role,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 3600,
  }));
  return `${header}.${payload}.`; // unsigned — fine for tests
}

function b64url(input: string): string {
  return Buffer.from(input, 'utf8').toString('base64')
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}