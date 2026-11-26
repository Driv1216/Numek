// The shared results shell every workflow composition is drawn on, live or saved:
//   header (what was analysed) → outcome band (recorded statement, finding counts, state) → findings ledger and the
//   workflow's Modules mosaic → coverage and methodology → reports and files.
// The shell owns the order, the ledger-to-chapter and ledger-to-report navigation, and the result states; a composition
// owns the hero, the tiles and what they draw.
import { useEffect, useState, type ReactNode } from 'react';
import { Status } from '../../../foundation/system';
import { date } from '../adapter';
import type { Companion, Dashboard, LedgerFinding } from '../model';
import { Tiles, type TileRequest } from '../Tiles';
import { CoverageLedger } from './Coverage';
import { FindingsLedger, RankMark } from './Ledger';
import { InterpretationContext, SummaryLead } from './Interpretation';
import { call } from '../../api';

/** The presentation companion for this result (dashboard_companion_v1), or null when it cannot be read: the dashboard
 *  then shows canonical titles and says the report link was not verified. */
export function useCompanion(path: string | null): Companion | null | undefined {
  const [c, setC] = useState<Companion | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    setC(undefined);
    if (!path) { setC(null); return; }
    call<Companion>('GET', path).then((x) => live && setC(x)).catch(() => live && setC(null));
    return () => { live = false; };
  }, [path]);
  return c;
}

const CHIP = { findings: 'Findings to review', clean: 'No threshold-level findings', partial: 'Partial: completed evidence shown' } as const;

function counts(findings: LedgerFinding[]) {
  const by = new Map<string, { n: number; f: LedgerFinding }>();
  for (const f of findings) { const k = f.rank.label || 'Unranked'; by.set(k, { n: (by.get(k)?.n ?? 0) + 1, f: by.get(k)?.f ?? f }); }
  return [...by.entries()].sort((a, b) => a[1].f.rank.order - b[1].f.rank.order);
}

export function ResultsShell({ d, label, out, onOpenReport, saved, live }: {
  d: Dashboard; label: string; out: ReactNode; onOpenReport: (anchor?: string) => void; saved?: ReactNode; live: boolean;
}) {
  const [request, setRequest] = useState<TileRequest | null>(null);
  const s = d.state;
  const evidence = (f: LedgerFinding) => f.tile && setRequest({ tile: f.tile, ref: f.ref, nonce: Date.now() });
  const report = (f: LedgerFinding) => onOpenReport(f.locator.kind === 'anchor' || f.locator.kind === 'section' ? String(f.locator.value) : undefined);
  const id = d.identity;
  return (
    <InterpretationContext.Provider value={{ interp: d.interpretation ?? null, live, composition: d.composition }}>
    <div className={`ap-rs ap-dash ap-dash--${d.composition}`}>
      <header className="ap-rs__bar ap-dash__head">
        <div>
          <span className="nk-label">{id.workflow}{id.variant && id.variant !== id.workflow ? ` · ${id.variant}` : ''}</span>
          <h1>{id.name}</h1>
        </div>
        <p>
          {id.sources}{id.scale ? ` · ${id.scale}` : ''}<br />
          {id.when ? `Analysed ${date(id.when)}` : 'Analysis time not recorded'} · {id.methodology ?? 'methodology not recorded'}{id.schema ? ` · schema ${id.schema}` : ''} · local<br />
          <button type="button" className="ap-rs__open" onClick={() => onOpenReport()}>Open report ↗</button>
        </p>
      </header>
      <div className="ap-dash__chips">
        <span className={`ap-state is-${s.chip}`}>{CHIP[s.chip]}</span>
        {s.bounded && <span className="ap-state is-bounded">Bounded search: coverage limits apply</span>}
        {saved ?? ((s.saved || !live) && <Status tone="on">Saved analysis · read-only canonical result</Status>)}
      </div>
      {d.notice}
      <section className="ap-outcome" aria-label="Outcome">
        <SummaryLead interp={d.interpretation} fallback={d.statement} />
        <div className="ap-outcome__n">
          {d.findings.length
            ? counts(d.findings).map(([k, v]) => <span key={k} className="ap-outcome__c"><RankMark rank={v.f.rank} /> <b>{v.n}</b></span>)
            : <span className="ap-outcome__c">No findings</span>}
          {s.run === 'partial' && <span className="ap-outcome__c is-warn">Run incomplete: some checks did not finish</span>}
        </div>
        {!!s.historical.length && <p className="ap-outcome__hist">Recorded by an earlier version: {s.historical.join(' and ')} {s.historical.length > 1 ? 'were' : 'was'} not recorded, so nothing is shown or filled in for {s.historical.length > 1 ? 'them' : 'it'}.</p>}
      </section>
      <div className="ap-dash__body">
        <div className={`ap-dash__grid ${d.tiles.length ? '' : 'is-solo'}`}>
          <FindingsLedger findings={d.findings} clean={{ checked: d.coverage.completed, unknowns: d.unknowns }} onEvidence={evidence} onReport={report} />
          {d.tiles.length > 0 && <div className="ap-dash__mosaic"><Tiles tiles={d.tiles} label={label} request={request} /></div>}
        </div>
      </div>
      <CoverageLedger c={d.coverage} unknowns={d.unknowns} />
      {out}
    </div>
    </InterpretationContext.Provider>
  );
}
