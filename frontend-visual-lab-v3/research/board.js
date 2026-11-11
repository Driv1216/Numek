import '@fontsource-variable/archivo/wdth.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource-variable/schibsted-grotesk';
import '@fontsource-variable/source-serif-4';
import '@fontsource-variable/newsreader';
import '@fontsource-variable/familjen-grotesk';
import '@fontsource-variable/hanken-grotesk';
import '@fontsource-variable/azeret-mono';
import '@fontsource-variable/recursive/full.css';
import { refs, discovery } from './board-data.js';
import { directions } from './directions-data.js';

const byId = Object.fromEntries(refs.map((r) => [r.id, r]));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const img = (id, f) => `./captures/${id}/${f}.jpg`;

// Each specimen is set in the direction's own typefaces, so the board shows real type.
const specimens = {
  markup: `<div class="spec spec--markup"><span class="m-cap">SHEET 01 · ADULT · 48,842 × 15</span><span class="m-big">5 GROUPS, 10 ROWS,<br/>LABELS DISAGREE</span><span class="m-mono">① annual_income_over_50k · conflicting · evidence only</span></div>`,
  'every-row': `<div class="spec spec--rows"><span class="r-big">48,842 rows.<br/>Every one accounted for.</span><span class="r-serif">Of these, <mark class="t">11,687</mark> earn over 50K, and <mark class="m">10 rows</mark> in five identical groups disagree on it.</span></div>`,
  issue: `<div class="spec spec--issue"><span class="i-lab">ISSUE 01 · THE ADULT DATASET · AUGUST 2026</span><span class="i-big">69.0</span><span class="i-it"><em>Elevated</em>, held there by one weak measure.</span><span class="i-lead">Contents ........................................ 08</span></div>`,
  passage: `<div class="spec spec--passage"><span class="p-ix">1/6</span><span class="p-big">Tables</span><span class="p-lab">48,842 RECORDS · 15 FIELDS</span><div class="p-strip"><i style="background:#B4633B"></i><i style="background:#5D6A72"></i><i style="background:#6D7A55"></i><i style="background:#D7C5A3"></i><i style="background:#8DA2B6"></i><i style="background:#22262A"></i></div></div>`,
  'two-readings': `<div class="spec spec--two"><span class="t-mono">"final_score": 69.0, "cap": "critical_sub_score"</span><span class="t-human">Final score 69.0 — held at the cap by a target-balance score of 47.86.</span></div>`,
};

function layout(boxes) {
  return `<div class="lay">${boxes.map(([x, y, w, h, label, kind]) =>
    `<div class="lay__b ${kind === 'hero' ? 'is-hero' : ''}" style="left:${x}%;top:${y}%;width:${w}%;height:${h}%"><span>${esc(label)}</span></div>`).join('')}</div>`;
}

document.getElementById('directions').innerHTML = directions.map((d) => `
  <article class="dir dir--${d.id}" id="dir-${d.id}">
    <header class="dir__head">
      <span class="dir__no">${d.no}</span>
      <h2 class="dir__name">${esc(d.name)}</h2>
      <p class="dir__thesis">${esc(d.thesis)}</p>
    </header>
    <div class="dir__grid">
      <div class="dir__visual">
        ${specimens[d.id]}
        <div class="pal">${d.palette.map(([n, h]) => `<div class="pal__c"><i style="background:${h}"></i><span>${esc(n)}<b>${h}</b></span></div>`).join('')}</div>
        <p class="meta"><b>Type</b> ${esc(d.type.display)} · text ${esc(d.type.text)} · ${esc(d.type.mono)}</p>
        <p class="meta"><b>Motion</b> ${esc(d.motion)}</p>
      </div>
      <div class="dir__text">
        <h3>Product presentation</h3><p>${esc(d.product)}</p>
        <h3>Landing page, in order</h3><ol>${d.landing.map((l) => `<li>${esc(l)}</li>`).join('')}</ol>
        <div class="dir__two">
          <div><h3>Dashboard</h3><p>${esc(d.app)}</p>${layout(d.layout.app)}</div>
          <div><h3>Results</h3><p>${esc(d.results)}</p>${layout(d.layout.results)}</div>
        </div>
        <h3>Main risk and guard</h3><p>${esc(d.risk)}</p>
      </div>
      <aside class="dir__from">
        <h3>Derived from</h3>
        ${d.from.map(([id, why]) => { const r = byId[id]; return `<a class="from" href="#ref-${id}"><img loading="lazy" src="${img(id, r.frames[r.frames.length > 2 ? 2 : 0])}" alt="${esc(r.name)} capture"/><span><b>${esc(r.name)}</b>${esc(why)}</span></a>`; }).join('')}
      </aside>
    </div>
  </article>`).join('');

const rows = [
  ['Core idea', (d) => ({ markup: 'Findings are marks on the artefact', 'every-row': 'Every record visible; marks rearrange', issue: 'Each audit is a published issue', passage: 'Travel across representations', 'two-readings': 'Machine output ↔ human evidence' })[d.id]],
  ['Ground', (d) => d.palette[0][0]],
  ['Landing architecture', (d) => ({ markup: 'Drawing set: sheets in sequence', 'every-row': 'Sticky field, scrollytelling steps', issue: 'Cover → contents → chapter fields', passage: 'Pinned horizontal panels', 'two-readings': 'Sentence window → morph → facts' })[d.id]],
  ['App structure', (d) => ({ markup: 'Sheet index · canvas · schedule', 'every-row': 'Population band · narrative · arrangement', issue: 'Issue covers → reading room', passage: 'Miller columns drill', 'two-readings': 'Timeline · split machine/human · ⌘K' })[d.id]],
  ['Results hero', (d) => ({ markup: 'Table drawing with numbered marks', 'every-row': 'All 48,842 rows, arranged', issue: 'Decision spread + articles', passage: 'Five-column drill to rows', 'two-readings': 'Score as a calculation, dual reading' })[d.id]],
  ['Motion', (d) => ({ markup: 'Draw-on, leader lines', 'every-row': 'Marks travel between layouts', issue: 'Page lifts, long holds', passage: 'Panels slide over panels', 'two-readings': 'Typeface axis morph' })[d.id]],
  ['Type', (d) => d.type.fonts.join(' + ')],
];
document.getElementById('matrix').innerHTML = `<table><thead><tr><th></th>${directions.map((d) => `<th>${d.no} ${esc(d.name)}</th>`).join('')}</tr></thead><tbody>${rows.map(([k, f]) => `<tr><th>${k}</th>${directions.map((d) => `<td>${esc(f(d))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;

const groups = [...new Set(refs.map((r) => r.group))];
document.getElementById('refs').innerHTML = groups.map((g) => `
  <h3 class="sub">${esc(g)}</h3>
  <div class="refs">${refs.filter((r) => r.group === g).map((r) => `
    <article class="ref ref--${r.status}" id="ref-${r.id}">
      <div class="ref__media" data-video="./motion/${r.id}.mp4">
        <div class="ref__frames">${r.frames.map((f) => `<img loading="lazy" src="${img(r.id, f)}" alt="${esc(r.name)} — ${f}"/>`).join('')}</div>
        <span class="ref__play">▶ recording</span>
      </div>
      <div class="ref__body">
        <p class="ref__title"><b>${esc(r.name)}</b> <span class="st">${r.status}</span></p>
        <p class="ref__by">${esc(r.by)} · <a href="${r.url}" target="_blank" rel="noopener">source</a></p>
        <p><i>Seen</i> ${esc(r.seen)}</p>
        <p><i>Take</i> ${esc(r.take)}</p>
        <p><i>Leave</i> ${esc(r.leave)}</p>
        <p class="ref__tech" data-meta="${r.id}"></p>
      </div>
    </article>`).join('')}</div>`).join('');

document.getElementById('discovery').innerHTML = discovery.map((d) => `<a href="${d.url}" target="_blank" rel="noopener"><img loading="lazy" src="${img(d.id, '02-settled-6s')}" alt=""/><span>${esc(d.name)}</span></a>`).join('');

// Technical observations recorded at capture time.
document.querySelectorAll('[data-meta]').forEach(async (el) => {
  try {
    const m = await fetch(`./captures/${el.dataset.meta}/meta.json`).then((r) => r.json());
    const o = m.observed || {};
    const libs = Object.entries(o.libs || {}).filter(([, v]) => v).map(([k]) => k);
    el.textContent = [o.fonts?.length ? `Fonts: ${o.fonts.slice(0, 3).join(', ')}` : '', libs.length ? `Detected: ${libs.join(', ')}` : '', o.canvases ? `${o.canvases} canvas` : ''].filter(Boolean).join(' · ');
  } catch { /* metadata is optional */ }
});

// Hover (or focus) a reference to play its recording in place.
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
document.querySelectorAll('.ref__media').forEach((m) => {
  let v;
  const on = () => {
    if (reduce) return;
    if (!v) {
      v = Object.assign(document.createElement('video'), { src: m.dataset.video, muted: true, loop: true, playsInline: true });
      v.className = 'ref__video';
      v.onerror = () => v.remove();
      m.append(v);
    }
    m.classList.add('is-playing'); v.play().catch(() => {});
  };
  const off = () => { m.classList.remove('is-playing'); v?.pause(); };
  m.addEventListener('mouseenter', on); m.addEventListener('mouseleave', off);
  m.tabIndex = 0; m.addEventListener('focus', on); m.addEventListener('blur', off);
});
