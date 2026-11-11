import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './camera.css';
import { useState } from 'react';
import { adult, local } from '../../fixture';
import { ColumnsCard, ConflictCard, FindingsCard, HoursCard, Icon, Overview, ScoreCard, Sidebar, SubScores, Topbar, type Tab } from './ui';

export default function Results() {
  const [tab, setTab] = useState<Tab>('overview');
  const [open, setOpen] = useState<string | null>(null);
  const [exp, setExp] = useState(false);
  const [grp, setGrp] = useState(0);
  return (
    <div className="cm cm--results">
      <div className="cm-app">
        <Sidebar active="adult" link />
        <div className="cm-main" onClick={(e) => { if (exp && !(e.target as HTMLElement).closest('.cm-top__r')) setExp(false); }}>
          <Topbar tab={tab} onTab={setTab} exportOpen={exp} onExport={() => setExp((v) => !v)} />
          {tab === 'overview' && <Overview open={open} onOpen={setOpen} />}
          {tab === 'findings' && (
            <div className="cm-pane cm-two">
              <FindingsCard open={open ?? adult.findings[0].code} onOpen={setOpen} />
              <div style={{ display: 'grid', gap: 14 }}><ScoreCard /><SubScores /></div>
            </div>
          )}
          {tab === 'columns' && <div className="cm-pane"><ColumnsCard /></div>}
          {tab === 'evidence' && (
            <div className="cm-pane cm-two">
              <div style={{ display: 'grid', gap: 14 }}>
                <section className="cm-card">
                  <div className="cm-card__h"><span>Conflicting label groups</span><span className="cm-muted">{adult.conflicts.length} groups · 10 rows</span></div>
                  <div className="cm-groups">
                    {adult.conflicts.map((g, i) => (
                      <button key={g.id} type="button" className={i === grp ? 'is-on' : ''} aria-pressed={i === grp} onClick={() => setGrp(i)}>
                        <span className="cm-mono">group {g.id}</span>
                        <span className="cm-mono">rows {g.rows.map((r) => r.toLocaleString()).join(' · ')}</span>
                        <span className="cm-mono cm-muted">{g.labels.join(' / ')}</span>
                      </button>
                    ))}
                  </div>
                </section>
                <ConflictCard group={grp} />
              </div>
              <div style={{ display: 'grid', gap: 14 }}>
                <HoursCard />
                <section className="cm-card cm-ds">
                  <div className="cm-card__h"><span>Duplicates and gaps</span><span className="cm-muted">no finding</span></div>
                  <dl>
                    <div><dt>Duplicate groups</dt><dd>{adult.duplicates.groups}</dd></div>
                    <div><dt>Repeated rows</dt><dd>{adult.duplicates.repeated_rows} · largest group {adult.duplicates.largest}</dd></div>
                    <div><dt>Empty cells</dt><dd>{adult.missing.cells.toLocaleString()} · {adult.missing.cellRate}% of feature cells</dd></div>
                    <div><dt>Rows with a gap</dt><dd>{(adult.missing.rows.one + adult.missing.rows.two + adult.missing.rows.three_plus).toLocaleString()} · {adult.missing.rowRate}%</dd></div>
                  </dl>
                </section>
              </div>
            </div>
          )}
          {tab === 'report' && (
            <div className="cm-pane cm-two">
              <section className="cm-card">
                <div className="cm-card__h"><span>Report topics</span><span className="cm-muted">canonical HTML</span></div>
                <ol className="cm-topics">{adult.topics.map((t) => <li key={t}>{t}</li>)}</ol>
                <p className="cm-note">{adult.limits}</p>
              </section>
              <section className="cm-card">
                <div className="cm-card__h"><span>Files</span><span className="cm-muted">{adult.generatedAt}</span></div>
                <div className="cm-files">
                  {[['adult.html', 'Canonical · eight topics'], ['adult.pdf', 'Decision pages + appendix'], ['adult.json', 'Strict, complete']].map(([f, n]) => <div key={f}>{Icon.file}<b>{f}</b><span>{n}</span></div>)}
                </div>
                <p className="cm-note cm-mono" style={{ wordBreak: 'break-word' }}>$ {local.commands[0]}<br />{local.cliOutput.join(' · ')}</p>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
