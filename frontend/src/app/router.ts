// History routing under /app/. The server's job state decides which step is reachable.
import { useEffect, useState } from 'react';

export type Step = 'upload' | 'configure' | 'confirm' | 'report';
export const steps: { id: Step; n: number; t: string }[] = [
  { id: 'upload', n: 1, t: 'Upload' }, { id: 'configure', n: 2, t: 'Configure' }, { id: 'confirm', n: 3, t: 'Confirm' }, { id: 'report', n: 4, t: 'Report' },
];

export const stepHref = (s: Step) => (s === 'upload' ? '/app/' : `/app/core/${s}`);

export function stepOf(path: string): Step {
  const m = /^\/app\/core\/(configure|confirm|report|upload)\/?$/.exec(path);
  return (m?.[1] as Step | undefined) ?? 'upload';
}

export function navigate(href: string, replace = false) {
  if (href === location.pathname) return;
  history[replace ? 'replaceState' : 'pushState'](null, '', href);
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
  if (a.origin !== location.origin || !a.pathname.startsWith('/app/')) return;
  e.preventDefault();
  navigate(a.pathname);
}
