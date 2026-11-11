// Captures genuine browser evidence from the reference library:
// intro frames, wheel-driven scroll frames, a short screen recording and
// lightweight technical observations (fonts, canvas/WebGL, animation libraries).
// Usage: node research/scripts/capture-refs.mjs [id ...]
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const refs = JSON.parse(fs.readFileSync(path.join(root, process.env.REFS || 'references.json'), 'utf8'));
const only = process.argv.slice(2);
const list = only.length ? refs.filter((r) => only.includes(r.id)) : refs;

const W = 1440, H = 900;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function captureOne(browser, ref) {
  const dir = path.join(root, 'captures', ref.id);
  const vidDir = path.join(root, 'motion', '_raw', ref.id);
  fs.mkdirSync(dir, { recursive: true });
  fs.mkdirSync(vidDir, { recursive: true });
  const context = await browser.newContext({
    viewport: { width: W, height: H },
    deviceScaleFactor: 1,
    recordVideo: { dir: vidDir, size: { width: W, height: H } },
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();
  const meta = { id: ref.id, url: ref.url, ok: false, frames: [] };
  const shot = async (name) => {
    const file = path.join(dir, `${name}.jpg`);
    await page.screenshot({ path: file, type: 'jpeg', quality: 78 }).catch(() => {});
    meta.frames.push(`${name}.jpg`);
  };
  try {
    await page.goto(ref.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(900);
    await shot('00-intro-1s');
    await page.mouse.move(W * 0.3, H * 0.4, { steps: 12 });
    await sleep(1800);
    await shot('01-intro-3s');
    await page.mouse.move(W * 0.7, H * 0.6, { steps: 20 });
    await sleep(3000);
    await shot('02-settled-6s');
    meta.title = await page.title();
    // Wheel-driven scroll so smooth-scroll libraries respond as they would to a person.
    const steps = ref.scrollSteps ?? 24;
    for (let i = 1; i <= steps; i++) {
      await page.mouse.wheel(0, 260);
      await sleep(260);
      if (i % 4 === 0) {
        await sleep(700);
        await shot(`s${String(i).padStart(2, '0')}`);
      }
    }
    meta.observed = await page.evaluate(() => {
      const fams = new Set();
      document.fonts.forEach((f) => { if (f.status === 'loaded') fams.add(f.family.replace(/"/g, '')); });
      const canv = [...document.querySelectorAll('canvas')];
      const w = window;
      const h1 = document.querySelector('h1');
      const cs = h1 ? getComputedStyle(h1) : null;
      return {
        fonts: [...fams].slice(0, 12),
        canvases: canv.length,
        largestCanvas: canv.reduce((m, c) => Math.max(m, c.width * c.height), 0),
        libs: {
          gsap: !!w.gsap,
          ScrollTrigger: !!w.ScrollTrigger,
          lenis: !!document.documentElement.className.match(/lenis/),
          three: !!w.THREE || !!w.__THREE__,
          webflow: !!w.Webflow,
          next: !!w.__NEXT_DATA__ || !!document.querySelector('#__next'),
          nuxt: !!w.__NUXT__,
        },
        h1: h1 ? { text: h1.innerText.slice(0, 120), size: cs.fontSize, family: cs.fontFamily.slice(0, 60), weight: cs.fontWeight, tracking: cs.letterSpacing } : null,
        docHeight: document.documentElement.scrollHeight,
        bg: getComputedStyle(document.body).backgroundColor,
      };
    });
    meta.ok = true;
  } catch (e) {
    meta.error = String(e.message || e).slice(0, 300);
    await shot('error-state');
  }
  const video = page.video();
  await context.close();
  try {
    const raw = await video.path();
    const out = path.join(root, 'motion', `${ref.id}.mp4`);
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', raw, '-t', '26', '-vf', 'scale=960:-2,fps=24',
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '30', '-movflags', '+faststart', out]);
    meta.motion = `${ref.id}.mp4`;
  } catch (e) { meta.motionError = String(e.message || e).slice(0, 200); }
  fs.writeFileSync(path.join(dir, 'meta.json'), JSON.stringify(meta, null, 2));
  console.log(`${meta.ok ? 'ok ' : 'ERR'} ${ref.id} ${meta.title ?? meta.error ?? ''}`);
}

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true,
  args: ['--ignore-gpu-blocklist', '--enable-webgl', '--use-angle=swiftshader', '--autoplay-policy=no-user-gesture-required'],
});
const queue = [...list];
await Promise.all(Array.from({ length: 4 }, async () => {
  while (queue.length) {
    const ref = queue.shift();
    // A hard limit per site: heavy WebGL pages can stall headless capture indefinitely.
    await Promise.race([captureOne(browser, ref), new Promise((r) => setTimeout(() => { console.log(`TIMEOUT ${ref.id}`); r(); }, 150000))]);
  }
}));
await browser.close().catch(() => {});
fs.rmSync(path.join(root, 'motion', '_raw'), { recursive: true, force: true });
