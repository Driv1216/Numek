import '@fontsource-variable/archivo/wdth.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import './markup.css';
import type { ReactNode } from 'react';
import { runFindings, runs, type Representation } from '../../fixture';
import { href } from '../../shell/router';
import { Wordmark } from './drawing';
import { SheetGlyph } from './glyphs';

export const sheetNo: Record<string, string> = { adult: 'A-101', german: 'A-102', bank: 'A-103', bike: 'B-201', sms: 'D-401', coco: 'E-501', finance: 'F-601' };
const groups: [Representation, string][] = [['tables', 'A · Tables'], ['outcomes', 'B · Outcomes'], ['text', 'D · Text'], ['images', 'E · Images'], ['connected', 'F · Connected']];

export function SheetIndex({ current }: { current?: string }) {
  return (
    <nav className="mk-index" aria-label="Sheets">
      {groups.map(([rep, label]) => (
        <div key={rep} style={{ display: 'contents' }}>
          <h4>{label}</h4>
          {runs.filter((r) => r.rep === rep).map((r) => (
            <a key={r.id} href={r.id === 'adult' ? href('markup', 'results') : href('markup', 'app')} aria-current={current === r.id ? 'page' : undefined}>
              <span className="no">{sheetNo[r.id]}</span>
              <span>{r.name}</span>
              <span className={`sc ${r.score == null ? 'sc--n' : ''}`}>{r.score == null ? '—' : r.score.toFixed(1)}</span>
            </a>
          ))}
        </div>
      ))}
    </nav>
  );
}

export function TopBar({ path }: { path: ReactNode }) {
  return (
    <header className="mk-bar">
      <div><Wordmark small /></div>
      <div className="mk-bar__path">{path}</div>
      <div className="mk-bar__tools">
        <span className="mk-search" aria-hidden="true"><span>Find a mark, column, sheet</span><span>⌘K</span></span>
        <a className="mk-btn mk-btn--ink" href={href('markup', 'app')}>New sheet</a>
      </div>
    </header>
  );
}

export default function App() {
  const schedule = Object.entries(runFindings).flatMap(([id, fs]) => fs.map((f, i) => ({ id, n: i + 1, ...f })));
  return (
    <div className="mk mk--app">
      <TopBar path={<><span>Local workspace</span><span>/</span><span>~/datasets</span><span>/</span><b>Set overview</b><span>· 7 sheets · nothing leaves this machine</span></>} />
      <div className="mk-work">
        <SheetIndex />
        <main className="mk-canvas">
          <div className="mk-cover__head">
            <div>
              <p className="mk-cap">Cover sheet · set issued 13 Oct 2026</p>
              <h1>Reliability set<br />~/datasets</h1>
            </div>
            <dl className="mk-res__score">
              <div><dt>Sheets</dt><dd>7</dd></div>
              <div><dt>Marks</dt><dd>{schedule.length}</dd></div>
              <div><dt>Scored</dt><dd>3</dd></div>
              <div><dt>No score defined</dt><dd>4</dd></div>
            </dl>
          </div>
          <div className="mk-thumbs">
            {runs.map((r) => (
              <a key={r.id} className="mk-thumb" href={r.id === 'adult' ? href('markup', 'results') : href('markup', 'app')}>
                <div className="mk-thumb__draw mk-sheets is-drawn" style={{ border: 0, display: 'block' }}><SheetGlyph rep={r.rep} /></div>
                <div className="mk-thumb__tb">
                  <span className="no">{sheetNo[r.id]}</span>
                  <h3>{r.name}</h3>
                  <span className="meta">{r.task} · {r.size}</span>
                  <span className={`score ${r.score == null ? 'score--n' : ''}`}>{r.score == null ? '—' : r.score.toFixed(1)}<small>{r.band ?? 'no score defined'}</small></span>
                  <span className="lead">{r.lead}</span>
                </div>
              </a>
            ))}
          </div>
          <div className="mk-drop">
            <div>
              <h3>Start a sheet</h3>
              <p>Drop a CSV, JSONL or Parquet table, an image folder with annotations, or a records-and-documents manifest. DataTrust validates and previews it here before anything runs — on this machine.</p>
            </div>
            <a className="mk-btn mk-btn--v" href={href('markup', 'results')}>Open the Adult sheet</a>
          </div>
        </main>
        <aside className="mk-schedule" aria-label="Markup schedule">
          <div className="mk-schedule__h">
            <h3>Markup schedule</h3>
            <p>All marks in this set, by sheet</p>
          </div>
          <table className="mk-sched">
            <thead><tr><th className="n">No</th><th>Sheet</th><th>Mark</th></tr></thead>
            <tbody>
              {schedule.map((m) => (
                <tr key={`${m.id}${m.n}`} onClick={() => { location.hash = m.id === 'adult' ? href('markup', 'results') : href('markup', 'app'); }}>
                  <td className="n"><span className={`mk-dotn ${m.effect === 'evidence' ? 'mk-dotn--b' : m.effect === 'none-defined' ? 'mk-dotn--o' : ''}`}>{m.n}</span></td>
                  <td className="mk-eff">{sheetNo[m.id]}</td>
                  <td>{m.title}<br /><span className="mk-eff">{m.severity} · {m.effect === 'score' ? 'affects score' : m.effect === 'evidence' ? 'evidence only' : 'no score defined'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </aside>
      </div>
    </div>
  );
}
