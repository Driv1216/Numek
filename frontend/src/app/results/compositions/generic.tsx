// A result this app has no composition for (an unknown or future methodology, or a newer schema): shown as recorded
// (header, every finding with its recorded rank, coverage and the report), never drawn as another workflow.
import type { ReactNode } from 'react';
import { ResultsShell, useCompanion } from '../shell/ResultsShell';
import { buildDashboard } from './common';

type Doc = Record<string, unknown>;

export function GenericPage({ a, out, onOpen, presentation, saved, fallbackName }: {
  a: Doc; out: ReactNode; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean; fallbackName: string;
}) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  const ctx = (a.context as Doc | undefined) ?? {}, narrative = (a.narrative as Doc | undefined) ?? {}, profile = (a.profile as Doc | undefined) ?? {};
  const method = String(a.methodology_id ?? 'not recorded'), schema = String(a.schema_version ?? 'not recorded');
  const d = buildDashboard(a, companion, {
    composition: 'generic', variant: method, saved: !!saved,
    identity: { name: String(ctx.dataset_name ?? profile.dataset_name ?? fallbackName), sources: String(ctx.source_filename ?? '') || 'Sources not recorded',
                workflow: 'Recorded result', when: (a.generated_at as string) ?? null, methodology: method, schema },
    statement: String(narrative.overall_assessment ?? narrative.summary ?? '') || undefined, tiles: [], tileOf: () => null,
  });
  d.notice = (
    <p className="ap-note"><b>Shown as recorded.</b> This analysis was produced by <code>{method}</code> (schema {schema}), which this app has no dashboard for.
      Its findings, coverage and report are shown as they were recorded; nothing is scored or drawn for it. Open the report for its own presentation.</p>
  );
  return <ResultsShell d={d} label="Recorded checks" out={out} onOpenReport={onOpen} live={!saved} />;
}
