/* CG5 authoring and presentation. Backend services own every analytic result. */
(() => {
  'use strict';
  const el = id => byId('cg5-' + id), pretty = value => JSON.stringify(value, null, 2);
  let lookInspection, preview, draft, inspection, resultID, family, admission, active, cursor, evidence, selection = new Set(), rows = [], previousSections=[], upstream={};
  const show = text => { el('status').textContent = text; };
  const action = fn => async () => { try { await fn(); } catch (error) { show(error.message); } };
  const read = id => JSON.parse(el(id).value);
  for (const id of ['nav-evaluate','nav-history','nav-investigations']) {
    const previous=byId(id).onclick;
    byId(id).onclick=async event => { if(!el('workspace').hidden)previousSections.forEach(([n,hidden])=>{n.hidden=hidden;}); el('workspace').hidden=true; if(previous) await previous(event); el('workspace').hidden=true; byId('nav-policies').removeAttribute('aria-current'); };
  }
  function enter() { if(el('workspace').hidden)previousSections=[...document.querySelectorAll('main>section')].map(n=>[n,n.hidden]); document.querySelectorAll('main > section').forEach(n => { n.hidden=n!==el('workspace'); }); document.querySelectorAll('.product-nav button').forEach(n=>n.removeAttribute('aria-current')); byId('nav-policies').setAttribute('aria-current','page'); }
  byId('nav-policies').onclick=enter;
  function invalidate(){draft=null;inspection=null;admission=null;show('Configuration changed; inspect before optimization or assessment.');}
  el('spec').addEventListener('input',invalidate); el('config').addEventListener('input',invalidate);
  el('use-evaluation').onclick=action(async()=>{ const configured=current();const supplied=configured.spec;if(supplied.methods?.length)throw Error('Freeze fitting methods upstream before using CG5.');evidence=supplied.evaluation||supplied;upstream={};for(const key of ['roles','representations','fitted_methods','membership_sidecars','separation','method_handles'])if(supplied[key])upstream[key]=supplied[key];if(upstream.roles)el('roles').value=pretty(upstream.roles);else if(evidence.runs.some(r=>r.entity_columns?.length)){const roles=read('roles');if(roles.proportions){roles.unit='entity';el('roles').value=pretty(roles);}}el('config').value=pretty(configured.config||{}); const regression=evidence.task.kind==='regression';el('objectives').value=pretty([{id:'primary',metric:regression?'mae':'issued_accuracy',direction:regression?'minimize':'maximize',basis:'observed_outcome'}]);compose(); });
  function compose(){
    if(!evidence) throw Error('Use a configured evaluation first, or edit the complete specification.');
    const task=evidence.task,run=el('run').value.trim()||evidence.runs[0].id,mode=el('action').value,decision=read('decision-costs');
    const base={task,run,nodes:{},root:'root',fallback:{kind:'abstain'},unavailable:{kind:'unavailable'},decision_costs:decision};
    const leaf=kind=>({kind:'action',action:kind}), metrics=read('objectives'), families=[];
    let candidates=[];
    if(mode==='supplied') {base.nodes.root=leaf({kind:'supplied'});candidates=[base];}
    else if(mode==='expected') {
      const costs=Object.keys(decision)[0];if(!costs)throw Error('Supply a complete decision cost table first.');
      const actions=task.kind==='regression'?el('numeric').value.split(',').map(v=>({kind:'numeric',value:Number(v)})):task.classes.map(label=>({kind:'label',label}));
      base.nodes.root=leaf({kind:'expected_cost',costs,actions,source:task.kind==='regression'?'samples':'probabilities'});candidates=[base];
    } else if(mode==='finite') {
      if(task.kind!=='regression')throw Error('Finite numeric actions require regression.');
      base.nodes.root={parameter:'action'};
      families.push({id:'numeric_actions',kind:'finite',template:base,parameters:[{id:'action',kind:'node',values:el('numeric').value.split(',').map(v=>leaf({kind:'numeric',value:Number(v)}))}]});
    } else {
      const binary=task.kind==='binary_classification';let selector;
      if(el('selector').value.trim()) selector=JSON.parse(el('selector').value);
      else if(binary&&evidence.runs[0].probabilities) selector={kind:'probability',target:task.positive_class};
      else if(binary&&evidence.runs[0].score?.meaning!=='selection'&&evidence.runs[0].score?.column)selector={kind:'score'};
      else if(task.kind==='multiclass_classification'&&evidence.runs[0].probabilities) selector={kind:'confidence'};
      else if(task.kind==='multiclass_classification'){base.nodes.root=leaf({kind:'argmax',source:'class_scores'});candidates=[base];}
      else if(binary){base.nodes.root=leaf({kind:'supplied'});candidates=[base];}
      else {base.nodes.root=leaf({kind:'numeric',source:{kind:'point'}}); candidates=[base];}
      if(selector){
        const binaryCut=binary&&(selector.kind==='score'||selector.kind==='probability'&&selector.target===task.positive_class);
        let when={kind:'compare',value:selector,op:['interval_width','set_size'].includes(selector.kind)||selector.kind==='score'&&evidence.runs[0].score?.direction==='lower'?'le':'ge',constant:{parameter:'cut'}};
        if(['interval_width','set_size'].includes(selector.kind))when={kind:'all',items:[{kind:'compare',value:{kind:selector.kind==='interval_width'?'interval_state':'set_state',target:selector.target},op:'ne',constant:'empty'},when]};
        const accepted=binaryCut?{kind:'label',label:task.positive_class}:task.kind==='regression'?{kind:'numeric',source:{kind:'point'}}:evidence.runs[0].probabilities?{kind:'argmax'}:evidence.runs[0].score?.columns?{kind:'argmax',source:'class_scores'}:{kind:'supplied'};
        base.nodes={root:{kind:'accept',when,accepted:'yes',rejected:'no'},yes:leaf(accepted),no:leaf(binaryCut?{kind:'label',label:task.classes.find(c=>c!==task.positive_class)}:{kind:'abstain'})};
        families.push({id:'score_groups',kind:binaryCut?'threshold':'acceptance',template:base,parameters:[{id:'cut',kind:'cutpoints',value:selector}]});
      }
    }
    const incumbent={...base,nodes:{root:leaf({kind:'supplied'})}};
    const spec={input:{...upstream,evaluation:evidence,roles:read('roles')},objectives:metrics,constraints:read('constraints'),candidates,families,baselines:[incumbent],evaluation_costs:read('evaluation-costs'),charges:read('charges')};
    if(el('region-handle').value.trim())spec.region_family_handles=[el('region-handle').value.trim()];
    el('spec').value=pretty(spec);invalidate();show('Review costs, populations, fallbacks, uncertainty states and role separation.');
  }
  el('compose').onclick=action(async()=>compose());
  async function save(){ if(!draft)draft=await api('/policy-studies',{method:'POST',body:{spec:read('spec'),config:read('config')}}); return draft; }
  async function run(kind,extra={}){
    const d=['policy_preview','policy_restate','policy_inspect_look','policy_assess_look'].includes(kind)?null:await save();
    const request={kind,client_request_id:'cg5-'+crypto.randomUUID(),...extra};
    if(d)Object.assign(request,{policy_study_id:d.id,revision:d.revision,retain:el('retain').checked});
    active=await api('/jobs',{method:'POST',body:request});
    while(['pending','running','cancelling'].includes(active.state)) {show(`${kind}: ${active.state}`);await new Promise(resolve=>setTimeout(resolve,300));active=await api('/jobs/'+active.id);}
    if(active.state!=='succeeded')throw Error(`${active.error?.code||active.state}: ${active.error?.message||'Operation stopped'}`);
    show('Completed '+kind.replaceAll('_',' '));return active.output;
  }
  el('inspect').onclick=action(async()=>{inspection=await run('policy_inspect');el('inspection').textContent=pretty(inspection);});
  el('optimize').onclick=action(async()=>{if(!inspection)throw Error('Inspect this draft first.');await openResult((await run('policy_optimize',{fingerprint:inspection.fingerprint})).result_id);});
  el('replay').onclick=action(async()=>openResult((await run('policy_replay')).result_id));
  el('history').onclick=action(async()=>openResult((await run('policy_history')).result_id));
  el('cancel').onclick=action(async()=>{if(active)await api('/jobs/'+active.id+'/cancel',{method:'POST',body:{}});});
  async function openResult(id){
    resultID=id;cursor=null;rows=[];selection.clear();el('candidates').replaceChildren();
    const summary=await api(`/results/${id}/policy/summary`);el('searches').textContent=pretty(summary.policy);el('frontier').replaceChildren();if(summary.policy.frontier?.plot){const plot=summary.policy.frontier.plot,svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 400 210');svg.setAttribute('aria-label',plot.x_metric+' versus '+plot.y_metric);svg.setAttribute('role','img');for(const point of plot.points){const dot=document.createElementNS('http://www.w3.org/2000/svg','circle');for(const [key,value] of Object.entries({cx:point.x,cy:point.y,r:point.nominated?5:3,fill:point.nominated?'#b45124':'#22787b'}))dot.setAttribute(key,String(value));const title=document.createElementNS('http://www.w3.org/2000/svg','title');title.textContent=point.policy_digest;dot.append(title);svg.append(dot);}const caption=document.createElement('p');caption.textContent=plot.x_metric+' × '+plot.y_metric+' · '+summary.policy.frontier.standing+' · '+plot.omitted_display_points+' display points omitted. '+plot.interpretation;el('frontier').append(svg,caption);}renderAssessment(summary.policy.assessments||[]);
    if(summary.policy.nomination)selection.add(summary.policy.nomination.policy_digest);
    await more();
    const nominee=summary.policy.nomination?.policy_digest;
    if(nominee){
      const plan=await api(`/results/${id}/policy/claim-planning`);const claims=plan.required_constraints.map(c=>({id:c.id,policy_digest:nominee,metric:c.metric,operator:c.operator,bound:c.bound,minimum_support:c.minimum_support||1,required:true}));
      if(claims.length)el('assessment').value=pretty({claims,sampling:'descriptive',confidence:.95});
    }
  }
  function renderAssessment(value){
    const container=el('assessment-result');container.replaceChildren();
    if(Array.isArray(value)&&value.length){
      const title=document.createElement('h4');title.textContent='Completed frozen claims';container.append(title);
      const table=document.createElement('table'),head=document.createElement('tr');
      for(const label of ['Claim / estimand','Conclusion','Simultaneous interval','Eligible support']){const th=document.createElement('th');th.textContent=label;head.append(th);}table.append(head);
      for(const claim of value){const row=document.createElement('tr');for(const item of [claim.id+' · '+claim.metric+' / '+claim.basis,claim.state+(claim.reason?' · '+claim.reason:''),claim.lower==null?'Unavailable':claim.lower.toPrecision(5)+' – '+claim.upper.toPrecision(5),claim.support==null?'Unavailable':String(claim.support)]){const td=document.createElement('td');td.textContent=item;row.append(td);}table.append(row);}container.append(table);
    }
    if(!Array.isArray(value)||value.length){const detail=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='Exact assessment evidence and qualifications';pre.textContent=pretty(value);detail.append(summary,pre);container.append(detail);}
  }
  async function more(){if(!resultID)return;const page=await api(`/results/${resultID}/policy/candidates?cursor=${cursor||0}&limit=50`);rows.push(...page.items);cursor=page.next_cursor;
    for(const row of page.items){const card=document.createElement('article');card.className='policy-candidate';const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=selection.has(row.policy_digest);check.onchange=()=>{check.checked?selection.add(row.policy_digest):selection.delete(row.policy_digest);family=null;admission=null;};label.append(check,document.createTextNode(`${row.baseline?'Baseline · ':''}${row.policy_digest.slice(0,12)} · ${row.observed_feasibility}`));const table=document.createElement('table');const head=document.createElement('tr');for(const value of ['Metric / evidence basis','Value / state','Eligible support']){const th=document.createElement('th');th.textContent=value;head.append(th);}table.append(head);for(const [id,m] of Object.entries(row.metrics)){const tr=document.createElement('tr');for(const value of [id+' · '+m.metric+' / '+m.basis,m.value_state==='finite'?String(m.value):m.reason||m.value_state,String(m.denominator)]){const td=document.createElement('td');td.textContent=value;tr.append(td);}table.append(tr);}const constraints=document.createElement('p');constraints.textContent=row.constraints.map(c=>c.id+': '+c.state+(c.slack===null?'':' · slack '+c.slack)).join('; ');const details=document.createElement('details'),summary=document.createElement('summary'),detail=document.createElement('pre');summary.textContent='Exact populations and retained details';detail.textContent=pretty({metrics:row.metrics,constraints:row.constraints});details.append(summary,detail);card.append(label,table,constraints,details);el('candidates').append(card);}
    el('more').disabled=!cursor;
  }
  el('more').onclick=action(more);
  el('apply-assumptions').onclick=action(async()=>{const protocol=read('assessment');Object.assign(protocol,{sampling:el('sampling').value,upstream_independence:el('upstream').value,external_exposure:el('exposure').value});if(el('author').value.trim())protocol.declaration_author=el('author').value.trim();if(el('reason').value.trim())protocol.declaration_reason=el('reason').value.trim();el('assessment').value=pretty(protocol);family=null;admission=null;show('Assumptions recorded; review the complete claims before freezing.');});
  el('preview').onclick=action(async()=>{if(!resultID)throw Error('Select policies on S first.');preview=await run('policy_preview',{result_id:resultID,assessment:read('assessment'),planned_e_size:Number(el('e-size').value)});el('preview-result').textContent=pretty(preview);});
  function familyLink(){el('family').replaceChildren();const link=document.createElement('a');link.href=`${base}/policy-families/${family.handle}/content`;link.textContent='Download protected frozen family';el('family').append(link);}
  el('freeze').onclick=action(async()=>{if(!resultID)throw Error('Select policies on S first.');family=await api('/policy-families',{method:'POST',body:{result_id:resultID,policy_digests:[...selection],assessment:read('assessment'),assessment_preview:preview}});admission=null;familyLink();show('Family frozen before E assessment.');});
  el('inspect-assessment').onclick=action(async()=>{if(!family)throw Error('Freeze or import a family first.');admission=await run('policy_assessment_inspect',{family_handle:family.handle});renderAssessment(admission);});
  el('assess').onclick=action(async()=>{if(!family||!admission)throw Error('Inspect the frozen assessment first.');await openResult((await run('policy_assess',{family_handle:family.handle,assessment_fingerprint:admission.fingerprint})).result_id);});
  el('assessment').addEventListener('input',()=>{family=null;admission=null;preview=null;el('family').textContent='Protocol changed; freeze a new family.';});
  for(const type of ['policy','family'])el('import-'+type).onchange=action(async()=>{const file=el('import-'+type).files[0];if(!file)return;const response=await fetch(base+(type==='policy'?'/policies/import':'/policy-families/import'),{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':csrf,'Content-Type':'application/json'},body:await file.text()});const packet=await response.json();if(!response.ok)throw Error(packet.error?.message||'Protected import refused');const imported=packet.data;if(type==='family'){family=imported;familyLink();}else{const spec=read('spec');spec.schema_version='confidenceguard.policy_application_spec/1.0';spec.policy={handle:imported.handle};spec.metrics=spec.objectives;for(const k of ['objectives','families','candidates','baselines','search'])delete spec[k];el('spec').value=pretty(spec);invalidate();}show('Protected '+type+' imported.');});
  el('restate').onclick=action(async()=>{if(!resultID)throw Error('Open a retained historical record first.');await openResult((await run('policy_restate',{result_id:resultID,as_of:el('asof').value,reason:el('revisit-reason').value})).result_id);});
  el('inspect-look').onclick=action(async()=>{if(!resultID)throw Error('Open the retained initial assessment.');lookInspection=await run('policy_inspect_look',{result_id:resultID,look_id:el('look-id').value});el('look-inspection').textContent=pretty(lookInspection);});
  el('assess-look').onclick=action(async()=>{if(!lookInspection)throw Error('Inspect the predeclared look first.');await openResult((await run('policy_assess_look',{result_id:resultID,look_id:el('look-id').value,assessment_fingerprint:lookInspection.fingerprint})).result_id);});
  el('refresh-saved').onclick=action(async()=>{el('saved').replaceChildren();const page=await api('/workspace/assessments');for(const record of page.items.filter(v=>v.methodology_id==='policy_selection_v1')){const button=document.createElement('button');button.textContent=record.name+' · '+record.generated_at;button.onclick=action(async()=>{const opened=await api('/workspace/policies/'+record.id+'/open',{method:'POST',body:{}});await openResult(opened.result_id);});el('saved').append(button);}});
  el('export').onclick=action(async()=>{if(!resultID)throw Error('Open completed evidence first.');let job=await api('/jobs',{method:'POST',body:{kind:'export',client_request_id:'cg5-export-'+crypto.randomUUID(),result_id:resultID,format:el('format').value,audience:el('audience').value}});while(['pending','running'].includes(job.state)){await new Promise(r=>setTimeout(r,300));job=await api('/jobs/'+job.id);}if(job.state!=='succeeded')throw Error(job.error?.message||'Export stopped');const artifacts=await api('/results/'+resultID+'/artifacts');el('downloads').replaceChildren();for(const artifact of artifacts.filter(v=>job.output.artifact_ids.includes(v.id))){const link=document.createElement('a');link.href=`${base}/artifacts/${artifact.id}/content`;link.textContent=`Download ${artifact.kind} (${artifact.audience})`;link.style.display='block';el('downloads').append(link);}});
  window.openConfidenceGuardPolicy=async(id,retained=false)=>{enter();if(retained)await api('/workspace/policies/'+id+'/open',{method:'POST',body:{}});await openResult(id);};
  const previousShowResult=showResult;showResult=async id=>{const data=await api('/results/'+id);if(data.methodology_id==='policy_selection_v1'){enter();return openResult(id);}return previousShowResult(id);};
})();
