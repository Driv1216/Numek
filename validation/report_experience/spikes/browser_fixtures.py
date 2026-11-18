"""Spikes (a) and (e): build the browser fixtures for info links, popover focus behaviour and the report CSP.

Usage: PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.spikes.browser_fixtures
Writes spikes/browser/term_popover.html (standalone report shape) and spikes/browser/iframe_parent.html (the app's viewer
shape: a same-origin parent embedding the report). The page records its own observations in window.dtSpike, which the
browser session reads; results are recorded in spikes/results/browser.json by hand from that session.

The fixture's only executable script is hashed into the meta CSP. Two simulated injections (an inline script and an
inline event handler) must be blocked by that CSP; a data: image must still load.
"""
import base64
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent / 'browser'

SCRIPT = r"""
(function () {
  var spike = window.dtSpike = window.dtSpike || {};
  spike.popoverSupported = typeof HTMLElement.prototype.showPopover === 'function';
  spike.enhanced = false;
  var pop = document.getElementById('dt-pop');
  if (!spike.popoverSupported || !pop) return;
  var title = pop.querySelector('.dt-pop__title'), body = pop.querySelector('.dt-pop__body');
  var close = pop.querySelector('.dt-pop__close'), trigger = null;
  document.querySelectorAll('a.dt-term').forEach(function (link) {
    link.setAttribute('role', 'button');
    link.setAttribute('aria-expanded', 'false');
    link.setAttribute('aria-controls', 'dt-pop');
    function open(event) {
      event.preventDefault();
      var entry = document.getElementById(link.getAttribute('href').slice(1));
      if (!entry) return;
      title.textContent = entry.querySelector('h3').textContent;
      body.replaceChildren();
      entry.querySelectorAll('.dt-layer').forEach(function (layer) { body.appendChild(layer.cloneNode(true)); });
      var more = document.createElement('a'); more.href = '#' + entry.id; more.textContent = 'More in Understand this report';
      more.addEventListener('click', function () { pop.hidePopover(); });
      body.appendChild(more);
      trigger = link;
      if (pop.matches(':popover-open')) pop.hidePopover();
      pop.showPopover();
      link.setAttribute('aria-expanded', 'true');
      title.focus();
    }
    link.addEventListener('click', open);
    link.addEventListener('keydown', function (event) { if (event.key === ' ') open(event); });
  });
  close.addEventListener('click', function () { pop.hidePopover(); });
  pop.addEventListener('toggle', function (event) {
    if (event.newState === 'closed' && trigger) {
      trigger.setAttribute('aria-expanded', 'false');
      trigger.focus();
      spike.focusReturned = document.activeElement === trigger;
    }
  });
  spike.enhanced = true;
  var img = document.getElementById('data-img');
  spike.dataImageLoaded = !!img && img.complete && img.naturalWidth > 0;
})();
"""

PNG = base64.b64encode(bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0f01f0005000201'
    'a5f8f39a0000000049454e44ae426082')).decode()


def page():
    digest = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    csp = f"default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-{digest}'"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Info link spike</title>
<style>
body {{ font: 15px/1.5 -apple-system, "Segoe UI", sans-serif; max-width: 860px; margin: 32px auto; padding: 0 16px; color: #17202d }}
a.dt-term {{ display: inline-block; margin-left: 4px; width: 1.25em; height: 1.25em; line-height: 1.25em; text-align: center;
  border-radius: 50%; border: 1px solid #176b87; color: #176b87; font-size: .8em; text-decoration: none }}
a.dt-term:focus-visible, .dt-pop :focus-visible {{ outline: 3px solid #176b87; outline-offset: 2px }}
#dt-pop {{ max-width: 360px; border: 1px solid #c9d5df; border-radius: 8px; padding: 14px 16px; box-shadow: 0 8px 24px rgba(0,0,0,.12) }}
.dt-pop__title {{ margin: 0 0 6px; font-size: 1rem }}
.entry {{ border-top: 1px solid #d8e0e9; padding-top: 8px; margin-top: 12px }}
@media print {{ [popover], a.dt-term {{ display: none }} }}
</style></head><body>
<h1>Spike report</h1>
<section id="sec-missing"><h2>Missingness evidence<a class="dt-term" href="#concept-missingness" aria-label="Explain missingness">i</a></h2>
<p>Columns with <strong>IQR outliers</strong><a class="dt-term" href="#concept-iqr" aria-label="Explain IQR outliers">i</a> are listed below.</p>
<p><button type="button" id="other-control">An unrelated control</button></p></section>
<img id="data-img" alt="data URI pixel" width="1" height="1" src="data:image/png;base64,{PNG}">
<script>window.dtSpike = window.dtSpike || {{}}; window.dtSpike.injectedInlineScriptRan = true;</script>
<img alt="" src="data:image/png;base64,invalid" onerror="window.dtSpike = window.dtSpike || {{}}; window.dtSpike.injectedHandlerRan = true">
<section id="understand"><h2>Understand this report</h2>
<div class="entry" id="concept-missingness"><h3>Missingness</h3><p class="dt-layer">How often a value is absent.</p>
<p class="dt-layer">In this report: 3 of 17 columns have missing values.</p><p><a href="#sec-missing">Back to section</a></p></div>
<div class="entry" id="concept-iqr"><h3>IQR outliers</h3><p class="dt-layer">Values more than 1.5 × IQR below Q1 or above Q3.</p>
<p class="dt-layer">An outlier is not necessarily an error.</p><p><a href="#sec-missing">Back to section</a></p></div>
</section>
<div id="dt-pop" popover="auto" role="dialog" aria-labelledby="dt-pop-title">
<h3 class="dt-pop__title" id="dt-pop-title" tabindex="-1"></h3><div class="dt-pop__body"></div>
<button type="button" class="dt-pop__close">Close</button></div>
<script>{SCRIPT}</script>
</body></html>"""


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / 'term_popover.html').write_text(page(), encoding='utf-8')
    (HERE / 'iframe_parent.html').write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>App viewer shape</title></head><body>'
        '<p>Parent page standing in for the app viewer.</p>'
        '<iframe id="viewer" title="report" src="term_popover.html" style="width:100%;height:640px;border:1px solid #ccc"></iframe>'
        '</body></html>', encoding='utf-8')
    print('wrote', HERE)


if __name__ == '__main__':
    main()
