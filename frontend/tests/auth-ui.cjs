/* Isolated email-auth UI contract. No live mail, account, or personal profile. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { workspaceFixture } = require('./workspace-fixture.cjs');
const evidence = path.resolve(__dirname, '../../evidence');
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    page.setDefaultTimeout(15000);
    const errors = [], requests = [], workspace = workspaceFixture();
    const profile = { id: 'auth-ui-member', name: 'UI Member', email: 'member@example.test', avatarInitials: 'UM', role: 'Member', tier: 'Personal workspace' };
    let user = null, confirmed = false;
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      if (await workspace.handle(route)) return;
      const request = route.request(), pathname = new URL(request.url()).pathname;
      requests.push(pathname);
      const reply = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
      if (pathname === '/api/auth/config') return reply(200, { configured: true, required: true, email_enabled: true });
      if (pathname === '/api/auth/session') return reply(200, { user, configured: true, required: true });
      if (pathname === '/api/auth/signup') return reply(200, { user: null, message: 'Check your email to confirm your account.' });
      if (pathname === '/api/auth/resend') return reply(200, { message: 'If this address has a pending account, a confirmation email has been sent.' });
      if (pathname === '/api/auth/signin') {
        if (!confirmed) return reply(401, { error: { code: 'email_confirmation_required', message: 'Confirm your email before signing in. You can resend the verification email.' } });
        user = profile; return reply(200, { user });
      }
      if (pathname === '/api/auth/signout') { user = null; return reply(200, { user: null }); }
      if (pathname === '/api/health') return reply(200, { status: 'ok', ai_available: false, versions: {}, limits: { max_qubits: 10 } });
      return reply(200, []);
    });
    await page.goto(base + '/#access_token=fixture-only&refresh_token=fixture-only&type=signup');
    await page.getByRole('status', { name: 'Welcome to qubit' }).waitFor({ state: 'hidden' });
    assert(!new URL(page.url()).hash.includes('token'));
    const dialog = page.getByRole('dialog', { name: 'Your QORE Account' });
    // Returning from a confirmation link opens the account dialog itself.
    await dialog.waitFor();
    await dialog.getByText('Sign in with your verified email and password.', { exact: true }).waitFor();
    assert.equal(await dialog.getByRole('button', { name: /google/i }).count(), 0);
    await dialog.getByRole('button', { name: 'Create account', exact: true }).click();
    await dialog.getByLabel('Your Name', { exact: true }).fill('UI Member');
    await dialog.getByLabel('Email Address', { exact: true }).fill(profile.email);
    assert.equal(await dialog.getByLabel('Password', { exact: true }).getAttribute('minlength'), '12');
    const password = 'ui-fixture-password-only';
    await dialog.getByLabel('Password', { exact: true }).fill(password);
    await dialog.locator('button[type="submit"]').click();
    await dialog.getByText('Check your email to confirm your account.', { exact: true }).waitFor();
    assert.equal(await dialog.getByLabel('Password', { exact: true }).inputValue(), '');
    await dialog.getByLabel('Password', { exact: true }).fill(password);
    await dialog.getByRole('button', { name: 'Sign In to QORE', exact: true }).click();
    await dialog.getByRole('alert').getByText(/Confirm your email/).waitFor();
    await dialog.getByRole('button', { name: 'Resend verification email', exact: true }).click();
    await dialog.getByText('If this address has a pending account, a confirmation email has been sent.', { exact: true }).waitFor();
    confirmed = true;
    await dialog.getByRole('button', { name: 'Sign In to QORE', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' });
    await page.getByRole('button', { name: 'Account', exact: true }).click();
    await dialog.getByRole('button', { name: 'Sign out', exact: true }).waitFor();
    assert.equal(requests.filter(value => value === '/api/auth/signout').length, 0, 'Opening an existing verified profile must not sign it out');
    assert.equal(await dialog.getByText(profile.email, { exact: true }).count(), 1);
    const stored = await page.evaluate(() => Object.values(localStorage).join('\n'));
    assert(!stored.includes(password));
    await dialog.getByRole('button', { name: 'Sign out', exact: true }).click();
    await dialog.getByRole('button', { name: 'Sign In to QORE', exact: true }).waitFor();
    assert.equal(requests.filter(value => value === '/api/auth/signout').length, 1);
    assert.deepEqual(errors, []);
    const report = { passed: true, scope: 'Mocked email authentication UI; does not prove real mail delivery', checks: ['No Google sign-in', 'Provider token fragment removed', 'Signup enforces 12 characters and clears password', 'Confirmation and generic resend feedback', 'Verified sign-in and profile reopening retain session', 'Sign-out clears profile', 'No password in browser storage', 'No runtime errors'] };
    fs.mkdirSync(evidence, { recursive: true });
    fs.writeFileSync(path.join(evidence, 'email-auth-ui-check.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
