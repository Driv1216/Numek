import '@fontsource-variable/unbounded';
import '@fontsource-variable/inter';
import '@fontsource/dm-mono/400.css';
import './collection.css';
import { useEffect, useState } from 'react';
import { adult, local, runs } from '../../fixture';
import { href } from '../../shell/router';
import { ColumnObject, code, describe, num, runsCols } from './objects';

const A = runsCols.adult;
const idx = (n: string) => A.columns.findIndex((c) => c.name === n);

export function Header() {
  const [pct, setPct] = useState(0);
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const on = () => setPct(Math.round((scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight)) * 100));
    addEventListener('scroll', on, { passive: true }); const t = setInterval(() => setTime(new Date()), 30000);
    return () => { removeEventListener('scroll', on); clearInterval(t); };
  }, []);
  return (
    <header className="co-head">
      <a className="co-head__wm" href={href('collection', 'landing')}>NUMEK</a>
      <span className="co-mono">{time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · Local, 127.0.0.1</span>
      <span className="co-mono">{String(pct).padStart(2, '0')}%</span>
      <nav aria-label="Primary"><a href={href('collection', 'landing')}><i>1.</i> Collection</a><a href={href('collection', 'app')}><i>2.</i> Index</a><a href={href('collection', 'results')}><i>3.</i> Adult</a><span className="co-dot" /></nav>
    </header>
  );
}

function Frame({ i, large = false, run = 'adult' }: { i: number; large?: boolean; run?: string }) {
  const R = runsCols[run];
  const c = R.columns[i];
  return (
    <figure className={`co-frame ${large ? 'co-frame--l' : ''}`}>
      <div className="co-frame__stage"><ColumnObject c={c} /></div>
      <figcaption>
        <span className="co-mono">{num(i)} / {code(i)}</span>
        <span className="co-frame__n">{c.name}</span>
      </figcaption>
    </figure>
  );
}

export default function Landing() {
  return (
    <div className="co co--landing">
      <Header />
      <section className="co-hero">
        <h1 className="co-word" aria-label="NUMEK">NUMEK</h1>
        <div className="co-hero__row">
          <Frame i={idx('hours_per_week')} large />
          <div className="co-hero__mid">
            <p className="co-mono">(DataTrust_by_NUMEK)</p>
            <p className="co-hero__t">Every dataset is a collection of objects. DataTrust measures each one — its shape, its gaps, its extremes — on your own machine.</p>
          </div>
          <Frame i={idx('occupation')} />
        </div>
      </section>

      <section className="co-all">
        <div className="co-all__head">
          <h2>See the whole collection <span aria-hidden="true">↗</span></h2>
          <span className="co-count">0_{A.columns.length}</span>
        </div>
        <p className="co-mono co-all__sub">(Adult · 48,842 rows · every object shaped by its real distribution)</p>
        <div className="co-grid">
          {A.columns.map((c, i) => (
            <a key={c.name} className={`co-cell ${c.target ? 'is-target' : ''}`} href={href('collection', 'results')}>
              <div className="co-cell__stage"><ColumnObject c={c} /></div>
              <span className="co-mono">{num(i)} / {code(i)}</span>
              <b>{c.name}</b>
              <em>{describe(c, A.rows)}</em>
            </a>
          ))}
        </div>
      </section>

      <section className="co-about">
        <p className="co-mono">(About_DataTrust)</p>
        <p className="co-about__t">Numeric columns are turned like vessels from their histograms; categorical columns are stacked by the share of each value; gaps are left hollow. The shapes are the evidence. DataTrust reads them for missing values, duplicates, imbalance, outliers and leakage — and says, for each finding, whether it changed the score.</p>
      </section>

      <section className="co-spreads">
        {[
          { i: idx('hours_per_week'), title: 'An unusual silhouette', body: 'Quartiles at 40 and 45 hours put the fences at 32.5 and 52.5. Everything darker sits outside them: 13,496 rows, 27.63%. DataTrust files a Moderate finding and a small feature-usability penalty; it deletes nothing.', spec: [['Range', '1 – 99 hours'], ['Median', '40'], ['Outside fences', '13,496 · 27.63%'], ['Finding', 'Numeric outlier concentration']] },
          { i: idx('occupation'), title: 'A hollow at the base', body: 'Fourteen categories, stacked by share. The hollow block is the 2,809 rows with no occupation recorded — 5.75%, minimal by DataTrust’s thresholds and still shown.', spec: [['Categories', '14'], ['Most common', 'Prof-specialty 12.64%'], ['Missing', '2,809 · 5.75%'], ['Finding', 'Evidence, no finding']] },
          { i: idx('annual_income_over_50k'), title: 'Two pieces, unequal', body: 'The target: 37,155 rows at ≤50K, 11,687 above. A 76.07% majority sets the target-balance sub-score at 47.86 — critical — and caps the dataset at 69.0, Elevated.', spec: [['Classes', '2'], ['Majority', '76.07%'], ['Target balance', '47.86 · critical'], ['Final score', '69.0 · Elevated']] },
        ].map((s) => (
          <article key={s.title} className="co-spread">
            <Frame i={s.i} large />
            <div className="co-spread__t">
              <span className="co-mono">{num(s.i)} / {code(s.i)} · {A.columns[s.i].name}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
              <dl>{s.spec.map(([k, v]) => <div key={k}><dt className="co-mono">{k}</dt><dd>{v}</dd></div>)}</dl>
            </div>
          </article>
        ))}
      </section>

      <section className="co-more">
        <div className="co-all__head">
          <h2>More collections</h2>
          <span className="co-count">0_{runs.length}</span>
        </div>
        <div className="co-more__row">
          {(['german', 'bank', 'bike'] as const).map((id) => {
            const R = runsCols[id]; const r = runs.find((x) => x.id === id)!;
            return (
              <a key={id} className="co-coll" href={href('collection', 'app')}>
                <div className="co-coll__shelf">{R.columns.slice(0, 7).map((c) => <span key={c.name}><ColumnObject c={c} /></span>)}</div>
                <span className="co-mono">{r.size} · {r.score == null ? 'no score defined' : `${r.score.toFixed(1)} ${r.band}`}</span>
                <b>{r.name}</b>
              </a>
            );
          })}
        </div>
        <p className="co-mono co-more__n">Text corpora, image sets and record–document reconciliations are not tables; DataTrust reports them by their own units.</p>
      </section>

      <footer className="co-foot">
        <div className="co-foot__top">
          <p>Measured locally, with no network at analysis time. Reported in HTML, PDF and JSON.</p>
          <code className="co-mono">$ {local.commands[1]}</code>
          <a className="co-btn" href={href('collection', 'app')}>Open DataTrust ↗</a>
        </div>
        <p className="co-word co-word--foot" aria-hidden="true">NUMEK</p>
        <p className="co-mono co-foot__f">© NUMEK · AI reliability verification · {adult.source} · model-confidence and LLM-grounding work are research directions, not products</p>
      </footer>
    </div>
  );
}
