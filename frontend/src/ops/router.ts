// Client routes under /ops/. The server serves the shell for every /ops/ path.
import { useEffect, useState } from 'react';

export type Route = { page: 'fleet' } | { page: 'incidents' } | { page: 'incident'; id: string } | { page: 'deployments' }
  | { page: 'deployment'; id: string } | { page: 'setup'; deployment: string | null } | { page: 'investigations' } | { page: 'proposals' }
  | { page: 'sources'; deployment: string | null } | { page: 'admin' };

export function routeOf(path: string): Route {
  const incident = /^\/ops\/incidents\/([0-9a-f-]{36})\/?$/.exec(path);
  if (incident) return { page: 'incident', id: incident[1] };
  if (/^\/ops\/incidents\/?$/.test(path)) return { page: 'incidents' };
  const deployment = /^\/ops\/deployments\/([a-z0-9][a-z0-9_.-]{0,63})\/?$/.exec(path);
  if (deployment) return { page: 'deployment', id: deployment[1] };
  if (/^\/ops\/deployments\/?$/.test(path)) return { page: 'deployments' };
  const setup = /^\/ops\/setup(?:\/([a-z0-9][a-z0-9_.-]{0,63}))?\/?$/.exec(path);
  if (setup) return { page: 'setup', deployment: setup[1] ?? null };
  if (/^\/ops\/investigations\/?$/.test(path)) return { page: 'investigations' };
  if (/^\/ops\/proposals\/?$/.test(path)) return { page: 'proposals' };
  const sources = /^\/ops\/sources(?:\/([a-z0-9][a-z0-9_.-]{0,63}))?\/?$/.exec(path);
  if (sources) return { page: 'sources', deployment: sources[1] ?? null };
  if (/^\/ops\/admin\/?$/.test(path)) return { page: 'admin' };
  return { page: 'fleet' };
}

export function navigate(href: string) {
  if (href === location.pathname + location.search) return;
  history.pushState(null, '', href);
  dispatchEvent(new PopStateEvent('popstate'));
}

export function usePath() {
  const [path, setPath] = useState(location.pathname);
  useEffect(() => {
    const on = () => setPath(location.pathname);
    addEventListener('popstate', on);
    return () => removeEventListener('popstate', on);
  }, []);
  return path;
}

/** In-app links: plain anchors that route without a reload. */
export function onLink(e: React.MouseEvent<HTMLAnchorElement>) {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.currentTarget;
  if (a.origin !== location.origin || !a.pathname.startsWith('/ops/') || a.target) return;
  e.preventDefault();
  navigate(a.pathname);
}
