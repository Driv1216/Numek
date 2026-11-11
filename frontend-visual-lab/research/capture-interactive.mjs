// Second capture pass for references that need one click (enter gate or cookie
// banner) before their content is visible. Cookie banners are dismissed with the
// most privacy-preserving option the banner offers.
import { chromium } from 'playwright';
import path from 'node:path';

const OUT = path.resolve('public/research/captures');
const CHROME =
  process.env.CHROME_PATH ||
  `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const jobs = [
  { id: 'siena', url: 'https://siena.film', click: ['text=Enter'], wait: 7000, stops: [0, 1, 2.2, 3.6, 5] },
  { id: 'cartier365', url: 'https://365ayearof.cartier.com/', click: ['text=Allow technical cookies only'], wait: 12000, stops: [0, 1, 2.2, 3.6] },
  { id: 'phantom', url: 'https://www.phantom.land/', click: ['text=Decline'], wait: 8000, stops: [0, 1, 2.2] },
];

const only = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: CHROME,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
for (const job of jobs.filter((j) => !only.length || only.includes(j.id))) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  try {
    await page.goto(job.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(job.wait);
    for (const sel of job.click) {
      const el = page.locator(sel).first();
      if (await el.isVisible().catch(() => false)) await el.click({ timeout: 5000 }).catch(() => {});
      await sleep(4000);
    }
    let y = 0;
    for (const [i, s] of job.stops.entries()) {
      const target = Math.round(s * 900);
      while (y < target) {
        await page.mouse.move(720, 450);
        await page.mouse.wheel(0, 240);
        y += 240;
        await sleep(60);
      }
      await sleep(2500);
      await page.screenshot({ path: path.join(OUT, `${job.id}-${i}.jpg`), type: 'jpeg', quality: 78 });
    }
    console.log(job.id, 'ok');
  } catch (e) {
    console.log(job.id, 'ERROR', String(e.message).split('\n')[0]);
  }
  await ctx.close();
}
await browser.close();
