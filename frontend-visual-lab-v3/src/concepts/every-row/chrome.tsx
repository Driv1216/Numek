import { href } from '../../shell/router';

export function Wordmark() {
  return (
    <a className="er-wm" href={href('every-row', 'landing')} aria-label="NUMEK home">
      <span className="er-wm__grid" aria-hidden="true">{Array.from({ length: 9 }, (_, i) => <i key={i} className={i === 5 ? 'on' : ''} />)}</span>
      NUMEK
    </a>
  );
}

export function Header() {
  return (
    <header className="er-head">
      <Wordmark />
      <nav aria-label="Primary">
        <a href="#units">Units</a>
        <a href="#local">Local</a>
        <a href="#reports">Reports</a>
        <a href={href('every-row', 'results')}>Adult, in full</a>
      </nav>
      <a className="er-btn er-btn--s" href={href('every-row', 'app')}>Open DataTrust</a>
    </header>
  );
}
