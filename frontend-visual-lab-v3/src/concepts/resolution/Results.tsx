import '@fontsource-variable/martian-mono';
import './resolution.css';
import { useEffect, useRef, useState } from 'react';
import { adult } from '../../fixture';
import { reducedMotion } from '../../shell/motion';
import { Header, Sheet } from './Landing';
import { TileCard } from './Wall';
import { tiles, type Tile } from './tiles';

/** Adult's artefacts clustered by finding; each cluster resolves as it comes into focus. */
const clusters: { title: string; sev: string; ids: string[] }[] = [
  { title: adult.findings[1].title, sev: 'Moderate · can cap the score', ids: ['a-target', 'a-score', 'a-subs'] },
  { title: adult.findings[0].title, sev: 'Moderate · evidence only', ids: ['a-conf', 'a-col-annual_income_over_50k'] },
  { title: adult.findings[2].title, sev: 'Moderate · changes a sub-score', ids: ['a-hours'] },
  { title: adult.findings[3].title, sev: 'Low · evidence only', ids: ['a-leak', 'a-col-marital_status'] },
  { title: 'No finding · recorded as evidence', sev: 'completeness 99.12 · uniqueness 99.89', ids: ['a-missing', 'a-dups'] },
];

function Cluster({ c, onOpen }: { c: (typeof clusters)[number]; onOpen: (t: Tile) => void }) {
  const ref = useRef<HTMLElement>(null);
  const [sharp, setSharp] = useState(reducedMotion());
  useEffect(() => {
    if (reducedMotion()) return;
    const io = new IntersectionObserver(([e]) => setSharp(e.intersectionRatio > 0.45), { threshold: [0, 0.45, 1] });
    if (ref.current) io.observe(ref.current); return () => io.disconnect();
  }, []);
  const list = c.ids.map((id) => tiles.find((t) => t.id === id)).filter(Boolean) as Tile[];
  return (
    <section ref={ref} className={`rs-cluster ${sharp ? 'is-sharp' : ''}`}>
      <div className="rs-cluster__h"><h2>{c.title}</h2><span className="rs-k">{c.sev}</span></div>
      <div className="rs-cluster__g">{list.map((t) => <div key={t.id} className="rs-slot rs-slot--static"><TileCard t={t} onOpen={onOpen} /></div>)}</div>
    </section>
  );
}

export default function Results() {
  const [open, setOpen] = useState<Tile | null>(null);
  return (
    <div className="rs rs--results" style={{ ['--accent' as string]: '#FF5A3C' }}>
      <Header here="results" />
      <div className="rs-res">
        <div className="rs-res__pin">
          <span className="rs-k">{adult.file} · {adult.generatedAt}</span>
          <h1>Adult</h1>
          <div className="rs-big"><b>{adult.finalScore.toFixed(1)}</b><span>{adult.band} · evidence {adult.evidenceScore} · cap 69 (target balance 47.86)</span></div>
          <p className="rs-small">{adult.limits}</p>
        </div>
        <div className="rs-res__list">{clusters.map((c) => <Cluster key={c.title} c={c} onOpen={setOpen} />)}</div>
      </div>
      {open && <Sheet t={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
