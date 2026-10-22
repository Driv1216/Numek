// The approved Modules mosaic for a real run: all fourteen tiles in their original places, emerging one
// after another, each growing into its chapter. Tile states and chapter text come from the canonical JSON.
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { reducedMotion } from '../../foundation/motion';
import type { Analysis } from '../api';
import type { Run, ShownFinding } from './adapter';
import { effectLabel, mods, shade, type ModId } from './modules';
import { Viz } from './viz';

export function Mosaic({ a, run, runName }: { a: Analysis; run: Run; runName: string }) {
  const list = mods;
  const grid = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState<ModId | null>(null);
  const [shown, setShown] = useState<ModId | null>(null);

  const inset = (id: ModId) => {
    const g = grid.current!, t = g.querySelector<HTMLElement>(`[data-mod="${id}"]`);
    if (!t) return 'inset(0 round 18px)';
    const gb = g.getBoundingClientRect(), tb = t.getBoundingClientRect();
    return `inset(${tb.top - gb.top}px ${gb.right - tb.right}px ${gb.bottom - tb.bottom}px ${tb.left - gb.left}px round 12px)`;
  };

  // Grow from the tile on open; shrink back into it on close.
  useLayoutEffect(() => {
    const p = panel.current; if (!p) return;
    if (open) {
      if (reducedMotion()) { p.style.clipPath = 'inset(0 round 18px)'; return; }
      p.style.transition = 'none'; p.style.clipPath = inset(open);
      void p.offsetWidth;
      p.style.transition = 'clip-path .7s cubic-bezier(.7, 0, .18, 1)'; p.style.clipPath = 'inset(0 round 18px)';
    }
  }, [open]);
  useEffect(() => { if (open) closeBtn.current?.focus(); }, [open]);
  const openCh = (id: ModId) => { setShown(id); setOpen(id); };

  const close = () => {
    const p = panel.current, id = shown;
    if (!p || !id) { setOpen(null); return; }
    const done = () => { setOpen(null); setShown(null); grid.current?.querySelector<HTMLElement>(`[data-mod="${id}"]`)?.focus(); };
    if (reducedMotion()) { done(); return; }
    p.style.clipPath = inset(id);
    setTimeout(done, 650);
  };
  const step = (d: number) => { const i = list.findIndex((m) => m.id === shown); setShown(list[(i + d + list.length) % list.length].id); };
  useEffect(() => {
    if (!open) return;
    const on = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); if (e.key === 'ArrowRight') step(1); if (e.key === 'ArrowLeft') step(-1); };
    addEventListener('keydown', on); return () => removeEventListener('keydown', on);
  });

  const m = mods.find((x) => x.id === shown);
  const s = m ? run[m.id] : undefined;
  return (
    <div className="nk-checks">
      <div ref={grid} className="nk-mosaic nk-mosaic--big nk-mosaic--run">
        {list.map((x, i) => {
          const [bg, light] = shade[x.id];
          const t = run[x.id];
          return (
            <div key={x.id} className="nk-slot2" style={{ gridArea: x.area, ['--d' as string]: i }}>
              <button type="button" data-mod={x.id} className={`nk-tile nk-tile--btn ${light ? 'is-light' : ''} ${t && !t.dim ? '' : 'is-dim'}`} style={{ ['--bg' as string]: bg }} onClick={() => openCh(x.id)} aria-label={`${x.name}: ${t ? t.label : 'Not for this data'}. Open`}>
                <span className="nk-tile__top"><span className="nk-tile__name">{x.name}</span><span className="nk-tile__n">{x.n}</span></span>
                <span className="nk-tile__fig nk-tile__fig--state"><b className={t && (t.tone === 'critical' || t.tone === 'finding') ? `is-${t.tone}` : ''}>{t ? t.label : 'Not for this data'}</b><span>{t ? t.detail : x.line}</span></span>
                {t && !t.dim && <span className="nk-tile__viz"><Viz id={x.id} a={a} t={t} /></span>}
                <span className="nk-tile__open" aria-hidden="true">Open ↗</span>
              </button>
            </div>
          );
        })}
        {open && m && (
          <div ref={panel} className={`nk-ch ${shade[m.id][1] ? 'is-light' : ''}`} style={{ ['--bg' as string]: shade[m.id][0] }} role="dialog" aria-modal="false" aria-label={`${m.name} chapter`}>
            <div className="nk-ch__bar">
              <span className="nk-ch__n">{m.n} / 14 · {m.rep}</span>
              <div>
                <button type="button" onClick={() => step(-1)} aria-label="Previous check">←</button>
                <button type="button" onClick={() => step(1)} aria-label="Next check">→</button>
                <button ref={closeBtn} type="button" onClick={close} aria-label="Close chapter">Close ✕</button>
              </div>
            </div>
            <div className="nk-ch__in" key={m.id}>
              <div className="nk-ch__text">
                <h3>{m.name}</h3>
                <div className="nk-ch__run"><span>In {runName}</span><b>{s ? s.label : 'Not for this data'}</b><p>{s ? (s.findings.length ? `${s.findings.length} finding${s.findings.length > 1 ? 's' : ''} in the canonical report. Options, prerequisites and checks for each are in the report’s preprocessing guidance.` : s.detail) : (m.elsewhere ?? `${m.name} reads ${m.rep.toLowerCase()} data; this run is a table.`)}</p></div>
                <p className="nk-ch__line">{m.line}</p>
                {s?.findings.map((f, i) => (
                  <div key={`${f.code}:${i}`} className="nk-ch__f">
                    <b>{f.title} <em>{f.severity}</em>{f.context && <em>Context</em>}{f.unmapped && <em>Unmapped finding</em>}</b>
                    <p>{f.finding}{typeof f.evidence === 'string' && f.evidence ? ` ${f.evidence}` : ''}</p>
                    <Evidence f={f} />
                    {f.modeling_impact && <p>{f.modeling_impact}</p>}
                    {f.recommendation && <p>{f.recommendation}</p>}
                    {firstCheck(a, f.code) && <p className="nk-ch__first"><b>Check first:</b> {firstCheck(a, f.code)}</p>}
                    {f.score_effect && <span className="nk-ch__eff">{f.score_effect}</span>}
                  </div>
                ))}
                {!!s?.scope.length && <ul className="nk-ch__cov" aria-label="Scope of this check">{s.scope.map((x) => <li key={x}>{x}</li>)}</ul>}
                {s && !s.findings.length && <span className="nk-ch__eff">{s.effect ?? (m.effectNote.startsWith(effectLabel[m.effect]) ? m.effectNote : `${effectLabel[m.effect]} · ${m.effectNote}`)}</span>}
                {!!s?.facts.length && <dl>{s.facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}
                <p className="nk-ch__not">{m.not}</p>
              </div>
              <div className="nk-ch__viz"><Viz id={m.id} a={a} t={s} big /></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** The first investigation step the analysis recorded for a finding (finding_guidance_v1), if any. */
function firstCheck(a: Analysis, code: string) {
  const items = (a as { guidance?: { items?: Record<string, { investigate?: string[] }> } }).guidance?.items ?? {};
  return (items[code] ?? Object.entries(items).find(([k]) => k.startsWith(`context.${code}.`))?.[1])?.investigate?.[0];
}

/** Structured canonical evidence (a list or an object of measurements) as a compact table, never coerced to text. */
function Evidence({ f }: { f: ShownFinding }) {
  const ev = f.evidence as unknown;
  if (ev == null || typeof ev !== 'object') return null;
  const rows = (Array.isArray(ev) ? ev : [ev]).slice(0, 12) as unknown[];
  const cell = (v: unknown): string => (v == null ? 'Unavailable' : typeof v === 'object' ? (Array.isArray(v) ? v.map(cell).join(', ') : Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k.replace(/_/g, ' ')} ${cell(x)}`).join('; ')) : typeof v === 'number' ? v.toLocaleString('en-US') : String(v));
  const records = rows.filter((r): r is Record<string, unknown> => !!r && typeof r === 'object' && !Array.isArray(r));
  if (!records.length) return <p>{rows.map(cell).join('; ')}</p>;
  const keys = [...new Set(records.flatMap((r) => Object.keys(r)))];
  const total = Array.isArray(ev) ? ev.length : 1;
  return (
    <div className="nk-ch__ev">
      <table><thead><tr>{keys.map((k) => <th key={k} scope="col">{k.replace(/_/g, ' ')}</th>)}</tr></thead>
        <tbody>{records.map((r, i) => <tr key={i}>{keys.map((k) => <td key={k}>{cell(r[k])}</td>)}</tr>)}</tbody></table>
      {total > rows.length && <p>Showing {rows.length} of {total}; the canonical report lists every entry.</p>}
    </div>
  );
}
