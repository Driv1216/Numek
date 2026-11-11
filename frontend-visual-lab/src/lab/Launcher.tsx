import { useState } from 'react';
import { concepts, type Concept } from '../concepts/registry';
import type { Screen } from '../shared/router';
import './lab.css';

const screens: { id: Screen; label: string }[] = [
  { id: 'landing', label: 'Landing' },
  { id: 'workspace', label: 'Workspace' },
  { id: 'results', label: 'Results' },
];

function Card({ c, i, screen }: { c: Concept; i: number; screen: Screen }) {
  return (
    <article className="lab-card">
      <a href={`#/${c.id}/${screen}`} className="lab-thumb">
        <img src={`screenshots/${c.id}-${screen}-desktop.jpg`} alt={`${c.name} ${screen}, 1440 × 900 capture`} loading="lazy" />
      </a>
      <div className="lab-card-body">
        <h2>
          <span className="lab-idx">{i}</span>
          {c.name}
        </h2>
        <p>{c.line}</p>
        <p className="lab-src">From {c.sources.join(', ')}</p>
        <div className="lab-card-links">
          {screens.map((s) => (
            <a key={s.id} href={`#/${c.id}/${s.id}`}>
              {s.label}
            </a>
          ))}
        </div>
      </div>
    </article>
  );
}

export default function Launcher() {
  const [screen, setScreen] = useState<Screen>('landing');
  const r3 = concepts.filter((c) => c.round === 3);
  const r2 = concepts.filter((c) => c.round === 2);
  const r1 = concepts.filter((c) => !c.round);
  return (
    <div className="lab">
      <header className="lab-head">
        <div>
          <p className="lab-kicker">NUMEK DataTrust visual lab</p>
          <h1>Fifteen visual directions for the same product</h1>
          <p className="lab-sub">
            Every concept shows identical evidence. Rounds two and three use real <code>datatrust audit</code> output for Adult and its
            planted-leakage mutation, and round three adds real distributions of all 15 columns; round one uses the stored validation summary. Only the visual language differs.
          </p>
        </div>
        <nav className="lab-links">
          <a href="#/board">Reference board</a>
          <a href="screenshots/index.html">Screenshot sheet</a>
        </nav>
      </header>

      <div className="lab-toggle" role="tablist" aria-label="Compare screen">
        <span>Compare</span>
        {screens.map((s) => (
          <button key={s.id} role="tab" aria-selected={screen === s.id} onClick={() => setScreen(s.id)}>
            {s.label}
          </button>
        ))}
      </div>

      <h2 className="lab-round">Round three: product-native</h2>
      <p className="lab-round-sub">Each hero demonstrates the core act on real Adult evidence; each app browses the dataset itself. One brand system per concept.</p>
      <section className="lab-grid">
        {r3.map((c, i) => (
          <Card key={c.id} c={c} i={i + 11} screen={screen} />
        ))}
      </section>

      <h2 className="lab-round">Round two: product-led</h2>
      <p className="lab-round-sub">Craft learned from AI and infrastructure product sites, applied to what Numek actually sells.</p>
      <section className="lab-grid">
        {r2.map((c, i) => (
          <Card key={c.id} c={c} i={i + 6} screen={screen} />
        ))}
      </section>

      <h2 className="lab-round">Round one: first exploration</h2>
      <p className="lab-round-sub">Kept for comparison. These borrowed the references' subject matter, which is why they read as costumes.</p>
      <section className="lab-grid is-dim">
        {r1.map((c, i) => (
          <Card key={c.id} c={c} i={i + 1} screen={screen} />
        ))}
      </section>

      <footer className="lab-foot">
        <p>Prototype only. No analysis runs here. Figures come from real local runs and stored repository evidence; nothing is uploaded.</p>
      </footer>
    </div>
  );
}
