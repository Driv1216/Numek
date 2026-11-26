// Reports and files, the same place on every results page: view the canonical report, download its files, and say
// where the result is kept.
import type { ReactNode } from 'react';
import { Status } from '../../../foundation/system';
import { onLink } from '../../router';

export function ReportBar({ saved, savedNote, note, downloads, onView, extra }: {
  saved: boolean; savedNote?: ReactNode; note?: ReactNode; downloads: ReactNode; onView?: () => void; extra?: ReactNode;
}) {
  return (
    <section className="ap-rs__out ap-reports" aria-labelledby="ap-reports-h">
      <div>
        <h2 id="ap-reports-h" className="ap-q">Reports and files</h2>
        {saved
          ? <p className="ap-muted ap-rs__savedline"><Status tone="on">Saved on this machine · <a href="/app/history" onClick={onLink}>manage in History</a></Status>{savedNote ?? 'A PDF you download now is added to the saved copy.'}</p>
          : <p className="ap-muted">{note ?? 'The canonical report, PDF and JSON carry the same evidence. Exports use completed evidence and do not reanalyse. This result lasts for this session.'}</p>}
      </div>
      <div className="ap-acts">
        {onView && <button type="button" className="nk-btn" onClick={onView}>View full report</button>}
        {downloads}
        {extra}
      </div>
    </section>
  );
}
