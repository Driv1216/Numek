/* One ConfidenceGuard product. This client displays backend evidence; no metrics are computed here. */
'use strict';
(() => {
  let inspection = null, assessment = null, result = null, active = null, preview = null, models = [];
  const el = id => document.getElementById('history-' + id);
  const show = message => { el('status').textContent = message; };
  const action = fn => async () => { try { await fn(); } catch (error) { show(error.message); } };
  const node = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = String(text); return n; };
  const json = id => JSON.parse(el(id).value);
  const id = () => crypto.randomUUID();
  const pretty = value => JSON.stringify(value, null, 2);
  let legacySections = [];
  byId('nav-history').onclick = action(async () => {
    legacySections = [...document.querySelectorAll('main > section')].filter(n => n.id !== 'history-workspace').map(n => [n, n.hidden]);
    legacySections.forEach(([n]) => { n.hidden = true; }); el('workspace').hidden = false;
    byId('nav-history').setAttribute('aria-current', 'page'); byId('nav-evaluate').removeAttribute('aria-current'); await refresh();
  });
  byId('nav-evaluate').onclick = () => { el('workspace').hidden = true; legacySections.forEach(([n, hidden]) => { n.hidden = hidden; }); byId('nav-evaluate').setAttribute('aria-current', 'page'); byId('nav-history').removeAttribute('aria-current'); };
  async function refresh() {
    const access = await api('/workspace/access'); el('controls').hidden = !access.authorized;
    el('access').textContent = !access.enabled ? 'History is off for this host. Initialize a workspace and launch confidenceguard ui --workspace PATH.' : !access.authorized ? 'Open the one-time ConfidenceGuard launch link printed in your terminal to authorize this browser.' : 'Authorized local workspace. Event evidence is sensitive and stored separately from DataTrust history.';
    if (!access.authorized) return;
    const state = await api('/workspace'); el('storage').textContent = `Catalog ${state.catalog_sequence} · ${state.bytes.toLocaleString()} bytes · saving ${state.config.saving ? 'on' : 'off'} · no automatic eviction`;
    el('consent').textContent = state.config.saving ? 'Stop saving future imports' : 'Enable historical saving'; el('consent').dataset.enabled = state.config.saving;
    models = (await api('/workspace/models')).items;
    el('models').replaceChildren(); el('variant').replaceChildren();
    for (const model of models) {
      const card = node('article'); card.append(node('h4', `${model.run.model.display_name || model.run.model.id} · ${model.run.model.version}`), node('p', `${model.method_digests.length ? 'Fitted-method variant' : 'Supplied prediction variant'} · identity ${model.id}`), node('p', 'Historical evidence does not validate new applications or guarantee future reliability.'));
      el('models').append(card); el('variant').add(new Option(`${model.run.model.id} ${model.run.model.version} · ${model.id.slice(-10)}`, model.id));
    }
    const saved = (await api('/workspace/assessments')).items; el('assessments').replaceChildren();
    if (!saved.length) el('assessments').append(node('p', 'No saved assessments.'));
    for (const item of saved) { const button = node('button', `${item.name} · ${item.generated_at}`); button.onclick = action(() => open(item.id)); el('assessments').append(button); }
  }
  async function job(kind, fields = {}) {
    const accepted = await api('/workspace/jobs', { method: 'POST', body: { kind, client_request_id: id(), ...fields } }); active = accepted.id;
    let current = accepted;
    while (['pending', 'running', 'cancelling'].includes(current.state)) { show(`${current.state} · ${current.progress?.stage || kind}`); await new Promise(resolve => setTimeout(resolve, 350)); current = await api('/jobs/' + current.id); }
    active = null;
    if (current.state !== 'succeeded') throw Error(current.error?.code || current.state);
    show('Completed.');
    if(current.output.method_handles?.length){importedMethodHandles=current.output.method_handles;byId('method-import-status').textContent=importedMethodHandles.length+' protected fitted methods available in this session.';}
    for (const artifact of current.output.artifact_ids || []) { const link = node('a', 'Download protected or audience-selected artifact'); link.href = base + '/artifacts/' + artifact + '/content'; link.className = 'history-download'; el('downloads').append(link); }
    return current.output;
  }
  el('refresh').onclick = action(refresh);
  el('consent').onclick = action(async () => { await api('/workspace/consent', { method: 'POST', body: { saving: el('consent').dataset.enabled !== 'true' } }); await refresh(); });
  el('detach').onclick = action(async () => { await api('/workspace/detach', { method: 'POST', body: {} }); result = null; el('result').hidden = true; await refresh(); });
  el('backup').onclick = action(() => job('backup'));
  el('compose-batch').onclick = action(async () => {
    const request = byId('advanced').checked ? JSON.parse(byId('spec').value) : compose();
    const evaluation = request.spec; const core = evaluation.evaluation || evaluation;
    for (const run of core.runs) { if (el('clock').value) run.prediction_at = { column: el('clock').value }; if (el('entities').value) run.entity_columns = split(el('entities').value); }
    if (core.outcomes) { if (el('availability').value) core.outcomes.available_at = { column: el('availability').value }; if (el('due').value) core.outcomes.due_at = { column: el('due').value }; }
    const batch = { namespace: el('namespace').value, outcome_definition_version: el('definition').value, operation: el('operation').value, evaluation, bindings: core.runs.map(run => ({ run: run.id, features: json('features') })) };
    el('batch').value = pretty(batch); show('Review keys, opportunities, outcomes and retained fields before recording.');
  });
  el('ingest').onclick = action(async () => { await job('ingest', { spec: json('batch') }); await refresh(); });
  el('update-outcomes').onclick = action(async () => { await job('outcomes', { spec: json('outcomes') }); await refresh(); });
  el('compose-analysis').onclick = action(async () => {
    const variant = el('variant').value;
    const spec = { namespace: el('namespace').value, variants: [variant], windows: [{ id: 'reference', start: el('ref-start').value, end: el('ref-end').value }, { id: 'current', start: el('ref-end').value, end: el('current-end').value }], maturity: el('maturity').value,
      comparisons: [{ id: 'change', reference_window: 'reference', current_window: 'current', reference_variant: variant, current_variant: variant }], features: json('features') };
    if (el('asof').value) spec.as_of = el('asof').value;
    if (spec.maturity === 'equal_followup') spec.followup_ns = el('followup').value;
    el('spec').value = pretty(spec); inspection = null; el('confirm').checked = false;
  });
  el('spec').oninput = () => { inspection = null; el('confirm').checked = false; };
  el('inspect').onclick = action(async () => { inspection = await api('/workspace/inspect', { method: 'POST', body: { spec: json('spec') } }); el('inspection').textContent = pretty({windows:inspection.spec.windows,as_of:inspection.spec.as_of,maturity:inspection.spec.maturity,populations:inspection.population_preview,qualifications:inspection.qualifications}); });
  el('analyze').onclick = action(async () => { if (!inspection || !el('confirm').checked) throw Error('Inspect and confirm the current declarations first.'); const output = await job('analyze', { spec: json('spec'), fingerprint: inspection.fingerprint }); await refresh(); await open(output.assessment_id); });
  el('cancel').onclick = action(async () => { if (active) await api('/jobs/' + active + '/cancel', { method: 'POST', body: {} }); });
  async function open(identifier) {
    assessment = identifier; result = await api('/workspace/assessments/' + identifier); el('result').hidden = false; el('result-title').textContent = result.name;
    el('metric').replaceChildren(); const definitions = new Map(result.measurements.map(m => [m.metric_key || m.metric, m]));
    definitions.forEach((m, key) => el('metric').add(new Option(m.metric_label || m.metric, key)));
    const accuracy = [...definitions].find(([, m]) => m.metric === 'accuracy');
    if (accuracy) el('metric').value = accuracy[0];
    render();
  }
  function table(headers, rows) { const table = node('table'), head = node('thead'), tr = node('tr'); headers.forEach(h => tr.append(node('th', h))); head.append(tr); table.append(head); const body = node('tbody'); rows.forEach(row => { const tr = node('tr'); row.forEach(cell => tr.append(node('td', typeof cell === 'object' ? pretty(cell) : cell ?? 'Unavailable'))); body.append(tr); }); table.append(body); return table; }
  function panel(id, title, value) { el(id).replaceChildren(node('h4', title), node('pre', pretty(value))); }
  function render() {
    const history = result.history; if (!history) { show('Saved standalone assessment; longitudinal reconstruction is separately recorded.'); return; }
    const selectedKey = el('metric').value, matches = item => (item.metric_key || item.metric) === selectedKey;
    const selected = result.measurements.find(matches), metric = selected?.metric, label = selected?.metric_label || metric;
    const series = history.temporal.filter(matches);
    el('timeline').replaceChildren(node('h4', 'What changed?'));
    for (const item of series) {
      const figure = node('figure'), svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', '0 0 700 200'); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', label + ' across selected windows');
      const finite = item.points.filter(p => p.value !== null); const lo = Math.min(...finite.map(p => p.value)), hi = Math.max(...finite.map(p => p.value)); let previous = null;
      item.points.forEach((point, index) => { if (point.value === null) { previous = null; return; } const x = 35 + index * 630 / Math.max(1, item.points.length - 1), y = hi === lo ? 90 : 170 - (point.value - lo) * 130 / (hi - lo);
        if (previous) { const line = document.createElementNS(svg.namespaceURI, 'line'); ['x1','y1','x2','y2'].forEach((key, i) => line.setAttribute(key, [previous.x, previous.y, x, y][i])); line.setAttribute('stroke', '#226f73'); line.setAttribute('stroke-width', '2'); svg.append(line); }
        const circle = document.createElementNS(svg.namespaceURI, 'circle'); circle.setAttribute('cx', x); circle.setAttribute('cy', y); circle.setAttribute('r', '5'); circle.setAttribute('fill', '#226f73'); circle.append(node('title', `${point.window}: ${point.value}; eligible support ${point.support}; assessment ${assessment}`)); svg.append(circle); previous = {x,y}; });
      for (const [text,x,y] of [[Number(lo).toPrecision(5),4,178],[Number(hi).toPrecision(5),4,30],[item.points[0]?.window,35,195],[item.points[item.points.length-1]?.window,580,195]]) {const label=document.createElementNS(svg.namespaceURI,'text');label.setAttribute('x',x);label.setAttribute('y',y);label.setAttribute('font-size','12');label.textContent=text??'';svg.append(label);} figure.append(svg, node('figcaption', `${item.metric_label || metric} · ${result.runs.find(r=>r.id===item.variant)?.display_name || item.variant} · gaps remain gaps`)); el('timeline').append(figure);
    }
    panel('validity', 'Are comparisons valid?', history.comparisons.map(c => ({ id: c.id, kind: c.kind, status: c.status, reasons: c.reasons })));
    el('support').replaceChildren(node('h4','Maturity and observed-label support'),table(['Variant / window','Selected predictions','Label eligibility states','Maturity / output limitations'],history.window_coverage.map(c=>[c.variant+' / '+c.window,c.selected_predictions,c.outcome_states,{unknown_maturity:c.unknown_maturity,unlocated:c.unlocated_opportunities,ambiguous:c.ambiguous_predictions,output_failures:c.application_failures}])));
    el('changes').replaceChildren(node('h4','What might account for change?'),table(['Field','Distribution effect','Scope / prioritization'],history.drift.map(d=>[d.field,d.status==='completed'?d.kind==='numeric'?{KS:d.ks_distance,Wasserstein_1:d.wasserstein_1}:{TV:d.total_variation,JS_nats:d.jensen_shannon_divergence_nats}:d.reason,d.kind+' / '+d.comparison+' / '+(d.prioritization?.status || 'Legacy descriptive evidence')])),node('p','Drift does not establish degradation. Mix and within-cohort contributions describe associations.'),table(['Metric / partition','Mix contribution','Within contribution','Aggregate delta / qualification'],history.mix.filter(m=>m.metric_key ? matches(m) : m.metric===metric).map(m=>[m.metric+' / '+m.cohort,m.mix,m.within,m.status==='completed'?m.aggregate_delta:m.reason])));
    panel('investigation', 'How strong is the evidence? What needs investigation?', { contrasts: history.comparisons.map(c => ({ id:c.id, metrics:c.metrics.filter(matches) })), temporal: series, limitations: result.coverage.limitations });
    el('measurements').replaceChildren(table(['Variant / window', 'Metric', 'Value / state', 'Denominator / population','Protected investigation'], result.measurements.filter(matches).map(m => {const inspect=node('span');for(const reference of m.evidence_refs || []){const button=node('button','Select retained witness');button.onclick=()=>{el('reference').value=reference;show('Witness selected. Resolve without values, or explicitly enable a bounded excerpt.');};inspect.append(button);}return [(result.runs.find(r=>r.id===m.run)?.display_name || m.run) + ' / ' + m.scope,m.metric_label || m.metric,m.value_state==='finite'?m.value:m.value_state,`${m.denominator} · ${m.population_id}`,inspect];})));
  }
  el('metric').onchange = render;
  for (const format of ['html','pdf']) el('export-' + format).onclick = action(() => job('export', { assessment_id: assessment, format, audience: el('audience').value }));
  el('resolve').onclick = action(async () => { const packet = await job('resolve_evidence', { assessment_id: assessment, reference: el('reference').value, reveal_values: el('reveal').checked }); el('evidence').textContent = pretty(packet); });
  el('restate').onclick = action(async () => { const packet = await job('restate', { assessment_id: assessment, as_of: el('restate-asof').value || null, reason: el('restate-reason').value }); await refresh(); await open(packet.assessment_id); });
  el('delete-preview').onclick = action(async () => { preview = await api('/workspace/deletion-preview', { method:'POST', body:{ assessment_ids:[assessment] } }); el('deletion').textContent = pretty(preview); el('delete').hidden = false; });
  el('delete').onclick = action(async () => { if (!preview) return; await job('delete', { plan:preview }); preview = null; el('delete').hidden = true; el('result').hidden = true; await refresh(); });
})();
