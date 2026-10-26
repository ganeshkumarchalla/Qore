/* Explicitly mocked UI contract checks. Backend correctness is tested separately.
 * Replay: node frontend/tests/assistant-ui.cjs [http://127.0.0.1:8000]
 * Uses a fresh browser context; no personal profile or live login is used.
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

async function main() {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  const checks = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    page.setDefaultTimeout(15000);
    const runtimeErrors = [], consoleErrors = [], requested = [];
    page.on('pageerror', error => runtimeErrors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
    page.on('request', request => requested.push(request.url()));
    const ir = { version: '1.0', num_qubits: 3, num_clbits: 3, global_phase: 0, operations: [
      { name: 'h', qubits: [0], clbits: [], params: [] },
      { name: 'cx', qubits: [0, 1], clbits: [], params: [] },
      { name: 'cx', qubits: [1, 2], clbits: [], params: [] },
      ...[0, 1, 2].map(qubit => ({ name: 'measure', qubits: [qubit], clbits: [qubit], params: [] })),
    ] };
    const matrix = Array.from({ length: 8 }, () => Array.from({ length: 8 }, () => ({ real: 0, imag: 0, magnitude: 0, phase: 0 })));
    // GHZ operator: H(q0), CX(q0,q1), CX(q1,q2), with q0 as the least significant bit.
    for (let column = 0; column < 8; column++) for (let bit = 0; bit < 2; bit++) {
      let row = (column & ~1) | bit;
      if (row & 1) row ^= 2;
      if (row & 2) row ^= 4;
      const real = (column & 1) && bit ? -Math.SQRT1_2 : Math.SQRT1_2;
      matrix[row][column] = { real, imag: 0, magnitude: Math.SQRT1_2, phase: real < 0 ? Math.PI : 0 };
    }
    const parsed = { ir, metrics: { qubits: 3, clbits: 3, gate_count: 3, depth: 4,
      two_qubit_gate_count: 2, measurement_count: 3, barrier_count: 0, gate_types: { h: 1, cx: 2, measure: 3 }, definition: 'UI fixture' },
      source_hash: 'ui-contract-fixture', warnings: [], unitary_matrix: matrix,
      statevector_amplitudes: ['000', '111'].map(state => ({ state, real: Math.SQRT1_2, imag: 0,
        magnitude: Math.SQRT1_2, phase: 0, probability: 0.5 })),
      bloch_vectors: [0, 1, 2].map(qubit => ({ qubit, x: 0, y: 0, z: 0, theta: 0, phi: 0, purity: 0.5, is_pure: false })),
    };
    let source = '', assistantRequest, runCount = 0;
    const workspace = workspaceFixture();
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const request = route.request(), pathname = new URL(request.url()).pathname;
      let body = {};
      if (pathname === '/api/health') body = { status: 'ok', ai_available: true, versions: { qiskit: 'ui-fixture-version' }, limits: { max_qubits: 10 } };
      else if (pathname === '/api/projects' || pathname === '/api/experiments') body = [];
      else if (pathname === '/api/parse') { source = request.postDataJSON().source; body = parsed; }
      else if (pathname === '/api/assistant') {
        assistantRequest = request.postDataJSON();
        body = { available: true, answer: 'The active circuit prepares a three-qubit GHZ state.', model: 'ui-fixture-model' };
      } else if (pathname === '/api/simulate') {
        runCount++;
        source = request.postDataJSON().source;
        body = { ...parsed, id: 'ui-fixture-run-' + runCount, kind: 'simulation', source,
          created_at: '2026-10-25T08:00:00Z', counts: { '000': 512, '111': 512 },
          probabilities: { '000': 0.5, '111': 0.5 }, theoretical_probabilities: { '000': 0.5, '111': 0.5 },
          shots: 1024, seed: 81, backend: 'ui-fixture-backend', versions: { qiskit: 'ui-fixture-version' },
          execution_ms: 12.34, bit_ordering: 'UI fixture ordering', tvd: 0,
        };
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(base);
    await page.getByRole('status', { name: 'Welcome to qubit' }).waitFor({ state: 'hidden' });
    await page.locator('.quantum-onboarding-overlay').waitFor({ state: 'visible', timeout: 10000 });
    await page.getByRole('radio', { name: /Quantum Superposition/ }).click();
    await page.getByRole('button', { name: /Initialize Quantum Experience/ }).click();
    await page.locator('.quantum-onboarding-overlay').waitFor({ state: 'hidden', timeout: 30000 });
    await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
    assert.equal(requested.some(url => /QuantumEditor|monaco-editor|\/monaco[.-]/i.test(url)), false, 'Monaco must be deferred on an empty workspace');
    checks.push('Empty welcome/workspace does not request Monaco');
    await page.getByRole('button', { name: 'Get Started', exact: true }).click();
    await page.locator('.monaco-editor').first().waitFor();
    await page.waitForFunction(() => document.querySelector('.monaco-editor .view-lines')?.textContent.includes('QuantumCircuit'), null, { timeout: 15000 });
    assert(requested.some(url => /QuantumEditor|monaco-editor|\/monaco[.-]/i.test(url)));
    assert.equal(requested.some(url => /cdn\.jsdelivr|unpkg\.com|cdnjs\.cloudflare/.test(url)), false, 'Monaco is local, not CDN loaded');
    assert.equal(await page.locator('.vscode-sidebar').count(), 1, 'Identity transition must not duplicate Explorer');
    checks.push('Get Started opens a working local Monaco editor; exactly one Explorer');

    await page.locator('#qore-assistant-toggle').click();
    const sidebar = page.locator('#qore-assistant-sidebar'); await sidebar.waitFor();
    assert.equal(await page.locator('.activity-bar').getByRole('button', { name: 'Assistant', exact: true }).count(), 0);
    await page.getByLabel('Ask QI Assistant').fill('Explain the active circuit');
    await page.getByRole('button', { name: 'Ask assistant', exact: true }).click();
    await sidebar.getByText('The active circuit prepares a three-qubit GHZ state.', { exact: true }).waitFor();
    assert.equal(assistantRequest.source, source);
    await page.screenshot({ path: path.join(EVIDENCE, 'assistant-studio-1366.png') });
    await page.getByRole('button', { name: 'Simulation', exact: true }).click();
    await page.getByRole('heading', { name: 'No Simulation Results' }).waitFor();
    assert(await sidebar.isVisible());
    await sidebar.getByRole('button', { name: 'Close assistant sidebar', exact: true }).focus();
    await page.keyboard.press('Escape'); await sidebar.waitFor({ state: 'hidden' });
    assert.equal(await page.locator('#qore-assistant-toggle').evaluate(element => element === document.activeElement), true);
    checks.push('Assistant uses exact active source; independent Lab view; Escape closes and restores focus');

    for (const width of [1366, 1440, 1920, 900, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      await page.locator('#qore-assistant-toggle').click(); await sidebar.waitFor();
      const box = await sidebar.boundingBox();
      assert(box.x >= -1 && box.x + box.width <= width + 1, 'Drawer must fit width ' + width);
      assert.equal(await sidebar.getAttribute('role'), width <= 1100 ? 'dialog' : 'complementary');
      if (width <= 1100) {
        for (let index = 0; index < 14; index++) await page.keyboard.press('Tab');
        assert.equal(await sidebar.evaluate(element => element.contains(document.activeElement)), true);
      }
      if (width === 390) assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      if (width === 1366 || width === 390) await page.screenshot({ path: path.join(EVIDENCE, 'assistant-sidebar-' + width + '.png') });
      await sidebar.getByRole('button', { name: 'Close assistant sidebar', exact: true }).click();
      await sidebar.waitFor({ state: 'hidden' });
    }
    checks.push('Drawer fits 1366/1440/1920/900/390; overlay focus is contained; mobile has no document horizontal overflow');
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.getByRole('button', { name: 'Run Kernel', exact: true }).click();
    await page.locator('.topbar-util-btn').filter({ has: page.locator('svg') }).last().click();
    const consoleInput = page.getByRole('textbox', { name: 'QORE console command' });
    if (!await consoleInput.isVisible()) await page.locator('.topbar-util-btn').last().click();
    await consoleInput.waitFor();
    const command = async value => { await consoleInput.fill(value); await consoleInput.press('Enter'); };
    await command('clear'); await command('unitary');
    await page.getByText('Circuit unitary (8 × 8):', { exact: false }).waitFor();
    await command('statevector'); await page.getByText('Complex state amplitudes:', { exact: false }).waitFor();
    await command('qiskit --version'); await page.locator('.terminal-log-scroll').getByText('ui-fixture-version', { exact: false }).waitFor();
    const before = runCount; await command('az quantum execute'); await command('qsharp run');
    assert.equal(runCount, before, 'Unsupported cloud/Q# commands must not dispatch Aer');
    await command('cat another_file.py'); await page.getByText('File is not the active buffer:', { exact: false }).waitFor();
    checks.push('Terminal prints supplied unitary/amplitudes/versions; unsupported cloud/Q# never execute; cat rejects another file');

    await page.locator('#qore-assistant-toggle').click();
    await page.getByLabel('Ask QI Assistant').fill('Explain again');
    await page.getByRole('button', { name: 'Ask assistant', exact: true }).click();
    await sidebar.getByText('The active circuit prepares a three-qubit GHZ state.', { exact: true }).waitFor();
    assert.equal(assistantRequest.simulation_id, 'ui-fixture-run-1');
    await page.getByLabel('Ask QI Assistant').fill('open lab');
    await page.getByRole('button', { name: 'Ask assistant', exact: true }).click();
    await page.getByText('Done — open lab.', { exact: true }).waitFor();
    await page.locator('.lab-view-shell').waitFor();
    assert.equal(requested.some(url => url.includes('/api/auth/')), false);
    checks.push('QI command opens Lab without any authentication request');
    assert.deepEqual(runtimeErrors, []);
    assert.equal(consoleErrors.some(message => /same key|unique.*key/i.test(message)), false);
    checks.push('No browser runtime errors or duplicate-key errors');
    const report = { base: new URL(page.url()).origin, scope: 'Mocked UI contract checks; not live authentication or numerical backend verification', checks, runtimeErrors, passed: true };
    fs.writeFileSync(path.join(EVIDENCE, 'assistant-ui-check.json'), JSON.stringify(report, null, 2));
    fs.writeFileSync(path.join(EVIDENCE, 'assistant-ui-check.md'), '# Assistant UI verification\n\nAPI responses were explicitly mocked; real API acceptance is reported separately.\n\n' + checks.map(check => '- PASS: ' + check).join('\n') + '\n');
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
