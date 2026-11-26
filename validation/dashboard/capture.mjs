// Headless capture of saved DataTrust results pages for the dashboard redesign (plan section L, visual inspection).
// node capture.mjs <plan.json>
// plan: { base, launch, out, playwright_dir, sizes: [[w, h, label]], chapters_at: label, cases: [{ name, id }] }
// For every case and size: the first viewport, the full page and the page text. At `chapters_at` only, every tile is
// opened and its chapter captured. Reduced motion is emulated so captures are deterministic; nothing is clicked except
// tiles and their close button, and nothing is downloaded or revealed.
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join } from 'node:path';

const plan = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const require = createRequire(join(plan.playwright_dir, 'noop.js'));
const { chromium } = require('playwright');

function executable() {
  const cache = join(homedir(), 'Library/Caches/ms-playwright');
  const found = existsSync(cache) ? readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort((a, b) => +b.split('-')[1] - +a.split('-')[1]) : [];
  for (const d of found) {
    const p = join(cache, d, 'chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing');
    if (existsSync(p)) return p;
  }
  return undefined;
}

const browser = await chromium.launch({ executablePath: executable() });
const results = [];
// One browser context: the launch link unlocks saved analyses once, for that browser session.
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce', deviceScaleFactor: 1 });
const page = await context.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto(`${plan.base}/app/?launch=${plan.launch}`, { waitUntil: 'networkidle' });
for (const [w, h, label] of plan.sizes) {
  await page.setViewportSize({ width: w, height: h });
  for (const c of plan.cases) {
    const dir = join(plan.out, c.name);
    mkdirSync(dir, { recursive: true });
    const start = errors.length;
    const t0 = Date.now();
    await page.goto(`${plan.base}/app/history/${c.id}`, { waitUntil: 'networkidle' });
    let state = 'rendered';
    try {
      await page.waitForFunction(() => document.querySelector('.ap-rs') && !document.querySelector('.ap-rs__wait'), null, { timeout: 15000 });
    } catch { state = 'still_waiting_after_15s'; }
    const ms = Date.now() - t0;
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(dir, `${label}-first.jpg`), type: 'jpeg', quality: 80 });
    await page.screenshot({ path: join(dir, `${label}-full.jpg`), type: 'jpeg', quality: 70, fullPage: true });
    writeFileSync(join(dir, `${label}.txt`), await page.evaluate(() => document.querySelector('main')?.innerText ?? ''));
    const chapters = [];
    if (label === plan.chapters_at && state === 'rendered') {
      const tiles = await page.$$('.nk-tile--btn');
      for (let i = 0; i < tiles.length; i++) {
        const tile = (await page.$$('.nk-tile--btn'))[i];
        const name = ((await tile.getAttribute('aria-label')) ?? `tile ${i}`).split(':')[0].replace(/[^a-z0-9]+/gi, '-').toLowerCase().slice(0, 40);
        await tile.scrollIntoViewIfNeeded();
        await tile.click();
        await page.waitForSelector('.nk-ch', { timeout: 3000 }).catch(() => {});
        await page.waitForTimeout(250);
        const box = await page.$('.nk-mosaic--run');
        await box?.scrollIntoViewIfNeeded();
        const file = `${label}-chapter-${String(i + 1).padStart(2, '0')}-${name}.jpg`;
        await page.screenshot({ path: join(dir, file), type: 'jpeg', quality: 78 });
        chapters.push({ file, text: await page.evaluate(() => document.querySelector('.nk-ch')?.innerText ?? '') });
        await page.keyboard.press('Escape');
        await page.waitForTimeout(150);
      }
      writeFileSync(join(dir, `${label}-chapters.json`), JSON.stringify(chapters, null, 1));
    }
    // The ledger's two ways into the evidence: its chapter (a focused finding block) and the verified report location.
    const ledger = {};
    if (label === plan.chapters_at && state === 'rendered' && await page.$('.ap-ledger__it')) {
      const links = await page.$$('.ap-ledger__it .ap-link');
      for (const b of links) {
        if ((await b.innerText()) !== 'Evidence') continue;
        await b.click();
        await page.waitForSelector('.nk-ch', { timeout: 3000 }).catch(() => {});
        await page.waitForTimeout(300);
        ledger.evidence_focused = !!(await page.$('.nk-ch .is-focus'));
        ledger.hash = await page.evaluate(() => location.hash);
        await page.screenshot({ path: join(dir, `${label}-ledger-evidence.jpg`), type: 'jpeg', quality: 78 });
        await page.keyboard.press('Escape');
        await page.waitForTimeout(250);
        break;
      }
      for (const b of await page.$$('.ap-ledger__it .ap-link')) {
        if ((await b.innerText()) !== 'In report') continue;
        await b.click();
        await page.waitForSelector('.ap-view iframe', { timeout: 4000 }).catch(() => {});
        await page.waitForTimeout(800);
        ledger.report_src = await page.evaluate(() => document.querySelector('.ap-view iframe')?.getAttribute('src') ?? null);
        ledger.report_target_found = await page.evaluate(() => {
          const f = document.querySelector('.ap-view iframe');
          const id = decodeURIComponent((f?.getAttribute('src') ?? '').split('#')[1] ?? '');
          return id ? !!f.contentDocument?.getElementById(id) : null;
        });
        await page.screenshot({ path: join(dir, `${label}-ledger-report.jpg`), type: 'jpeg', quality: 70 });
        await page.keyboard.press('Escape');
        await page.waitForTimeout(300);
        break;
      }
    }
    results.push({ name: c.name, size: label, state, ms, chapters: chapters.length, ledger, errors: errors.slice(start) });
    process.stdout.write(`${label} ${c.name} ${state} ${ms}ms chapters=${chapters.length}\n`);
  }
}
await context.close();
await browser.close();
writeFileSync(join(plan.out, 'capture.json'), JSON.stringify(results, null, 1));
