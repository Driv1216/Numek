import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { useRoute } from './shared/router';
import { concepts } from './concepts/registry';
import Launcher from './lab/Launcher';
import './lab/reset.css';

const Board = lazy(() => import('./lab/Board'));

function App() {
  const route = useRoute();
  if (route.page === 'board')
    return (
      <Suspense fallback={null}>
        <Board />
      </Suspense>
    );
  const concept = concepts.find((c) => c.id === route.concept);
  if (route.page === 'concept' && concept) {
    const C = concept.Component;
    return (
      <Suspense fallback={null}>
        <C screen={route.screen} />
      </Suspense>
    );
  }
  return <Launcher />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
