import '@fontsource-variable/bricolage-grotesque/standard.css';
import './modules.css';
import { useRef, useState } from 'react';
import { runs } from '../../fixture';
import { href } from '../../shell/router';
import { mods, runStates, type ModId } from './data';
import { Header } from './Landing';
import { Chapter, Tile } from './Mosaic';
import { Viz } from './viz';

/** Which run each drawing is made from. A drawing only appears on a tile when it shows the selected run. */
const drawnFrom: Record<ModId, string | null> = {
  score: 'adult', gaps: 'adult', dups: 'adult', conflicts: 'adult', imbalance: 'adult', leakage: 'adult', outliers: 'adult',
  relations: 'bike', time: null, text: 'sms', images: 'coco', docs: 'finance', local: '*', reports: '*',
};
const runName = (id: string) => runs.find((r) => r.id === id)?.name ?? id;

export default function App() {
  const [run, setRun] = useState('adult');
  const [open, setOpen] = useState<ModId | null>(null);
  const main = useRef<HTMLElement>(null);
  const r = runs.find((x) => x.id === run)!;
  const st = runStates[run];
  const applies = mods.filter((m) => st[m.id]).map((m) => m.id);

  return (
    <div className="md md--app">
      <Header here="app" />
      <div className="md-ws">
        <nav className="md-runs" aria-label="Local runs">
          {runs.map((x) => (
            <button key={x.id} type="button" className={x.id === run ? 'is-on' : ''} aria-pressed={x.id === run} onClick={() => { setOpen(null); setRun(x.id); }}>
              <b>{x.name}</b>
              <span>{x.rep} · {x.size}</span>
              <span>{x.score == null ? 'No score defined' : `${x.score.toFixed(1)} · ${x.band}`}</span>
            </button>
          ))}
        </nav>
        <main ref={main} className="md-main">
          <div className="md-main__h">
            <h1>{r.name}</h1>
            <p>{r.file} · {r.task}<br />{r.when} · {r.runtime} · {applies.length} of 14 modules apply{run === 'adult' && <> · <a href={href('modules', 'results')}>Open report ↗</a></>}</p>
          </div>
          <section className="md-mosaic" aria-label={`Modules for ${r.name}`}>
            {mods.map((m, i) => {
              const s = st[m.id];
              const src = drawnFrom[m.id];
              const showViz = !!s && (src === run || src === '*');
              return (
                <div key={`${run}-${m.id}`} className="md-slot" style={{ gridArea: m.area, ['--d' as string]: i * 0.5 }}>
                  <Tile m={m} onOpen={setOpen} dim={!s}>
                    <span className="md-tile__fig md-tile__fig--state">
                      <b className={s ? `is-${s.tone}` : ''}>{s ? s.label : 'Not for this data'}</b>
                      <span>{s ? s.detail : m.line}</span>
                    </span>
                    {showViz && <span className="md-tile__viz"><Viz id={m.id} /></span>}
                  </Tile>
                </div>
              );
            })}
          </section>
          {open && (
            <Chapter id={open} within={main.current} onClose={() => setOpen(null)} onNav={setOpen}
              extra={(m) => {
                const s = st[m.id];
                const src = drawnFrom[m.id];
                return (
                  <div className="md-ch__run">
                    <span>In {r.name}</span>
                    <b>{s ? s.label : 'Not for this data'}</b>
                    <p>{s ? s.detail : `${m.name} reads ${m.rep.toLowerCase()} data; ${r.name} is ${r.rep}.`}</p>
                    {src && src !== '*' && src !== run && <em>The example and drawing below are from {runName(src)}.</em>}
                  </div>
                );
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
}
