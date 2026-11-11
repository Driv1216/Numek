// Every tile is a real artefact from one of the seven local runs.
import type { ReactNode } from 'react';
import bikeHours from '../../fixture/bike-hours.generated.json';
import columnsAll from '../../fixture/columns.generated.json';
import { adult, bike, finance, local } from '../../fixture';

interface Col { name: string; kind: 'numeric' | 'categorical'; bins?: number[]; values?: [string, number][]; unique: number; missing: number }
const cols = (columnsAll as unknown as Record<string, { rows: number; columns: Col[] }>).adult.columns;

export type Unit = 'row' | 'value' | 'sentence' | 'image' | 'pair' | 'report';
export interface Tile { id: string; run: string; unit: Unit; title: string; caption: string; body: ReactNode; finding?: string; detail?: string }

export const runColour: Record<string, string> = { adult: '#FF5A3C', bike: '#5DB8E1', german: '#C7B8FF', bank: '#F2C94C', sms: '#9BE15D', coco: '#FF8FB3', finance: '#E8E8E4' };

const Bars = ({ v, red }: { v: number[]; red?: (i: number) => boolean }) => {
  const m = Math.max(1, ...v);
  return <svg viewBox={`0 0 ${v.length} 40`} preserveAspectRatio="none" className="rs-bars">{v.map((x, i) => <rect key={i} x={i + 0.1} y={40 - Math.max(0.6, Math.sqrt(x / m) * 40)} width={0.8} height={Math.max(0.6, Math.sqrt(x / m) * 40)} className={red?.(i) ? 'is-red' : ''} />)}</svg>;
};
const Kv = ({ rows }: { rows: [string, string][] }) => <dl className="rs-kv">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;

const g = adult.conflicts[0];
const hrs = bikeHours.hours as { t: string; casual: number; registered: number; cnt: number }[];
const hMax = Math.max(...hrs.map((h) => h.cnt));

export const tiles: Tile[] = [
  { id: 'a-conf', run: 'adult', unit: 'pair', title: 'Two rows, one difference', caption: 'adult · conflicting labels · 1/5', finding: 'Potentially conflicting target labels', detail: adult.findings[0].review,
    body: <div className="rs-rows">{g.rows.map((r, k) => <p key={r}><b>row {r.toLocaleString()}</b>{Object.values(g.features).slice(0, 8).join(',')},…,<mark>{g.labels[k]}</mark></p>)}</div> },
  { id: 'a-score', run: 'adult', unit: 'report', title: 'Final score', caption: 'adult · decision summary', detail: adult.guardrail.explanation,
    body: <div className="rs-big"><b>{adult.finalScore.toFixed(1)}</b><span>{adult.band} · evidence {adult.evidenceScore} · cap 69</span></div> },
  { id: 'a-target', run: 'adult', unit: 'value', title: 'Target classes', caption: 'adult · annual_income_over_50k', finding: 'Target imbalance', detail: adult.findings[1].evidence,
    body: <div className="rs-waffle">{Array.from({ length: 100 }, (_, i) => <i key={i} className={i < 76 ? '' : 'is-min'} />)}</div> },
  { id: 'a-hours', run: 'adult', unit: 'value', title: 'hours_per_week', caption: 'adult · 1.5 × IQR · 13,496 outside', finding: 'Numeric outlier concentration', detail: `Fences ${adult.hours.lower} – ${adult.hours.upper}; ${adult.hours.below.toLocaleString()} below, ${adult.hours.above.toLocaleString()} above.`,
    body: <Bars v={adult.hours.hist.counts} red={(i) => i + 1 < adult.hours.lower || i + 1 > adult.hours.upper} /> },
  { id: 'a-missing', run: 'adult', unit: 'value', title: 'Where it is empty', caption: 'adult · completeness 99.12', detail: `${adult.missing.cells.toLocaleString()} empty cells; ${adult.missing.rowRate}% of rows touched.`,
    body: <Kv rows={Object.entries(adult.missing.byColumn).map(([k, v]) => [k, v.toLocaleString()])} /> },
  { id: 'a-dups', run: 'adult', unit: 'row', title: 'Repeated rows', caption: 'adult · uniqueness 99.89', detail: `${adult.duplicates.groups} groups; largest ${adult.duplicates.largest}.`,
    body: <div className="rs-big"><b>{adult.duplicates.repeated_rows}</b><span>repeated rows in {adult.duplicates.groups} groups</span></div> },
  { id: 'a-leak', run: 'adult', unit: 'value', title: 'marital_status', caption: 'adult · review-only name', finding: 'Leakage review prompts', detail: adult.findings[3].review,
    body: <div className="rs-big"><b className="rs-mid">review only</b><span>leakage risk 100 · no cap</span></div> },
  { id: 'a-subs', run: 'adult', unit: 'report', title: 'Five sub-scores', caption: 'adult · scoring', detail: 'Evidence is the mean of the five; any at or below 50 caps the result at 69.',
    body: <Kv rows={adult.subScores.map((s) => [s.label, String(s.value)])} /> },
  ...cols.slice(0, 10).map((c): Tile => ({ id: `a-col-${c.name}`, run: 'adult', unit: 'value', title: c.name, caption: `adult · ${c.kind} · ${c.unique} distinct`, body: <Bars v={c.kind === 'numeric' ? c.bins ?? [] : (c.values ?? []).map((v) => v[1])} /> })),
  ...adult.topics.slice(0, 4).map((t, i): Tile => ({ id: `a-topic-${i}`, run: 'adult', unit: 'report', title: t, caption: `adult.html · topic ${i + 1} of 8`, body: <div className="rs-page">{Array.from({ length: 7 }, (_, k) => <i key={k} style={{ width: `${55 + ((k * 23 + i * 11) % 40)}%` }} />)}</div> })),
  { id: 'a-cli', run: 'adult', unit: 'report', title: 'Three files', caption: 'cli · datatrust audit', body: <pre className="rs-pre">{local.cliOutput.join('\n')}</pre> },
  { id: 'b-rel', run: 'bike', unit: 'value', title: bike.relationship, caption: 'bike_hour · 17,379 / 17,379 rows', finding: 'Supported target relationships', detail: 'casual and registered are declared unavailable at prediction time; regression has no universal score.',
    body: <svg viewBox={`0 0 ${hrs.length} 40`} preserveAspectRatio="none" className="rs-bars">{hrs.map((h, i) => <g key={h.t}><rect x={i + 0.1} y={40 - (h.registered / hMax) * 40} width={0.8} height={(h.registered / hMax) * 40} /><rect x={i + 0.1} y={40 - (h.cnt / hMax) * 40} width={0.8} height={(h.casual / hMax) * 40} className="is-red" /></g>)}</svg> },
  { id: 'b-casual', run: 'bike', unit: 'value', title: 'casual', caption: 'bike_hour · IQR candidates', detail: bike.outlier, body: <div className="rs-big"><b>6.86%</b><span>{bike.outlier}</span></div> },
  { id: 'b-holiday', run: 'bike', unit: 'value', title: 'holiday', caption: 'bike_hour · near-constant', detail: bike.nearConstant, body: <div className="rs-big"><b>97.12%</b><span>one value · 2 observed</span></div> },
  { id: 'g-subs', run: 'german', unit: 'report', title: 'No cap applied', caption: 'german_credit · 91.8 Low', body: <Kv rows={[['Completeness', '100'], ['Uniqueness', '100'], ['Target balance', '60'], ['Feature usability', '99.2'], ['Leakage risk', '100']]} /> },
  { id: 'bk-target', run: 'bank', unit: 'value', title: 'Target balance 23.4', caption: 'bank_marketing · 88.3% majority', detail: 'Majority-to-minority ratio 7.55 : 1; capped at 69.', body: <div className="rs-waffle">{Array.from({ length: 100 }, (_, i) => <i key={i} className={i < 88 ? '' : 'is-min'} />)}</div> },
  { id: 's-sms', run: 'sms', unit: 'sentence', title: '5,574 records', caption: 'sms.jsonl · text corpus', detail: 'Near-duplicate candidates via calibrated MinHash search; candidates are review items.', body: <div className="rs-lines">{Array.from({ length: 9 }, (_, k) => <i key={k} className={k === 2 || k === 6 ? 'is-red' : ''} style={{ width: `${48 + ((k * 31) % 50)}%` }} />)}</div> },
  { id: 'c-coco', run: 'coco', unit: 'image', title: '128 images', caption: 'coco val2017 subset · 875 objects', detail: '61 ICC-bearing images excluded from default visual methods.', body: <div className="rs-imgs">{Array.from({ length: 128 }, (_, i) => <i key={i} className={i < 61 ? 'is-x' : ''} />)}</div> },
  { id: 'f-rec', run: 'finance', unit: 'pair', title: 'Record ↔ document', caption: `finance · ${finance.records} records · ${finance.documents} PDFs`, finding: 'Record and document disagree', detail: finance.note, body: <Kv rows={[['agree', String(finance.agreements)], ['discrepancy', String(finance.discrepancies)], ['conflict', String(finance.conflicts)], ['locator', 'page · table · cell']]} /> },
];

export const units: [Unit | 'all', string][] = [['all', 'All'], ['row', 'Rows'], ['value', 'Values'], ['pair', 'Pairs'], ['sentence', 'Sentences'], ['image', 'Images'], ['report', 'Reports']];
