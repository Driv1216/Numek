// A recorded evidence table: native table semantics, sortable headers with aria-sort (WAI-ARIA APG sortable table),
// an accessible caption that says how many rows are shown of how many recorded, and paging instead of silent slicing.
import { useMemo, useState } from 'react';

type Row = Record<string, unknown>;
const cell = (v: unknown) => (v == null ? '—' : typeof v === 'number' ? v.toLocaleString('en-US', Number.isInteger(v) ? {} : { maximumSignificantDigits: 6 })
  : typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v));

export function EvidenceTable({ rows, keys, caption, where, page = 20 }: { rows: Row[]; keys?: string[]; caption: string; where?: string; page?: number }) {
  const columns = useMemo(() => (keys ?? Object.keys(rows[0] ?? {}).filter((k) => rows.some((r) => ['string', 'number', 'boolean'].includes(typeof r[k])))).slice(0, 8), [rows, keys]);
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [shown, setShown] = useState(page);
  const ordered = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => {
      const x = a[sort.key], y = b[sort.key];
      if (x == null) return 1; if (y == null) return -1;
      return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))) * sort.dir;
    });
  }, [rows, sort]);
  if (!rows.length || !columns.length) return null;
  const visible = ordered.slice(0, shown);
  return (
    <div className="ap-chtab ap-evt">
      <table>
        <caption>{caption} · {visible.length.toLocaleString('en-US')} of {rows.length.toLocaleString('en-US')} recorded rows{where ? ` · all in ${where}` : ''}. Column buttons sort.</caption>
        <thead><tr>{columns.map((k) => {
          const on = sort?.key === k;
          return <th key={k} scope="col" aria-sort={on ? (sort!.dir === 1 ? 'ascending' : 'descending') : 'none'}>
            <button type="button" onClick={() => setSort({ key: k, dir: on && sort!.dir === 1 ? -1 : 1 })}>{k.replace(/_/g, ' ')}<span aria-hidden="true">{on ? (sort!.dir === 1 ? ' ▲' : ' ▼') : ' ◇'}</span></button>
          </th>;
        })}</tr></thead>
        <tbody>{visible.map((r, i) => <tr key={i}>{columns.map((k) => <td key={k}>{cell(r[k])}</td>)}</tr>)}</tbody>
      </table>
      {rows.length > shown && <button type="button" className="ap-link" onClick={() => setShown((n) => n + page * 5)}>Show {Math.min(page * 5, rows.length - shown).toLocaleString('en-US')} more rows</button>}
    </div>
  );
}
