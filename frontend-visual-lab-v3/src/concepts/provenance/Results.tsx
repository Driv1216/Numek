import '@fontsource-variable/eb-garamond';
import '@fontsource-variable/eb-garamond/wght-italic.css';
import '@fontsource-variable/inter-tight';
import './provenance.css';
import { adult } from '../../fixture';
import { Header, RecordCard, rowA, rowB } from './trace';
import { traces } from './traces';

export default function Results() {
  return (
    <div className="pv pv--results">
      <Header app />
      <main className="pv-res">
        <header className="pv-label">
          <div>
            <p className="pv-kicker">{adult.file} · {adult.task} · generated {adult.generatedAt}</p>
            <h1>Adult <i>48,842 × 15</i></h1>
          </div>
          <dl>
            <div className="is-o"><dt>Final</dt><dd>69.0</dd></div>
            <div><dt>Band</dt><dd>Elevated</dd></div>
            <div><dt>Evidence score</dt><dd>89.15</dd></div>
          </dl>
        </header>
        <p className="pv-res__narr">{adult.narrative}</p>
        {traces.adult.map((t, i) => (
          <section key={t.title} className="pv-ftrace">
            <div>
              <p className="pv-kicker">{String(i + 1).padStart(2, '0')} · {t.severity}</p>
              <h2>{t.title}</h2>
              <p className="pv-ftrace__meta">{t.effect}</p>
            </div>
            <div>
              <ol className="pv-steps">{t.steps.map((s) => <li key={s.k} className={s.o ? 'is-o' : ''}><b>{s.k}</b><span>{s.v}</span></li>)}</ol>
              {i === 0 && (
                <div className="pv-lightbox">
                  <RecordCard values={rowA} other={rowB} stage={4} />
                  <RecordCard values={rowB} other={rowA} stage={4} label="Row 34,343" />
                </div>
              )}
            </div>
          </section>
        ))}
        <p className="pv-kicker" style={{ marginTop: 40, maxWidth: 900, lineHeight: 1.6 }}>{adult.limits}</p>
      </main>
    </div>
  );
}
