import { useEffect, useState, type ReactNode } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { useFitText, useInView } from '../../shared/hooks';
import {
  adult,
  audits,
  capabilities,
  evidenceScore,
  fmt,
  imbalanceRatio,
  majorityShare,
  pct,
  principles,
  type Audit,
} from '../../shared/data';
import { PopulationField } from './PopulationField';
import './census.css';
import '@fontsource-variable/archivo/wdth';
import '@fontsource/newsreader/400';
import '@fontsource/newsreader/400-italic';
import '@fontsource/newsreader/500';

const C = 'census';
const SLATE = '#3c4f63';
const OCHRE = '#c48a1c';
const CLASS_GROUPS = [
  { count: adult.classes[0].count, color: SLATE },
  { count: adult.classes[1].count, color: OCHRE },
];

function Masthead({ children, tag = 'h1' }: { children: string; tag?: 'h1' | 'h2' }) {
  const ref = useFitText<HTMLSpanElement>([children]);
  const Tag = tag;
  return (
    <Tag className={`cn-mast cn-mast--${tag}`}>
      <span ref={ref}>{children}</span>
    </Tag>
  );
}

function Leader({ k, v, strong }: { k: ReactNode; v: ReactNode; strong?: boolean }) {
  return (
    <div className={`cn-leader${strong ? ' is-strong' : ''}`}>
      <span className="cn-leader-k">{k}</span>
      <span className="cn-leader-dots" aria-hidden="true" />
      <span className="cn-leader-v">{v}</span>
    </div>
  );
}

const sentences: Record<Screen, [string, string]> = {
  landing: ['Every dataset is a population.', 'DataTrust reads all of it before you train.'],
  workspace: ['Seven audits on this machine.', 'Nothing has left it.'],
  results: ['Adult, 48,842 people.', 'Four things worth a closer look.'],
};

function Bar({ screen }: { screen: Screen }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="cn-bar">
      <Go to={href(C)} className="cn-wordmark" label="DataTrust home">
        NUMEK <span>DataTrust</span>
      </Go>
      <p className="cn-sentence">
        {sentences[screen][0]}
        <br />
        {sentences[screen][1]}
      </p>
      <nav className="cn-nav" aria-label="Concept screens">
        <Go to={href(C, 'workspace')} className={screen === 'workspace' ? 'is-on' : ''}>
          Workspace
        </Go>
        <Go to={href(C, 'results')} className={screen === 'results' ? 'is-on' : ''}>
          Adult audit
        </Go>
        <button className="cn-menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          Menu <i aria-hidden="true" />
        </button>
      </nav>
      {open && (
        <div className="cn-drawer" role="dialog" aria-label="Menu">
          <Go to={href(C)}>Introduction</Go>
          <Go to={href(C, 'workspace')}>Workspace</Go>
          <Go to={href(C, 'results')}>Adult audit</Go>
          <Go to="#/">All concepts</Go>
        </div>
      )}
    </header>
  );
}

function Foot() {
  const ref = useFitText<HTMLSpanElement>();
  return (
    <footer className="cn-foot">
      <div className="cn-foot-meta">
        <Leader k="Local workspace" v="~/numek/audits" />
        <Leader k="Reports" v="HTML, PDF, JSON" />
      </div>
      <p className="cn-foot-mark" aria-hidden="true">
        <span ref={ref}>NUMEK</span>
      </p>
    </footer>
  );
}

function Population({ caption = true }: { caption?: boolean }) {
  const [ref, seen] = useInView<HTMLDivElement>(0.2);
  // Narrow screens group more rows per square so the field keeps its proportions.
  const [perDot] = useState(() => (window.innerWidth < 700 ? 100 : 20));
  return (
    <figure className="cn-pop" ref={ref}>
      <PopulationField groups={CLASS_GROUPS} sorted={seen} perDot={perDot} />
      {caption && (
        <figcaption className="cn-pop-cap">
          <span>
            <i style={{ background: SLATE }} /> ≤50K, {fmt(adult.classes[0].count)}
          </span>
          <span>
            <i style={{ background: OCHRE }} /> &gt;50K, {fmt(adult.classes[1].count)}
          </span>
          <span className="cn-pop-scale">One square is {perDot} rows</span>
        </figcaption>
      )}
    </figure>
  );
}

function RowPortrait({ r, against, first }: { r: (typeof adult.conflictPair)[number]; against: string; first?: boolean }) {
  const differs = r.label !== against;
  return (
    <article className={`cn-portrait${first ? ' cn-portrait--first' : ''}`}>
      <div className="cn-portrait-plate">
        <span className="cn-portrait-row">Line {fmt(r.row)}</span>
        <dl>
          <div>
            <dt>age</dt>
            <dd>{r.age}</dd>
          </div>
          <div>
            <dt>education</dt>
            <dd>{r.education}</dd>
          </div>
          <div>
            <dt>hours_per_week</dt>
            <dd>{r.hours}</dd>
          </div>
        </dl>
        <p className={`cn-portrait-label${differs ? ' is-diff' : ''}`}>{r.label}</p>
      </div>
      <p className="cn-caption">
        CSV line {fmt(r.row)}
        <br />
        <em>labelled {r.label}</em>
      </p>
    </article>
  );
}

/* ------------------------------------------------------------------ Landing */

function Landing() {
  return (
    <main>
      <section className="cn-hero">
        <Masthead>DATATRUST</Masthead>
        <p className="cn-dek">A reliability report for the data you are about to train on.</p>
        <Population />
        <div className="cn-hero-grid">
          <p className="cn-lede">
            Adult is a public census table of {fmt(adult.rows)} people. Three in four earn ≤50K. A model that always
            answers ≤50K is right {pct(majorityShare)} of the time and useless for the people it is meant to find.
          </p>
          <div className="cn-hero-leaders">
            <Leader k="Rows" v={fmt(adult.rows)} />
            <Leader k="Columns" v={adult.columns} />
            <Leader k="Majority baseline" v={pct(majorityShare)} />
            <Leader k="Read in" v={`${adult.runtime.toFixed(2)} s, on this laptop`} />
          </div>
        </div>
      </section>

      <section className="cn-chapter">
        <Masthead tag="h2">SAME PERSON, TWO ANSWERS</Masthead>
        <div className="cn-meta">
          <Leader k="Adult" v="Census income" />
          <Leader k="Groups that disagree" v={adult.conflictGroups} />
          <Leader k="Rows involved" v={adult.conflictRows} />
        </div>
        <div className="cn-pair">
          <RowPortrait first r={adult.conflictPair[0]} against={adult.conflictPair[1].label} />
          <RowPortrait r={adult.conflictPair[1]} against={adult.conflictPair[0].label} />
          <p className="cn-pair-note">
            Identical on every recorded feature. Different on the answer. DataTrust finds these groups across the
            whole table and leaves the judgement to you: a label error, a person seen twice, or a feature nobody
            recorded.
          </p>
        </div>
      </section>

      <section className="cn-chapter cn-chapter--split">
        <div>
          <Masthead tag="h2">HOW IT READS</Masthead>
        </div>
        <ol className="cn-principles">
          {principles.map((p) => (
            <li key={p.title}>
              <h3>{p.title}</h3>
              <p>{p.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="cn-chapter">
        <Masthead tag="h2">WHAT IT CAN READ</Masthead>
        <div className="cn-capabilities">
          {capabilities.map((c) => (
            <Leader key={c.name} k={c.name} v={c.detail} />
          ))}
          <Leader k="Audio" v="Deferred" />
        </div>
        <div className="cn-cta-row">
          <Go to={href(C, 'workspace')} className="cn-cta">
            Open the workspace
          </Go>
          <Go to={href(C, 'results')} className="cn-cta cn-cta--ghost">
            Read the Adult audit
          </Go>
        </div>
      </section>
      <Foot />
    </main>
  );
}

/* ---------------------------------------------------------------- Workspace */

function AuditGlyph({ a }: { a: Audit }) {
  // A strip of squares, one per 1,000 rows (minimum one), tinted by band.
  const n = Math.max(1, Math.round(a.rows / 1000));
  const tone =
    a.score === null ? 'none' : a.band === 'High' ? 'high' : a.band === 'Elevated' ? 'elevated' : 'low';
  return (
    <span className={`cn-glyph is-${tone}`} aria-hidden="true">
      {Array.from({ length: Math.min(n, 50) }, (_, i) => (
        <i key={i} />
      ))}
    </span>
  );
}

function Workspace() {
  const [filter, setFilter] = useState<'All' | Audit['kind']>('All');
  const kinds: ('All' | Audit['kind'])[] = ['All', 'Classification', 'Regression', 'Connected evidence', 'Controlled mutation'];
  const list = audits.filter((a) => filter === 'All' || a.kind === filter);
  return (
    <main>
      <section className="cn-hero cn-hero--tight">
        <Masthead>WORKSPACE</Masthead>
        <div className="cn-meta">
          <Leader k="Location" v="~/numek/audits" />
          <Leader k="Audits" v={audits.length} />
          <Leader k="Uploaded" v="Nothing" />
        </div>
      </section>

      <section className="cn-ws">
        <div className="cn-ws-filter" role="tablist" aria-label="Filter audits">
          {kinds.map((k) => (
            <button key={k} role="tab" aria-selected={filter === k} onClick={() => setFilter(k)}>
              {k}
            </button>
          ))}
        </div>

        <ol className="cn-index">
          {list.map((a) => {
            const inner = (
              <>
                <span className="cn-index-name">{a.name}</span>
                <span className="cn-index-dots" aria-hidden="true" />
                <span className="cn-index-score">{a.score === null ? '—' : a.score}</span>
                <span className="cn-index-sub">
                  <AuditGlyph a={a} />
                  <span>
                    {a.kind}. {fmt(a.rows)} {a.kind === 'Connected evidence' ? 'records' : 'rows'}
                    {a.columns ? ` × ${a.columns}` : ''}. {a.findings} findings.
                  </span>
                  <em>{a.score === null ? a.band : `${a.band}. ${a.note}`}</em>
                </span>
              </>
            );
            return (
              <li key={a.id}>
                {a.id === 'adult' ? (
                  <Go to={href(C, 'results')} className="cn-index-row is-link">
                    {inner}
                  </Go>
                ) : (
                  <div className="cn-index-row">{inner}</div>
                )}
              </li>
            );
          })}
        </ol>

        <aside className="cn-new">
          <p className="cn-new-title">Start an audit</p>
          <div className="cn-slip">
            <p>Drop a table, a corpus or a folder of images here.</p>
            <p className="cn-slip-small">CSV, Parquet, JSONL, image folders. Read on this machine only.</p>
          </div>
          <Leader k="Or from a terminal" v={<code>datatrust audit data.csv</code>} />
        </aside>
      </section>
      <Foot />
    </main>
  );
}

/* ------------------------------------------------------------------ Results */

function DotScore({ value, alert }: { value: number; alert?: boolean }) {
  const filled = Math.round(value / 2);
  return (
    <span className={`cn-dotscore${alert ? ' is-alert' : ''}`} aria-hidden="true">
      {Array.from({ length: 50 }, (_, i) => (
        <i key={i} className={i < filled ? 'on' : ''} />
      ))}
    </span>
  );
}

function HoursChart() {
  const max = Math.max(...adult.hourBins.map((b) => b.low + b.high));
  return (
    <figure className="cn-hours">
      {adult.hourBins.map((b) => (
        <div className="cn-hours-row" key={b.label}>
          <span className="cn-hours-k">{b.label} h</span>
          <span className="cn-hours-bar">
            <i style={{ width: `${(b.low / max) * 100}%`, background: SLATE }} />
            <i style={{ width: `${(b.high / max) * 100}%`, background: OCHRE }} />
          </span>
          <span className="cn-hours-v">{fmt(b.low + b.high)}</span>
        </div>
      ))}
      <figcaption className="cn-caption">
        hours_per_week, all {fmt(adult.rows)} rows. Outlier rates use the IQR rule; the rows are not removed.
      </figcaption>
    </figure>
  );
}

function FindingChapter({ i }: { i: number }) {
  const f = adult.findings[i];
  const visual =
    f.code === 'conflicting_target_labels' ? (
      <div className="cn-pair cn-pair--compact">
        <RowPortrait first r={adult.conflictPair[0]} against={adult.conflictPair[1].label} />
        <RowPortrait r={adult.conflictPair[1]} against={adult.conflictPair[0].label} />
      </div>
    ) : f.code === 'target_imbalance' ? (
      <Population />
    ) : f.code === 'numeric_outlier_concentration' ? (
      <HoursChart />
    ) : (
      <div className="cn-specimen">
        <span>marital_status</span>
        <p className="cn-caption">Flagged by its name only. No strong leakage candidate was found.</p>
      </div>
    );
  return (
    <section className="cn-finding" id={f.code}>
      <div className="cn-finding-head">
        <span className={`cn-sev is-${f.severity.toLowerCase()}`}>{f.severity}</span>
        <Masthead tag="h2">{f.title.toUpperCase()}</Masthead>
      </div>
      <div className="cn-finding-body">
        <div className="cn-finding-text">
          <p className="cn-finding-lede">{f.finding}</p>
          <p className="cn-evidence"><b>Evidence</b>{f.evidence}</p>
          <h4>Why it matters</h4>
          <p>{f.impact}</p>
          <h4>What to check next</h4>
          <p>{f.next}</p>
          <p className="cn-effect">{f.scoreEffect}</p>
        </div>
        <div className="cn-finding-visual">{visual}</div>
      </div>
    </section>
  );
}

function Results() {
  const [active, setActive] = useState(adult.findings[0].code);
  useEffect(() => {
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: '-45% 0px -50% 0px' },
    );
    document.querySelectorAll('.cn-finding').forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return (
    <main>
      <section className="cn-hero cn-hero--tight">
        <Masthead>ADULT</Masthead>
        <div className="cn-meta">
          <Leader k={adult.task} v={<code>{adult.target}</code>} />
          <Leader k="Shape" v={`${fmt(adult.rows)} × ${adult.columns}`} />
          <Leader k="Read in" v={`${adult.runtime.toFixed(2)} s`} />
        </div>
      </section>

      <section className="cn-verdict">
        <div className="cn-verdict-score">
          <span className="cn-big">{adult.score}</span>
          <span className="cn-band">{adult.band}</span>
        </div>
        <div className="cn-verdict-text">
          <p className="cn-lede">
            The evidence averages {evidenceScore}. One weakness is critical: target balance scored{' '}
            {adult.subScores[4].value}, so the guardrail caps the result at {adult.guardrail.cap}.
          </p>
          <div className="cn-subscores">
            {adult.subScores.map((s) => (
              <div className="cn-subscore" key={s.key}>
                <Leader k={s.label} v={s.value.toFixed(2)} strong={s.value < 50} />
                <DotScore value={s.value} alert={s.value < 50} />
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="cn-results">
        <nav className="cn-toc" aria-label="Findings">
          <p className="cn-toc-title">Findings, in priority order</p>
          <ol>
            {adult.findings.map((f) => (
              <li key={f.code}>
                <a href={`#/${C}/results`} onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(f.code)?.scrollIntoView({ behavior: 'smooth' });
                }} className={active === f.code ? 'is-on' : ''}>
                  {f.title}
                </a>
              </li>
            ))}
          </ol>
          <div className="cn-toc-meta">
            <Leader k="Missing feature rows" v={`${adult.missingRowRate}%`} />
            {adult.missingness.map((m) => (
              <Leader key={m.field} k={<code>{m.field}</code>} v={fmt(m.count)} />
            ))}
            <Leader k="Duplicate groups" v={adult.duplicateGroups} />
            <Leader k="Majority to minority" v={`${imbalanceRatio.toFixed(2)} : 1`} />
          </div>
          <div className="cn-exports">
            <button>HTML report</button>
            <button>PDF</button>
            <button>JSON evidence</button>
          </div>
        </nav>
        <div className="cn-findings">
          {adult.findings.map((_, i) => (
            <FindingChapter key={i} i={i} />
          ))}
        </div>
      </div>
      <Foot />
    </main>
  );
}

export default function Census({ screen }: { screen: Screen }) {
  return (
    <div className="c-census">
      <Bar screen={screen} />
      {screen === 'landing' && <Landing />}
      {screen === 'workspace' && <Workspace />}
      {screen === 'results' && <Results />}
    </div>
  );
}
