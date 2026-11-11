import '@fontsource-variable/archivo/wdth.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import './markup.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { href } from '../../shell/router';
import { HoursDetail, TableDrawing, marks, useDrawn, type MarkId } from './drawing';
import { SheetIndex, TopBar } from './App';

const byCode = Object.fromEntries(adult.findings.map((f) => [f.code, f]));

export default function Results() {
  const [active, setActive] = useState<MarkId | null>(1);
  const [ref, on] = useDrawn<HTMLDivElement>();
  const m = marks.find((x) => x.id === active);
  const f = m ? byCode[m.code] : null;
  const toggle = (id: MarkId) => setActive((a) => (a === id ? null : id));
  const [scale, setScale] = useState<'fit' | 'full'>('fit');

  return (
    <div className="mk mk--app">
      <TopBar path={<><span>Local workspace</span><span>/</span><a href={href('markup', 'app')}>~/datasets</a><span>/</span><b>A-101 Adult</b><span>· generated {adult.generatedAt}</span></>} />
      <div className="mk-work">
        <SheetIndex current="adult" />
        <main className="mk-canvas" style={{ padding: 0 }}>
          <nav className="mk-tbar" aria-label="Views of this sheet">
            <a aria-current="page" href={href('markup', 'results')}>Elevation · marks</a>
            <a href={href('markup', 'results')}>Columns · 15</a>
            <a href={href('markup', 'results')}>Method & limits</a>
            <a href={href('markup', 'results')}>Issue · HTML / PDF / JSON</a>
          </nav>
          <div style={{ padding: '24px 32px 60px' }}>
            <div className="mk-res__head">
              <div>
                <p className="mk-cap">Sheet A-101 · {adult.file} · {adult.task} · target {adult.target}</p>
                <h1>Adult</h1>
              </div>
              <dl className="mk-res__score" aria-label="Score path">
                <div><dt>Evidence score</dt><dd>{adult.evidenceScore}</dd></div>
                <div><dt>Guardrail cap</dt><dd className="v">{adult.guardrail.cap.toFixed(1)}</dd></div>
                <div><dt>Final · {adult.band}</dt><dd className="v">{adult.finalScore.toFixed(1)}</dd></div>
                <div><dt>Rows · cols</dt><dd>48,842 · 15</dd></div>
              </dl>
            </div>
            <div className={`mk-sheetwrap mk-sheetwrap--${scale}`} ref={ref}>
              <div className="mk-zoom" role="group" aria-label="Drawing scale">
                <button aria-pressed={scale === 'fit'} onClick={() => setScale('fit')}>Fit</button>
                <button aria-pressed={scale === 'full'} onClick={() => setScale('full')}>1 : 1</button>
              </div>
              <div className="mk-scroll"><TableDrawing rows={10} drawn={on} active={active} onMark={toggle} showCallouts={false} /></div>
            </div>
            <div className="mk-details">
              <section>
                <h4>Detail 2 · hours_per_week · 1:1 · all 48,842 rows</h4>
                <HoursDetail width={560} height={170} />
              </section>
              <section>
                <h4>Detail 1 · the five conflicting groups · 10 rows</h4>
                <div className="mk-groups">
                  {adult.conflicts.map((g) => (
                    <button key={g.id} className="mk-group" onClick={() => setActive(1)} style={{ textAlign: 'left', cursor: 'pointer' }}>
                      <span>G{g.id}</span>
                      <span className="who">rows {g.rows.join(', ')} · {String(g.features.age)} · {String(g.features.education)} · {String(g.features.occupation ?? '?')}</span>
                      <span className="lbls">{g.labels.map((l, i) => <span key={i}>{l}</span>)}</span>
                    </button>
                  ))}
                </div>
                <h4 style={{ marginTop: 18 }}>Detail 4 · target · {adult.classes.le50k.toLocaleString()} : {adult.classes.gt50k.toLocaleString()}</h4>
                <svg viewBox="0 0 400 34" style={{ width: '100%' }} role="img" aria-label="Target split 76.07% at most 50K, 23.93% over 50K">
                  <rect x="0" y="4" width={400 * 0.7607} height="18" fill="none" stroke="#161513" />
                  <rect x={400 * 0.7607} y="4" width={400 * 0.2393} height="18" fill="rgba(226,69,43,.15)" stroke="#e2452b" />
                  <text x="6" y="17" className="lab">≤50K · 76.07%</text>
                  <text x={400 * 0.7607 + 6} y="17" className="lab lab--v">&gt;50K · 23.93%</text>
                </svg>
              </section>
            </div>
            <p className="mk-cap" style={{ marginTop: 18, maxWidth: 900, textTransform: 'none', lineHeight: 1.5 }}>{adult.limits}</p>
          </div>
        </main>
        <aside className="mk-schedule" aria-label="Marks on this sheet">
          <div className="mk-schedule__h">
            <h3>Schedule · A-101</h3>
            <p>Select a mark to isolate it on the drawing</p>
          </div>
          {f && m && (
            <div className="mk-finding">
              <h3><span className={`mk-dotn ${m.tone === 'b' ? 'mk-dotn--b' : ''}`}>{m.id}</span>{f.title}</h3>
              <dl>
                <div><dt>Finding · {f.severity}</dt><dd>{f.finding}</dd></div>
                <div><dt>Evidence</dt><dd>{f.evidence}</dd></div>
                <div><dt>Modelling impact</dt><dd>{f.impact}</dd></div>
                <div><dt>Review next</dt><dd>{f.review}</dd></div>
                <div><dt>Score effect</dt><dd>{f.scoreEffect}</dd></div>
              </dl>
            </div>
          )}
          <table className="mk-sched">
            <thead><tr><th className="n">No</th><th>Mark</th><th>Effect</th></tr></thead>
            <tbody>
              {marks.map((x) => (
                <tr key={x.id} className={active === x.id ? 'is-on' : ''} onClick={() => toggle(x.id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && toggle(x.id)}>
                  <td className="n"><span className={`mk-dotn ${x.tone === 'b' ? 'mk-dotn--b' : ''}`}>{x.id}</span></td>
                  <td>{byCode[x.code].title}<br /><span className="mk-eff">{x.line}</span></td>
                  <td className="mk-eff">{byCode[x.code].scoreEffect.startsWith('Evidence only') ? 'evidence only' : 'score'}</td>
                </tr>
              ))}
              <tr><td className="n"><span className="mk-dotn mk-dotn--o">G</span></td><td>Guardrail · critical sub-score<br /><span className="mk-eff">Target balance 47.86 caps the score at 69.0</span></td><td className="mk-eff">cap</td></tr>
            </tbody>
          </table>
          <div style={{ padding: 18 }}>
            <p className="mk-cap">Sub-scores</p>
            {adult.subScores.map((s) => (
              <div key={s.key} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 48px', gap: 8, alignItems: 'center', fontSize: 12.5, marginBottom: 6 }}>
                <span>{s.label}</span>
                <span style={{ height: 6, background: '#d9d4c8', position: 'relative' }}><span style={{ position: 'absolute', inset: 0, width: `${s.value}%`, background: s.critical ? '#e2452b' : '#161513' }} /></span>
                <span className="mk-eff" style={{ textAlign: 'right', color: s.critical ? '#e2452b' : undefined }}>{s.value.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
