// Retry for references whose screenshot timed out (heavy canvas); uses CDP capture.
import { chromium } from 'playwright';
const CHROME = `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const jobs = [
  { id: 'level2', url: 'https://www.trylevel2.com/', stops: [0, 1.2, 2.6] },
  { id: 'eclipses', url: 'https://eclipses.bogachev.fr', stops: [0, 1.2, 2.6] },
  { id: 'mesh-gallery', url: 'https://mesh3d.gallery/the-state-of-the-gallery', stops: [0, 1.2, 2.6] },
  { id: 'phantom-intro', url: 'https://www.phantom.land/', stops: [0], wait: 6400 },
];
if (process.env.RETRY) jobs.splice(0, jobs.length, ...JSON.parse(process.env.RETRY));
const browser = await chromium.launch({ executablePath: CHROME, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
for (const j of jobs.filter((x) => !process.argv[2] || x.id === process.argv[2])) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  try {
    await page.goto(j.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(j.wait ?? 8000);
    let y = 0;
    for (const [i, s] of j.stops.entries()) {
      const t = Math.round(s * 900);
      while (y < t) { await page.mouse.move(720, 450); await page.mouse.wheel(0, 240); y += 240; await sleep(60); }
      await sleep(s ? 2500 : 0);
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 78 });
      const fs = await import('node:fs');
      fs.writeFileSync(`public/research/captures/${j.id}-${i}.jpg`, Buffer.from(data, 'base64'));
    }
    console.log(j.id, 'ok');
  } catch (e) { console.log(j.id, 'ERROR', String(e.message).split('\n')[0]); }
  await ctx.close();
}
await browser.close();
