/* CG4 product adapter: displays canonical evidence, never calculates metrics. */
'use strict';
(() => {
  const el = id => byId('cg4-' + id), node = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = String(text); return n; };
  const pretty = value => JSON.stringify(value, null, 2), read = id => JSON.parse(el(id).value), show = text => { el('status').textContent = text; };
  function requiredNumber(id,label) {
    const text=el(id).value.trim(),value=Number(text);
    if(!text||!Number.isFinite(value))throw Error(`Enter an explicit finite ${label}.`);
    return value;
  }
  const action = fn => async () => { try { await fn(); } catch (e) { show(e.message); } };
  let draft = null, inspection = null, result = null, resultID = null, family = null, confirmation = null, active = null, cursor = null, sourceSnapshot = null;
  let previousSections = [], selection = new Set(), thresholds = new Map(), asset = null, model = null, scheduledInspection = null, overlapCursor = null;
  const originalEvaluate = byId('nav-evaluate').onclick, originalHistory = byId('nav-history').onclick;
  function enter() {
    if (el('workspace').hidden) previousSections = [...document.querySelectorAll('main > section')].map(n => [n, n.hidden]);
    [...document.querySelectorAll('main > section')].forEach(n => { n.hidden = n !== el('workspace'); });
    document.querySelectorAll('.product-nav button').forEach(n => n.removeAttribute('aria-current'));byId('nav-investigations').setAttribute('aria-current', 'page');
  }
  byId('nav-investigations').onclick = action(async () => { enter(); await refresh(); });
  function leave() { previousSections.forEach(([n, hidden]) => { n.hidden = hidden; }); el('workspace').hidden = true;byId('nav-investigations').removeAttribute('aria-current'); }
  byId('nav-evaluate').onclick = event => { leave(); if (originalEvaluate) originalEvaluate(event); el('workspace').hidden = true; };
  byId('nav-history').onclick = async event => { leave(); if (originalHistory) await originalHistory(event); el('workspace').hidden = true; };
  async function refresh() {
    const previous=el('keys-source').value;el('keys-source').replaceChildren();
    sources.forEach(s => el('keys-source').add(new Option(s.label, s.handle)));el('keys-source').value=previous;
    const enrichment=el('enrichment-source').value;el('enrichment-source').replaceChildren();sources.forEach(s=>el('enrichment-source').add(new Option(s.label,s.handle)));el('enrichment-source').value=enrichment;
    const session=await api('/session');el('asset-root').replaceChildren();session.root_aliases.forEach(r => el('asset-root').add(new Option(r.label,r.id)));
    const access=await api('/workspace/access');el('retained').hidden=!access.authorized;el('retain').disabled=!access.authorized;el('tracking').disabled=!access.authorized;
    if (access.authorized) {
      const saved=(await api('/workspace/assessments')).items.filter(r => r.methodology_id==='failure_investigation_v1');el('saved').replaceChildren();
      saved.forEach(r => { const button=node('button',`${r.name} · ${r.generated_at}`);button.onclick=action(async()=>window.openConfidenceGuardInvestigation(r.id,true));el('saved').append(button); });
      el('exposure').textContent=pretty(await api('/workspace/evidence-use'));
    }
  }
  function invalidate() { draft=null;inspection=null;confirmation=null;el('inspection').textContent='Configuration changed; inspect again.';el('admission').textContent='';el('feasibility').textContent='';el('confirmation-membership').replaceChildren();el('feasibility-summary').textContent=family?'Input changed; inspect the frozen family against the new H input again.':''; }
  el('spec').addEventListener('input',invalidate);
  el('config').addEventListener('input',invalidate);
  function invalidateFamily(){family=null;confirmation=null;el('family').textContent='Selection, thresholds or confirmation protocol changed; freeze again.';el('family-download').replaceChildren();el('feasibility').textContent='';el('feasibility-summary').textContent='';el('confirmation-membership').replaceChildren();}
  el('confirmation').addEventListener('input',invalidateFamily);
  el('use-evaluation').onclick=action(async()=>{
    const evaluation=current().spec;const entities=split(el('entities').value);evaluation.runs.forEach(r=>{if(entities.length)r.entity_columns=entities;});
    sourceSnapshot={evaluation};composeSpec();show('Evaluation copied. Review typed fields, objective and D/S/H before inspection.');
  });
  el('use-history').onclick=action(async()=>{
    sourceSnapshot={history:{selection:JSON.parse(byId('history-spec').value)}};composeSpec();show('Historical selection copied. Its catalog sequence and cutoffs will be frozen by inspection.');
  });
  function composeSpec() {
    invalidate();
    if (!sourceSnapshot) sourceSnapshot={evaluation:current().spec};
    const source=structuredClone(sourceSnapshot),run=source.evaluation?.runs[0].id||source.history.selection.variants?.[0];
    if (!run) throw Error('Choose an evaluated run or an explicit retained variant.');
    const roles={namespace:el('namespace').value,unit:el('role-unit').value,seed:Number(el('seed').value)};
    if(el('role-column').value)roles.column=el('role-column').value;
    const objective={id:'objective',metric:el('objective').value,run,direction:el('direction').value,comparator:el('comparator').value};
    if(el('units').value.trim())objective.units=el('units').value.trim();
    if(el('delta').value.trim())objective.practical_threshold=Number(el('delta').value);
    if(el('target').value)objective.target=el('target').value;if(el('interval').value)objective.interval=el('interval').value;
    if(objective.comparator==='ceiling')objective.ceiling=requiredNumber('ceiling',"ceiling in the objective's units");
    if(objective.comparator==='paired')objective.reference_run=el('reference-run').value;
    if(objective.direction==='nominal_shortfall')objective.nominal=requiredNumber('nominal','nominal coverage');
    const strategies=[...el('strategies').querySelectorAll('input:checked')].map(n=>n.value);
    const specification={schema_version:'confidenceguard.investigation_spec/1.0',name:el('name').value,...source,roles,objectives:[objective],features:read('features'),representations:read('representations'),strategies};
    if(el('asof').value)specification.as_of=el('asof').value;specification.feature_time_view=el('time-view').value;
    el('spec').value=pretty(specification);
  }
  el('compose').onclick=action(composeSpec);
  el('add-field').onclick=action(()=>{
    const field={id:el('field-id').value,column:el('field-column').value,kind:el('field-kind').value,role:el('field-role').value};
    const views=read('features');let view=views.find(v=>v.id==='context');if(!view){view={id:'context',availability:el('field-availability').value,fields:[]};views.push(view);}
    if(view.fields.some(f=>f.id===field.id))throw Error('Choose a unique field identity.');view.fields.push(field);el('features').value=pretty(views);show('Field added; compose the complete specification to apply it.');
  });
  el('matrix-upload').onchange=action(async()=>{const file=el('matrix-upload').files[0];if(!file)return;const data=new FormData();data.append('file',file);asset=await api('/investigation-assets',{method:'POST',body:data});el('asset-status').textContent='Owned vector handle '+asset.handle;});
  el('register-asset').onclick=action(async()=>{
    const kind=el('representation-kind').value==='supplied'?'vectors':'model';const value=await api('/investigation-assets',{method:'POST',body:{root_id:el('asset-root').value,relative_path:el('asset-path').value,kind}});
    if(kind==='model')model=value;else asset=value;el('asset-status').textContent=`Owned ${kind} handle ${value.handle}; full validation runs under supervision.`;
  });
  el('add-representation').onclick=action(()=>{
    const kind=el('representation-kind').value,rep={id:el('representation-id').value,kind,normalization:el('normalization').value,availability:el('rep-availability').value};
    if(kind==='supplied'){if(!asset)throw Error('Register or upload a vector matrix.');rep.matrix_handle=asset.handle;rep.keys_source={id:'representation_keys',handle:el('keys-source').value};rep.key_columns=split(el('keys').value);}
    else if(kind!=='retained'){if(!model)throw Error('Register the installed pinned model. No download runs here.');rep.model_handle=model.handle;rep.field=el('content-field').value;}
    const reps=read('representations');reps.push(rep);el('representations').value=pretty(reps);show('Representation added; compose the complete specification to apply it.');
  });
  async function job(kind,fields={}) {
    let j=await api('/jobs',{method:'POST',body:{kind,client_request_id:crypto.randomUUID(),...fields}});active=j.id;
    while(['pending','running','cancelling'].includes(j.state)){show(`${j.state} · ${j.progress?.stage||kind}`);await new Promise(resolve=>setTimeout(resolve,350));j=await api('/jobs/'+j.id);}
    active=null;
    if(kind==='export'&&j.state==='failed'&&j.error?.code==='pdf_or_json_export_failed_surviving_artifacts_retained'&&Array.isArray(j.output?.artifact_ids)&&j.output.artifact_ids.length)
      return {...j.output,export_error:j.error.code};
    if(j.state!=='succeeded')throw Error(`${j.error?.code||j.state}: ${j.error?.message||'Operation stopped; review the declared inputs and limits.'}`);return j.output;
  }
  function binding(){if(!draft)throw Error('Inspect the current investigation first.');return{investigation_id:draft.id,revision:draft.revision};}
  el('inspect').onclick=action(async()=>{
    draft=await api('/investigations',{method:'POST',body:{spec:read('spec'),config:read('config')}});
    inspection=await job('investigation_inspect',binding());el('spec').value=pretty(inspection.effective_spec);el('inspection').textContent=pretty(inspection);
    const roles=inspection.population.roles,limits=inspection.effective_config;el('admission').textContent=`Planned ${inspection.population.planned}: D ${roles.D}, S ${roles.S}, H ${roles.H}. ${Object.keys(inspection.features).length} typed fields, ${Object.keys(inspection.representations).length} representations. ${limits.threads} threads, ${(limits.max_rss_bytes/2**30).toFixed(1)} GiB RSS, ${(limits.max_seconds/60).toFixed(1)} minutes, ${(limits.result_bytes/2**20).toFixed(0)} MiB result budget. H outcome metrics were sealed during this discovery inspection.`;
    show('Inspection complete. Review objective semantics, D/S/H counts, availability and resources. H outcome summaries have not been disclosed.');
  });
  el('discover').onclick=action(async()=>{
    if(!inspection)throw Error('Inspect the current specification.');const output=await job('investigation_discover',{...binding(),fingerprint:inspection.fingerprint,retain:el('retain').checked});await openResult(output.result_id);
  });
  function table(headers,rows) {const t=node('table'),head=node('thead'),body=node('tbody'),r=node('tr');headers.forEach(h=>r.append(node('th',h)));head.append(r);t.append(node('caption','Scroll horizontally to see all evidence when the table is wider than the view.'),head,body);rows.forEach(row=>{const r=node('tr');row.forEach(v=>{const td=node('td');td.append(v instanceof Node?v:node('span',v??'Unavailable'));r.append(td);});body.append(r);});const viewport=node('div');viewport.className='cg4-table';viewport.tabIndex=0;viewport.setAttribute('role','region');viewport.setAttribute('aria-label','Scrollable investigation evidence table');viewport.append(t);return viewport;}
  async function openResult(id,retained=false) {
    if(retained)await api('/workspace/investigations/'+id+'/open',{method:'POST',body:{}});
    enter();resultID=id;result=await api(`/results/${id}/investigation/summary`);el('result').hidden=false;el('result-title').textContent=result.name;
    scheduledInspection=null;
    renderAssessment(result);
    if(result.investigation.stage!=='confirmation')invalidateFamily();
    selection=new Set(result.investigation.shortlist||[]);thresholds=new Map();cursor='0';el('candidates').replaceChildren();
    await moreCandidates();
    const hasCandidates=result.investigation.candidate_count>0;
    el('candidates').hidden=!hasCandidates;el('more').hidden=!hasCandidates;el('reveal').parentElement.hidden=!hasCandidates;el('evidence').hidden=!hasCandidates;
    el('strategy-status').parentElement.hidden=!(result.investigation.strategies||[]).length;
    const overlap=result.investigation.overlap,hasOverlap=overlap&&!Array.isArray(overlap)&&'shortlist_union_support' in overlap;
    el('overlap-summary').parentElement.hidden=!hasOverlap;
    el('overlap-summary').textContent=hasOverlap?`The shortlist covers ${overlap.shortlist_union_support} distinct S opportunities out of ${overlap.selection_population}; overlapping supports are counted once. ${overlap.retained_pairs} overlapping pairs have retained detail. ${overlap.total_overlapping_pairs===undefined?'Complete pair coverage was not recorded for this historical result.':`${overlap.total_overlapping_pairs} pairs overlap in total; ${overlap.omitted_pairs} were omitted from retained detail.`} Absence from the displayed pairs does not establish disjointness.`:'';
    el('overlap').textContent=pretty(result.investigation.overlap);overlapCursor='0';await moreOverlap();el('strategy-status').textContent=pretty(result.investigation.strategies);el('more').disabled=cursor===null;
    show(result.investigation.stage==='confirmation'?'Immutable assessment opened. Finding states apply to the displayed population, practical threshold and assumptions.':'Immutable evidence opened. Candidate effects are exploratory until independently assessed.');
  }
  window.openConfidenceGuardInvestigation=openResult;
  function renderAssessment(value){
    const panel=value.investigation,container=el('assessment');container.replaceChildren();
    if(panel.stage==='discovery'){
      const roles=value.coverage.roles||{},count=panel.shortlist?.length||0;container.append(node('p',`Exploratory evidence. D ${roles.D??'unavailable'}, S ${roles.S??'unavailable'}, sealed H ${roles.H??'unavailable'}. ${count} proposed ${count===1?'hypothesis is':'hypotheses are'} shortlisted; every retained candidate remains available below.`));
      if(panel.selection_policy==='severity_material_excess_support_frontier_v2')container.append(node('p','Selection uses S only: preserve the severity extreme, then prioritize (adverse effect minus the declared practical threshold) × conditional support when another slot is available. Remaining gates use the effect/support/complexity frontier and marginal-coverage checks. This is an investigation heuristic, not a statistical or causal guarantee.'));
    }
    if(panel.assessments?.length){
      const scope=value.outcomes?.scope;
      container.append(node('p',scope==='observed_labels'?'Outcome scope: observed labels only. These findings do not establish failure rates or reliability for unobserved outcomes.':scope==='complete_population'?'Outcome scope: the complete frozen population. Incomplete required outcomes refuse this claim.':'The exact outcome scope was not retained in this view; consult the original protected assessment before interpreting its findings.'));
      const rows=panel.assessments.map(a=>[a.objective?.metric||'Frozen metric',a.state.replaceAll('_',' '),a.effect??a.effect_state??'Not assessed',
        a.interval?`[${a.interval.lower.toPrecision(5)}, ${a.interval.upper.toPrecision(5)}]; δ ${a.practical_threshold}`:'No admissible interval',
        `Planned ${a.support?.planned??'Unavailable'}; applicable ${a.support?.available??'Unavailable'}; members ${a.support?.members??'Unavailable'}; metric ${a.support?.conditional_members??'Unavailable'} / ${a.support?.conditional_nonmembers??'Unavailable'}; membership unavailable ${a.support?.unavailable??'Unavailable'}`,(a.strength||'Descriptive').replaceAll('_',' ')]);
      container.append(table(['Objective','Finding','Adverse effect','Simultaneous interval / threshold','Population and metric support','Statistical strength'],rows));
      panel.assessments.filter(a=>a.strength==='approximate').forEach(a=>container.append(node('p',`Historical approximate assessment (${a.objective?.metric||a.hypothesis||a.hypothesis_id||'frozen finding'}; recorded finding: ${a.state.replaceAll('_',' ')}): this record retains its original procedure and finding. Current CG4 closure does not qualify general BCa/cluster or ranking-percentile confirmation. Reading this record does not establish a new formal confirmation.`)));
      const independence=panel.independence||{};container.append(node('p',`Local separation: ${independence.local_separation||'unknown'}. Upstream independence: ${independence.upstream||'unknown'}. External exposure: ${independence.external_exposure||'unknown'}. Exposure continuity: ${independence.exposure_continuity||'unknown'}. These checks do not establish workspace-wide or external guarantees.`));
      if(independence.local_identity_scope==='canonical_history_keys_original_aliases_incomplete'||panel.assessments.some(a=>a.independence_qualification?.local_identity_scope==='canonical_history_keys_original_aliases_incomplete'))container.append(node('p','Original source aliases were not retained completely for these historical claims. Local checks cover canonical historical identities; missing overlap records do not prove prior evidence was untouched.'));
      if(panel.predeclared_restatement)container.append(node('p',`Predeclared look ${panel.predeclared_restatement.look.id}, allocated error ${panel.predeclared_restatement.look_error_allocation}. This reuses the frozen population and supplies no fresh independent evidence.`));
      panel.assessments.filter(a=>a.reason).forEach(a=>container.append(node('p',`Finding limitation: ${a.reason.replaceAll('_',' ')}`)));
    }
    if(panel.history?.length)container.append(table(['Period','Objective','Adverse effect','Member support','State'],panel.history.map(h=>[h.period,h.objective?.metric,h.evidence?.effect??h.evidence?.effect_state,h.evidence?.conditional_members,h.state])));
    (panel.notes||[]).forEach(note=>container.append(node('p','Private note: '+note.text)));
    const details=node('details'),summary=node('summary','Complete assessment, population and provenance evidence');details.append(summary,node('pre',pretty({coverage:value.coverage,outcomes:value.outcomes,assessments:panel.assessments,independence:panel.independence,history:panel.history})));container.append(details);
  }
  async function moreCandidates(){if(cursor===null)return;const page=await api(`/results/${resultID}/investigation/candidates?cursor=${cursor}&limit=25`);renderCandidates(page.items);cursor=page.next_cursor;el('more').disabled=cursor===null;}
  async function moreOverlap(){if(overlapCursor===null)return;const page=await api(`/results/${resultID}/investigation/overlap?cursor=${overlapCursor}&limit=25`);el('overlap').textContent+='\n'+pretty(page.items);overlapCursor=page.next_cursor;el('more-overlap').disabled=overlapCursor===null;}
  el('more-overlap').onclick=action(moreOverlap);
  function renderCandidates(candidates){
    const rows=candidates.map(c=>{const choose=node('input');choose.type='checkbox';choose.checked=selection.has(c.id);choose.setAttribute('aria-label','Select hypothesis '+c.id);choose.onchange=()=>{choose.checked?selection.add(c.id):selection.delete(c.id);invalidateFamily();};
      const threshold=node('input');threshold.type='number';threshold.min='0';threshold.step='any';threshold.placeholder='Required before confirmation';threshold.setAttribute('aria-label','Material effect threshold for '+c.id);threshold.value=c.objective?.practical_threshold??'';threshold.oninput=()=>{thresholds.set(c.id,threshold.value.trim()?Number(threshold.value):null);invalidateFamily();};
      const detail=node('details'),summary=node('summary','Gate, denominators, fidelity, stability and evidence'),content=node('pre',pretty(c));detail.append(summary,content);
      (c.examples||[]).forEach(example=>{const button=node('button','Resolve '+example.selection);button.onclick=action(async()=>{const output=await job('resolve_evidence',{result_id:resultID,reference:example.reference,reveal_values:el('reveal').checked});el('evidence').textContent=pretty(output);});detail.append(button);});
      return[choose,c.id,c.proposal_source==='declared_ceiling_population_baseline_v1'?'Whole population (ceiling baseline)':c.strategy,c.objective?.metric,threshold,c.S?.effect??c.S?.effect_state,c.S?`${c.S.members} / ${c.S.available} / ${c.S.planned}; unavailable ${c.S.unavailable}`:'Withheld',detail];});
    el('candidates').append(table(['Freeze','Candidate','Strategy','Objective','Material effect δ','S adverse effect','Members / applicable / planned','Evidence'],rows));
  }
  el('more').onclick=action(moreCandidates);
  el('compose-confirmation').onclick=action(async()=>{
    invalidateFamily();
    const value={confidence:.95,method:el('method').value,sampling:el('sampling').value,upstream_independence:el('upstream').value,external_exposure:el('external').value,
      membership_scope:el('membership-scope').value,minimum_membership_coverage:requiredNumber('coverage','minimum applicable fraction'),replicates:requiredNumber('replicates','bootstrap replication budget'),max_replicates:requiredNumber('maximum-replicates','maximum replication budget'),replicate_policy:el('replicate-policy').value};
    if(value.sampling==='independent_entity_arms'&&value.method!=='finite')throw Error('One potential observation per entity in each comparison arm requires finite inference. General entity bootstrap remains a separate method.');
    if(el('declaration-author').value)value.declaration_author=el('declaration-author').value;if(el('declaration-reason').value)value.declaration_reason=el('declaration-reason').value;
    if(el('history-gap-declaration').checked){const state=await api('/workspace/evidence-use');if(!state.continuity_token)throw Error('The authorized workspace must expose its current history-gap context first.');if(value.external_exposure!=='declared_unexposed'||!value.declaration_author||!value.declaration_reason)throw Error('A current history-gap declaration needs an author, scoped reason and explicit prior-exposure declaration.');value.exposure_history_token=state.continuity_token;}
    el('confirmation').value=pretty(value);show('Confirmation protocol composed. Freeze it with the complete selected family before inspection.');
  });
  el('freeze').onclick=action(async()=>{
    if(!resultID||!selection.size)throw Error('Select retained hypotheses from a protected discovery result.');
    family=await api('/hypothesis-sets',{method:'POST',body:{result_id:resultID,candidate_ids:[...selection],practical_thresholds:Object.fromEntries([...thresholds].filter(([id])=>selection.has(id))),confirmation:read('confirmation')}});confirmation=null;
    el('family').textContent=pretty(await api('/hypothesis-sets/'+family.handle));const link=node('a','Download protected frozen hypotheses');link.href=base+'/hypothesis-sets/'+family.handle+'/content';el('family-download').replaceChildren(link);show('Hypotheses and complete multiplicity family frozen.');
  });
  el('import-family').onchange=action(async()=>{const file=el('import-family').files[0];if(!file)return;invalidateFamily();const data=new FormData();data.append('file',file);family=await api('/hypothesis-sets/import',{method:'POST',body:data});confirmation=null;el('family').textContent=pretty(await api('/hypothesis-sets/'+family.handle));});
  el('inspect-confirmation').onclick=action(async()=>{if(!family)throw Error('Freeze or import a hypothesis set.');confirmation=await job('confirmation_inspect',{...binding(),hypothesis_handle:family.handle});el('feasibility').textContent=pretty(confirmation);const f=confirmation.feasibility,reasons=[...new Set([...confirmation.admissibility_reasons,...f.reasons,...confirmation.membership.flatMap(row=>row.admissibility_reasons)])];el('feasibility-summary').textContent=`${f.family_size} frozen hypotheses; ${f.elementary_intervals.join(', ')} elementary intervals. ${f.effective_replicates===0?'Finite procedure; bootstrap is not used.':`Requested B ${f.requested_replicates}; admitted B ${f.effective_replicates}, maximum ${f.maximum_replicates}.`} ${f.independent_units} declared sampling units. Numerical admission: ${f.status.replaceAll('_',' ')}. Claim admission: ${reasons.length?'refused':'conditional on recorded assumptions'}. ${reasons.map(r=>r.replaceAll('_',' ')).join('; ')||'Original assumptions still apply.'}`;el('confirmation-membership').replaceChildren(table(['Hypothesis','Planned H','Applicable','Members','Nonmembers','Unavailable','Membership admission'],confirmation.membership.map(row=>[row.hypothesis_id,row.planned,row.available,row.members,row.nonmembers,row.unavailable,row.admissibility_reasons.map(r=>r.replaceAll('_',' ')).join('; ')||'No membership refusal'])));show('Feasibility inspected without H outcome metrics. Known contamination, unavailable membership and unsupported dependence remain explicit.');});
  el('confirm').onclick=action(async()=>{if(!family||!confirmation)throw Error('Inspect the frozen family and current H population first.');const output=await job('investigation_confirm',{...binding(),hypothesis_handle:family.handle,confirmation_fingerprint:confirmation.fingerprint,retain:el('retain').checked});await openResult(output.result_id);});
  el('cancel').onclick=action(async()=>{if(active)await api('/jobs/'+active+'/cancel',{method:'POST',body:{}});});
  el('tracking').onclick=action(async()=>{const current=await api('/workspace/evidence-use');const updated=await api('/workspace/evidence-use',{method:'POST',body:{enabled:!current.enabled}});el('exposure').textContent=pretty(updated);show('Evidence-use consent updated. Starting tracking does not establish earlier freshness.');});
  async function workspaceJob(kind,fields={}) {
    let j=await api('/workspace/jobs',{method:'POST',body:{kind,client_request_id:crypto.randomUUID(),...fields}});active=j.id;
    while(['pending','running','cancelling'].includes(j.state)){show(`${j.state} · ${j.progress?.stage||kind}`);await new Promise(resolve=>setTimeout(resolve,350));j=await api('/jobs/'+j.id);}
    active=null;if(j.state!=='succeeded')throw Error(j.error?.code||j.state);return j.output;
  }
  el('replay').onclick=action(async()=>{if(!resultID)throw Error('Open the original protected investigation.');const output=await job('investigation_replay',{...binding(),result_id:resultID,reason:el('revisit-reason').value,retain:el('retain').checked});await openResult(output.result_id);});
  el('restate').onclick=action(async()=>{if(!resultID)throw Error('Open a retained original assessment.');const output=await workspaceJob('restate',{assessment_id:resultID,as_of:el('revisit-asof').value,reason:el('revisit-reason').value});await openResult(output.result_id);});
  el('annotate').onclick=action(async()=>{if(!resultID)throw Error('Open a retained investigation.');const output=await workspaceJob('annotate_investigation',{assessment_id:resultID,text:el('note').value});await openResult(output.result_id);});
  el('compose-enrichment').onclick=action(()=>{const view=read('features')[0];if(!view)throw Error('Declare the typed enrichment view first.');el('retention-spec').value=pretty({source:{id:'enrichment',handle:el('enrichment-source').value},namespace:el('namespace').value,view,acquired_at:el('acquired-at').value,opportunity_column:'opportunity_key'});show('Review exact opportunity ownership, source columns and actual acquisition time. Prediction-owned enrichment also requires exact prediction fact identities.');});
  el('compose-preparation').onclick=action(()=>{const current=read('spec');if(!current.evaluation)throw Error('Representation preparation requires explicitly supplied prediction evidence.');el('retention-spec').value=pretty({schema_version:'confidenceguard.prediction_batch_spec/2.0',evaluation:current.evaluation,namespace:current.roles.namespace,outcome_definition_version:el('outcome-version').value,bindings:current.evaluation.runs.map(r=>({run:r.id})),feature_views:current.features||[],discovery_representations:current.representations||[]});show('Review prediction bindings, retention ownership and representation identities before recording.');});
  el('enrich').onclick=action(async()=>{el('retention-output').textContent=pretty(await workspaceJob('enrich_features',{spec:read('retention-spec'),config:read('config')}));await refresh();});
  el('prepare').onclick=action(async()=>{el('retention-output').textContent=pretty(await workspaceJob('prepare_representations',{spec:read('retention-spec'),config:read('config')}));await refresh();});
  el('retry').onclick=action(async()=>{if(!resultID)throw Error('Open a retained numerically insufficient confirmation.');const output=await workspaceJob('retry_confirmation',{assessment_id:resultID,replicates:Number(el('retry-replicates').value),config:read('config')});await openResult(output.result_id);});
  el('look-id').addEventListener('input',()=>{scheduledInspection=null;});
  el('inspect-look').onclick=action(async()=>{if(!resultID)throw Error('Open the retained original confirmation.');scheduledInspection=await workspaceJob('inspect_restatement_confirmation',{assessment_id:resultID,look_id:el('look-id').value,config:read('config')});el('look-feasibility').textContent=pretty(scheduledInspection);});
  el('assess-look').onclick=action(async()=>{if(!resultID||!scheduledInspection)throw Error('Inspect the original frozen look first.');const output=await workspaceJob('restate_confirmation',{assessment_id:resultID,look_id:el('look-id').value,fingerprint:scheduledInspection.fingerprint,config:read('config')});await openResult(output.result_id);});
  el('export').onclick=action(async()=>{
    if(!resultID)throw Error('Open a completed result.');const output=await job('export',{result_id:resultID,format:el('format').value,audience:el('audience').value});
    const artifacts=await api('/results/'+resultID+'/artifacts');el('downloads').replaceChildren();artifacts.filter(a=>output.artifact_ids.includes(a.id)).forEach(a=>{const link=node('a',`Download ${a.kind} (${a.audience})`);link.href=base+'/artifacts/'+a.id+'/content';link.className='history-download';el('downloads').append(link);});
    show(output.export_error?'Requested export failed; surviving canonical artifacts are available below.':'Canonical export complete. Download links retain their audience labels.');
  });
  const priorShowResult=showResult;showResult=async id=>{const data=await api('/results/'+id);if(data.investigation)return openResult(id);return priorShowResult(id);};
})();
