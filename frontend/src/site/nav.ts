// Links on the static marketing site: two pages (/ and /datatrust/), sections as #fragments.
// The site has no app: "Open DataTrust" leads to the run instructions on the DataTrust page.
import { useEffect } from 'react';
import { reducedMotion } from '../foundation/motion';

export function pageHref(p?: string, s?: string) {
  return `${p === 'datatrust' ? '/datatrust/' : '/'}${s ? `#${s}` : ''}`;
}

export function appHref() {
  return pageHref('datatrust', 'dt-run');
}

/** Scrolls to the #section once the page has rendered; in-page section links scroll smoothly. */
export function useHashScroll() {
  useEffect(() => {
    const go = (id: string, smooth: boolean) =>
      document.getElementById(id)?.scrollIntoView({ behavior: smooth && !reducedMotion() ? 'smooth' : 'auto', block: 'start' });
    const t = setTimeout(() => { const id = decodeURIComponent(location.hash.slice(1)); if (id) go(id, false); }, 60);
    const click = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (!a || a.origin !== location.origin || a.pathname !== location.pathname) return;
      e.preventDefault();
      history.pushState(null, '', a.hash || a.pathname);
      if (a.hash) go(decodeURIComponent(a.hash.slice(1)), true); else scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' });
    };
    document.addEventListener('click', click);
    return () => { clearTimeout(t); document.removeEventListener('click', click); };
  }, []);
}
