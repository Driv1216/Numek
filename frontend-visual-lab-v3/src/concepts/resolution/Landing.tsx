import '@fontsource-variable/martian-mono';
import './resolution.css';
import { useEffect, useState } from 'react';
import { adult, company, local, runs } from '../../fixture';
import { href } from '../../shell/router';
import { TileCard, Wall } from './Wall';
import { runColour, tiles, units, type Tile, type Unit } from './tiles';

export function Status() {
  const [t, setT] = useState(() => new Date());
  useEffect(() => { const i = setInterval(() => setT(new Date()), 1000); return () => clearInterval(i); }, []);
  return <span className="rs-status">RUNS {runs.length} · ARTEFACTS {tiles.length} · NETWORK 0 · LOCAL {t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>;
}

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="rs-head">
      <a className="rs-head__wm" href={href('resolution', 'landing')}>NUMEK</a>
      <Status />
      <nav aria-label="Primary">
        <a href={href('resolution', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>Wall</a>
        <a href={href('resolution', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Runs</a>
        <a href={href('resolution', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
    </header>
  );
}

/** The evidence sheet: opening a tile takes on that run's colour. */
export function Sheet({ t, onClose }: { t: Tile; onClose: () => void }) {
  const r = runs.find((x) => x.id === t.run)!;
  useEffect(() => { const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); addEventListener('keydown', k); return () => removeEventListener('keydown', k); }, [onClose]);
  return (
    <aside className="rs-sheet" style={{ ['--c' as string]: runColour[t.run] }} role="dialog" aria-label={t.title}>
      <button type="button" className="rs-sheet__x" onClick={onClose} autoFocus>Close ✕</button>
      <span className="rs-k">{r.name.toUpperCase()} · {t.unit.toUpperCase()}</span>
      <h2>{t.title}</h2>
      <div className="rs-sheet__body">{t.body}</div>
      {t.finding && <p className="rs-sheet__f">Finding · {t.finding}</p>}
      {t.detail && <p>{t.detail}</p>}
      <dl className="rs-kv"><div><dt>run</dt><dd>{r.file}</dd></div><div><dt>task</dt><dd>{r.task}</dd></div><div><dt>score</dt><dd>{r.score == null ? 'none defined' : `${r.score.toFixed(1)} · ${r.band}`}</dd></div></dl>
    </aside>
  );
}

export function Index({ list, onOpen }: { list: Tile[]; onOpen: (t: Tile) => void }) {
  const [hov, setHov] = useState<Tile>(list[0]);
  const counts = Object.fromEntries(runs.map((r) => [r.id, list.filter((t) => t.run === r.id).length]));
  return (
    <div className="rs-index">
      <div className="rs-index__prev">{hov && <TileCard t={hov} onOpen={onOpen} />}</div>
      <ol>
        {list.map((t) => (
          <li key={t.id}><button type="button" onMouseEnter={() => setHov(t)} onFocus={() => setHov(t)} onClick={() => onOpen(t)}>
            <b>{t.title}<sup>{t.run}{counts[t.run]}</sup></b><span>{t.caption}</span><em>{t.unit}</em>
          </button></li>
        ))}
      </ol>
    </div>
  );
}

export default function Landing() {
  const [view, setView] = useState<'wall' | 'index'>('wall');
  const [unit, setUnit] = useState<Unit | 'all'>('all');
  const [open, setOpen] = useState<Tile | null>(null);
  const list = tiles.filter((t) => unit === 'all' || t.unit === unit);
  return (
    <div className="rs rs--landing" style={{ ['--accent' as string]: open ? runColour[open.run] : '#9BE15D' }}>
      <Header here="landing" />
      <section className="rs-hero">
        {view === 'wall' ? <Wall list={list} onOpen={setOpen} active={open?.id} /> : <Index list={list} onOpen={setOpen} />}
        <p className="rs-corner rs-corner--tl" aria-hidden="true">NUMEK</p>
        <p className="rs-corner rs-corner--br" aria-hidden="true">DATATRUST</p>
        <div className="rs-ctl">
          <div className="rs-pill" role="tablist" aria-label="View">
            <button type="button" role="tab" aria-selected={view === 'wall'} onClick={() => setView('wall')}>Wall</button>
            <button type="button" role="tab" aria-selected={view === 'index'} onClick={() => setView('index')}>Index</button>
          </div>
          <div className="rs-pill rs-pill--units" role="group" aria-label="Filter by unit">
            {units.map(([u, l]) => <button key={u} type="button" aria-pressed={unit === u} onClick={() => setUnit(u)}>{l}</button>)}
          </div>
        </div>
        {open && <Sheet t={open} onClose={() => setOpen(null)} />}
      </section>
      <section className="rs-about">
        <p className="rs-k">WHAT YOU ARE LOOKING AT</p>
        <p className="rs-lede">Every tile is something DataTrust produced on this machine: a row, a distribution, a score, a page of a report, a reconciliation. Each one arrives coarse and resolves to exact — evidence is what sharpens a claim.</p>
        <dl className="rs-kv rs-kv--wide">
          <div><dt>runs</dt><dd>{runs.length}</dd></div><div><dt>adult</dt><dd>{adult.rows.toLocaleString()} rows · {adult.finalScore.toFixed(1)} {adult.band}</dd></div><div><dt>scored</dt><dd>classification only</dd></div><div><dt>network</dt><dd>0 calls during analysis</dd></div>
        </dl>
        <pre className="rs-pre rs-pre--cmd">$ {local.commands[0]}{'\n'}{local.cliOutput.join('\n')}</pre>
      </section>
      <footer className="rs-foot"><span>NUMEK · {company.line}</span><span>{company.direction}</span><span>Findings support human review; they are not certification.</span></footer>
    </div>
  );
}
