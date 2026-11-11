// Captures the real engine-generated Adult report so concepts can present the actual artifact.
import { chromium } from 'playwright';
const CHROME = `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
const b = await chromium.launch({ executablePath: CHROME });
for (const [f, w] of [['adult', 1200], ['adult-leak', 1200]]) {
  const p = await (await b.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 2 })).newPage();
  await p.goto(`file://${process.cwd()}/research/engine/${f}.html`);
  await p.waitForTimeout(500);
  await p.screenshot({ path: `public/round2/report-${f}-top.jpg`, type: 'jpeg', quality: 86 });
  await p.screenshot({ path: `public/round2/report-${f}-full.jpg`, type: 'jpeg', quality: 80, fullPage: true });
}
await b.close();
