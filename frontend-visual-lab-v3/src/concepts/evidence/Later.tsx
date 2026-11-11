import '@fontsource-variable/archivo/standard.css';
import '@fontsource/ibm-plex-mono/400.css';
import './evidence.css';
import { href } from '../../shell/router';
import { Wordmark } from './mark';

/** The workspace and results screens are built only after the landing direction is approved. */
export default function Later() {
  return (
    <div className="em em-later">
      <Wordmark />
      <div>
        <span className="em-label">Not built yet</span>
        <h1 className="em-h2">The workspace and results come next.</h1>
        <p className="em-lede">This direction is under review as a landing page first. Once it is approved, the DataTrust workspace and the Adult result will use the same mark: every finding drawn on its evidence.</p>
        <a className="em-btn" href={href('evidence', 'landing')}>Back to the landing page</a>
      </div>
    </div>
  );
}
