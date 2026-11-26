// One entry for the core and M3 results: the recorded methodology picks the composition (resolve.ts), never the mode
// a job or saved entry was opened with. The supervised workflows (M4 to M9) render their own pages on the same shell.
import type { ReactNode } from 'react';
import { resolveComposition } from '../resolve';
import { AnnotationPage } from './annotation';
import { ClassificationPage } from './classification';
import { GenericPage } from './generic';
import { MultilabelPage } from './multilabel';
import { NumericPage } from './numeric';
import { ProfilePage } from './profile';
import { ReadinessPage } from './readiness';

type Doc = Record<string, unknown>;
export const TABULAR = ['classification', 'numeric', 'profile', 'annotation', 'multilabel', 'readiness', 'generic'] as const;

export function TabularPage({ a, out, onOpen, presentation, saved, live, fallbackName }: {
  a: Doc; out: ReactNode; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean; live: boolean; fallbackName: string;
}) {
  const { composition, variant } = resolveComposition(a);
  const props = { a, out, onOpen, presentation, saved, live };
  switch (composition) {
    case 'classification': return <ClassificationPage {...props} />;
    case 'numeric': return <NumericPage {...props} variant={variant} />;
    case 'profile': return <ProfilePage {...props} />;
    case 'annotation': return <AnnotationPage {...props} />;
    case 'multilabel': return <MultilabelPage {...props} />;
    case 'readiness': return <ReadinessPage {...props} variant={variant} />;
    default: return <GenericPage {...props} fallbackName={fallbackName} />;
  }
}
