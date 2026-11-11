// Deeper reference capture for round three: per-site interactions (gates, drags, hovers, long loaders),
// dense wheel-scroll frames, a 45 s recording and structural observations (headings, nav, fonts, motion libraries).
// Usage: REFS=references-r4.json node research/scripts/capture-deep.mjs [id ...]   → research/r4/captures, research/r4/motion
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const refs = JSON.parse(fs.readFileSync(path.join(root, process.env.REFS || 'references-r4.json'), 'utf8'));
const only = process.argv.slice(2);
const list = only.length ? refs.filter((r) => only.includes(r.id)) : refs;
const outRoot = path.join(root, 'r4');
const W = 1440, H = 900;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function one(browser, ref) {
  const dir = path.join(outRoot, 'captures', ref.id);
  const vid = path.join(outRoot, 'motion', '_raw', ref.id);
  fs.mkdirSync(dir, { recursive: true }); fs.mkdirSync(vid, { recursive: true });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, recordVideo: { dir: vid, size: { width: W, height: H } },
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36' });
  const page = await ctx.newPage();
  const meta = { id: ref.id, url: ref.url, group: ref.group, ok: false, frames: [], steps: [] };
  let n = 0;
  const shot = async (name) => { const f = `${String(n++).padStart(2, '0')}-${name}.jpg`; await page.screenshot({ path: path.join(dir, f), type: 'jpeg', quality: 76, timeout: 30000 }).catch(() => {}); meta.frames.push(f); };
  try {
    await page.goto(ref.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(1500); await shot('t1s');
    await page.mouse.move(W * 0.35, H * 0.45, { steps: 15 }); await sleep(2500); await shot('t4s');
    for (const [k, ...a] of ref.actions ?? []) {
      try {
        if (k === 'wait') await sleep(a[0]);
        else if (k === 'shot') await shot(a[0]);
        else if (k === 'hover') await page.mouse.move(a[0], a[1], { steps: 20 });
        else if (k === 'click-xy') await page.mouse.click(a[0], a[1]);
        else if (k === 'click') await page.getByText(a[0], { exact: false }).first().click({ timeout: 5000 });
        else if (k === 'drag') { await page.mouse.move(a[0], a[1]); await page.mouse.down(); await page.mouse.move(a[2], a[3], { steps: 30 }); await page.mouse.up(); }
        meta.steps.push(`${k} ok`);
      } catch (e) { meta.steps.push(`${k} ${a[0] ?? ''} failed: ${String(e.message).slice(0, 80)}`); }
    }
    meta.title = await page.title();
    const steps = ref.scroll ?? 48;
    for (let i = 1; i <= steps; i++) {
      await page.mouse.wheel(0, 240); await sleep(220);
      if (i % 4 === 0) { await sleep(650); await shot(`s${String(i).padStart(2, '0')}`); }
      if (i % 12 === 6) { await page.mouse.move(W * (0.2 + (i % 5) * 0.15), H * 0.5, { steps: 10 }); }
    }
    meta.observed = await page.evaluate(() => {
      const fams = new Set(); document.fonts.forEach((f) => { if (f.status === 'loaded') fams.add(f.family.replace(/"/g, '')); });
      const w = window; const canv = [...document.querySelectorAll('canvas')];
      const heads = [...document.querySelectorAll('h1,h2,h3')].map((h) => h.innerText.replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 16);
      const nav = [...document.querySelectorAll('nav a, header a')].map((a) => a.innerText.trim()).filter((t) => t && t.length < 24).slice(0, 12);
      const h1 = document.querySelector('h1'); const cs = h1 ? getComputedStyle(h1) : null;
      return { fonts: [...fams].slice(0, 10), canvases: canv.length, libs: { gsap: !!w.gsap, ScrollTrigger: !!w.ScrollTrigger, lenis: /lenis/.test(document.documentElement.className), three: !!w.THREE || !!w.__THREE__, webflow: !!w.Webflow, next: !!w.__NEXT_DATA__ || !!document.querySelector('#__next'), nuxt: !!w.__NUXT__ },
        headings: heads, nav, h1: h1 ? { size: cs.fontSize, family: cs.fontFamily.slice(0, 50), weight: cs.fontWeight } : null, docHeight: document.documentElement.scrollHeight, bg: getComputedStyle(document.body).backgroundColor };
    });
    meta.ok = true;
  } catch (e) { meta.error = String(e.message || e).slice(0, 200); await shot('error'); }
  const v = page.video(); await ctx.close();
  try { execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', await v.path(), '-t', '45', '-vf', 'scale=960:-2,fps=24', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '30', '-movflags', '+faststart', path.join(outRoot, 'motion', `${ref.id}.mp4`)]); meta.motion = `${ref.id}.mp4`; } catch (e) { meta.motionError = String(e.message).slice(0, 120); }
  fs.writeFileSync(path.join(dir, 'meta.json'), JSON.stringify(meta, null, 2));
  console.log(`${meta.ok ? 'ok ' : 'ERR'} ${ref.id} · ${meta.frames.length} frames · ${meta.steps.filter((s) => s.includes('failed')).length} failed steps`);
}

fs.mkdirSync(path.join(outRoot, 'motion'), { recursive: true });
const browser = await chromium.launch({ executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`, headless: true,
  args: ['--ignore-gpu-blocklist', '--enable-webgl', '--use-angle=swiftshader', '--autoplay-policy=no-user-gesture-required'] });
const queue = [...list];
await Promise.all(Array.from({ length: 3 }, async () => {
  while (queue.length) { const r = queue.shift(); await Promise.race([one(browser, r), new Promise((res) => setTimeout(() => { console.log(`TIMEOUT ${r.id}`); res(); }, 200000))]); }
}));
await browser.close().catch(() => {});
fs.rmSync(path.join(outRoot, 'motion', '_raw'), { recursive: true, force: true });
