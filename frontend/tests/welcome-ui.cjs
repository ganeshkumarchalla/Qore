/* The QORE icon opens the workspace without questions or a manual step. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { workspaceFixture } = require('./workspace-fixture.cjs');
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  const errors = [];
  async function open({ reducedMotion = 'no-preference', visited = false, legacy = false, unavailableStorage = false, viewport = { width: 1366, height: 768 } } = {}) {
    const context = await browser.newContext({ viewport, reducedMotion });
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(({ visited, legacy, unavailableStorage }) => {
      if (visited) localStorage.setItem('qore_has_visited', 'true');
      if (legacy) localStorage.setItem('qore_started', 'true');
      if (unavailableStorage) {
        const get = Storage.prototype.getItem;
        Storage.prototype.getItem = function (key) {
          if (key === 'qore_has_visited' || key === 'qore_started') throw new DOMException('Storage unavailable', 'SecurityError');
          return get.call(this, key);
        };
        const set = Storage.prototype.setItem;
        Storage.prototype.setItem = function (key, value) {
          if (key === 'qore_has_visited' || key === 'qore_started') throw new DOMException('Storage full', 'QuotaExceededError');
          return set.call(this, key, value);
        };
      }
    }, { visited, legacy, unavailableStorage });
    const workspace = workspaceFixture();
    let questionRequests = 0;
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === '/api/quantum/onboarding-question') questionRequests++;
      let body = [];
      if (pathname === '/api/health') body = { status: 'ok', ai_available: false, auth_required: false,
        storage: 'sqlite', versions: { qiskit: 'fixture' }, limits: { max_qubits: 10 } };
      else if (pathname === '/api/parse') body = { ir: { version: '1.0', num_qubits: 3, num_clbits: 3, global_phase: 0, operations: [] },
        metrics: { qubits: 3, clbits: 3, gate_count: 6, depth: 4, two_qubit_gate_count: 2, measurement_count: 3, barrier_count: 0, gate_types: {}, definition: 'fixture' }, source_hash: 'fixture', warnings: [] };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(base);
    return { page, context, workspace, getQuestionRequests: () => questionRequests };
  }

  try {
    let { page, context, getQuestionRequests } = await open();
    const intro = page.getByRole('dialog', { name: 'Opening QORE', exact: true });
    await intro.waitFor();
    assert.equal(await page.evaluate(() => localStorage.getItem('qore_has_visited')), null);
    assert.equal(await intro.locator('.qore-icon-entry-mark svg').count(), 1);
    assert.equal(await intro.getByRole('button').count(), 0);
    assert.equal(await intro.getByText(/Welcome to QORE|question/i).count(), 0);
    await intro.waitFor({ state: 'hidden', timeout: 4000 });
    assert.equal(await page.evaluate(() => localStorage.getItem('qore_has_visited')), 'true');
    assert.equal(await page.evaluate(() => document.body.style.overflow), '');
    assert.equal(getQuestionRequests(), 0);
    await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
    assert.equal(await page.getByRole('dialog').count(), 0);
    await page.reload();
    await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
    assert.equal(await intro.count(), 0);
    await context.close();
    console.log('PASS: icon-only first visit opens automatically, asks no question, and stays dismissed on refresh');

    ({ page, context } = await open({ reducedMotion: 'reduce', viewport: { width: 390, height: 650 } }));
    await page.getByRole('dialog', { name: 'Opening QORE' }).waitFor({ state: 'hidden', timeout: 3000 });
    await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
    assert.equal(await page.getByRole('dialog').count(), 0);
    await context.close();
    console.log('PASS: mobile and reduced-motion entry open promptly');

    for (const options of [{ visited: true }, { legacy: true }, { unavailableStorage: true }]) {
      ({ page, context } = await open(options));
      if (options.unavailableStorage) {
        await page.getByRole('dialog', { name: 'Opening QORE' }).waitFor({ state: 'hidden', timeout: 4000 });
      }
      await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
      assert.equal(await page.getByRole('dialog').count(), 0);
      await context.close();
    }
    assert.deepEqual(errors, []);
    console.log('PASS: returning visitors, legacy preferences, unavailable storage, and no browser exceptions');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
