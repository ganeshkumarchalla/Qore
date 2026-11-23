/* Mocked browser regression for graphite menus, editor and terminal. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { workspaceFixture } = require('./workspace-fixture.cjs');
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    const workspace = workspaceFixture();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const pathname = new URL(route.request().url()).pathname;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(
        pathname === '/api/health' ? { status: 'ok', ai_available: false, auth_required: false, storage: 'sqlite', versions: {}, limits: { max_qubits: 10 } } : []
      ) });
    });
    await page.goto(base);
    await page.getByRole('button', { name: 'Get Started', exact: true }).click();
    await page.locator('.monaco-editor').waitFor();
    for (const width of [1366, 900, 390]) {
      await page.setViewportSize({ width, height: 768 });
      const title = await page.locator('.editor-pane .pane-titlebar').evaluate(element => {
        const filename = element.querySelector('.pane-name');
        const metadata = element.querySelector('.pane-meta');
        const actions = element.querySelector('.pane-title-actions');
        const nameBox = filename.getBoundingClientRect();
        const metaBox = metadata.getBoundingClientRect();
        const actionsBox = actions.getBoundingClientRect();
        const barBox = element.getBoundingClientRect();
        return { nameRight: nameBox.right, metaLeft: metaBox.left, metaRight: metaBox.right,
          actionsLeft: actionsBox.left, barRight: barBox.right, nameTitle: filename.title,
          nameOverflow: getComputedStyle(filename).textOverflow };
      });
      assert(title.metaLeft - title.nameRight >= 6, `Filename and language need a visible gap at ${width}px`);
      assert(title.metaRight <= title.actionsLeft, `Metadata must not overlap actions at ${width}px`);
      assert(title.actionsLeft <= title.barRight, `Editor actions must fit at ${width}px`);
      assert.equal(title.nameTitle, 'my_first_qubits.py');
      assert.equal(title.nameOverflow, 'ellipsis');
    }
    await page.setViewportSize({ width: 1366, height: 768 });
    const fileRow = page.locator('.vs-file-row[tabindex="0"]').first();
    await fileRow.focus();
    assert.equal(await fileRow.locator('.vs-hover-tools').evaluate(element => getComputedStyle(element).display), 'flex',
      'Explorer file actions must appear on keyboard focus');
    for (const width of [1366, 900]) {
      await page.setViewportSize({ width, height: 768 });
      await page.getByRole('button', { name: 'File', exact: true }).click();
      const menu = page.getByRole('menu', { name: 'File' });
      await menu.waitFor();
      const visual = await menu.evaluate(element => {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return { right: box.right, width: box.width, background: style.backgroundImage,
          blur: style.backdropFilter, animation: style.animationName };
      });
      assert(visual.right <= width, 'File menu must fit the viewport');
      assert(visual.width >= 200, 'File menu must keep readable width');
      assert.match(visual.background, /rgba\(42, 42, 44, 0\.97\)/);
      assert.match(visual.blur, /blur\(26px\)/);
      assert.equal(visual.animation, 'none', 'Menu text should not fade through the Explorer');
      assert(await menu.getByRole('menuitem', { name: /Save file/ }).isEnabled());
      await page.keyboard.press('Escape');
    }
    await page.getByRole('button', { name: 'View', exact: true }).click();
    const view = page.getByRole('menu', { name: 'View' });
    assert(await view.getByRole('menuitem', { name: 'Simulation Lab' }).isVisible());
    assert(await view.getByRole('menuitem', { name: 'Transpiler Forge' }).isVisible());
    await page.keyboard.press('Escape');
    if (!await page.locator('.terminal-body').count()) {
      await page.getByTitle('Toggle Integrated Quantum Terminal (Ctrl+`)').click();
    }
    await page.locator('.terminal-body').waitFor();
    const palette = await page.evaluate(() => ({
      gate: getComputedStyle(document.querySelector('.gate-btn')).color,
      prompt: getComputedStyle(document.querySelector('.prompt-label')).color,
      terminal: getComputedStyle(document.querySelector('.terminal-body')).backgroundImage,
      editor: getComputedStyle(document.querySelector('.editor-wrapper')).backgroundImage,
    }));
    assert.equal(palette.gate, 'rgb(226, 223, 218)');
    assert.equal(palette.prompt, 'rgb(232, 229, 224)');
    assert.match(palette.terminal, /linear-gradient/);
    assert.match(palette.editor, /radial-gradient/);
    assert.deepEqual(errors, []);
    console.log('PASS: graphite menus, editor, gates and terminal; title spacing at 1366px, 900px and 390px');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
