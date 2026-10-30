/* Browser contract: long Forge candidates remain fully reachable on a laptop. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { workspaceFixture } = require('./workspace-fixture.cjs');

const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    page.setDefaultTimeout(20000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => localStorage.setItem('qore_started', 'true'));

    const workspace = workspaceFixture();
    const gates = Array.from({ length: 32 }, (_, i) => ({
      name: i % 4 === 0 ? 'cx' : 'h', qubits: i % 4 === 0 ? [0, 1] : [i % 4], clbits: [], params: [],
    }));
    const ir = { version: '1.0', num_qubits: 4, num_clbits: 0, global_phase: 0, operations: gates };
    const metrics = { qubits: 4, clbits: 0, gate_count: gates.length, depth: gates.length,
      two_qubit_gate_count: 8, measurement_count: 0, barrier_count: 0,
      gate_types: { h: 24, cx: 8 }, definition: 'Long circuit UI fixture' };
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const pathname = new URL(route.request().url()).pathname;
      let body = {};
      if (pathname === '/api/health') body = { status: 'ok', ai_available: false,
        versions: { qiskit: 'fixture' }, limits: { max_qubits: 10 } };
      else if (pathname === '/api/projects' || pathname === '/api/experiments') body = [];
      else if (pathname === '/api/optimize') body = {
        id: 'forge-scroll-fixture', kind: 'optimization', created_at: '2026-10-30T00:00:00Z',
        source: route.request().postDataJSON().source, source_hash: 'fixture-hash',
        original: { ir, metrics }, candidate: { ir, metrics, source: 'from qiskit import QuantumCircuit' },
        settings: { level: 2 }, differences: { gate_count: { original: 32, candidate: 32, absolute: 0, relative_percent: 0 } },
        validation: { status: 'validated', method: 'UI fixture', details: 'Long-circuit viewport only' },
        explanation: 'UI fixture', versions: { qiskit: 'fixture' }, warnings: [],
      };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });

    await page.goto(base);
    await page.getByRole('button', { name: 'Get Started', exact: true }).click();
    await page.locator('.monaco-editor').first().waitFor();
    await page.getByTitle('Quantum execution options').click();
    await page.getByRole('button', { name: /Transpile & Optimize/ }).click();
    const viewport = page.getByRole('region', { name: /Candidate circuit diagram/ });
    await viewport.waitFor();
    const candidateBounds = await viewport.boundingBox();
    const workbenchBounds = await page.locator('.workbench-body').boundingBox();
    assert(candidateBounds && workbenchBounds &&
      candidateBounds.x >= workbenchBounds.x - 1 &&
      candidateBounds.x + candidateBounds.width <= workbenchBounds.x + workbenchBounds.width + 1,
      'The candidate scroll area must fit inside the workbench instead of overflowing behind its edge');
    const initial = await viewport.evaluate(element => ({
      clientWidth: element.clientWidth, scrollWidth: element.scrollWidth, scrollLeft: element.scrollLeft,
      svgWidth: element.querySelector('svg')?.getBoundingClientRect().width,
    }));
    assert(initial.scrollWidth > initial.clientWidth + 200,
      `Candidate needs a local horizontal scroll area: ${JSON.stringify(initial)}`);

    await viewport.focus();
    for (let i = 0; i < 8; i++) await viewport.press('ArrowRight');
    await page.waitForFunction(() => document.querySelector('.candidate .forge-circuit-viewport')?.scrollLeft > 0);
    await viewport.evaluate(element => { element.scrollLeft = element.scrollWidth; });
    const end = await viewport.evaluate(element => {
      const bounds = element.getBoundingClientRect();
      const last = element.querySelector('.circuit-gate-group:last-child')?.getBoundingClientRect();
      return { scrollLeft: element.scrollLeft, maxScroll: element.scrollWidth - element.clientWidth,
        viewportRight: bounds.right, lastRight: last?.right, lastLeft: last?.left };
    });
    assert(end.scrollLeft >= end.maxScroll - 2, `Candidate did not reach its right edge: ${JSON.stringify(end)}`);
    assert(end.lastLeft < end.viewportRight && end.lastRight <= end.viewportRight,
      `Rightmost candidate gate is still clipped: ${JSON.stringify(end)}`);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: true, checks: ['Candidate fits inside the workbench at 1366×768',
      'Candidate has a local horizontal scroll area at 1366×768',
      'Keyboard scroll reaches further gates', 'Last gate is visible after scrolling to the right'] }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
