import { useEffect, useState, type ReactNode, type MouseEvent } from 'react';

export type Screen = 'landing' | 'workspace' | 'results';
export interface Route {
  page: 'launcher' | 'board' | 'concept';
  concept?: string;
  screen: Screen;
}

function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  if (parts[0] === 'board') return { page: 'board', screen: 'landing' };
  if (!parts[0]) return { page: 'launcher', screen: 'landing' };
  const screen = (['landing', 'workspace', 'results'].includes(parts[1]) ? parts[1] : 'landing') as Screen;
  return { page: 'concept', concept: parts[0], screen };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => {
      setRoute(parse(window.location.hash));
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return route;
}

export const href = (concept: string, screen: Screen = 'landing') => `#/${concept}/${screen}`;

export function Go({
  to,
  className,
  children,
  label,
  onClick,
}: {
  to: string;
  className?: string;
  children: ReactNode;
  label?: string;
  onClick?: (e: MouseEvent<HTMLAnchorElement>) => void;
}) {
  return (
    <a href={to} className={className} aria-label={label} onClick={onClick}>
      {children}
    </a>
  );
}
