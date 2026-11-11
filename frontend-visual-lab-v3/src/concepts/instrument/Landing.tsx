import '@fontsource-variable/instrument-sans';
import '@fontsource/instrument-serif/400.css';
import '@fontsource/instrument-serif/400-italic.css';
import '@fontsource-variable/jetbrains-mono';
import './instrument.css';
import { adult, company, finance, local, runs } from '../../fixture';
import { href } from '../../shell/router';
import { Dial } from './dial';
import { Instrument } from './Instrument';

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="in-head">
      <a className="in-wm" href={href('instrument', 'landing')}>NUMEK</a>
      <nav aria-label="Primary">
        <a href={href('instrument', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>Instrument</a>
        <a href={href('instrument', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Runs</a>
        <a href={href('instrument', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
      <span className="in-head__r">DataTrust · local · 127.0.0.1</span>
    </header>
  );
}

export default function Landing() {
  return (
    <div className="in in--landing">
      <Header here="landing" />
      <section className="in-hero">
        <div className="in-hero__t">
          <p className="in-kicker">DataTrust by {company.name}</p>
          <h1><em>Ask your data a question.</em></h1>
          <p>DataTrust measures a dataset on your machine. Here that measurement is one instrument: fifteen sectors for Adult’s fifteen columns, each ring a bin of the column’s real distribution. Pick a question; the instrument answers with the evidence.</p>
        </div>
        <Instrument run="adult" />
      </section>

      <section className="in-read">
        <h2><em>How to read it</em></h2>
        <div className="in-read__g">
          <figure className="in-read__d"><Dial run="adult" mode="outliers" core={[adult.finalScore.toFixed(1), adult.band]} /></figure>
          <ol className="in-read__l">
            <li><b>Sector</b><span>One column. Numbered clockwise from the top, in file order.</span></li>
            <li><b>Ring</b><span>One slice of the column’s distribution, from its smallest value at the centre to its largest at the rim. Thicker means more rows.</span></li>
            <li><b>Red ring</b><span>Values beyond the 1.5 × IQR fences. Drawn only where the IQR is above zero, as in DataTrust.</span></li>
            <li><b>Rim mark</b><span>The share of rows where the column is empty, to scale.</span></li>
            <li><b>Core</b><span>The final score where one is defined. Regression, text, image and document runs leave it empty.</span></li>
            <li><b>Range</b><span>The rows of the file. Questions about rows mark them here.</span></li>
          </ol>
        </div>
      </section>

      <section className="in-others">
        <h2><em>Other instruments</em></h2>
        <div className="in-others__g">
          {(['german', 'bank', 'bike'] as const).map((id) => {
            const r = runs.find((x) => x.id === id)!;
            return (
              <a key={id} className="in-other" href={href('instrument', 'app')}>
                <Dial run={id} mode={id === 'bike' ? 'relation' : id === 'bank' ? 'target' : 'score'} core={r.score == null ? ['—', 'no score defined'] : [r.score.toFixed(1), r.band ?? '']} />
                <b>{r.name}</b><span>{r.size} · {r.task}</span><em>{r.lead}</em>
              </a>
            );
          })}
          <div className="in-other in-other--txt">
            <b>Not tables</b>
            <p>SMS (5,574 records), the COCO subset (128 images, 875 objects) and the finance reconciliation ({finance.records} records against {finance.documents} PDFs) are read by their own units, so they get their own instruments in the app — and no score dial.</p>
          </div>
        </div>
      </section>

      <section className="in-cmd">
        <h2><em>Calibrate it on your own data.</em></h2>
        <pre>$ {local.commands[0]}{'\n'}{local.cliOutput.join('\n')}{'\n\n'}$ {local.commands[1]}{'\n'}→ http://127.0.0.1:8000/</pre>
      </section>
      <footer className="in-foot">
        <span className="in-wm">NUMEK</span>
        <p>{company.line}. DataTrust is the product. {company.direction}</p>
        <p className="in-dim">{adult.source} · Findings support human review; they are not certification.</p>
      </footer>
    </div>
  );
}
