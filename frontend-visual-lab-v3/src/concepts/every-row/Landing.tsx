import '@fontsource-variable/schibsted-grotesk';
import '@fontsource-variable/source-serif-4';
import '@fontsource-variable/source-serif-4/wght-italic.css';
import './every-row.css';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { adult, bike, finance, formats, local } from '../../fixture';
import { href } from '../../shell/router';
import { FieldView } from './FieldView';
import type { Arrangement } from './layouts';
import { PairsGlyph, UnitStrip } from './units';
import { Header } from './chrome';

const steps: { a: Arrangement; kicker: string; title: ReactNode; body: ReactNode }[] = [
  {
    a: 'target', kicker: 'Target',
    title: <>A baseline is not a result.</>,
    body: <><mark className="slate">37,155 rows</mark> earn ≤50K and <mark className="teal">11,687</mark> earn more. A model that always guesses the majority is right 76.07% of the time. DataTrust reports that baseline as context — and its target-balance sub-score of 47.86 is what holds the overall score at 69.0.</>,
  },
  {
    a: 'missing', kicker: 'Missingness',
    title: <>Gaps, counted where they are.</>,
    body: <><mark className="amber">3,620 rows</mark> (7.41%) have a missing feature. Nearly all of it sits in three columns: occupation 2,809, workclass 2,799, native_country 857. Minimal by DataTrust’s thresholds, and still on the page.</>,
  },
  {
    a: 'duplicates', kicker: 'Duplicates',
    title: <>The same row, twice.</>,
    body: <><mark className="mag">52 rows</mark> repeat another exactly, in 49 groups of two or three. Small here; on a smaller dataset it can decide which rows a model memorises.</>,
  },
  {
    a: 'conflicts', kicker: 'Conflicting labels',
    title: <>Identical people, different answers.</>,
    body: <>Five pairs of rows match in all 14 features yet <mark className="mag">disagree on the label</mark>. DataTrust does not call them errors. It asks what they are: label mistakes, the same person over time, an updated target, or a feature nobody recorded. The finding changes no score.</>,
  },
  {
    a: 'outliers', kicker: 'Outliers',
    title: <>Unusual is not wrong.</>,
    body: <><mark className="violet">13,496 rows</mark> report hours_per_week outside the IQR fences of 32.5 – 52.5 — part-time and long-hours work, mostly. The finding asks for review of the distribution; it deletes nothing.</>,
  },
  {
    a: 'accounted', kicker: 'Accounted for',
    title: <>69.0, Elevated — and why.</>,
    body: <>Every row now shows the strongest evidence it carries. The evidence score is 89.15; one critical sub-score caps the result at 69.0. Five sub-scores stay visible, so a weak one cannot hide behind a healthy average.</>,
  },
];

export default function Landing() {
  const [active, setActive] = useState<Arrangement>('population');
  const stepRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    const io = new IntersectionObserver((es) => {
      es.forEach((e) => { if (e.isIntersecting) setActive((e.target as HTMLElement).dataset.a as Arrangement); });
    }, { rootMargin: '-48% 0px -48% 0px' });
    stepRefs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, []);

  const area = (w: number, h: number) => (w > 900 ? { x: w * 0.42, y: h * 0.13, w: w * 0.54, h: h * 0.76 } : { x: 16, y: 70, w: w - 32, h: h * 0.5 });

  return (
    <div className="er er--landing">
      <Header />
      <section className="er-story">
        <div className="er-sticky">
          <FieldView arrangement={active} area={area} hover={active !== 'population'} />
          <ol className="er-progress" aria-label="Arrangement">
            {(['population', ...steps.map((s) => s.a)] as Arrangement[]).map((a) => <li key={a} className={a === active ? 'is-on' : ''}>{a}</li>)}
          </ol>
        </div>
        <div className="er-steps">
          <header className="er-hero" data-a="population" ref={(el) => { stepRefs.current[0] = el; }}>
            <p className="er-kicker">DataTrust by NUMEK · AI reliability verification</p>
            <h1>48,842 rows.<br />Every one accounted for.</h1>
            <p className="er-lede">DataTrust examines the datasets behind ML and AI systems and shows you which records carry which evidence — computed on your own machine, never summarised away.</p>
            <p className="er-note"><span className="er-sq" /> Each square is one row of the public UCI Adult dataset, in file order. Scroll, and the same squares become the evidence.</p>
            <div className="er-actions">
              <a className="er-btn" href={href('every-row', 'results')}>Explore the Adult result</a>
              <a className="er-btn er-btn--ghost" href={href('every-row', 'app')}>Open DataTrust</a>
            </div>
          </header>
          {steps.map((s, k) => (
            <article key={s.a} className="er-step" data-a={s.a} ref={(el) => { stepRefs.current[k + 1] = el; }}>
              <div className="er-card">
                <p className="er-kicker"><span>{String(k + 1).padStart(2, '0')}</span>{s.kicker}</p>
                <h2>{s.title}</h2>
                <p>{s.body}</p>
                {s.a === 'accounted' && (
                  <dl className="er-subs">
                    {adult.subScores.map((x) => (
                      <div key={x.key} className={x.critical ? 'is-crit' : ''}><dt>{x.label}</dt><dd><i style={{ width: `${x.value}%` }} />{x.value.toFixed(2)}</dd></div>
                    ))}
                  </dl>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="er-sec er-units" id="units">
        <div className="er-sec__head">
          <p className="er-kicker">Other datasets, other units</p>
          <h2>A row is one kind of unit.</h2>
          <p>DataTrust reads tables, outcomes, time, text, images and connected documents. Each has its own unit of evidence, so each gets its own mark.</p>
        </div>
        <div className="er-unitgrid">
          <figure>
            <UnitStrip count={5574} shape="dash" cols={66} size={5} gap={2} color={() => '#1A1A1A'} label="5,574 SMS records, one dash each" />
            <figcaption><b>Text · 5,574 records</b>SMS collection. Near-duplicate candidates come from calibrated, bounded MinHash search, with full-population accounting.</figcaption>
          </figure>
          <figure>
            <UnitStrip count={128} shape="frame" cols={16} size={18} gap={4} color={(k) => (k < 61 ? '#B8BEC4' : '#1A1A1A')} label="128 images; 61 ICC-bearing images excluded from default visual methods" />
            <figcaption><b>Images · 128 images, 875 objects</b>COCO val2017 subset. <span className="er-k er-k--grey" />61 carry ICC profiles and are excluded from default visual methods; <span className="er-k" />67 are eligible.</figcaption>
          </figure>
          <figure>
            <PairsGlyph />
            <figcaption><b>Connected · 20 records ↔ 21 PDFs</b>{finance.agreements} agree, <span className="er-c er-c--amber">1 discrepancy</span>, <span className="er-c er-c--mag">1 conflict</span> where two documents support different values — both kept, with exact page and cell locators.</figcaption>
          </figure>
          <figure>
            <svg viewBox="0 0 300 180" className="er-cols" role="img" aria-label="Bike hourly: 17 columns; cnt equals casual plus registered, both declared unavailable at prediction time.">
              {Array.from({ length: 17 }, (_, i) => {
                const hi = i === 14 || i === 15; const t = i === 16;
                return <rect key={i} x={10 + i * 16.6} y={30} width={11} height={120} className={hi ? 'is-hi' : t ? 'is-t' : ''} />;
              })}
              <path d="M242 160 v8 h28 v-8 M256 168 v6" className="brace" />
              <text x={150} y={20} textAnchor="middle">{bike.relationship}</text>
            </svg>
            <figcaption><b>Outcomes · 17,379 hours, no score</b>Bike sharing. One supported relationship, <span className="er-c er-c--violet">{bike.relationship}</span>; both components declared unavailable at prediction time. Regression carries no universal score, by design.</figcaption>
          </figure>
        </div>
      </section>

      <section className="er-sec er-local" id="local">
        <div className="er-sec__head">
          <p className="er-kicker">Local by construction</p>
          <h2>The squares never leave your machine.</h2>
        </div>
        <ul className="er-facts">
          {local.facts.map((f) => <li key={f.label}><b>{f.value}</b><span>{f.label}</span></li>)}
        </ul>
      </section>

      <section className="er-sec er-reports" id="reports">
        <div className="er-sec__head">
          <p className="er-kicker">Reports</p>
          <h2>One result, three readings.</h2>
          <p>The report a risk lead reads and the JSON an engineer diffs are the same completed evidence.</p>
        </div>
        <ol className="er-formats">
          {formats.map((f, i) => <li key={f.name}><span>{String(i + 1).padStart(2, '0')}</span><b>{f.name}</b><p>{f.note}</p></li>)}
        </ol>
      </section>

      <footer className="er-foot">
        <h2>See every row of your own data.</h2>
        <code>$ {local.commands[1]}</code>
        <a className="er-btn" href={href('every-row', 'app')}>Open DataTrust</a>
        <p className="er-foot__fine">NUMEK builds AI reliability verification. DataTrust is its product today; model-confidence and LLM-grounding work are research directions, not products. Adult data: UCI Machine Learning Repository.</p>
      </footer>
    </div>
  );
}
