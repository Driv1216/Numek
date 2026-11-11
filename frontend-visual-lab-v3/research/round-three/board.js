// Round-three board: ten direction proposals with type specimens set in their own faces and drawn
// from the real fixture, a comparison matrix, and the research board generated from research/r4/notes.md.
import '@fontsource/ibm-plex-sans/300.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource-variable/instrument-sans';
import '@fontsource/instrument-serif/400-italic.css';
import '@fontsource-variable/jetbrains-mono';
import '@fontsource-variable/newsreader';
import '@fontsource-variable/hanken-grotesk';
import '@fontsource/red-hat-mono/400.css';
import '@fontsource-variable/space-grotesk';
import '@fontsource/space-mono/400.css';
import '@fontsource-variable/martian-mono';
import '@fontsource-variable/cormorant';
import '@fontsource-variable/figtree';
import '@fontsource/dm-serif-display/400.css';
import '@fontsource-variable/dm-sans';
import '@fontsource-variable/anybody';
import '@fontsource-variable/albert-sans';
import columnsAll from '../../src/fixture/columns.generated.json';
import adultGen from '../../src/fixture/adult.generated.json';
import { directions } from './directions.js';

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const cols = columnsAll.adult.columns;
const subs = [['Completeness', 99.12], ['Uniqueness', 99.89], ['Target balance', 47.86], ['Feature usability', 98.86], ['Leakage risk', 100]];
const g = adultGen.conflicts[0];
const row = (label) => [...Object.values(g.features), label].join(',');

// ——— Specimens: each drawn from real Adult values, in the direction's own typefaces.
function cutawaySvg() {
  // 15 column strips on an isometric base; height = log of real cardinality, notch = real missing share.
  const W = 360, ox = 40, oy = 150;
  const iso = (x, y, z) => [ox + (x - y) * 0.87, oy + (x + y) * 0.5 - z];
  const parts = cols.map((c, i) => {
    const h = 14 + Math.log10(Math.max(2, c.unique)) * 22;
    const [x0, y0] = iso(i * 14, 0, 0), [x1, y1] = iso(i * 14 + 10, 0, 0), [x2, y2] = iso(i * 14 + 10, 26, 0);
    const top = [iso(i * 14, 0, h), iso(i * 14 + 10, 0, h), iso(i * 14 + 10, 26, h), iso(i * 14, 26, h)];
    const red = c.name === 'annual_income_over_50k' || c.name === 'hours_per_week';
    return `<g class="cw-col ${red ? 'is-red' : ''}"><path d="M${x0} ${y0} L${x1} ${y1} L${x2} ${y2} L${top[2][0]} ${top[2][1]} L${top[1][0]} ${top[1][1]} L${top[0][0]} ${top[0][1]} Z"/><path class="cw-top" d="M${top.map((p) => p.join(' ')).join(' L')} Z"/>${c.missing ? `<line x1="${top[1][0]}" y1="${top[1][1] + 6}" x2="${top[2][0]}" y2="${top[2][1] + 6}" class="cw-gap"/>` : ''}</g>`;
  }).join('');
  return `<svg viewBox="0 0 ${W} 210" class="cw-svg" aria-hidden="true">${parts}</svg>`;
}
function instrumentSvg() {
  const R = 96, cx = 110, cy = 110, n = cols.length;
  return `<svg viewBox="0 0 220 220" class="in-svg" aria-hidden="true">${cols.map((c, i) => {
    const a0 = (i / n) * Math.PI * 2 - Math.PI / 2, a1 = ((i + 0.86) / n) * Math.PI * 2 - Math.PI / 2;
    const bins = c.kind === 'numeric' ? c.bins : c.values.map((v) => v[1]);
    const m = Math.max(...bins);
    return bins.slice(0, 16).map((v, k) => {
      const r = 24 + k * 4.6, on = c.name === 'annual_income_over_50k';
      const w = 0.6 + (v / m) * 3.2;
      return `<path d="M${cx + r * Math.cos(a0)} ${cy + r * Math.sin(a0)} A${r} ${r} 0 0 1 ${cx + r * Math.cos(a1)} ${cy + r * Math.sin(a1)}" stroke-width="${w.toFixed(2)}" class="${on ? 'is-on' : ''}"/>`;
    }).join('');
  }).join('')}<circle cx="${cx}" cy="${cy}" r="${R}" class="in-ring"/></svg>`;
}
function sparkline() {
  const c = adultGen.hours.hist.counts; const m = Math.max(...c);
  return `<svg viewBox="0 0 98 14" class="fn-spark" aria-hidden="true">${c.map((v, i) => `<rect x="${i}" y="${14 - Math.max(.6, Math.sqrt(v / m) * 14)}" width=".8" height="${Math.max(.6, Math.sqrt(v / m) * 14)}"/>`).join('')}</svg>`;
}

const specimens = {
  cutaway: `<div class="spec sp-cut"><span class="cw-lab">ADULT · 48,842 × 15 · TARGET SPLIT 76.07 / 23.93</span>${cutawaySvg()}<span class="cw-cap">See inside your dataset.</span></div>`,
  line: `<div class="spec sp-line"><span class="ln-mono">adult.csv · 2449271d… · 683,788 cells</span><svg viewBox="0 0 360 60" class="ln-svg" aria-hidden="true"><path d="M0 30 H70 C90 30 90 12 110 12 H160 M110 30 H160 M110 48 H160 M90 30 C100 30 100 48 110 48 M160 12 C180 12 180 30 200 30 M160 48 C180 48 180 30 200 30 H360"/><circle cx="246" cy="30" r="3.5"/><line x1="290" y1="18" x2="290" y2="42" class="ln-cap"/></svg><span class="ln-big">From a file to a finding, on this machine.</span><span class="ln-mono">6,465 empty · 52 repeated · 5 conflicting · 13,496 outside · cap 69</span></div>`,
  instrument: `<div class="spec sp-inst"><div class="in-row">${instrumentSvg()}<div class="in-leg"><em>What held the score at 69?</em><span>target_balance <b>47.86</b> ≤ 50</span><span>cap · critical_sub_score</span><span>evidence 89.15 → <b>69.0</b></span></div></div></div>`,
  footnote: `<div class="spec sp-fn"><p class="fn-big">DataTrust reads a dataset on your machine<sup>1</sup> and shows what it found<sup>2</sup> — ${sparkline()} every finding with its evidence<sup>3</sup> and what it did to the score <span class="fn-tok">69.0</span><sup>4</sup>.</p><span class="fn-note">³ rows 16,684 and 34,343: 14 of 14 features equal; labels &gt;50K / &lt;=50K</span></div>`,
  cells: `<div class="spec sp-cells"><div class="ce-grid"><div class="ce-a"><span>FINAL</span><b>69.0</b></div><div><span>EVIDENCE</span><b>89.15</b></div><div><span>TARGET BALANCE</span><b>47.86</b></div><div class="ce-w"><span>ADULT · RUN 01:08:11 · 127.0.0.1</span><b>48,842 × 15</b></div><div class="ce-d"></div><div><span>FINDINGS</span><b>04</b></div></div></div>`,
  resolution: `<div class="spec sp-res"><span class="rs-stat">RUNS 7 · NETWORK 0 · ADULT · CONFLICT 1/5</span><div class="rs-wall">${Array.from({ length: 11 }, (_, i) => `<i class="rs-t rs-${i % 4}"></i>`).join('')}<div class="rs-exact"><b>row 16,684</b>${esc(row(g.labels[0]))}<br/><b>row 34,343</b>${esc(row(g.labels[1]))}</div></div></div>`,
  relief: `<div class="spec sp-rel"><span class="rl-relief">48,842</span><div class="rl-win"><span>Target balance</span><b>47.86</b><em>held the score at 69</em></div><span class="rl-cap">The ridge is forty hours: 46.69% of rows.</span></div>`,
  file: `<div class="spec sp-file"><div class="fl-stack">${Array.from({ length: 9 }, (_, i) => `<i style="--i:${i}"></i>`).join('')}<span>adult.csv</span></div><div class="fl-txt"><b>37,155 / 11,687</b><span>The stack parts by target.</span></div></div>`,
  slab: `<div class="spec sp-slab"><span class="sl-head">NUMEK · DATATRUST · ADULT · 127.0.0.1</span><div class="sl-bars">${subs.map(([l, v]) => `<div class="${v <= 50 ? 'is-crit' : ''}" style="height:${v}%"><span>${v}</span></div>`).join('')}<i class="sl-50"></i><i class="sl-69"></i></div><span class="sl-cred">Source UCI Adult · Rows 48,842 · Target annual_income_over_50k</span></div>`,
  findings: `<div class="spec sp-find"><div class="fd-t">${[['Target imbalance', 'Adult', 'Moderate', 'Can cap the score'], ['Numeric outlier concentration', 'Adult', 'Moderate', 'Changes a sub-score'], ['Supported target relationship', 'Bike', 'High', 'No score defined'], ['Record and document disagree', 'Finance', 'High', 'No score defined']].map((r) => `<div>${r.map((x, i) => `<span class="${i === 3 ? 'fd-e' : ''}">${esc(x)}</span>`).join('')}</div>`).join('')}</div><span class="fd-cap">Every finding, from every run on this machine.</span></div>`,
};

function layout(boxes) {
  return `<div class="lay">${boxes.map(([x, y, w, h, label, kind]) => `<div class="lay__b ${kind === 'hero' ? 'is-hero' : ''}" style="left:${x}%;top:${y}%;width:${w}%;height:${h}%"><span>${esc(label)}</span></div>`).join('')}</div>`;
}

const refs = await fetch('./refs.json').then((r) => r.json());
const byId = Object.fromEntries(refs.map((r) => [r.id, r]));
const thumb = (r) => r && r.frames.length ? `../r4/captures/${r.id}/${r.frames[Math.min(3, r.frames.length - 1)]}.jpg` : '';

document.getElementById('directions').innerHTML = directions.map((d) => `
  <article class="dir dir--${d.id}" id="dir-${d.id}">
    <header class="dir__head"><span class="dir__no">${d.no}</span><h2 class="dir__name">${esc(d.name)}</h2><p class="dir__thesis">${esc(d.thesis)}</p></header>
    <div class="dir__grid">
      <div class="dir__visual">
        ${specimens[d.id]}
        <div class="pal">${d.palette.map(([n, h]) => `<div class="pal__c"><i style="background:${h}"></i><span>${esc(n)}<b>${h}</b></span></div>`).join('')}</div>
        <p class="meta"><b>Type</b> ${esc(d.type.display)} · text ${esc(d.type.text)} · ${esc(d.type.mono)}</p>
        <p class="meta"><b>Motion</b> ${esc(d.motion)}</p>
        <p class="meta"><b>Unlike rounds one–two</b> ${esc(d.differs)}</p>
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
      <aside class="dir__from"><h3>Derived from</h3>
        ${d.from.map(([id, why]) => { const r = byId[id]; return `<a class="from" href="#ref-${id}">${r ? `<img loading="lazy" src="${thumb(r)}" alt="${esc(r.title)} capture"/>` : '<span></span>'}<span><b>${esc(r ? r.title : id)}</b>${esc(why)}</span></a>`; }).join('')}
      </aside>
    </div>
  </article>`).join('');

const rows = [
  ['Core idea', (d) => d.thesis.split('.')[0]],
  ['Ground', (d) => d.palette[0][0]],
  ['Product shown as', (d) => d.product.split('.')[0]],
  ['Motion', (d) => d.motion.split(';')[0]],
  ['Type', (d) => d.type.fonts.join(' + ')],
];
document.getElementById('matrix-table').innerHTML = `<table><thead><tr><th></th>${directions.map((d) => `<th>${d.no} ${esc(d.name)}</th>`).join('')}</tr></thead><tbody>${rows.map(([k, f]) => `<tr><th>${k}</th>${directions.map((d) => `<td>${esc(f(d))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;

// Research board: strongest first, then useful, weak, partial, inaccessible.
const order = { strong: 0, useful: 1, weak: 2 };
const rank = (r) => (r.status === 'inaccessible' ? 5 : r.status === 'partial' ? 4 : r.status === 'gallery' ? 3 : order[r.strength] ?? 1);
const used = new Set(directions.flatMap((d) => d.from.map(([id]) => id)));
const sorted = [...refs].sort((a, b) => rank(a) - rank(b));
const filters = [['all', 'All'], ['used', 'Used in a direction'], ['strong', 'Strong'], ['limited', 'Partial / inaccessible']];
let current = 'all';
const card = (r) => {
  const frames = r.frames.length > 4 ? [r.frames[2], r.frames[Math.floor(r.frames.length / 3)], r.frames[Math.floor(r.frames.length * 2 / 3)], r.frames[r.frames.length - 1]] : r.frames;
  return `<article class="ref ref--${r.status === 'live' ? 'live' : 'partial'}" id="ref-${r.id}">
    <div class="ref__media" data-video="../r4/motion/${r.id}.mp4">
      <div class="ref__frames">${frames.map((f) => `<img loading="lazy" src="../r4/captures/${r.id}/${f}.jpg" alt="${esc(r.title)} — ${f}"/>`).join('')}</div>
      ${r.motion ? '<span class="ref__play">▶ recording</span>' : ''}
    </div>
    <div class="ref__body">
      <p class="ref__title"><b>${esc(r.title)}</b> <span class="st">${r.status}</span>${r.strength === 'strong' ? '<span class="st st--strong">strong</span>' : ''}${used.has(r.id) ? '<span class="st st--used">used</span>' : ''}</p>
      <p class="ref__by">${esc(r.meta || r.group)} · ${r.url ? `<a href="${r.url}" target="_blank" rel="noopener">source</a>` : ''}</p>
      ${r.seen ? `<p><i>Seen</i> ${esc(r.seen)}</p>` : ''}
      ${r.take ? `<p><i>Take</i> ${esc(r.take)}</p>` : ''}
      ${r.leave ? `<p><i>Leave</i> ${esc(r.leave)}</p>` : ''}
    </div>
  </article>`;
};
function renderRefs() {
  const list = sorted.filter((r) => current === 'all' || (current === 'used' && used.has(r.id)) || (current === 'strong' && r.strength === 'strong') || (current === 'limited' && ['partial', 'inaccessible', 'gallery'].includes(r.status)));
  document.getElementById('refs').innerHTML = `<div class="refs">${list.map(card).join('')}</div>`;
  wireVideos();
}
document.getElementById('filters').innerHTML = filters.map(([k, l]) => `<button type="button" data-f="${k}" aria-pressed="${k === current}">${l}</button>`).join('');
document.getElementById('filters').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  current = b.dataset.f;
  document.querySelectorAll('#filters button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  renderRefs();
});

const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
function wireVideos() {
  document.querySelectorAll('.ref__media').forEach((m) => {
    let v;
    const on = () => {
      if (reduce) return;
      if (!v) { v = Object.assign(document.createElement('video'), { src: m.dataset.video, muted: true, loop: true, playsInline: true }); v.className = 'ref__video'; v.onerror = () => v.remove(); m.append(v); }
      m.classList.add('is-playing'); v.play().catch(() => {});
    };
    const off = () => { m.classList.remove('is-playing'); v?.pause(); };
    m.addEventListener('mouseenter', on); m.addEventListener('mouseleave', off);
    m.tabIndex = 0; m.addEventListener('focus', on); m.addEventListener('blur', off);
  });
}
renderRefs();
