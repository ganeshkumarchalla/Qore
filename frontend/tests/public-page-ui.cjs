/* Real public HTML/assets/SEO check; no authentication or API mocks. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '../..');
const EVIDENCE = path.join(ROOT, 'evidence');
fs.mkdirSync(EVIDENCE, { recursive: true });
const base = process.argv[2] || process.env.QORE_TEST_URL || 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const response = await page.goto(base + '/about.html');
    assert.equal(response.status(), 200);
    const title = await page.title();
    assert.match(title, /QORE/);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute('href');
    const canonicalUrl = new URL(canonical);
    assert.equal(canonicalUrl.protocol, 'https:');
    assert.equal(canonicalUrl.pathname, '/about.html');
    const description = await page.locator('meta[name="description"]').getAttribute('content');
    assert(description.length >= 50);
    const robots = await page.locator('meta[name="robots"]').getAttribute('content');
    assert(!/noindex/i.test(robots));
    const sitemapResponse = await page.request.get(base + '/sitemap.xml');
    assert.equal(sitemapResponse.status(), 200);
    const sitemap = await sitemapResponse.text();
    assert(sitemap.includes('<loc>' + canonical + '</loc>'), 'Sitemap must contain the exact About canonical URL');
    const viewports = [];
    for (const [name, width, height] of [['desktop', 1366, 768], ['mobile', 390, 844]]) {
      await page.setViewportSize({ width, height });
      const dimensions = await page.evaluate(() => ({ viewport: innerWidth, root: document.documentElement.scrollWidth,
        body: document.body.scrollWidth, headings: document.querySelectorAll('h1').length }));
      assert(dimensions.root <= width && dimensions.body <= width, name + ' must not overflow horizontally');
      assert.equal(dimensions.headings, 1);
      await page.screenshot({ path: path.join(EVIDENCE, 'about-' + name + '.png'), fullPage: true });
      viewports.push({ name, ...dimensions });
    }
    assert.deepEqual(errors, []);
    const report = { passed: true, scope: 'Real public production HTML and assets; no API mocks',
      base, title, canonical, descriptionLength: description.length, robots, sitemapCanonicalMatch: true,
      viewports, runtimeErrors: errors };
    fs.writeFileSync(path.join(EVIDENCE, 'public-page-ui-check.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
