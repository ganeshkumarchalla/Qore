/* First-visit welcome must work in Vite's React StrictMode and production. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { workspaceFixture } = require('./workspace-fixture.cjs');
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';
const splashName = 'Welcome to QORE Quantum Studio';
const introName = 'Welcome to QORE — quantum introduction';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  const errors = [];
  async function open({ reducedMotion = 'no-preference', visited = false, legacy = false, unavailableStorage = false, delayedQuestion = false } = {}) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, reducedMotion });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(({ visited, legacy, unavailableStorage }) => {
      if (visited) localStorage.setItem('qore_has_visited', 'true');
      if (legacy) localStorage.setItem('qore_started', 'true');
      if (unavailableStorage) {
        const original = Storage.prototype.getItem;
        Storage.prototype.getItem = function (key) {
          if (key === 'qore_has_visited' || key === 'qore_started') throw new DOMException('Storage unavailable', 'SecurityError');
          return original.call(this, key);
        };
        const originalSet = Storage.prototype.setItem;
        Storage.prototype.setItem = function (key, value) {
          if (key === 'qore_has_visited' || key === 'qore_started') throw new DOMException('Storage full', 'QuotaExceededError');
          return originalSet.call(this, key, value);
        };
      }
    }, { visited, legacy, unavailableStorage });
    let releaseQuestion;
    const questionGate = new Promise(resolve => { releaseQuestion = resolve; });
    const workspace = workspaceFixture();
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const pathname = new URL(route.request().url()).pathname;
      let body = [];
      if (pathname === '/api/health') body = { status: 'ok', ai_available: false, auth_required: false,
        storage: 'sqlite', versions: { qiskit: 'fixture' }, limits: { max_qubits: 10 } };
      else if (pathname === '/api/parse') body = { ir: { version: '1.0', num_qubits: 3, num_clbits: 3, global_phase: 0, operations: [] },
        metrics: { qubits: 3, clbits: 3, gate_count: 6, depth: 4, two_qubit_gate_count: 2, measurement_count: 3, barrier_count: 0, gate_types: {}, definition: 'fixture' }, source_hash: 'fixture', warnings: [] };
      else if (pathname === '/api/quantum/onboarding-question') {
        if (delayedQuestion) await questionGate;
        else { await route.abort(); return; }
        body = { question: 'A delayed replacement question', options: [
          { id: 'late', label: 'A', text: 'A delayed replacement answer', correct: true, explanation: 'This must not replace an answer in progress.' },
        ] };
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(base);
    return { page, context, releaseQuestion };
  }
  try {
    // A clean profile exposes the render-side-effect bug that returning-user tests missed.
    let { page, context, releaseQuestion } = await open();
    const splash = page.getByRole('dialog', { name: splashName, exact: true });
    await splash.waitFor();
    assert.equal(await page.evaluate(() => localStorage.getItem('qore_has_visited')), null);
    await page.keyboard.press('Tab');
    assert.equal(await page.getByRole('button', { name: 'Continue', exact: true }).evaluate(el => el === document.activeElement), true);
    await page.keyboard.press('Shift+Tab');
    assert.equal(await page.getByRole('button', { name: 'Continue', exact: true }).evaluate(el => el === document.activeElement), true);
    await splash.waitFor({ state: 'hidden', timeout: 9000 });
    await page.getByRole('dialog', { name: introName, exact: true }).waitFor();
    await page.getByRole('radio', { name: /Quantum Superposition/ }).click();
    await page.getByRole('button', { name: 'Initialize Quantum Experience' }).click();
    await page.getByRole('heading', { name: 'Welcome to the World Of Qiskit & Quantum' }).waitFor({ timeout: 7000 });
    await page.getByRole('dialog', { name: introName, exact: true }).waitFor({ state: 'hidden', timeout: 8000 });
    assert.equal(await page.evaluate(() => document.body.style.overflow), '');
    assert.equal(await page.evaluate(() => localStorage.getItem('qore_started')), 'true');
    await page.getByRole('button', { name: 'Get Started', exact: true }).click();
    await page.getByRole('button', { name: 'Open circuits/my_first_qubits.py', exact: true }).waitFor();
    await page.locator('.monaco-editor .view-lines').getByText(/QuantumCircuit/).first().waitFor();
    await page.getByRole('button', { name: 'Help', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: 'Replay Welcome', exact: true }).count(), 0);
    await page.keyboard.press('Escape');
    await page.reload();
    await page.getByRole('button', { name: 'Open circuits/my_first_qubits.py', exact: true }).waitFor();
    assert.equal(await splash.count(), 0);
    assert.equal(await page.getByRole('dialog', { name: introName, exact: true }).count(), 0);
    await context.close();
    console.log('PASS: first visit, timed animation, completion, Get Started, replay and refresh preserve the workspace');

    // Keyboard skip, delayed provider answer, short viewports and stale timer cleanup.
    ({ page, context, releaseQuestion } = await open({ delayedQuestion: true }));
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    await page.getByRole('radio', { name: /Quantum Superposition/ }).click();
    releaseQuestion();
    await page.waitForTimeout(250);
    assert.equal(await page.getByRole('radio', { name: /Quantum Superposition/ }).getAttribute('aria-checked'), 'true');
    assert.equal(await page.getByRole('radio', { name: /delayed replacement answer/ }).count(), 0);
    await page.setViewportSize({ width: 390, height: 650 });
    await page.getByRole('button', { name: 'Initialize Quantum Experience' }).click();
    await page.keyboard.press('Escape');
    await page.getByRole('dialog', { name: introName, exact: true }).waitFor({ state: 'hidden' });
    await page.waitForTimeout(9500);
    assert.equal(await page.getByRole('dialog').count(), 0, 'Closed introduction timers must not reopen or obscure the workspace');
    await context.close();
    console.log('PASS: delayed questions preserve selections; Escape exits the animated phase; no stale overlay');

    ({ page, context } = await open({ reducedMotion: 'reduce' }));
    await page.getByRole('dialog', { name: introName, exact: true }).waitFor({ timeout: 5000 });
    await page.getByRole('radio', { name: /Quantum Superposition/ }).click();
    await page.getByRole('button', { name: 'Initialize Quantum Experience' }).click();
    await page.getByRole('dialog', { name: introName, exact: true }).waitFor({ state: 'hidden', timeout: 3000 });
    await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
    await context.close();
    console.log('PASS: reduced motion completes without long typing or fade delays');

    for (const options of [{ visited: true }, { legacy: true }, { unavailableStorage: true }]) {
      ({ page, context } = await open(options));
      if (options.unavailableStorage) {
        await page.getByRole('button', { name: 'Continue', exact: true }).click();
        await page.getByRole('button', { name: 'Skip introduction', exact: true }).click();
      }
      await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
      assert.equal(await page.getByRole('dialog').count(), 0);
      await context.close();
    }
    assert.deepEqual(errors, []);
    console.log('PASS: returning visitors, legacy preferences, unavailable visit storage and no browser exceptions');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
