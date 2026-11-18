// Pieces shared by live and saved results.
import { useEffect, useRef, useState, type ReactNode } from 'react';

/** Four fixed-size corner brackets (Markup's mark). Fixed px, so every corner is identical at any size. */
export function Corners({ tone = 'hot' }: { tone?: 'hot' | 'ghost' }) {
  return <span className={`ap-cn ap-cn--${tone}`} aria-hidden="true"><i /><i /><i /><i /></span>;
}

/** DataTrust's canonical HTML report, full screen inside the app. */
export function Viewer({ name, src, note, downloads, onClose }: { name: string; src: string; note: string; downloads: ReactNode; onClose: () => void }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const back = useRef<HTMLButtonElement>(null);
  // A modal dialog: everything outside it is inert while it is open, focus starts on Back and returns to the opener.
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const made: HTMLElement[] = [];
    for (let node: HTMLElement | null = dialog.current; node && node.parentElement; node = node.parentElement) {
      for (const sibling of Array.from(node.parentElement.children)) {
        if (sibling !== node && sibling instanceof HTMLElement && !sibling.inert) { sibling.inert = true; made.push(sibling); }
      }
      if (node.parentElement === document.body) break;
    }
    back.current?.focus();
    return () => { made.forEach((el) => { el.inert = false; }); opener?.focus(); };
  }, []);
  // Reports from before "Understand this report" (saved analyses keep their original bytes) have no guide to open.
  const [guide, setGuide] = useState(false);
  useEffect(() => { const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }; addEventListener('keydown', esc); return () => removeEventListener('keydown', esc); }, [onClose]);
  const loaded = () => { try { setGuide(!!frame.current?.contentDocument?.getElementById('understand')); } catch { setGuide(false); } };
  const understand = () => {
    const win = frame.current?.contentWindow;
    if (!win) return;
    win.location.hash = 'understand';   // the report's own script opens its guide drawer and moves focus into it
    win.focus();
  };
  return (
    <div ref={dialog} className="ap-view" role="dialog" aria-modal="true" aria-label={`${name}: full DataTrust report`}>
      <header className="ap-view__h">
        <button ref={back} type="button" className="ap-sheet__x" onClick={onClose}>← Back</button>
        <b>{name}</b><span>{note}</span>
        <div className="ap-view__dl">
          {guide && <button type="button" className="ap-sheet__x" onClick={understand}>Understand this report</button>}
          {downloads}
        </div>
      </header>
      <iframe ref={frame} title={`${name} report`} src={src} onLoad={loaded} />
    </div>
  );
}

export const READ_ONLY = 'Private inspection isn’t available for saved analyses. DataTrust doesn’t keep your original sources or private evidence state. Run the analysis again to inspect evidence.';

export const fmt = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('en-US'));
export const MiB = (b: number) => (b / 1048576).toFixed(2);

export const SEPARATOR_OPTIONS: [string, string][] = [['auto', 'Detect automatically'], [',', 'Comma'], [';', 'Semicolon'], ['\t', 'Tab'], ['|', 'Vertical bar']];
export const separatorName = (d: string) => ({ ',': 'comma', ';': 'semicolon', '\t': 'tab', '|': 'vertical bar' } as Record<string, string>)[d] ?? d;

/** The CSV separator choice: detect, or one of the four DataTrust reads. */
export function SeparatorSelect({ value, onChange, auto = true, disabled, label = 'Separator' }: { value: string; onChange: (v: string) => void; auto?: boolean; disabled?: boolean; label?: string }) {
  return (
    <label className="ap-sep">{label}
      <select value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        {SEPARATOR_OPTIONS.filter(([v]) => auto || v !== 'auto').map(([v, t]) => <option key={v} value={v}>{t}</option>)}
      </select>
    </label>
  );
}

const SEPARATORS: [RegExp, string][] = [[/;/, 'Semicolon'], [/\t/, 'Tab'], [/\|/, 'Vertical bar']];
/** A file read with commas that arrived as one column whose name holds another separator. */
export function SeparatorHint({ inspection }: { inspection: { column_count: number; columns: string[] } }) {
  const only = inspection.column_count === 1 ? inspection.columns[0] ?? '' : '';
  const sep = SEPARATORS.find(([re]) => re.test(only))?.[1];
  if (!sep) return null;
  return (
    <p className="ap-note ap-note--warn" role="alert">
      <b>This file looks separated by {sep.toLowerCase()}s, not commas.</b> Read with commas, each row arrives as a single column and no real outcome can be offered. Choose “{sep}” as the separator above to read it in columns.
    </p>
  );
}
