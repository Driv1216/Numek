// Dataset profile (unlabeled, and role-aware profiling): no target and no score. The job is triage by column, so the
// hero counts columns per recorded flag (flags overlap, so each is its own bar) and the columns table is a tile.
import type { ReactNode } from 'react';
import { BarList } from '../charts/Bars';
import type { Companion, Dashboard } from '../model';
import { ResultsShell, useCompanion } from '../shell/ResultsShell';
import { buildDashboard } from './common';
import { checkedRoute, Facts, FindingBlocks, SHADE, columnsTile, identityOf, missingTile, n, numericTile, otherTile, parsingTile, pct, repeatsTile, routeOf, statementOf, variationTile, type Column, type Doc } from './tabular';

function profileHero(a: Doc, route: (f: Doc) => string, roles: Record<string, string[]> | null): Dashboard['tiles'][number] {
  const p = (a.profile as Doc) ?? {}, cols = ((p.columns as Column[] | undefined) ?? []), total = (p.column_count as number) ?? cols.length;
  const zero = (c: Column) => typeof c.numeric_summary?.q1 === 'number' && c.numeric_summary.q1 === c.numeric_summary.q3;
  const flags = [
    { label: 'With missing values', value: cols.filter((c) => (c.missing_count ?? 0) > 0).length },
    { label: 'Constant', value: cols.filter((c) => c.constant).length },
    { label: 'Near-constant', value: cols.filter((c) => c.near_constant).length },
    { label: 'High cardinality', value: cols.filter((c) => c.high_cardinality).length },
    { label: 'Numeric with IQR candidates', value: cols.filter((c) => (c.outlier_count ?? 0) > 0).length },
    { label: 'IQR zero (no fences)', value: cols.filter(zero).length },
  ];
  const bars = (big: boolean) => <BarList bars={flags} denominator={total} unit="columns" scale="denominator" max={big ? 6 : 4} caption="columns per recorded flag; a column can carry several flags, so counts overlap and do not sum" />;
  return {
    id: 'profile', hero: true, name: 'Dataset profile', n: '01', kicker: roles ? 'explicit roles' : 'no target', bg: SHADE.deep[0], light: SHADE.deep[1], tone: 'info',
    label: `${n(p.row_count)} rows × ${n(total)} columns`,
    detail: `${pct(p.missing_rate)} of cells missing · ${n(p.duplicate_rows)} repeated rows.`,
    viz: bars(false), bigViz: bars(true),
    chapter: <>
      <h3>Dataset profile</h3>
      <div className="nk-ch__run"><span>{roles ? 'Every column, in its declared role' : 'Every column takes part'}</span><b>{n(p.row_count)} rows × {n(total)} columns</b><p>Profiling describes what the table contains; it chooses no task and makes no readiness verdict.</p></div>
      <FindingBlocks a={a} tile="profile" route={route} />
      <Facts rows={[['Numeric features', n(p.numeric_feature_count)], ['Non-numeric features', n(p.non_numeric_feature_count)], ['Missing cells', `${n(p.missing_cells)} (${pct(p.missing_rate)})`], ['Repeated rows', n(p.duplicate_rows)],
        ...(roles ? Object.entries(roles).filter(([, v]) => v.length).map(([k, v]) => [`${k[0].toUpperCase()}${k.slice(1)}`, v.join(', ')] as [string, string]) : [])]} />
    </>,
  };
}

export function profileDashboard(a: Doc, companion: Companion | null, saved: boolean): Dashboard {
  const route = (f: Doc) => routeOf('profile', f);
  const r = ((a.profile as Doc)?.roles as Doc | undefined) ?? null;
  const roles = r ? { features: (r.features as string[]) ?? [], metadata: (r.metadata as string[]) ?? [], ignored: (r.ignored as string[]) ?? [], groups: (r.groups as string[]) ?? [] } : null;
  const tiles = [profileHero(a, route, roles), missingTile(a, route, 2), repeatsTile(a, route, 3, false), variationTile(a, route, 4),
    numericTile(a, route, 5, { legacy: false }), columnsTile(a, 6, route), parsingTile(a, 7)!];
  const final = checkedRoute('profile', tiles);
  const other = otherTile(a, final, tiles.length + 1);
  return buildDashboard(a, companion, {
    composition: 'profile', variant: roles ? 'roles' : 'unlabeled', saved, identity: identityOf(a, roles ? 'Profile with explicit roles' : 'Unlabeled profile'),
    statement: statementOf(a, false), tiles: other ? [...tiles, other] : tiles, tileOf: final,
  });
}

export function ProfilePage({ a, out, onOpen, presentation, saved, live }: { a: Doc; out: ReactNode; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean; live: boolean }) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  return <ResultsShell d={profileDashboard(a, companion, !!saved)} label="Profile evidence" out={out} onOpenReport={onOpen} live={live} />;
}
