import { useState } from 'react';
import { references as refs1, references2, references3, inaccessible, type RefStatus } from './references';
const references = [...references3, ...references2, ...refs1];
import { concepts } from '../concepts/registry';
import './lab.css';

const filters: { id: 'all' | RefStatus; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'used', label: 'Combined into a concept' },
  { id: 'studied', label: 'Studied' },
  { id: 'rejected', label: 'Rejected' },
];

export default function Board() {
  const [filter, setFilter] = useState<'all' | RefStatus>('all');
  const [round, setRound] = useState<1 | 2 | 3>(3);
  const [zoom, setZoom] = useState<string | null>(null);
  const list = references.filter((r) => (round === 1 ? !r.round : r.round === round) && (filter === 'all' || r.status === filter));
  const byId = Object.fromEntries(references.map((r) => [r.id, r]));
  return (
    <div className="lab">
      <header className="lab-head">
        <div>
          <p className="lab-kicker">
            <a href="#/">Visual lab</a> / Reference board
          </p>
          <h1>What fifteen directions were built from</h1>
          <p className="lab-sub">
            {references.length} live sites captured in a real browser at 1440 × 900 across three rounds (Unseen at 800 × 600, see its note). Each entry records what was
            observed, what was taken and where it went. Rejected references stay on the board with the reason.
          </p>
        </div>
      </header>

      <div className="lab-toggle" role="tablist" aria-label="Round">
        <span>Round</span>
        <button role="tab" aria-selected={round === 3} onClick={() => setRound(3)}>
          Three: product-native
        </button>
        <button role="tab" aria-selected={round === 2} onClick={() => setRound(2)}>
          Two: product-led
        </button>
        <button role="tab" aria-selected={round === 1} onClick={() => setRound(1)}>
          One: first exploration
        </button>
      </div>
      <section className="lab-hybrids">
        <h2 className="lab-h2">The hybrids</h2>
        <div className="lab-hybrid-grid">
          {concepts.filter((c) => (round === 1 ? !c.round : c.round === round)).map((c) => (
            <article key={c.id} className="lab-hybrid">
              <h3>
                <a href={`#/${c.id}/landing`}>{c.name}</a>
              </h3>
              <div className="lab-hybrid-refs">
                {c.refs.filter((id) => byId[id]?.shots.length).map((id) => (
                  <figure key={id}>
                    <img src={byId[id].shots[0]} alt="" loading="lazy" />
                    <figcaption>{byId[id].name}</figcaption>
                  </figure>
                ))}
              </div>
              <ul>
                {c.decisions.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <div className="lab-toggle" role="tablist" aria-label="Filter references">
        <span>References</span>
        {filters.map((f) => (
          <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => setFilter(f.id)}>
            {f.label}
          </button>
        ))}
      </div>

      <section className="lab-refs">
        {list.map((r) => (
          <article key={r.id} className={`lab-ref is-${r.status}`}>
            <div className="lab-ref-meta">
              <h3>{r.name}</h3>
              <p className="lab-ref-by">{r.by}</p>
              <a href={r.url} target="_blank" rel="noreferrer" className="lab-ref-url">
                {r.url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
              <dl>
                <dt>Source</dt>
                <dd>{r.origin}</dd>
                <dt>Status</dt>
                <dd className="lab-status">{r.status === 'used' ? 'Combined' : r.status === 'studied' ? 'Studied' : 'Rejected'}</dd>
                {r.concepts && (
                  <>
                    <dt>Into</dt>
                    <dd>{r.concepts.join(', ')}</dd>
                  </>
                )}
              </dl>
              <p>
                <b>Observed.</b> {r.observed}
              </p>
              {r.taken && (
                <p>
                  <b>Taken.</b> {r.taken}
                </p>
              )}
              {r.access && <p className="lab-ref-access">{r.access}</p>}
            </div>
            <div className="lab-ref-shots">
              {r.shots.map((src) => (
                <button key={src} onClick={() => setZoom(src)} aria-label={`Enlarge ${r.name} screenshot`}>
                  <img src={src} alt={`${r.name}, live capture`} loading="lazy" />
                </button>
              ))}
            </div>
          </article>
        ))}
      </section>

      <section className="lab-notes">
        <h2 className="lab-h2">Access notes</h2>
        {inaccessible.map((n) => (
          <p key={n.name}>
            <b>{n.name}.</b> {n.note}
          </p>
        ))}
        <p>
          Screenshots are used here for internal design reference and attribution only. No branded assets or
          compositions were copied into the concepts.
        </p>
      </section>

      {zoom && (
        <button className="lab-zoom" onClick={() => setZoom(null)} aria-label="Close enlarged screenshot">
          <img src={zoom} alt="" />
        </button>
      )}
    </div>
  );
}
