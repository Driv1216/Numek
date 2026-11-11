import { runs } from '../../fixture';
import { href } from '../../shell/router';

export const repColour: Record<string, string> = {
  tables: '#5E1F1C', outcomes: '#1F3B2D', time: '#3D3A5C', text: '#C08A2B', images: '#2F4B5C', connected: '#151311',
};

export function Masthead({ compact = false }: { compact?: boolean }) {
  return (
    <header className={`is-mast ${compact ? 'is-mast--c' : ''}`}>
      <a className="is-mast__name" href={href('issue', 'landing')} aria-label="NUMEK home">NUMEK</a>
      <p className="is-mast__line">Reliability evidence, published from your own machine</p>
      <nav aria-label="Primary">
        <a href={href('issue', 'app')}>Issues</a>
        <a href={href('issue', 'results')}>Current issue</a>
        <a href={`${href('issue', 'landing')}#colophon`}>Colophon</a>
        <a className="is-btn is-btn--s" href={href('issue', 'app')}>Open DataTrust</a>
      </nav>
    </header>
  );
}

type Run = (typeof runs)[number];

/** Issue covers are generated from each run's own data: representation colour, the defining number, one cover line. */
export function Cover({ run, no, size = 'm' }: { run: Run; no: number; size?: 's' | 'm' }) {
  const big = run.score != null ? run.score.toFixed(1) : run.id === 'finance' ? '18 · 1 · 1' : run.id === 'sms' ? '5,574' : run.id === 'coco' ? '128' : '—';
  const under = run.score != null ? run.band : run.id === 'bike' ? 'No score, by design' : run.id === 'finance' ? 'agree · differ · conflict' : run.id === 'sms' ? 'records' : 'images · 875 objects';
  return (
    <a className={`is-cover is-cover--${size}`} style={{ ['--c' as string]: repColour[run.rep] }} href={run.id === 'adult' ? href('issue', 'results') : href('issue', 'app')}>
      <span className="is-cover__mast">NUMEK<em>Issue {String(no).padStart(2, '0')}</em></span>
      <span className="is-cover__kicker">{run.task}</span>
      <span className="is-cover__big">{big}</span>
      <span className="is-cover__under">{under}</span>
      <span className="is-cover__title">{run.name}</span>
      <span className="is-cover__line">{run.lead}</span>
      <span className="is-cover__foot"><span>{run.size}</span><span>{run.when}</span></span>
    </a>
  );
}
