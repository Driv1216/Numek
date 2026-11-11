import { StrictMode, Suspense, lazy, useEffect, type ComponentType, type LazyExoticComponent } from 'react';
import { createRoot } from 'react-dom/client';
import { useRoute, type Screen } from './shell/router';
import { Launcher } from './shell/Launcher';
import { LabBar } from './shell/LabBar';
import './shell/shell.css';

type Concept = Record<Screen, LazyExoticComponent<ComponentType>>;

// Each concept is its own module tree with its own CSS (scoped under its root class).
const concepts: Record<string, Concept> = {
  markup: {
    landing: lazy(() => import('./concepts/markup/Landing')),
    app: lazy(() => import('./concepts/markup/App')),
    results: lazy(() => import('./concepts/markup/Results')),
  },
  'every-row': {
    landing: lazy(() => import('./concepts/every-row/Landing')),
    app: lazy(() => import('./concepts/every-row/App')),
    results: lazy(() => import('./concepts/every-row/Results')),
  },
  issue: {
    landing: lazy(() => import('./concepts/issue/Landing')),
    app: lazy(() => import('./concepts/issue/App')),
    results: lazy(() => import('./concepts/issue/Results')),
  },
  passage: {
    landing: lazy(() => import('./concepts/passage/Landing')),
    app: lazy(() => import('./concepts/passage/App')),
    results: lazy(() => import('./concepts/passage/Results')),
  },
  'two-readings': {
    landing: lazy(() => import('./concepts/two-readings/Landing')),
    app: lazy(() => import('./concepts/two-readings/App')),
    results: lazy(() => import('./concepts/two-readings/Results')),
  },
  provenance: {
    landing: lazy(() => import('./concepts/provenance/Landing')),
    app: lazy(() => import('./concepts/provenance/App')),
    results: lazy(() => import('./concepts/provenance/Results')),
  },
  collection: {
    landing: lazy(() => import('./concepts/collection/Landing')),
    app: lazy(() => import('./concepts/collection/App')),
    results: lazy(() => import('./concepts/collection/Results')),
  },
  modules: {
    landing: lazy(() => import('./concepts/modules/Landing')),
    app: lazy(() => import('./concepts/modules/App')),
    results: lazy(() => import('./concepts/modules/Results')),
  },
  camera: {
    landing: lazy(() => import('./concepts/camera/Landing')),
    app: lazy(() => import('./concepts/camera/App')),
    results: lazy(() => import('./concepts/camera/Results')),
  },
  lexicon: {
    landing: lazy(() => import('./concepts/lexicon/Landing')),
    app: lazy(() => import('./concepts/lexicon/App')),
    results: lazy(() => import('./concepts/lexicon/Results')),
  },
  cutaway: {
    landing: lazy(() => import('./concepts/cutaway/Landing')),
    app: lazy(() => import('./concepts/cutaway/App')),
    results: lazy(() => import('./concepts/cutaway/Results')),
  },
  line: {
    landing: lazy(() => import('./concepts/line/Landing')),
    app: lazy(() => import('./concepts/line/App')),
    results: lazy(() => import('./concepts/line/Results')),
  },
  instrument: {
    landing: lazy(() => import('./concepts/instrument/Landing')),
    app: lazy(() => import('./concepts/instrument/App')),
    results: lazy(() => import('./concepts/instrument/Results')),
  },
  footnote: {
    landing: lazy(() => import('./concepts/footnote/Landing')),
    app: lazy(() => import('./concepts/footnote/App')),
    results: lazy(() => import('./concepts/footnote/Results')),
  },
  cells: {
    landing: lazy(() => import('./concepts/cells/Landing')),
    app: lazy(() => import('./concepts/cells/App')),
    results: lazy(() => import('./concepts/cells/Results')),
  },
  resolution: {
    landing: lazy(() => import('./concepts/resolution/Landing')),
    app: lazy(() => import('./concepts/resolution/App')),
    results: lazy(() => import('./concepts/resolution/Results')),
  },
  relief: {
    landing: lazy(() => import('./concepts/relief/Landing')),
    app: lazy(() => import('./concepts/relief/App')),
    results: lazy(() => import('./concepts/relief/Results')),
  },
  file: {
    landing: lazy(() => import('./concepts/file/Landing')),
    app: lazy(() => import('./concepts/file/App')),
    results: lazy(() => import('./concepts/file/Results')),
  },
  slab: {
    landing: lazy(() => import('./concepts/slab/Landing')),
    app: lazy(() => import('./concepts/slab/App')),
    results: lazy(() => import('./concepts/slab/Results')),
  },
  numek: {
    landing: lazy(() => import('./concepts/numek/Landing')),
    app: lazy(() => import('./concepts/numek/App')),
    results: lazy(() => import('./concepts/numek/Later')),
  },
  evidence: {
    landing: lazy(() => import('./concepts/evidence/Landing')),
    app: lazy(() => import('./concepts/evidence/Later')),
    results: lazy(() => import('./concepts/evidence/Later')),
  },
  findings: {
    landing: lazy(() => import('./concepts/findings/Landing')),
    app: lazy(() => import('./concepts/findings/App')),
    results: lazy(() => import('./concepts/findings/Results')),
  },
};

function Root() {
  const route = useRoute();
  const Screen = route.concept ? concepts[route.concept]?.[route.screen] : null;

  useEffect(() => {
    document.body.dataset.concept = route.concept ?? 'launcher';
    document.body.dataset.screen = route.screen;
    window.scrollTo(0, 0);
  }, [route.concept, route.screen]);

  if (!Screen) return <Launcher />;
  return (
    <>
      <Suspense fallback={<div className="shell-loading" aria-busy="true" />}>
        <Screen key={`${route.concept}/${route.screen}`} />
      </Suspense>
      {!route.clean && <LabBar concept={route.concept!} screen={route.screen} />}
    </>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
