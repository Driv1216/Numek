import '@fontsource-variable/bricolage-grotesque/standard.css';
import './modules.css';
import { useState, type ReactNode } from 'react';
import { adult } from '../../fixture';
import { byId } from './data';
import { Header } from './Landing';
import { Expand } from './Mosaic';
import { Viz } from './viz';

type TId = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h';
interface Topic { id: TId; title: string; bg: string; light?: boolean; tile: ReactNode; lead: string; body: ReactNode; side: ReactNode }

const fx = adult.findings;
const effect = (s: string) => (s.startsWith('Evidence only') ? 'Evidence only' : s.startsWith('Reduces the target') ? 'Can cap the score' : 'Changes a sub-score');
const Facts = ({ items }: { items: [string, string][] }) => <dl className="md-ch__facts">{items.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;

const topics: Topic[] = [
  {
    id: 'a', title: adult.topics[0], bg: '#1d2440', light: true,
    tile: <><span className="md-topic__big">{adult.finalScore.toFixed(1)}</span><p className="md-topic__sum">{adult.band}. Evidence {adult.evidenceScore}, held at the 69 cap because target balance is {adult.subScores[2].value}.</p><span className="md-topic__viz"><Viz id="score" /></span></>,
    lead: 'The answer first, with its reason attached.',
    body: <><p className="md-ch__body">{adult.narrative}</p><Facts items={[['Evidence score', String(adult.evidenceScore)], ['Guardrail', adult.guardrail.label], ['Final score', adult.finalScore.toFixed(1)], ['Band', adult.band]]} /><p className="md-ch__eff"><b>Next</b> {adult.nextAction}</p></>,
    side: <Viz id="score" big />,
  },
  {
    id: 'b', title: adult.topics[1], bg: '#f5b83d',
    tile: <><ol className="md-topic__list">{fx.map((f, i) => <li key={f.code}><span>{i + 1}</span><span>{f.title}</span><em>{effect(f.scoreEffect)}</em><em>{f.severity}</em></li>)}</ol><p className="md-topic__foot">Two change the score; two are evidence only. Nothing is cleaned or removed.</p></>,
    lead: 'Four findings, in the order the report gives them.',
    body: <p className="md-ch__body">Each finding says what was seen, what it may mean, what to review — and whether it changed the score. Two of the four are evidence only.</p>,
    side: <div className="md-topic-ch__side">{fx.map((f, i) => (
      <div key={f.code} className="md-card-mod"><span>{String(i + 1).padStart(2, '0')} · {f.severity} · {effect(f.scoreEffect)}</span><b>{f.title}</b><p>{f.finding} {f.evidence}</p><p><i>Review:</i> {f.review}</p></div>
    ))}</div>,
  },
  {
    id: 'c', title: adult.topics[2], bg: '#c9bdf5',
    tile: <><span className="md-topic__big md-topic__big--m">48,842 × 15</span><p className="md-topic__sum">{adult.featureColumns} features · {adult.numericFeatures} numeric · {adult.nonNumericFeatures} non-numeric · {adult.runtimeSeconds.toFixed(2)} s</p></>,
    lead: 'What was read, and how fast.',
    body: <Facts items={[['File', adult.file], ['Task', adult.task], ['Target', adult.target], ['Rows × columns', `${adult.rows.toLocaleString()} × ${adult.columns}`], ['Features', `${adult.numericFeatures} numeric, ${adult.nonNumericFeatures} non-numeric`], ['Runtime', `${adult.runtimeSeconds} s, local`], ['Generated', adult.generatedAt], ['Source', adult.source]]} />,
    side: <ul className="md-leak">{adult.columnEvidence.map((c) => <li key={c.name} className={c.role === 'target' ? 'is-target' : ''}><span>{c.name}</span><em>{c.role === 'target' ? 'target' : c.type}</em></li>)}</ul>,
  },
  {
    id: 'd', title: adult.topics[3], bg: '#ef5b3c',
    tile: <><p className="md-topic__sum">{adult.majorityBaseline}% majority · {adult.conflicts.length} conflicting groups</p><span className="md-topic__viz"><Viz id="imbalance" /></span></>,
    lead: 'A dominant class, and five pairs that disagree.',
    body: <><p className="md-ch__body">{byId.imbalance.body}</p><p className="md-ch__body">{byId.conflicts.body}</p><Facts items={byId.imbalance.facts} /></>,
    side: <Viz id="conflicts" big />,
  },
  {
    id: 'e', title: adult.topics[4], bg: '#bfe0a0',
    tile: <><p className="md-topic__sum">{adult.missing.rowRate}% of rows · three columns</p><span className="md-topic__viz"><Viz id="gaps" /></span></>,
    lead: 'Three columns, 3,620 rows.',
    body: <><p className="md-ch__body">{byId.gaps.body}</p><Facts items={[['One gap', adult.missing.rows.one.toLocaleString()], ['Two gaps', adult.missing.rows.two.toLocaleString()], ['Three or more', String(adult.missing.rows.three_plus)], ['Completeness', String(adult.subScores[0].value)]]} /></>,
    side: <Viz id="gaps" big />,
  },
  {
    id: 'f', title: adult.topics[5], bg: '#e3ddcf',
    tile: <><p className="md-topic__sum">{adult.duplicates.repeated_rows} repeated rows · hours_per_week outside fences</p><span className="md-topic__viz"><Viz id="outliers" /></span></>,
    lead: 'Repeats, and one unusual distribution.',
    body: <><p className="md-ch__body">{byId.dups.body}</p><p className="md-ch__body">{byId.outliers.body}</p><Facts items={byId.outliers.facts} /></>,
    side: <Viz id="outliers" big />,
  },
  {
    id: 'g', title: adult.topics[6], bg: '#2a2a2e', light: true,
    tile: <><p className="md-topic__sum">Five sub-scores, one critical. {adult.limits.split('.')[0]}.</p><span className="md-topic__viz"><Viz id="score" /></span></>,
    lead: 'How the number was made, and what it does not cover.',
    body: <><Facts items={adult.subScores.map((s) => [s.label, `${s.value}${'critical' in s && s.critical ? ' · critical' : ''}`] as [string, string])} /><p className="md-ch__body">{adult.guardrail.explanation} Bands: ≥85 Low, 70–84 Moderate, 50–69 Elevated, below 50 High.</p><p className="md-ch__not">{adult.limits}</p></>,
    side: <Viz id="score" big />,
  },
  {
    id: 'h', title: adult.topics[7], bg: '#cfe0ea',
    tile: <><span className="md-topic__big md-topic__big--m">sha256</span><p className="md-topic__sum">{adult.sha256.slice(0, 16)}… · every column, every computed value</p></>,
    lead: 'Every column, as computed.',
    body: <p className="md-ch__body">The appendix lists each column’s role, type, completeness, cardinality, top-value share and IQR outliers. The same values are in the strict JSON report. File sha256 {adult.sha256}.</p>,
    side: (
      <div className="md-apx" role="table" aria-label="Column evidence">
        <div role="row" className="md-apx__h"><span>Column</span><span>Type</span><span>Missing</span><span>Unique</span><span>Outliers</span></div>
        {adult.columnEvidence.map((c) => <div key={c.name} role="row"><span>{c.name}</span><span>{c.type}</span><span>{c.missing}</span><span>{c.unique}</span><span>{c.outliers}</span></div>)}
      </div>
    ),
  },
];
const T = (id: TId) => topics.find((t) => t.id === id)!;

export default function Results() {
  const [open, setOpen] = useState<TId | null>(null);
  return (
    <div className="md md--results">
      <Header here="results" />
      <section className="md-res-h">
        <div>
          <p>{adult.file} · {adult.task} · {adult.rows.toLocaleString()} rows · {adult.generatedAt}</p>
          <h1>Adult, in eight parts.</h1>
        </div>
        <p>The report’s eight topics as tiles.<br />Open one; arrows move between them.</p>
      </section>
      <section className="md-topics" aria-label="Report topics">
        {topics.map((t, i) => (
          <button key={t.id} type="button" data-topic={t.id} className={`md-topic md-slot ${t.light ? 'is-light' : ''}`} style={{ gridArea: t.id, ['--bg' as string]: t.bg, ['--d' as string]: i }} onClick={() => setOpen(t.id)}>
            <span className="md-topic__n">{String(i + 1).padStart(2, '0')}</span>
            <h3>{t.title}</h3>
            {t.tile}
          </button>
        ))}
      </section>
      {open && (
        <Expand<TId> id={open} order={topics.map((t) => t.id)} onClose={() => setOpen(null)} onNav={setOpen} origin="data-topic"
          bg={(k) => T(k).bg} light={(k) => !!T(k).light} title={(k) => T(k).title}
          bar={(k) => `${String(topics.indexOf(T(k)) + 1).padStart(2, '0')} / 08 · Adult report`}>
          {(k) => {
            const t = T(k);
            return (
              <>
                <div className="md-ch__text">
                  <h2 className="md-ch__h2--topic">{t.title}</h2>
                  <p className="md-ch__line">{t.lead}</p>
                  {t.body}
                </div>
                <div className="md-ch__viz md-ch__viz--topic">{t.side}</div>
              </>
            );
          }}
        </Expand>
      )}
    </div>
  );
}
