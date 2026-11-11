// Proportionate checks for the visual prototypes: every screen renders without
// page or console errors, the in-concept navigation reaches all three screens,
// one interaction per concept responds, and nothing scrolls sideways at 390px.
// Usage: node scripts/verify.mjs   (dev or preview server must be running)
import { chromium } from 'playwright';

const BASE = process.env.LAB_URL || 'http://127.0.0.1:5190';
const CHROME =
  process.env.CHROME_PATH ||
  `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
const ids = ['census', 'instrument', 'trace', 'cells', 'screening', 'inspect', 'continual', 'assurance', 'argument', 'signal', 'provenance', 'proof', 'engine', 'terrain', 'notebook'];
const results = [];
const ok = (name, pass, detail = '') => results.push({ name, pass, detail });

const browser = await chromium.launch({ executablePath: CHROME, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));

for (const p of ['#/', '#/board']) {
  await page.goto(`${BASE}/${p}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('img', { timeout: 8000 }).catch(() => {});
  const imgs = await page.$$eval('img', (els) => els.length);
  ok(`${p} renders`, imgs > 0, `${imgs} images`);
}
const broken = await page.evaluate(async () => {
  const srcs = [...document.querySelectorAll('img')].map((i) => i.getAttribute('src'));
  const bad = [];
  for (const s of srcs) if (!(await fetch(s)).ok) bad.push(s);
  return bad;
});
ok('board images resolve', broken.length === 0, broken.join(', '));

for (const id of ids) {
  for (const screen of ['workspace', 'results']) {
    await page.goto(`${BASE}/#/${id}/landing`, { waitUntil: 'networkidle' });
    await page.waitForSelector(`a[href="#/${id}/${screen}"]`, { timeout: 8000 }).catch(() => {});
    const link = page.locator(`a[href="#/${id}/${screen}"]`).first();
    const has = (await link.count()) > 0;
    if (has) {
      await link.click({ force: true }).catch(async () => page.goto(`${BASE}/#/${id}/${screen}`));
      await page.waitForTimeout(700);
    }
    ok(`${id}: landing links to ${screen}`, has && page.url().endsWith(`#/${id}/${screen}`));
  }
}

const interactions = {
  census: async () => {
    await page.goto(`${BASE}/#/census/workspace`);
    await page.getByRole('tab', { name: 'Regression' }).click();
    return (await page.locator('.cn-index li').count()) === 2;
  },
  instrument: async () => {
    await page.goto(`${BASE}/#/instrument/landing`);
    await page.getByRole('button', { name: /TEXT/ }).click();
    return (await page.locator('.in-display-capname').textContent()) === 'Text';
  },
  trace: async () => {
    await page.goto(`${BASE}/#/trace/results`);
    await page.waitForTimeout(800);
    await page.getByRole('tab', { name: /Target imbalance/ }).click();
    await page.waitForTimeout(400);
    return (await page.locator('.tr-track').count()) === 2;
  },
  cells: async () => {
    await page.goto(`${BASE}/#/cells/results`);
    await page.getByRole('button', { name: /Numeric outlier/ }).click();
    return (await page.locator('.ce-finding.is-open .ce-hours').count()) === 1;
  },
  screening: async () => {
    await page.goto(`${BASE}/#/screening/landing`);
    await page.locator('.sc-ticket-main').click();
    return (await page.locator('.sc-ticket-menu a').count()) === 4;
  },
  inspect: async () => {
    await page.goto(`${BASE}/#/inspect/results`);
    await page.getByRole('tab', { name: /Numeric outlier/ }).click();
    return (await page.locator('.ins-box').count()) === 1;
  },
  continual: async () => {
    await page.goto(`${BASE}/#/continual/workspace`);
    await page.locator('.ct-li', { hasText: 'German Credit' }).first().click();
    return (await page.locator('.ct-detail h2').textContent()) === 'German Credit';
  },
  assurance: async () => {
    await page.goto(`${BASE}/#/assurance/results`);
    await page.getByRole('button', { name: /Target imbalance/ }).click();
    return (await page.locator('.as-split').count()) === 1;
  },
  argument: async () => {
    await page.goto(`${BASE}/#/argument/landing`);
    await page.locator('.ar-hero').getByRole('radio', { name: /Leakage/ }).click();
    await page.waitForTimeout(1200);
    return (await page.locator('.ar-hero-read b').textContent()) === '49';
  },
  signal: async () => {
    await page.goto(`${BASE}/#/signal/workspace`);
    await page.waitForTimeout(400);
    await page.keyboard.press('Meta+k');
    return (await page.locator('.sg-overlay .sg-palette').count()) === 1;
  },
  provenance: async () => {
    await page.goto(`${BASE}/#/provenance/results`);
    await page.getByRole('tab', { name: /Target imbalance/ }).click();
    return (await page.getByRole('tab', { name: /Target imbalance/ }).getAttribute('aria-selected')) === 'true';
  },
  proof: async () => {
    await page.goto(`${BASE}/#/proof/landing`);
    await page.getByRole('button', { name: 'German Credit', exact: true }).click();
    return (await page.locator('.pf-calc-out b').textContent()) === '70.00%';
  },
  engine: async () => {
    await page.goto(`${BASE}/#/engine/workspace`);
    await page.locator('.en-row', { hasText: 'German Credit' }).click();
    return (await page.locator('.en-con-top h1').textContent()) === 'German Credit';
  },
  terrain: async () => {
    await page.goto(`${BASE}/#/terrain/results`);
    await page.locator('.tn-find', { hasText: 'Target imbalance' }).click();
    return (await page.locator('.tn-find-body h2').textContent()).includes('dominated by one class');
  },
  notebook: async () => {
    // The hero notebook types and runs four cells; the last prints the exported report.
    await page.goto(`${BASE}/#/notebook/landing`);
    await page.waitForSelector('.nb-hero-nb .nb-out-file', { timeout: 30000 });
    return (await page.locator('.nb-hero-nb .nb-out').count()) === 4;
  },
};
for (const [id, fn] of Object.entries(interactions)) ok(`${id}: interaction responds`, await fn().catch(() => false));

const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
const mp = await mobile.newPage();
for (const id of ids)
  for (const s of ['landing', 'workspace', 'results']) {
    await mp.goto(`${BASE}/#/${id}/${s}`, { waitUntil: 'networkidle' });
    await mp.waitForTimeout(500);
    const [sw, iw] = await mp.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    ok(`${id}/${s}: no sideways scroll at 390px`, sw <= iw + 1, `${sw} vs ${iw}`);
  }

ok('no page or console errors', errors.length === 0, [...new Set(errors)].slice(0, 5).join(' | '));
await browser.close();
for (const r of results) console.log(`${r.pass ? 'PASS' : 'FAIL'}  ${r.name}${r.detail && !r.pass ? `  (${r.detail})` : ''}`);
const failed = results.filter((r) => !r.pass).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
