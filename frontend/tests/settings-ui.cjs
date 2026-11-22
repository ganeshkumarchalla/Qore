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
    await page.getByRole('dialog', { name: 'Opening QORE' }).waitFor({ state: 'hidden' });
    const trigger = page.getByRole('button', { name: 'Open Settings', exact: true });
    await trigger.click();
    const dialog = page.getByRole('dialog', { name: 'Settings & Preferences' });
    await dialog.waitFor();
    assert.equal(await dialog.getByRole('navigation', { name: 'Settings sections' }).getByRole('button').count(), 2);
    assert.equal(await dialog.getByText('Graphite', { exact: true }).count(), 1);
    assert.equal(await dialog.getByText(/Accent Color|Monaco Editor|Physical QPUs|QORE Intelligence/).count(), 0);
    await dialog.getByLabel('Editor font size').focus();
    await page.keyboard.press('End');
    await dialog.getByRole('switch', { name: 'Word wrap' }).click();
    await dialog.getByRole('button', { name: 'Quantum', exact: true }).click();
    await dialog.getByLabel('Simulation method').selectOption('matrix_product_state');
    await dialog.getByLabel('Default shots').selectOption('2048');
    await dialog.getByLabel('Random seed').fill('81');
    await dialog.getByRole('switch', { name: 'Noise simulation' }).click();
    assert(await dialog.getByLabel('Gate error').isEnabled());
    assert(await dialog.getByLabel('Readout error').isEnabled());
    await dialog.getByLabel('Forge optimization level').selectOption('3');
    for (let index = 0; index < 25; index++) {
      await page.keyboard.press('Tab');
      assert.equal(await dialog.evaluate(element => element.contains(document.activeElement)), true);
    }
    await page.screenshot({ path: path.join(EVIDENCE, 'settings-production-controls.png') });
    await dialog.getByRole('button', { name: 'Save settings' }).click();
    await dialog.waitFor({ state: 'hidden' });
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('qore_settings')));
    assert.equal(saved.fontSize, 20);
    assert.equal(saved.wordWrap, false);
    assert.equal(saved.simulationBackend, 'matrix_product_state');
    assert.equal(saved.defaultShots, 2048);
    assert.equal(saved.defaultSeed, 81);
    assert.equal(saved.defaultOptLevel, 3);
    assert.equal(saved.noiseSimulation, true);
    assert.equal(saved.theme, 'obsidian-void');
    assert.equal(saved.accentColor, '#d8d6d2');
    await trigger.click();
    await dialog.waitFor();
    await page.keyboard.press('Escape');
    await dialog.waitFor({ state: 'hidden' });
    assert.equal(await trigger.evaluate(element => element === document.activeElement), true);
    assert.deepEqual(errors, []);
    const report = { passed: true, base: new URL(page.url()).origin, scope: 'Mocked UI contract checks',
      checks: ['Two clear settings sections and fixed graphite appearance',
        'Editor, simulation, seed, shots, Forge and noise controls persist',
        'Tab remains inside settings; Escape restores focus', 'No browser runtime errors'] };
    fs.writeFileSync(path.join(EVIDENCE, 'settings-ui-check.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
