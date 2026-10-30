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
    page.on('pageerror', error => runtimeErrors.push(error.stack || error.message));
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
      bloch_vectors: [0, 1, 2].map(qubit => ({ qubit, x: 0, y: 0, z: 0, theta: 0, phi: 0, purity: 0.5, is_pure: false, direction_defined: false, azimuth_defined: false })),
    };
    let source = '', assistantRequest, runCount = 0, parseCount = 0;
    let holdNextSimulation = false, releaseSimulation;
    let holdNextAssistant = false, releaseAssistant;
    const workspace = workspaceFixture();
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const request = route.request(), pathname = new URL(request.url()).pathname;
      let body = {};
      if (pathname === '/api/health') body = { status: 'ok', ai_available: true, versions: { qiskit: 'ui-fixture-version' }, limits: { max_qubits: 10 } };
      else if (pathname === '/api/capabilities') body = {
        languages: [
          { id: 'qiskit-circuit-python', label: 'Qiskit circuit-building Python', execution: 'bounded_ast_interpreter', arbitrary_python: false },
          { id: 'openqasm-2', label: 'OpenQASM 2.0', execution: 'qiskit_qasm2_parser', arbitrary_python: false },
        ],
        modules: { qiskit: 'QuantumCircuit', qiskit_aer: 'AerSimulator', math: 'bounded numeric functions', numpy: 'bounded numeric functions' },
        gates: { h: { parameters: 0, qubits: 1 }, cx: { parameters: 0, qubits: 2 }, ccz: { parameters: 0, qubits: 3 } },
        circuit_methods: ['barrier', 'measure'], workflows: ['parse and validate', 'shot simulation', 'Forge transpilation and equivalence'],
        simulation_methods: ['statevector', 'matrix_product_state', 'stabilizer'], limits: { max_qubits: 10, max_shots: 100000 },
        safety_boundary: 'Circuit source is parsed and interpreted; arbitrary host execution is unavailable.',
      };
      else if (pathname === '/api/projects' || pathname === '/api/experiments') body = [];
      else if (pathname === '/api/parse') { parseCount++; source = request.postDataJSON().source; body = parsed; }
      else if (pathname === '/api/assistant') {
        assistantRequest = request.postDataJSON();
        if (holdNextAssistant) {
          holdNextAssistant = false;
          await new Promise(resolve => { releaseAssistant = resolve; });
        }
        body = { available: true, answer: 'The active circuit prepares a three-qubit GHZ state.', model: 'ui-fixture-model' };
      } else if (pathname === '/api/simulate') {
        runCount++;
        if (runCount === 2) {
          await route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({
            error: { code: 'unsupported_dynamic_circuit', message: 'Measurements must be terminal; no quantum gates may follow the first measurement.', details: { line: 16, column: 1 } },
          }) });
          return;
        }
        if (holdNextSimulation) await new Promise(resolve => { releaseSimulation = resolve; });
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
    assert.equal(parseCount, 0, 'Opening a file must not submit a background parse job');
    checks.push('Get Started opens a working local Monaco editor without automatic parsing; exactly one Explorer');

    const paletteTrigger = page.getByTitle('Command Palette (Ctrl+K)', { exact: true });
    await paletteTrigger.click();
    const palette = page.getByRole('dialog', { name: 'Command Palette' });
    await palette.waitFor();
    const searchCommands = page.getByRole('combobox', { name: 'Search commands' });
    await searchCommands.fill('View: Open Simulation Diagnostics');
    await searchCommands.press('Tab');
    assert.equal(await searchCommands.evaluate(element => document.activeElement === element), true,
      'Tab must remain inside the command palette');
    await searchCommands.press('Escape');
    await palette.waitFor({ state: 'hidden' });
    assert.equal(await paletteTrigger.evaluate(element => document.activeElement === element), true,
      'Escape must restore focus to the palette opener');
    await paletteTrigger.click();
    await searchCommands.fill('View: Open Simulation Diagnostics');
    await page.waitForFunction(() => {
      const options = document.querySelectorAll('#qore-command-list [role="option"]');
      return options.length === 1 && options[0].getAttribute('aria-selected') === 'true';
    });
    await searchCommands.press('Enter');
    await palette.waitFor({ state: 'hidden' });
    await page.locator('.lab-view-shell').waitFor();
    await page.getByRole('heading', { name: 'No Simulation Results' }).waitFor();
    await page.getByRole('button', { name: 'Circuit Editor', exact: true }).click();
    checks.push('Command palette contains keyboard focus, restores focus on Escape, and runs navigation commands');

    await page.locator('#qore-assistant-toggle').click();
    const sidebar = page.locator('#qore-assistant-sidebar'); await sidebar.waitFor();
    assert.equal(await page.locator('.activity-bar').getByRole('button', { name: 'Assistant', exact: true }).count(), 0);
    await page.getByLabel('Ask QORE Intelligence').fill('Explain the active circuit');
    const composerButton = await page.getByRole('button', { name: 'Ask assistant', exact: true }).boundingBox();
    const assistantViewport = await sidebar.locator('.qore-assistant-scroll').boundingBox();
        assert(composerButton && assistantViewport && composerButton.y + composerButton.height <= assistantViewport.y + assistantViewport.height,
      'The send control must be visible without scrolling on a 1366 × 768 laptop');
    await page.getByRole('button', { name: 'Ask assistant', exact: true }).click();
    await sidebar.getByText('The active circuit prepares a three-qubit GHZ state.', { exact: true }).waitFor();
    await sidebar.getByRole('heading', { name: 'QORE Intelligence', exact: true }).waitFor();
    assert.equal(await sidebar.getByText('ui-fixture-model', { exact: true }).count(), 0, 'Provider identifiers must not appear in the assistant interface');
    assert.match(assistantRequest.source, /QuantumCircuit/);
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
    await page.getByRole('button', { name: 'Run Kernel', exact: true }).evaluate(button => { button.click(); button.click(); });
    await page.locator('.workbench-banner.notice').getByText('Simulation complete', { exact: false }).waitFor();
    assert.equal(runCount, 1, 'A rapid repeated Run click must dispatch only one quantum job');
    await page.getByRole('heading', { name: 'Measurement outcome orbital shells' }).waitFor();
    await page.getByText('SELECTED MEASUREMENT OUTCOME', { exact: true }).waitFor();
    await page.getByText('Phase is unavailable for partial measurement or circuits beyond the statevector display limit.', { exact: false }).waitFor();
    await page.getByText('Accessible state-world data', { exact: true }).click();
    await page.getByRole('cell', { name: 'c = 000', exact: true }).waitFor();
    checks.push('State World labels classical outcomes and withholds phase when no complete amplitude map is available');
    await page.getByRole('button', { name: 'Bloch Spheres (3)', exact: true }).click();
    await page.getByText('Undefined (|r| = 0)', { exact: true }).first().waitFor();
    const focusedSphere = page.locator('.bloch-svg-wrap');
    const xAxisBefore = await focusedSphere.locator('svg line').nth(1).getAttribute('x2');
    const sphereBounds = await focusedSphere.boundingBox();
    await page.mouse.move(sphereBounds.x + sphereBounds.width / 2, sphereBounds.y + sphereBounds.height / 2);
    await page.mouse.down();
    await page.mouse.move(sphereBounds.x + sphereBounds.width / 2 + 65, sphereBounds.y + sphereBounds.height / 2 + 12);
    await page.mouse.up();
    assert.notEqual(await focusedSphere.locator('svg line').nth(1).getAttribute('x2'), xAxisBefore,
      'Pointer drag must rotate the Bloch camera');
    await page.getByRole('button', { name: 'All Qubits (3)', exact: true }).click();
    assert.equal(await page.locator('.bloch-grid-gallery .bloch-grid-svg').count(), 3);
    assert.equal(await page.locator('.bloch-grid-gallery .bloch-grid-svg').first().locator('line').count(), 4,
      'Each qubit must show three projected axes and its state vector');
    assert.equal(await page.locator('.bloch-grid-gallery').getByText('θ: undefined').count(), 3,
      'A zero Bloch vector must not claim a physical direction');
    await page.locator('.bloch-viewer-card').screenshot({ path: path.join(EVIDENCE, 'bloch-all-qubits-1366.png') });
    checks.push('Every qubit shares the 3D Bloch stage with XYZ axes; maximally mixed states have undefined direction');
    await page.getByRole('button', { name: 'Unitary Matrix (U)', exact: true }).click();
    assert.match(await page.locator('.unitary-matrix-table tbody tr').nth(7).locator('td').first().getAttribute('title'),
      /^⟨111\|U\|000⟩:/, 'Matrix tooltip must use the same row/column convention as the selected cell');
    checks.push('Unitary cell tooltips use ⟨row|U|column⟩ basis ordering');
    await page.locator('.topbar-util-btn').filter({ has: page.locator('svg') }).last().click();
    const consoleInput = page.getByRole('textbox', { name: 'QORE console command' });
    if (!await consoleInput.isVisible()) await page.locator('.topbar-util-btn').last().click();
    await consoleInput.waitFor();
    const command = async value => { await consoleInput.fill(value); await consoleInput.press('Enter'); };
    await command('clear'); await command('parse');
    await page.waitForFunction(() => document.body.textContent.includes('Parsed circuit successfully into QORE-IR.'));
    assert.equal(parseCount, 1, 'The explicit terminal parse command must submit exactly one parse job');
    await command('unitary');
    await page.getByText('Circuit unitary (8 × 8):', { exact: false }).waitFor();
    await command('statevector'); await page.getByText('Complex state amplitudes:', { exact: false }).waitFor();
    await command('qiskit --version'); await page.locator('.terminal-log-scroll').getByText('ui-fixture-version', { exact: false }).waitFor();
    await command('qiskit gates'); await page.locator('.terminal-log-scroll').getByText('"ccz"', { exact: false }).waitFor();
    await command('qiskit modules'); await page.locator('.terminal-log-scroll').getByText('AerSimulator', { exact: false }).waitFor();
    await command('qiskit bloch'); await page.locator('.terminal-log-scroll').getByText('q[0] x=0.00000000', { exact: false }).waitFor();
    await page.locator('.terminal-log-scroll').getByText('theta=undefined phi=undefined', { exact: false }).waitFor();
    await command('qiskit ideal'); await page.locator('.terminal-log-scroll').getByText('Ideal reference probabilities:', { exact: false }).waitFor();
    await command('qiskit bitorder'); await page.locator('.terminal-log-scroll').getByText('UI fixture ordering', { exact: false }).waitFor();
    await command('tree'); await page.locator('.terminal-log-scroll .term-pre').filter({ hasText: '└─ my_first_qubits.py' }).waitFor();
    const before = runCount; await command('az quantum execute'); await command('qsharp run');
    assert.equal(runCount, before, 'Unsupported cloud/Q# commands must not dispatch Aer');
    await command('cat another_file.py'); await page.getByText('Workspace file not found:', { exact: false }).waitFor();
    checks.push('Rapid Run clicks dispatch once; terminal executes capabilities, Bloch, ideal, bit-order and workspace-tree commands; unsupported cloud/Q# never execute');

    await page.locator('#qore-assistant-toggle').click();
    await page.getByLabel('Ask QORE Intelligence').fill('Explain again');
    await page.getByRole('button', { name: 'Ask assistant', exact: true }).click();
    await sidebar.getByText('The active circuit prepares a three-qubit GHZ state.', { exact: true }).waitFor();
    assert.equal(assistantRequest.simulation_id, 'ui-fixture-run-1');
    await page.waitForFunction(() => !document.querySelector('#assistant-question')?.disabled);
    holdNextAssistant = true;
    const delayedAssistant = page.waitForRequest(request => request.url().includes('/api/assistant') && request.method() === 'POST');
    await page.getByLabel('Ask QORE Intelligence').fill('Explain this draft');
    await page.getByRole('button', { name: 'Ask assistant', exact: true }).click();
    await delayedAssistant;
    await page.locator('.monaco-editor textarea.inputarea').first().focus();
    await page.keyboard.type('\n# edited before the assistant responded');
    await page.waitForFunction(() => !document.querySelector('#assistant-question')?.disabled);
    assert(releaseAssistant, 'The mocked assistant response must be held while source changes');
    const assistantResponse = page.waitForResponse(response => response.url().includes('/api/assistant'));
    releaseAssistant();
    await assistantResponse;
    assert.equal(await sidebar.getByText('The active circuit prepares a three-qubit GHZ state.', { exact: true }).count(), 0,
      'An answer for older source must not appear beside the edited draft');
    checks.push('QORE Intelligence discards responses when the active source changes');
    await page.getByLabel('Ask QORE Intelligence').fill('open lab');
    await page.getByRole('button', { name: 'Ask assistant', exact: true }).click();
    await page.locator('.lab-view-shell').waitFor();
    assert.equal(requested.some(url => url.includes('/api/auth/')), false);
    checks.push('QORE Intelligence command opens Lab without any authentication request');

    await page.getByRole('button', { name: 'Run Kernel', exact: true }).click();
    await page.locator('.terminal-log-scroll').getByText('Measurements must be terminal; no quantum gates may follow the first measurement.', { exact: false }).waitFor();
    assert(await page.locator('.vscode-terminal-dock').isVisible(), 'Execution errors must open the terminal');
    assert.equal(await page.locator('.workbench-banner.error').count(), 0, 'Execution errors must not render outside the terminal');
    checks.push('Execution errors appear only in the automatically opened terminal');
    await page.getByRole('button', { name: 'Circuit Editor', exact: true }).click();
    holdNextSimulation = true;
    const delayedRequest = page.waitForRequest(request => request.url().includes('/api/simulate') && request.method() === 'POST');
    await command('run');
    await delayedRequest;
    const editor = page.locator('.monaco-editor textarea.inputarea').first();
    await editor.focus();
    await page.keyboard.type('\n# changed during the pending simulation');
    await command('cat');
    await page.locator('.terminal-log-scroll .term-pre').filter({ hasText: 'changed during the pending simulation' }).last().waitFor();
    assert(releaseSimulation, 'The mocked simulation response must be held while the source changes');
    releaseSimulation();
    await page.getByRole('button', { name: 'Run Kernel', exact: true }).waitFor();
    await command('source-hash');
    await page.locator('.terminal-log-scroll').getByText('Parse or run the active source to calculate its hash.', { exact: true }).waitFor();
    checks.push('A simulation response for edited source is discarded instead of publishing stale results');
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
