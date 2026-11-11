import { useState } from 'react';
import type { Screen } from './router';

const names: Record<string, string> = { markup: '01 Markup', 'every-row': '02 Every Row', issue: '03 The Issue', passage: '04 Passage', 'two-readings': '05 Two Readings', provenance: '06 Provenance', collection: '07 Collection', modules: '08 Modules', camera: '09 Product Camera', lexicon: '10 Lexicon', cutaway: '11 Cutaway', line: '12 The Local Line', instrument: '13 Instrument', footnote: '14 Footnote', cells: '15 Cells', resolution: '16 Resolution', relief: '17 Relief', file: '18 The File', slab: '19 Slab', findings: '20 Findings First', evidence: '21 The Evidence Mark', numek: '22 NUMEK blend' };
const screens: [Screen, string][] = [['landing', 'Landing'], ['app', 'Dashboard'], ['results', 'Results']];

/** Lab-only navigation, deliberately neutral so it does not compete with the concept. */
export function LabBar({ concept, screen }: { concept: string; screen: Screen }) {
  const [open, setOpen] = useState(false);
  return (
    <nav className={`labbar ${open ? 'is-open' : ''}`} aria-label="Lab navigation">
      <button className="labbar__toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        Lab · {names[concept]} · {screens.find(([s]) => s === screen)?.[1]}
      </button>
      {open && (
        <div className="labbar__panel">
          <a href="#/">All concepts</a>
          {Object.entries(names).map(([id, n]) => (
            <div key={id} className="labbar__row">
              <span>{n}</span>
              {screens.map(([s, l]) => (
                <a key={s} href={`#/${id}/${s}`} aria-current={id === concept && s === screen ? 'page' : undefined} onClick={() => setOpen(false)}>{l}</a>
              ))}
            </div>
          ))}
          <a href="/research/">Research board</a>
        </div>
      )}
    </nav>
  );
}
