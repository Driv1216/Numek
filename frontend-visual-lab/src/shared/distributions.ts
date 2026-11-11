// Real distributions from the pinned Adult CSV (research/extract_distributions.py).
import raw from './distributions.json';

export interface NumericCol { name: string; missing: number; kind: 'numeric'; min: number; max: number; bins: number[]; edges: number[] }
export interface CatCol { name: string; missing: number; kind: 'categorical'; top: [string, number][]; other: number; distinct: number }
export type ColDist = NumericCol | CatCol;

const r = raw as unknown as {
  columns: ColDist[];
  grid: { age_edges: number[]; hour_edges: number[]; counts: number[][]; high: number[][] };
};
export const dists = r.columns;
export const grid = r.grid;
export const dist = (name: string) => dists.find((d) => d.name === name)!;
