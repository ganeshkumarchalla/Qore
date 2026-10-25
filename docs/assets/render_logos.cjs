/* Render attributed SVGs in a clean, headless browser, never a user profile. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('../../frontend/node_modules/playwright');
(async () => {
  const directory = path.join(__dirname, 'logos');
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  try {
    const page = await browser.newPage({ viewport: { width: 160, height: 160 }, deviceScaleFactor: 1 });
    for (const name of fs.readdirSync(directory).filter(name => name.endsWith('.svg'))) {
      const data = fs.readFileSync(path.join(directory, name)).toString('base64');
      await page.setContent(`<html><style>html,body{margin:0;width:160px;height:160px;background:transparent}img{position:absolute;left:16px;top:16px;width:128px;height:128px;object-fit:contain}</style><img src="data:image/svg+xml;base64,${data}" alt="">`);
      await page.locator('img').evaluate(async image => { await image.decode(); });
      await page.screenshot({ path: path.join(directory, name.replace('.svg', '.png')), omitBackground: true });
    }
    console.log('Rendered nine original brand marks with preserved aspect ratios.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
