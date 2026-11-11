// For each Awwwards site slug: live URL, award line, tags and credits, read from its Awwwards page.
// Usage: node research/scripts/awwwards-sites.mjs slug ... > research/r4/winners.json
import { chromium } from 'playwright';
const slugs = process.argv.slice(2);
const b = await chromium.launch({ executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing` });
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36' });
const out = [];
const queue = [...slugs];
await Promise.all(Array.from({ length: 4 }, async () => {
  while (queue.length) {
    const slug = queue.shift();
    const p = await ctx.newPage();
    try {
      await p.goto(`https://www.awwwards.com/sites/${slug}`, { waitUntil: 'domcontentloaded', timeout: 40000 });
      await p.waitForTimeout(1500);
      const r = await p.evaluate(() => {
        const txt = (s) => document.querySelector(s)?.innerText?.trim() ?? '';
        const visit = [...document.querySelectorAll('a')].find((a) => /visit site/i.test(a.innerText))?.href ?? '';
        const h1 = txt('h1');
        const body = document.body.innerText;
        const award = (body.match(/(Site of the (Day|Month|Year)|Honorable Mention|Developer Award|Special Kudos)[^\n]{0,30}/) || [''])[0];
        const tags = [...document.querySelectorAll('a[href*="/websites/"]')].map((a) => a.innerText.trim()).filter((t) => t && t.length < 30).slice(0, 14);
        const desc = [...document.querySelectorAll('p')].map((p) => p.innerText.trim()).find((t) => t.length > 60 && t.length < 400) ?? '';
        return { h1, visit, award, tags: [...new Set(tags)], desc };
      });
      out.push({ slug, ...r });
    } catch (e) { out.push({ slug, error: String(e.message).slice(0, 120) }); }
    await p.close();
  }
}));
console.log(JSON.stringify(out, null, 1));
await b.close();
