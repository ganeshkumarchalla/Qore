/* No-account UI contract. QORE must open without login or provider requests. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { workspaceFixture } = require('./workspace-fixture.cjs');
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    const requests = [], errors = [], workspace = workspaceFixture();
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const pathname = new URL(route.request().url()).pathname;
      requests.push(pathname);
      const body = pathname === '/api/health'
        ? { status: 'ok', ai_available: false, auth_configured: false, auth_required: false, storage: 'sqlite', versions: {}, limits: { max_qubits: 10 } }
        : [];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(base);
    await page.getByRole('status', { name: 'Welcome to qubit' }).waitFor({ state: 'hidden' });
    await page.locator('.quantum-onboarding-overlay').waitFor({ state: 'visible', timeout: 10000 });
    await page.getByRole('radio', { name: /Quantum Superposition/ }).click();
    await page.getByRole('button', { name: /Initialize Quantum Experience/ }).click();
    await page.locator('.quantum-onboarding-overlay').waitFor({ state: 'hidden', timeout: 30000 });
    await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: /account|sign in|log in/i }).count(), 0);
    assert.equal(requests.some(path => path.startsWith('/api/auth/')), false);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: true, checks: ['No account controls', 'No authentication API calls', 'Workspace opens normally'] }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
