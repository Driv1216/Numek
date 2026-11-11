import { representations } from '../../fixture';
import { href } from '../../shell/router';
import { repColour } from './artefacts';

export function Wordmark() {
  return (
    <a className="ps-wm" href={href('passage', 'landing')} aria-label="NUMEK home">
      <span className="ps-wm__bar" aria-hidden="true">{representations.map((r) => <i key={r.id} style={{ background: repColour[r.id] }} />)}</span>
      NUMEK
    </a>
  );
}

export function Header({ app = false }: { app?: boolean }) {
  return (
    <header className={`ps-head ${app ? 'ps-head--app' : ''}`}>
      <Wordmark />
      {!app && <nav aria-label="Primary"><a href={href('passage', 'results')}>Follow a finding</a><a href={href('passage', 'app')}>Workspace</a></nav>}
      {app ? <span className="ps-mono ps-head__local">Local workspace · 127.0.0.1</span> : <a className="ps-btn ps-btn--s" href={href('passage', 'app')}>Open DataTrust</a>}
    </header>
  );
}
