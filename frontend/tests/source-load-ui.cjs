/* Mocked browser regression: a late project or snapshot response cannot replace newer editor text. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { workspaceFixture } = require('./workspace-fixture.cjs');
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    page.setDefaultTimeout(20000);
    const runtimeErrors = [];
    page.on('pageerror', error => runtimeErrors.push(error.message));
    await page.addInitScript(() => localStorage.setItem('qore_started', 'true'));
    const workspace = workspaceFixture();
    let releaseProject, releaseSnapshot, holdSnapshot = true;
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const pathname = new URL(route.request().url()).pathname;
      let body = [];
      if (pathname === '/api/health') body = { status: 'ok', ai_available: false, auth_required: false,
        storage: 'sqlite', versions: { qiskit: 'fixture' }, limits: { max_qubits: 10 } };
      else if (pathname === '/api/projects') body = [{ id: 'old-project', name: 'legacy-project', source: '# server project' }];
      else if (pathname === '/api/experiments') body = [{ id: 'old-snapshot', name: 'legacy snapshot',
        source_hash: 'fixture-hash', created_at: '2026-10-25T08:00:00Z' }];
      else if (pathname === '/api/projects/old-project') {
        await new Promise(resolve => { releaseProject = resolve; });
        body = { id: 'old-project', name: 'legacy-project', source: '# server project' };
      } else if (pathname === '/api/experiments/old-snapshot') {
        if (holdSnapshot) {
          await new Promise(resolve => { releaseSnapshot = resolve; });
          holdSnapshot = false;
        }
        body = { id: 'old-snapshot', name: 'legacy snapshot', source: '# server snapshot',
          source_hash: 'fixture-hash', created_at: '2026-10-25T08:00:00Z' };
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(base);
    await page.getByRole('button', { name: 'Create blank file', exact: true }).click();
    const editor = page.locator('.monaco-editor textarea.inputarea').first();
    await editor.waitFor();
    const projectRequest = page.waitForRequest(request => request.url().endsWith('/api/projects/old-project'));
    await page.locator('.vs-file-row').filter({ hasText: 'legacy-project.py' }).click();
    await projectRequest;
    assert(releaseProject, 'Project response must be held during the edit');
    await editor.focus();
    await page.keyboard.type('# newer editor text');
    releaseProject();
    await page.getByRole('button', { name: 'Opening project...' }).waitFor({ state: 'hidden' });
    await page.locator('.topbar-util-btn').last().click();
    const terminal = page.getByRole('textbox', { name: 'QORE console command' });
    await terminal.fill('cat'); await terminal.press('Enter');
    await page.locator('.terminal-log-scroll .term-pre').filter({ hasText: '# newer editor text' }).last().waitFor();
    assert.equal(await page.locator('.terminal-log-scroll .term-pre').filter({ hasText: '# server project' }).count(), 0);

    await page.locator('.vs-section-header').filter({ hasText: 'EXPERIMENT SNAPSHOTS' }).click();
    const snapshotRequest = page.waitForRequest(request => request.url().endsWith('/api/experiments/old-snapshot'));
    await page.locator('.vs-history-item').filter({ hasText: 'legacy snapshot' }).click();
    await snapshotRequest;
    assert(releaseSnapshot, 'Snapshot response must be held during the edit');
    await editor.focus();
    await page.keyboard.type('\n# second newer edit');
    releaseSnapshot();
    await page.getByRole('button', { name: 'Opening snapshot in editor...' }).waitFor({ state: 'hidden' });
    await terminal.fill('cat'); await terminal.press('Enter');
    await page.locator('.terminal-log-scroll .term-pre').filter({ hasText: '# second newer edit' }).last().waitFor();
    assert.equal(await page.locator('.terminal-log-scroll .term-pre').filter({ hasText: '# server snapshot' }).count(), 0);

    const workspaceFiles = () => page.evaluate(() => JSON.parse(localStorage.getItem('qore_workspace_files') || '[]'));
    const original = (await workspaceFiles()).find(entry => entry.path === 'circuits/untitled.py');
    assert(original, 'Original workspace file must exist');
    const originalSource = original.source;
    await page.getByRole('button', { name: 'History', exact: true }).click();
    await page.locator('.experiment-item').filter({ hasText: 'legacy snapshot' }).click();
    await page.getByRole('button', { name: 'Copy to Editable Draft', exact: true }).click();
    await editor.focus();
    await page.keyboard.type('\n# edit to detached draft');
    assert.equal((await workspaceFiles()).find(entry => entry.id === original.id).source, originalSource,
      'Editing a copied snapshot must not overwrite the previously active workspace file');
    assert.deepEqual(runtimeErrors, []);
    console.log(JSON.stringify({ passed: true, checks: [
      'Late project response preserves newer editor text',
      'Late experiment response preserves newer editor text',
      'Editing a snapshot draft does not modify the previous workspace file',
      'No browser runtime errors',
    ] }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
