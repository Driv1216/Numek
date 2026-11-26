// Recorded temporal ticks, read in the unit the chronology evidence records (`clock_units`): nanoseconds since the
// epoch for instants and local date-times, days since the epoch for civil dates. Ticks are exact integers stored as
// strings; display rounds them to the precision a reader needs and never changes the recorded value.

export type ClockUnits = 'nanoseconds' | 'civil days' | string;

const NS_PER_DAY = 86_400_000_000_000;

function num(t: unknown): number | null {
  if (t == null || t === '') return null;
  const v = typeof t === 'number' ? t : Number(String(t));
  return Number.isFinite(v) ? v : null;
}

/** Milliseconds since the epoch for a recorded tick, or null. */
export function tickMs(t: unknown, units: ClockUnits = 'nanoseconds'): number | null {
  const v = num(t);
  if (v == null) return null;
  return units === 'civil days' ? v * 86_400_000 : v / 1e6;
}

/** A recorded tick as a date, or a date and minute when the span it sits in is under a few days. Local date-times
 *  are wall-clock values; instants are shown in UTC, and say so. */
export function fmtTick(t: unknown, units: ClockUnits = 'nanoseconds', opts: { span?: number | null; kind?: string } = {}): string {
  const ms = tickMs(t, units);
  if (ms == null) return '—';
  const iso = new Date(ms).toISOString();
  if (units === 'civil days') return iso.slice(0, 10);
  const short = opts.span != null && opts.span < 3 * NS_PER_DAY;
  const text = short ? `${iso.slice(0, 10)} ${iso.slice(11, 16)}` : iso.slice(0, 10);
  return short && opts.kind === 'instant' ? `${text} UTC` : text;
}

/** A recorded duration in ticks, in the largest whole unit that reads naturally. */
export function fmtSpan(t: unknown, units: ClockUnits = 'nanoseconds'): string {
  const v = num(t);
  if (v == null) return '—';
  if (units === 'civil days') return `${v.toLocaleString('en-US')} day${v === 1 ? '' : 's'}`;
  const steps: [number, string][] = [[NS_PER_DAY, 'day'], [3_600e9, 'hour'], [60e9, 'minute'], [1e9, 'second'], [1e6, 'millisecond'], [1e3, 'microsecond'], [1, 'nanosecond']];
  const abs = Math.abs(v);
  const [size, name] = steps.find(([s]) => abs >= s) ?? [1, 'nanosecond'];
  const q = v / size, r = Number.isInteger(q) ? q : Number(q.toPrecision(3));
  return `${r.toLocaleString('en-US')} ${name}${Math.abs(r) === 1 ? '' : 's'}`;
}

/** Field names that hold ticks (instants) or tick durations, so tables can format them. */
export const isTickKey = (k: string) => /(^|_)tick$|^(start|end|first|last)_tick|_at_tick$/.test(k) || /observed_(first|last)_tick/.test(k);
export const isSpanKey = (k: string) => /_ticks$|^cadence_ns$|_ns$/.test(k);
