// Shared console parts: standing glyphs, priority marks, data loading, and honest empty/refused/loading states.
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { ApiError, api, type Priority, type Standing } from './api';

export const STANDINGS: Record<Standing, { glyph: string; label: string }> = {
  D: { glyph: '■', label: 'Deterministic violation' },
  F: { glyph: '◆', label: 'Formal sequential evidence' },
  P: { glyph: '◐', label: 'Practical effect (descriptive)' },
  E: { glyph: '○', label: 'Estimate (named assumption)' },
  X: { glyph: '◇', label: 'Experimental' },
  A: { glyph: '△', label: 'Association' },
  H: { glyph: '◌', label: 'Hypothesis' },
};

export function Glyph({ s }: { s: Standing }) {
  const item = STANDINGS[s] ?? { glyph: '?', label: s };
  return <span className={`op-glyph op-glyph--${s}`} title={item.label} aria-label={item.label} role="img">{item.glyph}</span>;
}

export function Legend() {
  return (
    <details className="op-legend">
      <summary>Standings legend</summary>
      <ul>{(Object.keys(STANDINGS) as Standing[]).map((s) => <li key={s}><Glyph s={s} /> <b>{s}</b> {STANDINGS[s].label}</li>)}</ul>
    </details>
  );
}

/** Priority shown by shape and weight: P1 filled, P2 half, P3 outlined, P4 dotted. */
export function PriorityMark({ p }: { p: Priority }) {
  return <span className={`op-prio op-prio--${p}`}><i aria-hidden="true" />{p}</span>;
}

export const words = (s: string | null | undefined) => (s ?? '').replace(/_/g, ' ');

export function when(iso: string | null | undefined) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
}

export function Refused({ error }: { error: unknown }) {
  const e = error instanceof ApiError ? error : new ApiError('client_error', String(error), 0);
  return (
    <div className="op-refused" role="alert">
      <b className="op-mono">{e.code}</b>
      <p>{e.message}</p>
      {e.code === 'stale_revision' && <p>Someone changed this since you loaded it. Reload, then try again.</p>}
      {e.code === 'csrf_failed' && <p>This tab has no action token. Sign out and sign in again to act here.</p>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="op-empty">{children}</p>;
}

export function Loading({ what }: { what: string }) {
  return <p className="op-loading" aria-live="polite">Loading {what}…</p>;
}

/** Fetch a resource; reload() re-reads it. */
export function useResource<T>(path: string | null) {
  const [state, setState] = useState<{ data?: T; error?: unknown; loading: boolean }>({ loading: true });
  const load = useCallback(() => {
    if (!path) return;
    setState((s) => ({ ...s, loading: true }));
    api.get<T>(path).then((data) => setState({ data, loading: false }), (error) => setState({ error, loading: false }));
  }, [path]);
  useEffect(load, [load]);
  return { ...state, reload: load };
}

/** A button that performs one API action, shows its refusal verbatim, and reports success. */
export function Action({ label, run, onDone, disabled, title, tone = 'plain' }: { label: string; run: () => Promise<unknown>; onDone?: () => void; disabled?: boolean; title?: string; tone?: 'plain' | 'primary' }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <span className="op-action">
      <button type="button" className={`op-btn op-btn--${tone}`} disabled={disabled || busy} title={title}
        onClick={async () => { setBusy(true); setError(null); try { await run(); onDone?.(); } catch (e) { setError(e); } finally { setBusy(false); } }}>
        {busy ? 'Working…' : label}
      </button>
      {error != null && <Refused error={error} />}
    </span>
  );
}
