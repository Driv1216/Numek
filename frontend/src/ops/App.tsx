// The console shell: app bar, left rail and the session gate.
import { useEffect, useState } from 'react';
import { ApiError, api, type Session } from './api';
import { DeploymentPage, Deployments } from './Deployment';
import { Fleet } from './Fleet';
import { Incident } from './Incident';
import { Incidents } from './Incidents';
import { InvestigationsList, ProposalsList } from './Lists';
import { Admin } from './Admin';
import { Login } from './Login';
import { Setup } from './Setup';
import { Sources } from './Sources';
import { Legend, Loading } from './parts';
import { onLink, routeOf, usePath } from './router';

const AREAS: { id: string; label: string; href: string }[] = [
  { id: 'fleet', label: 'Fleet', href: '/ops/' },
  { id: 'incidents', label: 'Incidents', href: '/ops/incidents' },
  { id: 'deployments', label: 'Deployments', href: '/ops/deployments' },
  { id: 'investigations', label: 'Investigations', href: '/ops/investigations' },
  { id: 'proposals', label: 'Proposals', href: '/ops/proposals' },
  { id: 'sources', label: 'Sources', href: '/ops/sources' },
  { id: 'setup', label: 'Setup', href: '/ops/setup' },
  { id: 'admin', label: 'Admin', href: '/ops/admin' },
];

export default function App() {
  const path = usePath();
  const route = routeOf(path);
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  const refresh = () => api.get<Session>('/session').then(setSession, (e) => {
    if (e instanceof ApiError && e.status === 401) setSession(null); else setSession(null);
  });
  useEffect(() => { refresh(); }, []);

  if (session === undefined) return <div className="nk op"><Loading what="your session" /></div>;
  if (session === null) return <div className="nk op"><Login onSignedIn={refresh} /></div>;

  const active = route.page === 'incident' ? 'incidents' : route.page === 'deployment' ? 'deployments' : route.page;
  return (
    <div className="nk op">
      <header className="op-bar">
        <a className="op-mark" href="/ops/" onClick={onLink}><i aria-hidden="true" /><b>ConfidenceGuard</b><span>operations</span></a>
        <div className="op-bar__r">
          <span className="op-who"><b>{session.principal.name}</b><span className="op-mono">{session.permissions.join(' · ') || 'no permissions'}</span></span>
          <button type="button" className="op-btn" onClick={async () => { await api.signOut(); setSession(null); }}>Sign out</button>
        </div>
      </header>
      <div className="op-body">
        <nav className="op-rail" aria-label="Areas">
          {AREAS.map((a) => <a key={a.id} href={a.href} onClick={onLink} className={`op-rail__a ${active === a.id ? 'is-on' : ''}`} aria-current={active === a.id ? 'page' : undefined}>{a.label}</a>)}
          <Legend />
        </nav>
        <main className="op-main" id="main">
          {route.page === 'fleet' && <Fleet />}
          {route.page === 'incidents' && <Incidents />}
          {route.page === 'incident' && <Incident id={route.id} session={session} />}
          {route.page === 'deployments' && <Deployments />}
          {route.page === 'deployment' && <DeploymentPage id={route.id} />}
          {route.page === 'setup' && <Setup deployment={route.deployment} session={session} />}
          {route.page === 'investigations' && <InvestigationsList session={session} />}
          {route.page === 'proposals' && <ProposalsList session={session} />}
          {route.page === 'sources' && <Sources deployment={route.deployment} />}
          {route.page === 'admin' && <Admin session={session} />}
        </main>
      </div>
    </div>
  );
}
