import '@fontsource-variable/archivo/wdth.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import './markup.css';
import { useState } from 'react';
import { adult, bike, local } from '../../fixture';
import { href } from '../../shell/router';
import { Cross, HoursDetail, TableDrawing, TitleBlock, Wordmark, useDrawn } from './drawing';
import { SheetGlyph } from './glyphs';

const anatomy = adult.findings[0];

export default function Landing() {
  const [heroRef, heroOn] = useDrawn<HTMLDivElement>();
  return (
    <div className="mk mk--landing">
      <div className="mk-frame" aria-hidden="true"><Cross className="tl" /><Cross className="tr" /><Cross className="bl" /><Cross className="br" /></div>
      <header className="mk-nav">
        <Wordmark />
        <nav aria-label="Primary">
          <a href="#anatomy">How a mark is made</a>
          <a href="#sheets">What it reads</a>
          <a href="#measure">Scores</a>
          <a href="#boundary">Local</a>
          <a href="#set">Reports</a>
        </nav>
        <a className="mk-btn mk-btn--ink" href={href('markup', 'app')}>Open DataTrust</a>
      </header>

      <section className="mk-hero">
        <div className="mk-hero__copy">
          <p className="mk-eyebrow"><span>Sheet 01</span><span>DataTrust by NUMEK</span><span>AI reliability verification</span></p>
          <h1 className="mk-display">The dataset,<br />marked up.</h1>
        </div>
        <div className="mk-hero__side">
          <p className="mk-lede">DataTrust reads the data behind your model on your own machine and marks every finding on the exact rows, columns and pages it concerns — with the evidence, the likely modelling impact, and what to review next.</p>
          <div className="mk-actions">
            <a className="mk-btn mk-btn--v" href={href('markup', 'results')}>See the Adult sheet</a>
            <a className="mk-btn" href="#anatomy">How a mark is made</a>
          </div>
        </div>
        <div className="mk-hero__sheet" ref={heroRef}>
          <div className="mk-scroll"><TableDrawing rows={12} drawn={heroOn} /></div>
          <TitleBlock rows={[
            ['Subject', 'adult.csv · 48,842 × 15'],
            ['Task', 'Classification · binary'],
            ['Run', 'Local · 0.18 s'],
            ['Marks', '3 findings · 1 review prompt'],
            ['Drawn', '14 of 48,842 rows'],
            ['Sheet', 'A-101'],
          ]} />
        </div>
      </section>

      <section className="mk-sec" id="anatomy">
        <div className="mk-sec__head">
          <span className="mk-sec__no">02</span>
          <h2 className="mk-h2">Anatomy of a mark</h2>
          <p>A mark is never just a warning. Each one carries the same five dimensions, in the same order, so an ML engineer and a risk reviewer read the same thing.</p>
        </div>
        <Anatomy />
      </section>

      <section className="mk-sec" id="sheets">
        <div className="mk-sec__head">
          <span className="mk-sec__no">03</span>
          <h2 className="mk-h2">Six kinds of sheet</h2>
          <p>The same discipline across representations. Each has its own kind of mark, because a near-duplicate sentence is not a duplicate row.</p>
        </div>
        <SheetSet />
      </section>

      <section className="mk-sec" id="measure">
        <div className="mk-sec__head">
          <span className="mk-sec__no">04</span>
          <h2 className="mk-h2">Measured, not judged</h2>
          <p>Where a score is defined, it is drawn like a dimension: what the evidence measured, and the guardrail that held it. Where none is defined, the sheet says so.</p>
        </div>
        <Measure />
      </section>

      <section className="mk-sec" id="boundary">
        <div className="mk-sec__head">
          <span className="mk-sec__no">05</span>
          <h2 className="mk-h2">Boundary detail</h2>
          <p>Analysis happens inside the outline. The browser UI binds to loopback; optional models are pinned files you provision; nothing is fetched at run time.</p>
        </div>
        <Boundary />
      </section>

      <section className="mk-sec" id="set">
        <div className="mk-sec__head">
          <span className="mk-sec__no">06</span>
          <h2 className="mk-h2">The issued set</h2>
          <p>Every run issues one result in three forms. The HTML is canonical; the PDF opens with portrait decision pages and closes with a landscape technical appendix; the JSON holds every computed value.</p>
        </div>
        <IssuedSet />
      </section>

      <footer className="mk-foot">
        <div className="mk-foot__cta">
          <h2 className="mk-display mk-display--m">Draw your own<br />first sheet.</h2>
          <code className="mk-cmd">$ {local.commands[1]}</code>
          <a className="mk-btn mk-btn--v" href={href('markup', 'app')}>Open DataTrust</a>
        </div>
        <TitleBlock rows={[
          ['Company', 'NUMEK · AI reliability verification'],
          ['Product', 'DataTrust · dataset reliability'],
          ['Research', 'Model confidence and LLM grounding are directions, not products'],
          ['Issued', 'Visual lab v3 · concept 01'],
        ]} />
      </footer>
    </div>
  );
}

function Anatomy() {
  const [ref, on] = useDrawn<HTMLDivElement>();
  const parts: [string, string][] = [
    ['Finding', anatomy.finding],
    ['Evidence', anatomy.evidence],
    ['Modelling impact', anatomy.impact],
    ['Review next', anatomy.review],
    ['Score effect', anatomy.scoreEffect],
  ];
  const g = adult.conflicts[0];
  const show = ['age', 'workclass', 'education', 'occupation', 'hours_per_week', 'native_country'];
  return (
    <div className={`mk-anat ${on ? 'is-drawn' : ''}`} ref={ref}>
      <div className="mk-anat__mark"><span className="mk-pin">1</span><span>{anatomy.title}</span><span className="mk-tag">Moderate</span></div>
      <ol className="mk-dim">
        {parts.map(([k, v], i) => (
          <li key={k} style={{ ['--i' as string]: i }}>
            <span className="mk-dim__k">{String.fromCharCode(65 + i)} · {k}</span>
            <p>{v}</p>
          </li>
        ))}
      </ol>
      <div className="mk-anat__detail">
        <p className="mk-cap">Detail 1A · group 1 of 5 · rows {g.rows.join(' & ')} · identical in all 14 features</p>
        <div className="mk-scroll">
          <table className="mk-rows">
            <thead><tr><th>row</th>{show.map((c) => <th key={c}>{c}</th>)}<th>… 8 more</th><th className="is-v">{adult.target}</th></tr></thead>
            <tbody>
              {g.rows.map((r, i) => (
                <tr key={r}><td>{r}</td>{show.map((c) => <td key={c}>{String(g.features[c])}</td>)}<td>identical</td><td className="is-v">{g.labels[i]}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const sheets = [
  { no: 'A-101', rep: 'tables' as const, name: 'Tables', mark: 'Mark on a row group or column', body: 'Profiling, missingness, exact duplicates, feature-identical rows that disagree on the label, strong versus review-only leakage names.', ex: 'Adult · 48,842 × 15' },
  { no: 'B-201', rep: 'outcomes' as const, name: 'Outcomes', mark: 'Mark on a relationship', body: 'Explicit numerical targets and constraints; bounded copy, affine and two-feature-sum relationships; variation across repeated inputs.', ex: `Bike hourly · ${bike.relationship}` },
  { no: 'C-301', rep: 'time' as const, name: 'Time', mark: 'Mark on a clock', body: 'Exact clocks, declared availability and revisions, coverage of schedules and panels, supplied evaluation plans.', ex: 'Temporal CSV and Parquet' },
  { no: 'D-401', rep: 'text' as const, name: 'Text', mark: 'Mark on a passage', body: 'Corpora, annotations, QA, conversations and retrieval provenance; calibrated, bounded near-duplicate search.', ex: 'SMS · 5,574 records' },
  { no: 'E-501', rep: 'images' as const, name: 'Images', mark: 'Mark on a region', body: 'Orientation and coordinate compatibility, segmentation integrity, perceptual candidates kept as review items.', ex: 'COCO subset · 128 images' },
  { no: 'F-601', rep: 'connected' as const, name: 'Connected', mark: 'Mark across documents', body: 'Records reconciled against native PDF and DOCX with exact page and cell locators; competing evidence retained.', ex: '20 records ↔ 21 PDFs' },
];

function SheetSet() {
  const [ref, on] = useDrawn<HTMLDivElement>();
  return (
    <div className={`mk-sheets ${on ? 'is-drawn' : ''}`} ref={ref}>
      {sheets.map((s, i) => (
        <article key={s.no} className="mk-sheet" style={{ ['--i' as string]: i }}>
          <div className="mk-sheet__draw"><SheetGlyph rep={s.rep} /></div>
          <div className="mk-sheet__tb">
            <span className="mk-sheet__no">{s.no}</span>
            <h3>{s.name}</h3>
            <span className="mk-sheet__mark">{s.mark}</span>
          </div>
          <p>{s.body}</p>
          <p className="mk-sheet__ex">{s.ex}</p>
        </article>
      ))}
    </div>
  );
}

function Measure() {
  const [ref, on] = useDrawn<HTMLDivElement>();
  const x = (v: number) => (v / 100) * 900;
  return (
    <div className={`mk-measure ${on ? 'is-drawn' : ''}`} ref={ref}>
      <div className="mk-scroll">
        <svg viewBox="-170 -70 1130 300" className="mk-scale" role="img" aria-label="Adult: evidence score 89.15 held to a final score of 69.0 by the critical sub-score guardrail.">
          <defs><pattern id="mk-hatch2" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" className="hatch" /></pattern></defs>
          <rect x={x(69)} y={0} width={x(100) - x(69)} height={40} fill="url(#mk-hatch2)" className="capzone" />
          <line x1={0} x2={900} y1={40} y2={40} className="axis" pathLength={1} />
          {Array.from({ length: 11 }, (_, i) => <g key={i}><line x1={x(i * 10)} x2={x(i * 10)} y1={40} y2={i % 5 ? 48 : 54} className="axis" /><text x={x(i * 10)} y={70} className="lab" textAnchor="middle">{i * 10}</text></g>)}
          <line x1={x(89.15)} x2={x(89.15)} y1={-30} y2={40} className="dimline" pathLength={1} />
          <text x={x(89.15)} y={-40} textAnchor="middle" className="lab lab--b">EVIDENCE 89.15</text>
          <line x1={x(69)} x2={x(69)} y1={-30} y2={40} className="capline" pathLength={1} />
          <text x={x(69)} y={-40} textAnchor="middle" className="lab lab--v">CAP 69.0</text>
          <path d={`M${x(89.15)} -14 H${x(69) + 8}`} className="arrow" pathLength={1} />
          <path d={`M${x(69) + 14} -20 L${x(69) + 4} -14 L${x(69) + 14} -8`} className="arrowhead" />
          <text x={x(79)} y={-20} textAnchor="middle" className="lab">GUARDRAIL</text>
          <g transform="translate(0 110)">
            {adult.subScores.map((s, i) => (
              <g key={s.key} transform={`translate(0 ${i * 22})`}>
                <text x={-8} y={10} textAnchor="end" className="lab lab--k">{s.label.toUpperCase()}</text>
                <line x1={0} x2={x(s.value)} y1={6} y2={6} className={`sub ${s.critical ? 'sub--crit' : ''}`} pathLength={1} style={{ ['--i' as string]: i }} />
                <text x={x(s.value) + 8} y={10} className={`lab ${s.critical ? 'lab--v' : ''}`}>{s.value.toFixed(2)}{s.critical ? ' · CRITICAL' : ''}</text>
              </g>
            ))}
          </g>
        </svg>
      </div>
      <div className="mk-measure__notes">
        <div>
          <p className="mk-cap">Sheet A-101 · Adult · classification</p>
          <p className="mk-big">69.0 <span>Elevated</span></p>
          <p>{adult.guardrail.explanation} Five transparent sub-scores; a weak one cannot hide behind a healthy average.</p>
        </div>
        <div className="mk-void">
          <p className="mk-cap">Sheet B-201 · Bike hourly · regression</p>
          <p className="mk-big mk-big--void">— <span>No score</span></p>
          <p>Regression has no universal reliability score. The sheet carries its marks — {bike.relationship}, with both components declared unavailable at prediction time — and nothing pretends to sum them.</p>
        </div>
      </div>
    </div>
  );
}

function Boundary() {
  const [ref, on] = useDrawn<HTMLDivElement>();
  return (
    <div className={`mk-boundary ${on ? 'is-drawn' : ''}`} ref={ref}>
      <div className="mk-scroll">
        <svg viewBox="0 0 1000 360" role="img" aria-label="Machine boundary: inputs, DataTrust and reports inside; network outside with no connection at analysis time.">
          <rect x={30} y={30} width={700} height={300} className="bound" pathLength={1} />
          <text x={46} y={56} className="lab lab--k">YOUR MACHINE · LOOPBACK 127.0.0.1</text>
          {[['INPUTS', 'csv · jsonl · parquet', 'images · pdf · docx', 70], ['DATATRUST', 'local engine', 'pinned optional models', 290], ['REPORT', 'html · pdf · json', 'review snapshots', 510]].map(([t, a, b, xx]) => (
            <g key={t as string} transform={`translate(${xx} 130)`}>
              <rect width={170} height={110} className="box" pathLength={1} />
              <text x={14} y={30} className="lab lab--k">{t}</text>
              <text x={14} y={62} className="lab">{a}</text>
              <text x={14} y={80} className="lab">{b}</text>
            </g>
          ))}
          <path d="M240 185 H290 M460 185 H510" className="flow" pathLength={1} />
          <path d="M283 179 L290 185 L283 191 M503 179 L510 185 L503 191" className="flowhead" />
          <path d="M730 185 H860" className="nolink" pathLength={1} />
          <path d="M786 168 L804 202 M804 168 L786 202" className="nox" />
          <text x={870} y={180} className="lab lab--k">NETWORK</text>
          <text x={870} y={198} className="lab">not used at analysis time</text>
        </svg>
      </div>
      <ul className="mk-facts">
        {local.facts.map((f) => <li key={f.label}><span>{f.value}</span>{f.label}</li>)}
      </ul>
    </div>
  );
}

function IssuedSet() {
  const [ref, on] = useDrawn<HTMLDivElement>();
  const [open, setOpen] = useState<number | null>(null);
  const items = [
    { k: 'HTML', t: 'Canonical report', d: 'Eight topics, standalone, print-safe visuals.', w: 200, h: 260 },
    { k: 'PDF', t: 'Decision pages', d: 'Portrait: decision summary, priority actions.', w: 200, h: 260 },
    { k: 'PDF', t: 'Technical appendix', d: 'Landscape: complete per-column evidence.', w: 280, h: 200 },
    { k: 'JSON', t: 'Strict evidence', d: 'Every computed value, schema-versioned.', w: 200, h: 260 },
  ];
  return (
    <div className={`mk-set ${on ? 'is-drawn' : ''}`} ref={ref}>
      {items.map((it, i) => (
        <button key={i} className={`mk-page ${open === i ? 'is-open' : ''}`} style={{ ['--i' as string]: i, width: it.w, height: it.h }} onMouseEnter={() => setOpen(i)} onFocus={() => setOpen(i)} onMouseLeave={() => setOpen(null)} onBlur={() => setOpen(null)}>
          <span className="mk-page__k">{it.k}</span>
          <span className="mk-page__lines" aria-hidden="true">{Array.from({ length: it.k === 'JSON' ? 11 : 7 }, (_, j) => <i key={j} style={{ width: `${it.k === 'JSON' ? 30 + ((j * 37) % 60) : 90 - ((j * 23) % 40)}%` }} />)}</span>
          <span className="mk-page__t">{it.t}</span>
          <span className="mk-page__d">{it.d}</span>
        </button>
      ))}
      <div className="mk-set__hours">
        <p className="mk-cap">Detail 2 · as it appears in the appendix</p>
        <HoursDetail />
      </div>
    </div>
  );
}
