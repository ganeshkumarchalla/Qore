/* Account-free Explorer contract: folders and files remain editable after refresh. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    page.setDefaultTimeout(20000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    await page.addInitScript(() => localStorage.setItem('qore_started', 'true'));
    await page.route('**/api/**', async route => {
      const request = route.request(), pathname = new URL(request.url()).pathname;
      const body = pathname === '/api/health'
        ? { status: 'ok', ai_available: false, auth_required: false, storage: 'sqlite', versions: { qiskit: 'fixture' }, limits: { max_qubits: 10 } }
        : pathname === '/api/parse'
          ? { ir: { version: '1.0', num_qubits: 1, num_clbits: 0, global_phase: 0, operations: [] }, metrics: { qubits: 1, clbits: 0, gate_count: 0, depth: 0, two_qubit_gate_count: 0, measurement_count: 0, barrier_count: 0, gate_types: {}, definition: 'fixture' }, source_hash: 'fixture', warnings: [] }
          : [];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(base);
    await page.locator('.monaco-editor').first().waitFor();

    await page.getByTitle('New Folder', { exact: true }).click();
    await page.getByPlaceholder('New folder name...').fill('algorithms');
    await page.getByPlaceholder('New folder name...').press('Enter');
    const folder = page.getByTitle('Folder: algorithms/');
    await folder.waitFor(); await folder.hover();
    await page.getByTitle('Rename Folder "algorithms"', { exact: true }).click();
    const rename = page.getByLabel('Rename folder algorithms');
    await rename.fill('quantum-algorithms'); await rename.press('Enter');

    const renamed = page.getByTitle('Folder: quantum-algorithms/');
    await renamed.waitFor(); await renamed.hover();
    await page.getByTitle('New File inside quantum-algorithms', { exact: true }).click();
    const create = page.getByPlaceholder('filename.py (or .qasm, .json, .md)');
    await create.fill('vqe.py'); await create.press('Enter');
    await page.getByRole('button', { name: 'Open quantum-algorithms/vqe.py', exact: true }).click();
    const editor = page.locator('.monaco-editor textarea.inputarea').first();
    await editor.focus(); await page.keyboard.type('from qiskit import QuantumCircuit');
    await page.waitForTimeout(800);

    await page.reload();
    await page.getByTitle('Folder: quantum-algorithms/').click();
    await page.getByRole('button', { name: 'Open quantum-algorithms/vqe.py', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Open quantum-algorithms/vqe.py', exact: true }).click();
    await page.locator('.monaco-editor .view-lines').getByText(/QuantumCircuit/).waitFor();
    assert.equal(await page.getByTitle('Folder: quantum-algorithms/').count(), 1);
    assert.equal((await page.locator('.vscode-sidebar').count()), 1);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: true, checks: ['Folder create and rename', 'File create and edit', 'Path and source persist after refresh', 'Single Explorer instance'] }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
