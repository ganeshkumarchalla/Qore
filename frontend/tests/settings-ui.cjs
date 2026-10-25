/* Mocked UI-only settings check. No personal browser profile or live account.
 * Replay: node frontend/tests/settings-ui.cjs [http://127.0.0.1:8000]
 */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { workspaceFixture } = require('./workspace-fixture.cjs');
const ROOT = path.resolve(__dirname, '../..');
const EVIDENCE = path.join(ROOT, 'evidence');
fs.mkdirSync(EVIDENCE, { recursive: true });
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    page.setDefaultTimeout(15000);
    const errors = [];
    const workspace = workspaceFixture();
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const pathname = new URL(route.request().url()).pathname;
      const body = pathname === '/api/health' ? { status: 'ok', ai_available: false, auth_required: false, storage: 'sqlite', versions: {}, limits: { max_qubits: 10 } } : [];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(base);
    await page.getByRole('status', { name: 'Welcome to qubit' }).waitFor({ state: 'hidden' });
    await page.locator('.quantum-onboarding-overlay').waitFor({ state: 'visible' });
    await page.getByRole('radio', { name: /Quantum Superposition/ }).click();
    await page.getByRole('button', { name: /Initialize Quantum Experience/ }).click();
    await page.locator('.quantum-onboarding-overlay').waitFor({ state: 'hidden', timeout: 30000 });
    const trigger = page.getByRole('button', { name: 'Open Settings', exact: true });
    await trigger.click();
    const dialog = page.getByRole('dialog', { name: 'Settings & Preferences' }); await dialog.waitFor();
    const disabled = async title => {
      const group = dialog.getByRole('group', { name: title, exact: true });
      assert.equal(await group.getAttribute('disabled'), '', title + ' must be disabled');
      assert.equal(await group.locator('button:not(:disabled),input:not(:disabled),select:not(:disabled)').count(), 0);
    };
    const category = async name => { await dialog.getByRole('button', { name: new RegExp(name) }).click(); };
    await disabled('Workbench UI Density'); await disabled('Circuit Wire Shader Style');
    await disabled('Live State Pulse Propagation'); await disabled('Background Auto-Save');
    assert(await dialog.getByRole('switch', { name: 'Glassmorphism & Depth Shaders' }).isEnabled());
    await category('Monaco Editor');
    await disabled('Terminal Font Size (13px)'); await disabled('Terminal Cursor Blinking');
    assert(await dialog.getByRole('switch', { name: 'Format Code on Paste' }).isEnabled());
    await dialog.getByLabel('Editor font size', { exact: true }).focus(); await page.keyboard.press('End');
    await category('Quantum Kernel');
    await disabled('Classical Bit Ordering (Endianness)'); await disabled('Max Qubit Safety Guard (10 Qubits)');
    await disabled('Zero Amplitude Pruning Threshold'); await disabled('Numerical Precision Mode');
    await dialog.getByRole('button', { name: 'MPS', exact: true }).click();
    await dialog.getByRole('button', { name: '2048', exact: true }).click();
    await dialog.getByLabel('Deterministic RNG seed', { exact: true }).fill('81');
    await category('Physical QPUs');
    for (const title of ['Default Cloud Provider Execution', 'Fault-Tolerant Error Budget',
      'Target Hardware Coupling Architecture', 'Readout Error Mitigation Strategy', 'Dynamical Decoupling Pulse Sequence']) await disabled(title);
    await dialog.getByRole('switch', { name: 'Simulate Hardware Noise' }).click();
    await disabled('Thermal Relaxation & Dephasing (T1 / T2)');
    assert(await dialog.getByLabel('Depolarizing gate error', { exact: true }).isEnabled());
    assert(await dialog.getByLabel('Readout measurement error', { exact: true }).isEnabled());
    await page.screenshot({ path: path.join(EVIDENCE, 'settings-production-controls.png') });
    await category('Transpiler');
    for (const title of ['Qubit Layout & Routing Heuristic', 'Target Hardware Basis Gates',
      'Commutation Analysis & Gate Cancellation', 'Strict Unitary Verification (U† U = I)', 'Equivalence Numerical Tolerance']) await disabled(title);
    assert.equal(await dialog.getByRole('group', { name: 'Equivalence Numerical Tolerance', exact: true }).locator('select').inputValue(), '1e-9');
    await dialog.getByLabel('Transpiler optimization level', { exact: true }).selectOption('3');
    await category('AI Copilot');
    for (const title of ['Server-Managed Provider', 'Copilot Temperature (0.2)',
      'Auto-Explain Generated Circuits in Chat', 'Stream Token Generation Animation']) await disabled(title);
    for (let index = 0; index < 45; index++) {
      await page.keyboard.press('Tab');
      assert.equal(await dialog.evaluate(element => element.contains(document.activeElement)), true);
      assert.equal(await page.evaluate(() => document.activeElement.matches(':disabled')), false);
    }
    await dialog.getByRole('button', { name: 'Apply & Save Settings', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' });
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('qore_settings')));
    assert.equal(saved.fontSize, 18); assert.equal(saved.simulationBackend, 'matrix_product_state');
    assert.equal(saved.defaultShots, 2048); assert.equal(saved.defaultSeed, 81); assert.equal(saved.defaultOptLevel, 3);
    assert.equal(saved.noiseSimulation, true); assert.equal(saved.uiDensity, 'balanced');
    await trigger.click(); await dialog.waitFor(); await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'hidden' });
    assert.equal(await trigger.evaluate(element => element === document.activeElement), true);
    assert.deepEqual(errors, []);
    const report = { passed: true, base: new URL(page.url()).origin, scope: 'Mocked UI contract checks', disabledRows: 25,
      checks: ['All six sections preserved', 'Unsupported controls disabled through labeled fieldsets',
        'Server-controlled bit order, qubit limit and tolerance displayed accurately',
        'Editor, simulation, seed, shots, optimization and noise controls remain functional and persist',
        'Tab stays inside settings and skips disabled controls; Escape restores focus', 'No browser runtime errors'] };
    fs.writeFileSync(path.join(EVIDENCE, 'settings-ui-check.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
