import { useEffect, useState } from 'react';

export type Screen = 'landing' | 'app' | 'results';

export interface Route { concept: string | null; screen: Screen; clean: boolean; params: URLSearchParams }

// Routes: #/ (launcher), #/<concept>/<landing|app|results>[?clean]
export function parse(hash = location.hash): Route {
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const [concept, screen] = path.split('/');
  const params = new URLSearchParams(query);
  return {
    concept: concept || null,
    screen: (['landing', 'app', 'results'].includes(screen) ? screen : 'landing') as Screen,
    clean: params.has('clean'),
    params,
  };
}

export function useRoute() {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const on = () => setRoute(parse());
    addEventListener('hashchange', on);
    return () => removeEventListener('hashchange', on);
  }, []);
  return route;
}

export const href = (concept: string, screen: Screen) => {
  const clean = parse().clean ? '?clean' : '';
  return `#/${concept}/${screen}${clean}`;
};
