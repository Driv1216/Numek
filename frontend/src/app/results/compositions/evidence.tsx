// Shared pieces for the evidence-family workflows (text, image, records and documents): recorded evidence records
// shown as facts and tables, faces read from recorded scalars with their units, and the report's own names from the
// presentation companion. Nothing here computes a value the canonical JSON does not record.
import type { ReactNode } from 'react';
import { BarList } from '../charts/Bars';
import { EvidenceTable } from '../charts/EvidenceTable';
import { RankMark } from '../shell/Ledger';
import { GuidanceFor } from '../shell/Interpretation';
import { recordedRank } from '../normalize';
import type { Companion } from '../model';
import type { Tone } from '../adapter';
import { SHADE } from './tabular';

export type Doc = Record<string, unknown>;
export type Ev = { id: string; family: string; meaning?: string; data: Doc; references?: string[]; scope?: string; population?: string };
export type Fnd = { id: string; family: string; meaning?: string; count?: number; references?: string[]; action?: string; title?: string; priority?: string; population?: string; counts?: Doc };
export type Face = [label: string, detail: string];

export const arr = (v: unknown) => (Array.isArray(v) ? (v as Doc[]) : []);
export const words = (s: unknown) => String(s ?? '').replace(/_/g, ' ');
export const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);
export const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : Number(v) || 0);
export const n = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('en-US') : v == null ? '—' : String(v));
export const plural = (v: unknown, one: string, many = `${one}s`) => `${n(num(v))} ${num(v) === 1 ? one : many}`;
export const sumOf = (o: unknown) => Object.values((o ?? {}) as Doc).reduce<number>((t, v) => t + (typeof v === 'number' ? v : 0), 0);
export const counts = (o: unknown) => Object.entries((o ?? {}) as Doc).filter(([, v]) => typeof v === 'number') as [string, number][];
export const SHADES: (readonly [string, boolean])[] = [SHADE.pale, SHADE.blue, SHADE.card, SHADE.mist, SHADE.deep];

/** The report's name for a family, a meaning, a population or an outcome; the recorded word otherwise. */
export function namer(c: Companion | null) {
  const names = c?.names ?? {};
  return {
    family: (f: string) => names.families?.[f] ?? cap(words(f)),
    meaning: (m: string | undefined) => (m ? names.meanings?.[m] ?? cap(words(m)) : ''),
    population: (p: string | undefined) => (p ? names.populations?.[p] ?? cap(words(p)) : ''),
    status: (s: string) => names.statuses?.[s] ?? cap(words(s)),
    explanation: (id: string) => names.explanations?.[id] ?? null,
  };
}

/** The first recorded count of an evidence record, named by its field: never a generic "Measured". */
export function firstCount(d: Doc): Face {
  const hit = Object.entries(d).find(([, v]) => typeof v === 'number' && Number.isFinite(v));
  return hit ? [`${n(hit[1])} ${words(hit[0])}`, 'Recorded in the canonical evidence.'] : ['Recorded', 'The recorded measurement is in the chapter and the canonical report.'];
}

const cellOf = (v: unknown): string | number | boolean | null => {
  if (v == null) return null;
  if (typeof v === 'number') return Number.isInteger(v) ? v : Number(v.toPrecision(4));
  if (typeof v === 'string' || typeof v === 'boolean') return v;
  if (Array.isArray(v)) return v.every((x) => typeof x !== 'object') ? v.join(', ') || '—' : `${v.length} entries`;
  const entries = counts(v);
  return entries.length ? entries.map(([k, x]) => `${words(k)} ${n(x)}`).join(' · ') : null;
};

export function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return rows.length ? <dl>{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl> : null;
}

/** One evidence record: its scalar and count facts, then each retained list as a bounded, sortable table. */
export function RecordView({ e, title, note }: { e: Ev; title?: string; note?: string | null }) {
  const facts = Object.entries(e.data).map(([k, v]) => [k, cellOf(v)] as const).filter(([, v]) => v != null && v !== '').slice(0, 14);
  const tables = Object.entries(e.data).filter(([, v]) => Array.isArray(v) && v.length && typeof v[0] === 'object').slice(0, 3);
  return (
    <div className="nk-ch__rec">
      {title && <h4>{title}</h4>}
      {note && <p>{note}</p>}
      <Facts rows={facts.map(([k, v]) => [words(k), typeof v === 'number' ? n(v) : String(v)])} />
      {tables.map(([k, rows]) => <EvidenceTable key={k} caption={words(k)} where="the canonical JSON"
        rows={(rows as Doc[]).map((r) => Object.fromEntries(Object.entries(r).map(([c, v]) => [c, cellOf(v)])))} />)}
    </div>
  );
}

/** A finding's chapter block, focusable from the ledger by the same data-ref. */
export function FindingBlock({ f, title, children }: { f: Fnd; title: string; children?: ReactNode }) {
  return (
    <div className="nk-ch__f" data-ref={f.id}>
      <b>{title} <RankMark rank={recordedRank(f as unknown as Doc)} /></b>
      {f.action && <p>{f.action}</p>}
      {children}
      <GuidanceFor refKey={f.id} />
    </div>
  );
}

/** Recorded counts as bars over their own total (a state breakdown); the caption names what is counted. */
export function CountBars({ o, caption, max = 6, unit = '', hot, label }: { o: unknown; caption: string; max?: number; unit?: string; hot?: (k: string) => boolean; label?: (k: string) => string }) {
  const entries = counts(o).sort((x, y) => y[1] - x[1]);
  const total = entries.reduce((t, [, v]) => t + v, 0);
  if (!entries.length || !total) return null;
  return <BarList max={max} scale="denominator" unit={unit} denominator={total} caption={caption} bars={entries.map(([k, v]) => ({ label: label ? label(k) : words(k), value: v, hot: hot?.(k) }))} />;
}

/** Tone from the findings on a tile: a violation the method records as deterministic or declared is critical; any
 *  other finding is a finding. */
export function toneFrom(fs: Fnd[]): Tone {
  if (fs.some((f) => f.priority === 'High' || ['deterministic_violation', 'declared_violation'].includes(String(f.meaning)))) return 'critical';
  return fs.length ? 'finding' : 'info';
}

/** References a saved entry names without resolving them. */
export function References({ refs, note }: { refs: string[]; note: string }) {
  if (!refs.length) return null;
  const short = (r: string) => `…${r.slice(-6)}`;
  return <p className="nk-ch__lim">References {refs.slice(0, 6).map(short).join(' · ')}{refs.length > 6 ? ` · ${n(refs.length - 6)} more` : ''}. {note}</p>;
}
