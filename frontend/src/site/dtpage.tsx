// Step two of the blend: the DataTrust product page (third revision).
// 1 the Drop (a real file read, checked and reported, then explorable evidence), 2 Two Readings in
// Recursive, 3 the real report turning page by page, 4 run it and its limits.
import './dt.css';
import { adult, local } from './content';
import { Drop } from './drop';
import { Report } from './report';
import { Footer, Header } from './Landing';
import { Readers } from './readers';
import { Frame, Status } from '../foundation/system';
import { products } from '../products';
import { appHref, pageHref } from './nav';

const p = products[0];
const notIncluded = (adult.limits.split('Not included:')[1] ?? '').replace(/\.$/, '').replace(/\bor\b/, '').split(',').map((x) => x.trim()).filter(Boolean);

export function DataTrustPage() {
  return (
    <div className="nk nk--dt">
      <Frame />
      <Header page="datatrust" />
      <main>
        <section className="nk-dt-hero" aria-labelledby="dt-h1">
          <div className="nk-dt-hero__t">
            <span className="nk-card__k">DataTrust · 01 · {p.moment}</span>
            <h1 id="dt-h1">Drop in a dataset.<br />Get back what to fix.</h1>
          </div>
          <div className="nk-dt-hero__r">
            <Status tone="on">{p.status} · runs on your machine</Status>
            <p>DataTrust reads your data where it sits, checks what would hurt a model, and tells you in plain English, with the rows to prove it.</p>
            <div className="nk-hero__cta"><a className="nk-btn" href={appHref()}>Open DataTrust</a><a className="nk-btn nk-btn--ghost" href={pageHref('datatrust', 'dt-report')}>See the report</a></div>
          </div>
        </section>
        <section className="nk-dt-drop" aria-label="DataTrust reading adult.csv">
          <Drop />
        </section>

        <Readers />

        <Report />

        <section id="dt-run" className="nk-sec nk-dt-run" aria-labelledby="dt-run-h">
          <div className="nk-dt-run__in">
            <div>
              <span className="nk-label">Run it</span>
              <h2 id="dt-run-h" className="nk-h2">Two commands. Your data never leaves.</h2>
              <ul className="nk-facts">{local.facts.map((x) => <li key={x.label}><b>{x.value}</b><span>{x.label}</span></li>)}</ul>
            </div>
            <div className="nk-dt-run__r">
              <div className="nk-cmds">
                {[[local.commands[0], 'Audit a file: HTML, PDF and JSON'], [local.commands[1], 'Or open the guided app in your browser, on this machine']].map(([c, l]) => <div key={c}><span>{l}</span><code><i>$</i> {c}</code></div>)}
              </div>
              <div className="nk-dt-not">
                <span className="nk-k">What it does not do</span>
                <ul>{notIncluded.map((x) => <li key={x}>{x}</li>)}</ul>
                <p>Findings support human review. A report is not a certificate.</p>
              </div>
            </div>
          </div>
        </section>

      </main>
      <Footer />
    </div>
  );
}
