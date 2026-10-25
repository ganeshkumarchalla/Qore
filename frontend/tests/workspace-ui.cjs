// Workspace UI contract acceptance with explicit per-account in-memory API mocks.
// Numerical simulation and database authorization are verified by backend tests.
const { chromium } = require('playwright');
const { workspaceFixture } = require('./workspace-fixture.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '../..'), EVIDENCE = path.join(ROOT, 'evidence');
fs.mkdirSync(EVIDENCE, { recursive: true });
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';
const wait = async predicate => {
  const start = Date.now();
  while (!predicate()) { if (Date.now() - start > 15000) throw new Error('Workspace fixture did not reach the expected state.'); await new Promise(resolve => setTimeout(resolve, 70)); }
};
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    page.setDefaultTimeout(15000);
    page.on('dialog', dialog => dialog.accept());
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const ownerA = 'c7f73659-f339-4cb5-9b31-3fb384279718', ownerB = 'e1acfeee-8456-4f5b-88ee-4f7604700701';
    let owner = ownerA, failWorkspaceReads = false;
    const stores = { [ownerA]: workspaceFixture(), [ownerB]: workspaceFixture() }, workspace = stores[ownerA];
    const parsed = { ir: { version: '1.0', num_qubits: 3, num_clbits: 3, global_phase: 0, operations: [] },
      metrics: { qubits: 3, clbits: 3, gate_count: 3, depth: 3, two_qubit_gate_count: 2, measurement_count: 3,
        barrier_count: 0, gate_types: {}, definition: 'UI contract fixture' }, source_hash: 'mock-workspace', warnings: [] };
    const handleRoute = async route => {
      if (failWorkspaceReads && new URL(route.request().url()).pathname.startsWith('/api/workspace') && route.request().method() === 'GET') {
        await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { message: 'Mock offline snapshot.' } }) }); return;
      }
      if (await stores[owner].handle(route)) return;
      const pathname = new URL(route.request().url()).pathname;
      const body = pathname === '/api/auth/session' ? { user: { id: owner, name: 'Workspace Member', email: 'member@example.test',
        avatarInitials: 'WM', role: 'Member', tier: 'Personal workspace' }, configured: true, required: true }
        : pathname === '/api/health' ? { status: 'ok', ai_available: false, versions: {}, limits: { max_qubits: 10 } }
        : pathname === '/api/parse' ? parsed : [];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    };
    await page.route('**/api/**', handleRoute);
    const ready = async (target = page) => { await target.getByRole('status', { name: 'Welcome to qubit' }).waitFor({ state: 'hidden' }); };
    const append = async (text, target = page) => { const input = target.locator('.monaco-editor textarea.inputarea').first(); await input.focus(); await target.keyboard.press('ControlOrMeta+End'); await target.keyboard.type('\n# ' + text); };
    const saved = async () => { await page.locator('.qore-workspace-save').getByText('Saved to your account', { exact: true }).waitFor(); };
    await page.goto(base); await ready();
    assert.equal(workspace.entries.length, 0);
    await page.getByRole('button', { name: 'Get Started', exact: true }).click();
    await wait(() => workspace.entries.filter(entry => entry.type === 'file').length === 1 && workspace.active);
    const first = workspace.entries.find(entry => entry.type === 'file'), id = first.id;
    assert.match(id, /^[0-9a-f-]{36}$/); assert(first.source.includes('QuantumCircuit(3, 3)'));
    await page.locator('.monaco-editor').first().waitFor(); await saved();
    await append('persisted edit'); await wait(() => workspace.entries.find(entry => entry.id === id).source.includes('persisted edit')); await saved();
    const editVersion = workspace.entries.find(entry => entry.id === id).version;
    await page.reload(); await ready(); await page.locator('.monaco-editor').first().waitFor();
    await append('after refresh'); await wait(() => workspace.entries.find(entry => entry.id === id).source.includes('after refresh')); await saved();
    assert(workspace.entries.find(entry => entry.id === id).version > editVersion); assert.equal(workspace.active, id);

    workspace.failWrites = true;
    await append('offline draft'); await page.locator('.qore-workspace-save.has-error').waitFor();
    assert(!workspace.entries.find(entry => entry.id === id).source.includes('offline draft'));
    // A large cloud workspace intentionally keeps no disposable file mirror.
    // Its durable outbox must remain usable even with the snapshot API offline.
    await page.evaluate(user => localStorage.setItem('qore_workspace_files:' + user, '[]'), ownerA);
    failWorkspaceReads = true;
    await page.reload(); await ready();
    await page.getByRole('button', { name: 'Open ' + first.path, exact: true }).click();
    await page.locator('.monaco-editor').first().waitFor();
    assert((await page.locator('.monaco-editor .view-lines').first().innerText()).replace(/\u00a0/g, ' ').includes('offline draft'));
    const outbox = await page.evaluate(user => JSON.parse(localStorage.getItem('qore_workspace_files:' + user + ':outbox')), ownerA);
    assert(outbox.entries.some(([, pending]) => pending.entry.source.includes('offline draft')));
    await page.locator('.qore-workspace-save.has-error').waitFor();
    workspace.failWrites = false; failWorkspaceReads = false;
    await page.getByRole('button', { name: 'Retry sync', exact: true }).click();
    await wait(() => workspace.entries.find(entry => entry.id === id).source.includes('offline draft')); await saved();

    workspace.editRemotely(id, '# remote tab edit');
    await append('conflicting local draft');
    await page.getByRole('button', { name: 'Keep draft as new file', exact: true }).waitFor();
    assert.equal(workspace.entries.find(entry => entry.id === id).source, '# remote tab edit');
    await page.getByRole('button', { name: 'Keep draft as new file', exact: true }).click();
    await wait(() => workspace.entries.some(entry => entry.id !== id && entry.source.includes('conflicting local draft')));
    const recovered = workspace.entries.find(entry => entry.id !== id && entry.type === 'file'); await saved();
    assert.equal(workspace.entries.find(entry => entry.id === id).source, '# remote tab edit');
    const remove = async file => {
      const row = page.getByRole('button', { name: 'Open ' + file.path, exact: true });
      await row.hover(); await page.getByTitle('Delete ' + file.name, { exact: true }).click();
      await wait(() => workspace.entries.find(entry => entry.id === file.id)?.deleted_at);
      await row.waitFor({ state: 'hidden' });
    };
    await remove(recovered);
    const deleted = workspace.entries.find(entry => entry.id === recovered.id);
    assert.equal(Date.parse(deleted.expires_at) - Date.parse(deleted.deleted_at), 48 * 3600000);
    await page.getByRole('button', { name: 'Undo last file deletion', exact: true }).click();
    await page.getByRole('button', { name: 'Open ' + recovered.path, exact: true }).waitFor();
    assert.equal(workspace.entries.find(entry => entry.id === recovered.id).deleted_at, null);
    await remove(recovered);
    await page.getByRole('button', { name: 'Open recently deleted files', exact: true }).click();
    await page.getByRole('button', { name: 'Restore ' + recovered.path, exact: true }).click();
    await wait(() => !workspace.entries.find(entry => entry.id === recovered.id).deleted_at);
    await page.getByRole('button', { name: 'Close recently deleted', exact: true }).click(); await saved();
    await remove(recovered);
    workspace.advance(48 * 3600000 + 1);
    await page.getByRole('button', { name: 'Open recently deleted files', exact: true }).click();
    await page.getByText('Nothing in Trash', { exact: true }).waitFor();
    assert(workspace.entries.find(entry => entry.id === id && !entry.deleted_at));
    await page.screenshot({ path: path.join(EVIDENCE, 'workspace-trash.png') });
    await page.getByRole('button', { name: 'Close recently deleted', exact: true }).click();
    owner = ownerB;
    await page.reload(); await ready(); await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Open ' + first.path, exact: true }).count(), 0);
    assert.equal(stores[ownerB].entries.length, 0);
    const malformed = JSON.stringify({ entries: { unexpected: 'unreadable draft metadata' }, activeFileId: 42 });
    await page.evaluate(({ user, malformed }) => {
      localStorage.setItem('qore_workspace_files:' + user + ':outbox', malformed);
      localStorage.setItem('qore_workspace_files:' + user + ':folderEntries', '{}');
    }, { user: ownerB, malformed });
    await page.reload(); await ready(); await page.getByRole('button', { name: 'Get Started', exact: true }).waitFor();
    const recovery = await page.evaluate(user => Object.keys(localStorage)
      .filter(key => key.startsWith('qore_workspace_files:' + user + ':unreadable'))
      .map(key => localStorage.getItem(key)), ownerB);
    assert(recovery.includes(malformed)); assert(recovery.includes('{}'));
    assert.equal(stores[ownerB].entries.length, 0); assert.deepEqual(errors, []);
    await page.reload(); await ready();
    await page.getByRole('button', { name: 'Get Started', exact: true }).click(); await saved();
    const tabOneFile = stores[ownerB].entries.find(entry => entry.type === 'file');
    await page.getByTitle('New File (in active folder)', { exact: true }).click();
    const fileName = page.getByPlaceholder('filename.py (or .qasm, .json, .md)', { exact: true });
    await fileName.fill('second.py'); await fileName.press('Enter');
    await wait(() => stores[ownerB].entries.filter(entry => entry.type === 'file').length === 2); await saved();
    const tabTwoFile = stores[ownerB].entries.find(entry => entry.type === 'file' && entry.id !== tabOneFile.id);
    const secondPage = await page.context().newPage(); secondPage.on('dialog', dialog => dialog.accept());
    secondPage.on('pageerror', error => errors.push(error.message));
    await secondPage.route('**/api/**', handleRoute); await secondPage.goto(base); await ready(secondPage);
    await page.getByRole('button', { name: 'Open ' + tabOneFile.path, exact: true }).click();
    await secondPage.getByRole('button', { name: 'Open ' + tabTwoFile.path, exact: true }).click();
    workspace.failWrites = false; stores[ownerB].failWrites = true;
    await append('tab one offline journal'); await page.locator('.qore-workspace-save.has-error').waitFor();
    await append('tab two offline journal', secondPage); await secondPage.locator('.qore-workspace-save.has-error').waitFor();
    await page.evaluate(user => localStorage.setItem('qore_workspace_files:' + user, '[]'), ownerB);
    failWorkspaceReads = true;
    await page.reload(); await ready(); await secondPage.reload(); await ready(secondPage);
    await page.getByRole('button', { name: 'Open ' + tabOneFile.path, exact: true }).click();
    await secondPage.getByRole('button', { name: 'Open ' + tabTwoFile.path, exact: true }).click();
    assert((await page.locator('.monaco-editor .view-lines').first().innerText()).replace(/\u00a0/g, ' ').includes('tab one offline journal'));
    assert((await secondPage.locator('.monaco-editor .view-lines').first().innerText()).replace(/\u00a0/g, ' ').includes('tab two offline journal'));
    failWorkspaceReads = false; stores[ownerB].failWrites = false;
    await page.getByRole('button', { name: 'Retry sync', exact: true }).click(); await saved();
    await wait(() => stores[ownerB].entries.find(entry => entry.id === tabOneFile.id).source.includes('tab one offline journal')
      && stores[ownerB].entries.find(entry => entry.id === tabTwoFile.id).source.includes('tab two offline journal'));
    await secondPage.close();
    const remainingJournals = await page.evaluate(user => Object.keys(localStorage).filter(key => key.startsWith('qore_workspace_files:' + user + ':outbox-journal:')), ownerB);
    assert.equal(remainingJournals.length, 0, 'Acknowledged immutable journals should release source recovery copies.');
    assert.deepEqual(errors, []);
    const report = { passed: true, base, scope: 'Explicit per-account mocked workspace API; not live database authorization', checks: [
      'Empty workspace creates no files; Get Started explicitly creates one stable UUID entry',
      'Debounced edits and active file survive refresh from the server snapshot',
      'Offline draft survives reload without a server mirror or snapshot connection; Retry sync saves it',
      '409 preserves newer cloud contents; recovery copy saves local draft under a separate UUID',
      'Confirmed soft deletion removes Explorer entry; Undo and Trash Restore recover it',
      'Trash expires after exactly 48 hours in the API fixture; active files remain',
      'Another verified account receives no prior files or drafts; no browser runtime errors',
      'Malformed JSON-shaped outbox and folder metadata preserve exact recovery copies without crashing hydration',
      'Independent offline tabs preserve different-file drafts through both refreshes; successful account sync cleans acknowledged journals' ] };
    fs.writeFileSync(path.join(EVIDENCE, 'workspace-ui-check.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
