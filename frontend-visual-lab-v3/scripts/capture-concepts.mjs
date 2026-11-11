// Captures every concept in a real browser (dev server must be running on :5313).
//   node scripts/capture-concepts.mjs [--mobile-only] [--no-video] [concept ...]
// Writes public/screenshots/: <id>-landing.jpg (hero), <id>-story.jpg (scroll storyboard),
// <id>-app.jpg, <id>-results.jpg, <id>-m-landing.jpg, <id>-m-results.jpg, and <id>.mp4 (landing scroll recording).
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const out = path.join(root, 'public', 'screenshots');
const tmp = path.join(root, '.capture-tmp');
fs.mkdirSync(out, { recursive: true });
const args = process.argv.slice(2);
const mobileOnly = args.includes('--mobile-only');
const noVideo = args.includes('--no-video');
const ids = args.filter((a) => !a.startsWith('--'));
const concepts = ids.length ? ids : ['markup', 'every-row', 'issue', 'passage', 'two-readings', 'provenance', 'collection', 'modules', 'camera', 'lexicon', 'cutaway', 'line', 'instrument', 'footnote', 'cells', 'resolution', 'relief', 'file', 'slab', 'findings', 'evidence', 'numek'];
const BASE = 'http://127.0.0.1:5313/#/';
const exe = `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
const browser = await chromium.launch({ executablePath: exe, args: ['--ignore-gpu-blocklist', '--use-angle=swiftshader'] });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function shot(url, file, vp, { scrollTo = 0, settle = 2600, prime = true } = {}) {
  const page = await browser.newPage({ viewport: vp, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  if (prime) await page.evaluate(async () => { const h = document.body.scrollHeight; for (let y = 0; y < Math.min(h, 4000); y += 600) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 120)); } scrollTo(0, 0); });
  if (scrollTo) await page.evaluate((y) => scrollTo(0, y), scrollTo);
  await wait(settle);
  await page.screenshot({ path: file, type: 'jpeg', quality: 82, timeout: 120000 });
  await page.close();
}

/** Viewport frames at even scroll steps, tiled into one image (pinned sections make full-page captures misleading). */
async function storyboard(id) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await page.goto(`${BASE}${id}/landing?clean`, { waitUntil: 'load', timeout: 60000 });
  await wait(1200);
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  const frames = [];
  const step = 820;
  for (let y = 0, k = 0; y < h - 400 && k < 24; y += step, k++) {
    for (let s = Math.max(0, y - step); s <= y; s += 160) { await page.evaluate((v) => scrollTo(0, v), s); await wait(50); }
    await wait(1700);
    const f = path.join(tmp, `${id}-${String(k).padStart(2, '0')}.jpg`);
    await page.screenshot({ path: f, type: 'jpeg', quality: 80, timeout: 120000 });
    frames.push(f);
  }
  await page.close();
  const cols = 2, w = 720, hh = 450;
  const rows = Math.ceil(frames.length / cols);
  const inputs = frames.flatMap((f) => ['-i', f]);
  const filters = frames.map((_, i) => `[${i}:v]scale=${w}:${hh}[f${i}]`).join(';');
  const layout = frames.map((_, i) => `${(i % cols) * w}_${Math.floor(i / cols) * hh}`).join('|');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...inputs, '-filter_complex', `${filters};${frames.map((_, i) => `[f${i}]`).join('')}xstack=inputs=${frames.length}:layout=${layout}:fill=white`, '-frames:v', '1', '-q:v', '4', path.join(out, `${id}-story.jpg`)]);
  console.log(`story ${id}: ${frames.length} frames, ${rows} rows`);
}

async function video(id) {
  const dir = path.join(tmp, `v-${id}`);
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir, size: { width: 1440, height: 900 } } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}${id}/landing?clean`, { waitUntil: 'load', timeout: 60000 });
  await wait(2500);
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  const total = Math.min(h - 900, 14000);
  for (let y = 0; y < total; y += 22) { await page.mouse.wheel(0, 22); await wait(16); }
  await wait(1500);
  const v = page.video();
  await ctx.close();
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', await v.path(), '-vf', 'scale=1280:-2,fps=30', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '27', '-movflags', '+faststart', path.join(out, `${id}.mp4`)]);
  console.log(`video ${id}`);
}

fs.mkdirSync(tmp, { recursive: true });
for (const id of concepts) {
  const m = { width: 390, height: 844 };
  await shot(`${BASE}${id}/landing?clean`, path.join(out, `${id}-m-landing.jpg`), m);
  await shot(`${BASE}${id}/results?clean`, path.join(out, `${id}-m-results.jpg`), m, { prime: false });
  await shot(`${BASE}${id}/app?clean`, path.join(out, `${id}-m-app.jpg`), m, { prime: false });
  if (mobileOnly) continue;
  const d = { width: 1440, height: 900 };
  await shot(`${BASE}${id}/landing?clean`, path.join(out, `${id}-landing.jpg`), d, { settle: 4200 });
  await shot(`${BASE}${id}/app?clean`, path.join(out, `${id}-app.jpg`), d, { prime: false });
  await shot(`${BASE}${id}/results?clean`, path.join(out, `${id}-results.jpg`), d, { prime: false, settle: 4200 });
  await storyboard(id);
  if (!noVideo) await video(id);
  console.log(`done ${id}`);
}
await browser.close();
fs.rmSync(tmp, { recursive: true, force: true });
