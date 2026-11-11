// Captures real viewport screenshots of reference websites for the inspiration board.
// Usage: node research/capture-references.mjs [id ...]
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const OUT = path.resolve('public/research/captures');
const refs = JSON.parse(fs.readFileSync(process.env.REFS || 'research/references.json', 'utf8'));
const only = process.argv.slice(2);
const list = only.length ? refs.filter((r) => only.includes(r.id)) : refs;
fs.mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function capture(browser, ref) {
  const log = { id: ref.id, url: ref.url, shots: [], error: null };
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  });
  const page = await ctx.newPage();
  try {
    await page.goto(ref.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(ref.wait ?? 6000);
    const stops = ref.stops ?? [0, 1.1, 2.4, 4];
    for (const [i, s] of stops.entries()) {
      if (s > 0) {
        // Wheel scrolling works with smooth-scroll libraries that ignore window.scrollTo.
        const target = Math.round(s * 900);
        const current = await page.evaluate(() => window.scrollY).catch(() => 0);
        let delta = target - current;
        while (delta > 0) {
          const step = Math.min(240, delta);
          await page.mouse.move(720, 450);
          await page.mouse.wheel(0, step);
          delta -= step;
          await sleep(60);
        }
        await sleep(2200);
      }
      const file = `${ref.id}-${i}.jpg`;
      await page.screenshot({ path: path.join(OUT, file), type: 'jpeg', quality: 78 });
      log.shots.push(file);
    }
  } catch (e) {
    log.error = String(e.message || e).split('\n')[0];
  }
  await ctx.close();
  return log;
}

const CHROME = process.env.CHROME_PATH || `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
const results = [];
const queue = [...list];
await Promise.all(
  Array.from({ length: 3 }, async () => {
    while (queue.length) {
      const ref = queue.shift();
      const r = await capture(browser, ref);
      console.log(r.id, r.error ? `ERROR ${r.error}` : `${r.shots.length} shots`);
      results.push(r);
    }
  }),
);
await browser.close();
const logPath = path.join(OUT, 'capture-log.json');
const prev = fs.existsSync(logPath) ? JSON.parse(fs.readFileSync(logPath, 'utf8')) : [];
const merged = [...prev.filter((p) => !results.some((r) => r.id === p.id)), ...results];
fs.writeFileSync(logPath, JSON.stringify(merged, null, 2));
