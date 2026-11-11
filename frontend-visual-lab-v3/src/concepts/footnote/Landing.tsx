import '@fontsource-variable/newsreader';
import '@fontsource-variable/newsreader/wght-italic.css';
import '@fontsource-variable/hanken-grotesk';
import '@fontsource/red-hat-mono/400.css';
import './footnote.css';
import { useState, type ReactNode } from 'react';
import { adult, bike, company, finance, local, runFindings } from '../../fixture';
import { href } from '../../shell/router';
import { Cycle, RowChip, Spark, Token, Waffle, fileChip } from './inserts';

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="fn-head">
      <a className="fn-wm" href={href('footnote', 'landing')}>NUMEK</a>
      <nav aria-label="Primary">
        {here === 'landing' ? (
          <><a href="#fn-1"><sup>1</sup>Local</a><a href="#fn-2"><sup>2</sup>Findings</a><a href="#fn-3"><sup>3</sup>Evidence</a><a href="#fn-4"><sup>4</sup>Score</a></>
        ) : (
          <><a href={href('footnote', 'landing')}>DataTrust</a><a href={href('footnote', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Runs</a><a href={href('footnote', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a></>
        )}
      </nav>
      <a className="fn-head__r" href={href('footnote', 'app')}>Open DataTrust →</a>
    </header>
  );
}

const scoreLines: [string, string][] = [...adult.subScores.map((s) => [s.label, String(s.value)] as [string, string]), ['Evidence (mean)', String(adult.evidenceScore)], ['Guardrail', '≤ 50 → cap 69'], ['Final', `${adult.finalScore.toFixed(1)} · ${adult.band}`]];

/** A footnote section: a parenthetical label, one large sentence, then the facts. */
function Note({ n, id, label, children }: { n: number; id: string; label: string; children: ReactNode }) {
  return (
    <section id={id} className="fn-note-sec" aria-labelledby={`${id}-h`}>
      <p className="fn-paren" id={`${id}-h`}><sup>{n}</sup>({label})</p>
      {children}
    </section>
  );
}

export default function Landing() {
  const [open, setOpen] = useState<number | null>(null);
  const findings = runFindings.adult.map((f, i) => ({ ...f, raw: adult.findings[i] }));
  return (
    <div className="fn fn--landing">
      <Header here="landing" />
      <section className="fn-hero">
        <p className="fn-paren">(DataTrust, by {company.name})</p>
        <h1 className="fn-sentence">
          DataTrust reads <Cycle label="a dataset file" items={['adult.csv', 'bike_hour.csv', 'sms.jsonl', 'records.csv + 21 PDFs'].map(fileChip)} /> on your machine<a href="#fn-1" className="fn-sup"><sup>1</sup></a> and shows what it found<a href="#fn-2" className="fn-sup"><sup>2</sup></a> <Cycle label="evidence" items={[<Spark key="s" />, <Waffle key="w" />]} /> — every finding with its <span className="fn-hl">evidence</span><a href="#fn-3" className="fn-sup"><sup>3</sup></a>, and what it did to the score <Token value="69.0" label="Adult final score" lines={scoreLines} /><a href="#fn-4" className="fn-sup"><sup>4</sup></a>.
        </h1>
        <div className="fn-hero__foot">
          <p><span className="fn-paren">(Recently)</span> Adult, 48,842 rows, audited in {adult.runtimeSeconds.toFixed(2)} s. Four findings; one set the score.</p>
          <p><span className="fn-paren">(Not)</span> No hosted service, no monitoring, no certification. ConfidenceGuard and HallucinationGuard are research directions.</p>
          <p><span className="fn-paren">(Run)</span> <code>$ {local.commands[1]}</code></p>
        </div>
      </section>

      <Note n={1} id="fn-1" label="Local">
        <p className="fn-big">Nothing leaves <span className="fn-hl">127.0.0.1</span>. The browser interface binds to loopback, and there are <Token value="0" label="network calls" lines={[['at analysis time', '0 network calls'], ['models', 'never downloaded at runtime'], ['upload limit', local.uploadLimit]]} /> network calls while a dataset is analysed.</p>
        <dl className="fn-facts">{local.facts.map((f) => <div key={f.label}><dt>{f.label}</dt><dd>{f.value}</dd></div>)}</dl>
      </Note>

      <Note n={2} id="fn-2" label="Findings">
        <p className="fn-big">Four findings in Adult. <span className="fn-hl">Two</span> changed the score; two are evidence only.</p>
        <ol className="fn-rows">
          {findings.map((f, i) => (
            <li key={f.title} className={open === i ? 'is-open' : ''}>
              <span className="fn-rows__cat">{f.raw.locus.kind.toUpperCase()} · {f.raw.locus.columns.join(', ')}</span>
              <h3>{f.title}</h3>
              <p>{f.raw.finding} {f.evidence}</p>
              <div className="fn-rows__act">
                <a href="#fn-3">Open the evidence →</a>
                <button type="button" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>Look under the hood</button>
              </div>
              {open === i && <pre className="fn-hood">{`code          ${f.raw.code}\nseverity      ${f.raw.severity}\nevidence      ${f.raw.evidence}\nscore effect  ${f.raw.scoreEffect}`}</pre>}
              <dl className="fn-rows__spec"><div><dt>Severity</dt><dd>{f.severity}</dd></div><div><dt>Effect</dt><dd>{f.effect === 'score' ? 'Changes the score' : 'Evidence only'}</dd></div><div><dt>Run</dt><dd>Adult</dd></div></dl>
            </li>
          ))}
        </ol>
      </Note>

      <Note n={3} id="fn-3" label="Evidence">
        <p className="fn-big">Row 16,684 and row 34,343 agree on all fourteen features <RowChip /> and disagree on the label. DataTrust found <span className="fn-hl">five</span> such groups — ten rows — and leaves the judgement to you.</p>
        <p className="fn-small">Evidence only: this finding does not change any score or guardrail. Review whether these are label errors, repeated entities over time, target updates, or omitted distinguishing features.</p>
      </Note>

      <Note n={4} id="fn-4" label="Score">
        <p className="fn-big">The score is <Token value="69.0" label="final score" lines={scoreLines} />, held at the cap by a target balance of <Token value="47.86" label="target balance" lines={[['majority class', `${adult.majorityBaseline}%`], ['formula', '100 − (76.07 − 50) ÷ 50 × 100'], ['critical', '≤ 50']]} /> — without it, the mean of the five measures would be <Token value="89.15" label="evidence score" lines={adult.subScores.map((s) => [s.label, String(s.value)] as [string, string])} />.</p>
        <p className="fn-small">Only classification runs carry a score. Bike sharing has two High findings — {bike.relationship} — and no score, because regression has no universal one.</p>
      </Note>

      <section className="fn-kinds">
        <p className="fn-paren">(Six kinds of data)</p>
        <ol>
          <li>A <b>table</b> is read row by row: Adult has {adult.rows.toLocaleString()} <Spark label="hours distribution" />.</li>
          <li>An <b>outcome</b> is checked against its features: {bike.relationship}, on every one of 17,379 rows.</li>
          <li><b>Time</b> is checked against when each value became known — exact clocks, declared availability, revisions.</li>
          <li><b>Text</b> is searched for near-duplicates with a calibrated, bounded MinHash search — 5,574 SMS records.</li>
          <li><b>Images</b> are checked for coordinates, orientation and masks — 128 COCO images, 875 objects.</li>
          <li><b>Records</b> are reconciled against their documents: {finance.agreements} of {finance.records} agree, {finance.discrepancies} disagrees, {finance.conflicts} conflicts — each with a page locator.</li>
        </ol>
      </section>

      <footer className="fn-foot">
        <p className="fn-big fn-big--s">Read your own data the same way: <code>$ {local.commands[0]}</code></p>
        <p className="fn-small">{company.line}. DataTrust is the product. {company.direction} · {adult.source}. Findings support human review; they are not certification.</p>
      </footer>
    </div>
  );
}
