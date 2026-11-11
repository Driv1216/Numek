import { useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { adult, audits, capabilities, evidenceScore, fmt, pct, majorityShare, type Audit } from '../../shared/data';
import { Segments } from './Segments';
import './instrument.css';
import '@fontsource/michroma/400';
import '@fontsource/familjen-grotesk/400';
import '@fontsource/familjen-grotesk/500';
import '@fontsource/familjen-grotesk/600';

const C = 'instrument';
const SUB_SHORT = ['COMPL', 'UNIQ', 'USAB', 'LEAK', 'BAL'];
const CAP_KEYS = ['CLASS', 'REGR', 'NO LBL', 'ANNOT', 'TIME', 'TEXT', 'IMAGE', 'LINKED'];

/* ------------------------------------------------------------ primitives */

function Led({ on, tone = 'amber' }: { on: boolean; tone?: 'amber' | 'red' | 'green' }) {
  return <i className={`in-led is-${tone}${on ? ' is-on' : ''}`} aria-hidden="true" />;
}

function Fader({ label, value, alert }: { label: string; value: number; alert?: boolean }) {
  return (
    <div className="in-fader" aria-label={`${label} ${value}`}>
      <span className="in-fader-val">{value.toFixed(value === 100 ? 0 : 1)}</span>
      <div className="in-fader-track">
        {Array.from({ length: 11 }, (_, i) => (
          <span key={i} className="in-fader-tick" style={{ bottom: `${i * 10}%` }} />
        ))}
        <span className={`in-fader-cap${alert ? ' is-alert' : ''}`} style={{ bottom: `${value}%` }} />
      </div>
      <span className="in-silk">{label}</span>
    </div>
  );
}

function Strip({ screen }: { screen: Screen }) {
  const keys: [Screen | 'all', string][] = [
    ['landing', 'INTRO'],
    ['workspace', 'WORKSPACE'],
    ['results', 'AUDIT'],
  ];
  return (
    <header className="in-strip">
      <Go to={href(C)} className="in-logo" label="DataTrust home">
        numek
        <span>datatrust</span>
      </Go>
      <nav className="in-tabs" aria-label="Concept screens">
        {keys.map(([s, l]) => (
          <Go key={s} to={href(C, s as Screen)} className={`in-tab${screen === s ? ' is-on' : ''}`}>
            {l}
          </Go>
        ))}
        <Go to="#/" className="in-tab in-tab--dark">
          ALL CONCEPTS
        </Go>
      </nav>
      <div className="in-power">
        <Led on tone="green" /> <span className="in-silk">LOCAL</span>
      </div>
    </header>
  );
}

function Ticker({ items }: { items: string[] }) {
  const line = items.join('   ✳   ');
  return (
    <div className="in-ticker" aria-hidden="true">
      <div className="in-ticker-track">
        <span>{line}   ✳   </span>
        <span>{line}   ✳   </span>
      </div>
    </div>
  );
}

function Tape({ title }: { title: string }) {
  return (
    <div className="in-tape" aria-label="Printed findings">
      <div className="in-tape-paper">
        <p className="in-tape-head">
          NUMEK DATATRUST
          <br />
          {title}
        </p>
        <div className="in-tape-rule" />
        <dl className="in-tape-kv">
          <div>
            <dt>FILE</dt>
            <dd>{adult.file}</dd>
          </div>
          <div>
            <dt>SHAPE</dt>
            <dd>
              {fmt(adult.rows)} × {adult.columns}
            </dd>
          </div>
          <div>
            <dt>SCORE</dt>
            <dd>
              {adult.score} {adult.band.toUpperCase()}
            </dd>
          </div>
          <div>
            <dt>EVIDENCE</dt>
            <dd>{evidenceScore}</dd>
          </div>
          <div>
            <dt>CAP</dt>
            <dd>{adult.guardrail.cap} target balance</dd>
          </div>
        </dl>
        <div className="in-tape-rule" />
        {adult.findings.map((f, i) => (
          <div className="in-tape-item" key={f.code}>
            <p className="in-tape-title">
              {i + 1}. {f.title}
              <span>{f.severity.toUpperCase()}</span>
            </p>
            <p>{f.evidence}</p>
          </div>
        ))}
        <div className="in-tape-rule" />
        <p className="in-tape-foot">READ IN {adult.runtime.toFixed(2)} S. NOTHING UPLOADED.</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Landing */

function Landing() {
  const [cap, setCap] = useState<number | null>(null);
  const shown = cap === null ? null : capabilities[cap];
  return (
    <main className="in-main">
      <section className="in-hero">
        <h1 className="in-outline" aria-label="DataTrust">
          <span>DATA</span>
          <span>TRUST</span>
        </h1>
        <div className="in-hero-copy">
          <p className="in-kicker">Local reliability analyzer for training data</p>
          <p className="in-hero-lede">
            Put a dataset in. Read what is wrong with it before a model learns it. Every reading shows the rows behind it.
          </p>
          <div className="in-hero-actions">
            <Go to={href(C, 'workspace')} className="in-key in-key--amber in-key--wide">
              OPEN WORKSPACE
            </Go>
            <Go to={href(C, 'results')} className="in-key in-key--wide">
              READ ADULT AUDIT
            </Go>
          </div>
        </div>
      </section>

      <section className="in-device" aria-label="Device panel showing the Adult audit">
        <div className="in-screws" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
        </div>
        <div className="in-display">
          <div className="in-display-top">
            <span>{shown ? 'CAPABILITY' : adult.file.toUpperCase()}</span>
            <span>{shown ? `${cap! + 1}/8` : `${fmt(adult.rows)} × ${adult.columns}`}</span>
          </div>
          {shown ? (
            <div className="in-display-cap">
              <p className="in-display-capname">{shown.name}</p>
              <p>{shown.detail}</p>
            </div>
          ) : (
            <div className="in-display-main">
              <Segments value={String(adult.score)} digits={3} height={118} label={`Score ${adult.score}`} />
              <div className="in-display-side">
                <span className="in-display-band">{adult.band.toUpperCase()}</span>
                <span>EVIDENCE {evidenceScore}</span>
                <span>CAPPED AT {adult.guardrail.cap}</span>
              </div>
            </div>
          )}
          <div className="in-display-bottom">
            <span>
              <Led on tone="red" /> GUARDRAIL
            </span>
            <span>
              <Led on /> 4 FINDINGS
            </span>
            <span>
              <Led on={false} /> UPLOAD
            </span>
          </div>
        </div>

        <div className="in-faders">
          {adult.subScores.map((s, i) => (
            <Fader key={s.key} label={SUB_SHORT[i]} value={s.value} alert={s.value < 50} />
          ))}
        </div>

        <div className="in-pad">
          <span className="in-silk in-pad-title">WHAT IT READS</span>
          <div className="in-pad-grid">
            {CAP_KEYS.map((k, i) => (
              <button
                key={k}
                className={`in-key${cap === i ? ' is-pressed' : ''}`}
                aria-pressed={cap === i}
                onClick={() => setCap(cap === i ? null : i)}
              >
                <span className="in-key-num">{i + 1}</span>
                {k}
              </button>
            ))}
          </div>
          <div className="in-grille" aria-hidden="true" />
        </div>
      </section>

      <Ticker
        items={[
          'RUNS ON YOUR MACHINE',
          'NOTHING IS UPLOADED',
          'EVERY FINDING SHOWS ITS ROWS',
          'GUARDRAILS KEEP SEVERE RISKS VISIBLE',
          'A REPORT, NOT A CERTIFICATE',
        ]}
      />

      <section className="in-specs">
        <div className="in-specs-intro">
          <h2>What the readings mean</h2>
          <p>
            Five faders are five transparent sub-scores. Their average is the evidence score. When one falls into the
            critical range, a guardrail caps the final score so the weakness cannot be averaged away. On Adult, target
            balance sits at {adult.subScores[4].value}: a model that always predicts ≤50K is already right{' '}
            {pct(majorityShare)} of the time.
          </p>
        </div>
        <dl className="in-spec-table">
          {[
            ['Execution', 'On this machine, loopback only'],
            ['Inputs', 'CSV, Parquet, JSONL, image folders'],
            ['Interfaces', 'Python API, command line, browser'],
            ['Outputs', 'HTML report, PDF, JSON evidence'],
            ['Scoring', 'Five sub-scores and explained guardrails, classification only'],
            ['Without a score', 'Regression, unlabeled, connected evidence'],
            ['Upload limit', '100 MiB default, configurable'],
            ['Certification', 'None claimed'],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="in-silk">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="in-output">
        <div className="in-output-copy">
          <h2>What comes out</h2>
          <p>
            A layered report: a fast decision surface on top, the technical evidence underneath. The same completed
            result is exported as HTML, PDF and strict JSON.
          </p>
          <div className="in-output-keys">
            <span className="in-key">HTML</span>
            <span className="in-key">PDF</span>
            <span className="in-key">JSON</span>
          </div>
        </div>
        <Tape title="ADULT, CLASSIFICATION" />
      </section>
    </main>
  );
}

/* ---------------------------------------------------------------- Workspace */

function Meter({ value }: { value: number }) {
  const lit = Math.round(value / 10);
  return (
    <span className="in-meter" aria-hidden="true">
      {Array.from({ length: 10 }, (_, i) => (
        <i key={i} className={i < lit ? (value < 50 ? 'is-red' : i > 7 ? 'is-hi' : 'is-on') : ''} />
      ))}
    </span>
  );
}

function Channel({ a, n, active, onSelect }: { a: Audit; n: number; active: boolean; onSelect: () => void }) {
  const kind = { Classification: 'CLASS', Regression: 'REGR', 'Connected evidence': 'LINKED', 'Controlled mutation': 'TEST' }[
    a.kind
  ];
  return (
    <button className={`in-ch${active ? ' is-active' : ''}`} onClick={onSelect} aria-pressed={active}>
      <span className="in-ch-head">
        <span>CH {n}</span>
        <span>{kind}</span>
      </span>
      <span className="in-ch-seg">
        {a.score === null ? (
          <Segments value="--" digits={2} height={30} label="No score" />
        ) : (
          <Segments value={String(Math.round(a.score))} digits={2} height={30} label={`Score ${a.score}`} />
        )}
      </span>
      <span className="in-ch-led">
        <Led on={a.band === 'High' || a.band === 'Elevated'} tone={a.band === 'High' ? 'red' : 'amber'} />
        <Led on={a.band === 'Low'} tone="green" />
      </span>
      {a.sub ? (
        <span className="in-ch-meters">
          {a.sub.map((v, i) => (
            <span key={i} className="in-ch-meter">
              <Meter value={v} />
              <span className="in-silk">{SUB_SHORT[i][0]}</span>
            </span>
          ))}
        </span>
      ) : (
        <span className="in-ch-blank">
          <span className="in-silk">NO SCORE DEFINED</span>
        </span>
      )}
      <span className="in-ch-findings">
        {Array.from({ length: 4 }, (_, i) => (
          <Led key={i} on={i < a.findings} />
        ))}
      </span>
      <span className="in-scribble">{a.name}</span>
    </button>
  );
}

function Workspace() {
  const [sel, setSel] = useState(0);
  const a = audits[sel];
  return (
    <main className="in-main">
      <section className="in-ws-head">
        <div>
          <p className="in-silk">WORKSPACE</p>
          <h1>~/numek/audits</h1>
        </div>
        <p className="in-ws-meta">
          {audits.length} channels. Every audit was read on this machine. Select a channel to read its display.
        </p>
      </section>

      <section className="in-console" aria-label="Audit channels">
        <div className="in-console-ch">
          {audits.map((x, i) => (
            <Channel key={x.id} a={x} n={i + 1} active={sel === i} onSelect={() => setSel(i)} />
          ))}
        </div>
        <div className="in-load">
          <span className="in-silk">LOAD</span>
          <div className="in-slot">
            <span>Drop a table, corpus or image folder</span>
          </div>
          <p className="in-load-cli">
            <span className="in-silk">OR</span> datatrust audit data.csv
          </p>
          <div className="in-grille in-grille--small" aria-hidden="true" />
        </div>
      </section>

      <section className="in-readout">
        <div className="in-display in-display--wide">
          <div className="in-display-top">
            <span>
              CH {sel + 1} {a.name.toUpperCase()}
            </span>
            <span>{a.kind.toUpperCase()}</span>
          </div>
          <div className="in-readout-body">
            <Segments
              value={a.score === null ? '--' : String(a.score)}
              height={84}
              label={a.score === null ? 'No score' : `Score ${a.score}`}
            />
            <div className="in-readout-text">
              <p className="in-display-band">{a.band.toUpperCase()}</p>
              <p>{a.note}</p>
              <p>
                {fmt(a.rows)} {a.kind === 'Connected evidence' ? 'records' : 'rows'}
                {a.columns ? ` × ${a.columns}` : ''}. {a.findings} findings
                {a.runtime !== null ? `. Read in ${a.runtime.toFixed(2)} s` : ''}.
              </p>
            </div>
          </div>
        </div>
        <div className="in-readout-keys">
          {a.id === 'adult' ? (
            <Go to={href(C, 'results')} className="in-key in-key--amber in-key--tall">
              OPEN
              <br />
              AUDIT
            </Go>
          ) : (
            <span className="in-key in-key--tall is-disabled" title="Only the Adult audit is prototyped">
              OPEN
              <br />
              AUDIT
            </span>
          )}
          <span className="in-key in-key--tall">
            EXPORT
            <br />
            REPORT
          </span>
        </div>
      </section>
    </main>
  );
}

/* ------------------------------------------------------------------ Results */

function Scope({ code }: { code: string }) {
  if (code === 'target_imbalance') {
    const total = adult.rows;
    return (
      <div className="in-scope-body">
        <p className="in-scope-label">CLASS SPLIT, {fmt(total)} ROWS</p>
        <div className="in-split">
          {adult.classes.map((c, i) => (
            <div key={c.label} className={`in-split-seg is-${i}`} style={{ flexGrow: c.count }}>
              <span>{c.label}</span>
              <b>{fmt(c.count)}</b>
              <em>{pct(c.count / total)}</em>
            </div>
          ))}
        </div>
        <p className="in-scope-note">Majority to minority 3.18 : 1. Baseline accuracy {pct(majorityShare)}.</p>
      </div>
    );
  }
  if (code === 'numeric_outlier_concentration') {
    const max = Math.max(...adult.hourBins.map((b) => b.low + b.high));
    return (
      <div className="in-scope-body">
        <p className="in-scope-label">HOURS_PER_WEEK, ROWS PER BIN</p>
        <div className="in-bars">
          {adult.hourBins.map((b) => (
            <div key={b.label} className="in-bar">
              <span className="in-bar-fill" style={{ height: `${((b.low + b.high) / max) * 100}%` }}>
                <span className="in-bar-hi" style={{ height: `${(b.high / (b.low + b.high)) * 100}%` }} />
              </span>
              <span className="in-bar-k">{b.label.split('–')[0]}</span>
            </div>
          ))}
        </div>
        <p className="in-scope-note">Bright segment: rows labelled &gt;50K. Outlier rates use the IQR rule.</p>
      </div>
    );
  }
  if (code === 'conflicting_target_labels') {
    return (
      <div className="in-scope-body">
        <p className="in-scope-label">GROUP 1 OF 5, IDENTICAL FEATURES</p>
        <table className="in-scope-table">
          <thead>
            <tr>
              <th>CSV LINE</th>
              <th>AGE</th>
              <th>EDUCATION</th>
              <th>HOURS</th>
              <th>LABEL</th>
            </tr>
          </thead>
          <tbody>
            {adult.conflictPair.map((r) => (
              <tr key={r.row}>
                <td>{fmt(r.row)}</td>
                <td>{r.age}</td>
                <td>{r.education}</td>
                <td>{r.hours}</td>
                <td className={r.label.startsWith('>') ? 'is-hot' : ''}>{r.label}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="in-scope-note">10 rows across 5 groups. Shown columns are an excerpt of all 14 features.</p>
      </div>
    );
  }
  return (
    <div className="in-scope-body">
      <p className="in-scope-label">COLUMN NAME REVIEW</p>
      <p className="in-scope-big">marital_status</p>
      <p className="in-scope-note">Name-based prompt only. No strong leakage candidate. Leakage sub-score stays 100.</p>
    </div>
  );
}

function Results() {
  const [sel, setSel] = useState(0);
  const f = adult.findings[sel];
  return (
    <main className="in-main">
      <section className="in-res">
        <div className="in-res-left">
          <div className="in-display">
            <div className="in-display-top">
              <span>ADULT.CSV</span>
              <span>BINARY</span>
            </div>
            <div className="in-display-main">
              <Segments value={String(adult.score)} digits={2} height={104} label={`Score ${adult.score}`} />
              <div className="in-display-side">
                <span className="in-display-band">{adult.band.toUpperCase()}</span>
                <span>EVIDENCE {evidenceScore}</span>
                <span>CAP {adult.guardrail.cap}</span>
              </div>
            </div>
            <div className="in-display-bottom">
              <span>
                <Led on tone="red" /> GUARDRAIL
              </span>
              <span>{fmt(adult.rows)} ROWS</span>
            </div>
          </div>
          <p className="in-guard">{adult.guardrail.text}</p>
          <div className="in-faders in-faders--panel">
            {adult.subScores.map((s, i) => (
              <Fader key={s.key} label={SUB_SHORT[i]} value={s.value} alert={s.value < 50} />
            ))}
          </div>
        </div>

        <div className="in-res-mid">
          <div className="in-selector" role="tablist" aria-label="Findings">
            {adult.findings.map((x, i) => (
              <button
                key={x.code}
                role="tab"
                aria-selected={sel === i}
                className={`in-key in-key--finding${sel === i ? ' is-pressed' : ''}`}
                onClick={() => setSel(i)}
              >
                <Led on tone={x.severity === 'Low' ? 'green' : 'amber'} />
                <span className="in-key-num">{i + 1}</span>
                <span className="in-key-label">{x.title}</span>
              </button>
            ))}
          </div>
          <div className="in-scope" role="tabpanel">
            <div className="in-scope-grid" aria-hidden="true" />
            <Scope code={f.code} />
          </div>
          <div className="in-explain">
            <div>
              <p className="in-silk">READING</p>
              <h2>{f.finding}</h2>
            </div>
            <div className="in-explain-cols">
              <div>
                <p className="in-silk">WHY IT MATTERS</p>
                <p>{f.impact}</p>
              </div>
              <div>
                <p className="in-silk">CHECK NEXT</p>
                <p>{f.next}</p>
              </div>
              <div>
                <p className="in-silk">SCORE EFFECT</p>
                <p>{f.scoreEffect}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="in-res-right">
          <Tape title="ADULT, CLASSIFICATION" />
          <div className="in-output-keys">
            <button className="in-key">HTML</button>
            <button className="in-key">PDF</button>
            <button className="in-key">JSON</button>
          </div>
        </div>
      </section>
    </main>
  );
}

export default function Instrument({ screen }: { screen: Screen }) {
  return (
    <div className="c-instrument">
      <Strip screen={screen} />
      {screen === 'landing' && <Landing />}
      {screen === 'workspace' && <Workspace />}
      {screen === 'results' && <Results />}
    </div>
  );
}
