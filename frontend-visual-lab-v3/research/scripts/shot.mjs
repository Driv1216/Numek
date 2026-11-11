// Full-page or viewport screenshot of a local URL: node shot.mjs <url> <out.jpg> [width] [height] [full]
import { chromium } from 'playwright';
const [url, out, w = 1440, h = 900, full = '1', wait = '800', scrollTo = '0'] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`, args: ['--ignore-gpu-blocklist', '--use-angle=swiftshader'] });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
await page.goto(url, { waitUntil: 'networkidle' });
await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 500) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 140)); } window.scrollTo(0, 0); });
if (+scrollTo) { await page.evaluate((y) => window.scrollTo(0, y), +scrollTo); }
await page.waitForTimeout(+wait);
await page.screenshot({ path: out, fullPage: full === '1', type: 'jpeg', quality: 82 });
await browser.close();
