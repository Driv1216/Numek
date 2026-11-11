import '@fontsource-variable/schibsted-grotesk';
import '@fontsource/ibm-plex-mono/400.css';
import './nk.css';
import { href } from '../../shell/router';
import { Frame, Wordmark } from './system';

/** The product pages, app and results are later build steps of the blend plan. */
export default function Later() {
  return (
    <div className="nk nk-later">
      <Frame />
      <Wordmark />
      <div>
        <span className="nk-label">Not built yet</span>
        <h1 className="nk-h2">The product pages, the DataTrust app and the Adult result come next.</h1>
        <p className="nk-lede">Step one of the blend plan is the NUMEK landing. Once you have reviewed it, the DataTrust page, the ConfidenceGuard and HallucinationGuard pages, then the Modules workspace and results follow.</p>
        <a className="nk-btn" href={href('numek', 'landing')}>Back to the NUMEK landing</a>
      </div>
    </div>
  );
}
