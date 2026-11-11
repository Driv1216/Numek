// Lists the individual winning sites shown on Awwwards collection pages (title, award, Awwwards page).
// Usage: node research/scripts/awwwards-list.mjs > research/r4/awwwards.json
import { chromium } from 'playwright';
const pages = [
  'https://www.awwwards.com/websites/',
  'https://www.awwwards.com/websites/data-visualization/',
  'https://www.awwwards.com/websites/experimental/',
  'https://www.awwwards.com/websites/portfolio/',
  'https://www.awwwards.com/websites/sites_of_the_month/',
  'https://www.awwwards.com/websites/sites_of_the_day/',
];
const b = await chromium.launch({ executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing` });
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36' });
const out = {};
for (const url of pages) {
  const p = await ctx.newPage();
  try {
    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(2500);
    for (let i = 0; i < 6; i++) { await p.mouse.wheel(0, 1600); await p.waitForTimeout(500); }
    out[url] = await p.evaluate(() => {
      const seen = new Map();
      document.querySelectorAll('a[href*="/sites/"]').forEach((a) => {
        const href = a.href.split('?')[0];
        if (!/\/sites\/[^/]+\/?$/.test(href)) return;
        const card = a.closest('li, article, figure, div');
        const text = (card?.innerText || a.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160);
        if (!seen.has(href)) seen.set(href, text);
      });
      return [...seen].map(([href, text]) => ({ href, text }));
    });
  } catch (e) { out[url] = { error: String(e.message).slice(0, 200) }; }
  await p.close();
}
console.log(JSON.stringify(out, null, 1));
await b.close();
