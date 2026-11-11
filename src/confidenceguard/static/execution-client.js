/* Authoring and presentation only. The supervised backend owns all analytics. */
(() => {
  'use strict';
  const el=id=>byId('cg6-'+id), read=id=>JSON.parse(el(id).value), pretty=v=>JSON.stringify(v,null,2);
  const show=s=>{el('status').textContent=s;}, action=fn=>async()=>{try{await fn();}catch(e){show(e.message);}};
  let execution, scenarios=[], files=[], draft, inspected, active, result, cursor, protocol;
  const knownPredictors=new Map(),predictorId=p=>p.id||knownPredictors.get(p.handle)?.id;
  function retainHandles(output){for(const p of output.predictors||[]){knownPredictors.set(p.handle,p);el('registered-model').add(new Option(`${p.id} (${p.adapter}, ${p.task})`,p.handle));}for(const h of output.auxiliary_handles||[])el('aux-handle').add(new Option(h,h));}
  function activate(id){
    const panels={'nav-history':'history-workspace','nav-investigations':'cg4-workspace','nav-policies':'cg5-workspace','nav-execution':'cg6-workspace'},owned=new Set(Object.values(panels));
    document.querySelectorAll('main>section').forEach(n=>{n.hidden=id==='nav-evaluate'?(owned.has(n.id)||n.id==='results'&&!resultId):n.id!==panels[id];});
    document.querySelectorAll('.product-nav button').forEach(n=>{if(n.id===id)n.setAttribute('aria-current','page');else n.removeAttribute('aria-current');});
  }
  const preceding=[...document.querySelectorAll('.product-nav button')];
  for(const n of preceding)if(n.id!=='nav-execution'){const prev=n.onclick;n.onclick=async e=>{el('workspace').hidden=true;if(prev)await prev(e);activate(n.id);};}
  byId('nav-execution').onclick=()=>{activate('nav-execution');refreshSources();};
  function invalidate(){draft=null;inspected=null;show('Configuration changed. Inspect before executing.');}
  el('spec').oninput=invalidate;el('config').oninput=invalidate;el('workflow').onchange=invalidate;
  function setSpec(workflow,spec){el('workflow').value=workflow;el('spec').value=pretty(spec);invalidate();}
  function showFiles(){el('file-list').textContent=files.map(f=>`${f.name}: ${f.sha256}`).join('\n');el('entry').replaceChildren(...files.map(f=>new Option(f.name,f.handle)));show('Artifact bytes captured. Review the complete predictor before execution.');}
  el('files').onchange=action(async()=>{for(const file of el('files').files){const body=new FormData();body.append('file',file);files.push(await api('/execution/files',{method:'POST',body}));}showFiles();});
  el('capture-file').onclick=action(async()=>{files.push(await api('/execution/files',{method:'POST',body:{root_id:byId('root').value,relative_path:el('artifact-path').value}}));showFiles();});
  function model(){
    if(el('registered-model').value)return {handle:el('registered-model').value};
    const kind=el('task').value,classes=kind==='regression'?[]:split(el('classes').value),task={kind,outcome_definition:el('definition').value,classes};
    if(kind==='regression')task.units=el('units').value;if(kind==='binary_classification')task.positive_class=el('positive').value;
    const adapter=el('adapter').value,channel=el('channel').value,entry=files.find(f=>f.handle===el('entry').value);
    const p={id:el('model-id').value,task,adapter,inputs:split(el('inputs').value).map(column=>({id:column,column,kind:el('input-type').value,role:'model_input'})),
      outputs:[{channel,source:el('output').value||(adapter==='sklearn'?(channel==='probabilities'?'predict_proba':channel==='score'?'decision_function':'predict'):'output'),...(['probabilities','logits'].includes(channel)?{classes}:{})}],
      preprocessing:read('preprocessing'),decision:{rule:channel==='probabilities'?'probability_argmax':'none'}};
    if(adapter==='torch'||adapter==='constant')p.architecture=read('architecture');
    if(adapter==='custom')p.registration=el('registration').value;
    if(entry){p.entry=entry.name;p.files=files.map(f=>({name:f.name,handle:f.handle,sha256:f.sha256}));}
    return p;
  }
  function baseSpec(){
    const handle=el('source').value;if(!handle)throw Error('Select an input table registered in Evaluations & methods.');
    const device=el('device').value,s={predictors:[model()],sources:[{id:'input',handle}],input_source:'input',key_columns:split(el('keys').value),entity_columns:split(el('entities').value),namespace:el('namespace').value,
      device:{kind:device,index:device==='cuda'?Number(el('device-index').value):0,allow_cpu_fallback:el('fallback').checked}};
    if(el('outcome').value)s.outcomes={source:'input',column:el('outcome').value,key_columns:s.key_columns};
    if(el('role-column').value)s.roles={namespace:s.namespace,column:el('role-column').value,unit:s.entity_columns.length?'entity':'event'};
    return s;
  }
  el('compose').onclick=action(()=>{execution=baseSpec();setSpec('execution',execution);});
  el('add-model').onclick=action(()=>{if(!execution)throw Error('Compose the first predictor first.');execution.predictors.push(model());setSpec('execution',execution);});
  const needExecution=()=>{const current=read('spec'),candidate=current.execution||current;if(candidate.predictors&&candidate.sources)execution=structuredClone(candidate);if(!execution)throw Error('Compose an execution first.');return structuredClone(execution);};
  el('compose-aux').onclick=action(()=>{
    const s={execution:needExecution(),kind:el('aux-kind').value,base_predictor:predictorId(execution.predictors[0]),levels:split(el('levels').value).map(Number)};
    if(el('aux-family').value!=='all')s.candidates=[{id:'constant',family:'constant'},{id:el('aux-family').value,family:el('aux-family').value}];
    if(el('material').value){s.failure='material_error';s.material_error=Number(el('material').value);}setSpec('auxiliary',s);
  });
  function auxiliary(assess){if(!el('aux-handle').value)throw Error('Fit or import an auxiliary first.');setSpec('auxiliary',{execution:needExecution(),artifact_handle:el('aux-handle').value,role:assess?'E':null});}
  el('compose-apply').onclick=action(()=>auxiliary(false));el('compose-aux-assess').onclick=action(()=>auxiliary(true));
  el('add-scenario').onclick=action(()=>{
    const operation=el('operation').value,fields=split(el('transform-fields').value),severity=Number(el('severity').value),parameters=read('transform-params');
    const key={missing:'rate',noise:'scale',round:'step',finite_difference:'step',category:'rate',image_noise:'scale',image_blur:'radius',image_brightness:'factor',image_contrast:'factor'}[operation];if(key&&!Object.hasOwn(parameters,key))parameters[key]=severity;
    const constraints={};for(const f of fields){const c={mutable:true};if(el('lower').value)c.lower=Number(el('lower').value);if(el('upper').value)c.upper=Number(el('upper').value);if(Object.keys(c).length>1)constraints[f]=c;}
    const s={id:el('scenario-id').value,transformations:[{id:'transform',operation,fields,parameters,constraints}],replicates:Number(el('replicates').value),outcome_relation:el('outcome-relation').value};
    if(s.outcome_relation!=='unknown')s.outcome_reason=el('outcome-reason').value;
    if(el('attack').value)s.attack={algorithm:el('attack').value,fields,access:['fgsm','pgd'].includes(el('attack').value)?'white_box':'black_box',epsilon:Number(el('epsilon').value),queries_per_root:Number(el('queries').value),constraints};
    scenarios.push(s);show(`${scenarios.length} scenarios authored. Compose and inspect the experiment next.`);
  });
  el('clear-scenarios').onclick=()=>{scenarios=[];show('Scenario draft cleared.');};
  el('compose-robustness').onclick=action(()=>setSpec('robustness',{execution:needExecution(),scenarios:structuredClone(scenarios),sensitivity:read('sensitivity'),comparisons:execution.predictors.length===2?[{left:predictorId(execution.predictors[0]),right:predictorId(execution.predictors[1])}]:[]}));
  el('compose-reference').onclick=action(async()=>{const file=el('reference').files[0];if(!file)throw Error('Select the fixed keyed reference output file.');setSpec('execution',{execution:needExecution(),qualification:{reference:JSON.parse(await file.text()),atol:Number(el('atol').value),rtol:Number(el('rtol').value)}});});
  el('import-auxiliary-submit').onclick=action(async()=>{const file=el('import-auxiliary').files[0];if(!file)throw Error('Select an auxiliary descriptor.');const artifact=JSON.parse(await file.text()),bindings=read('auxiliary-bindings');for(const p of artifact.predictors){bindings[p.id]??={};for(const f of p.files){const captured=files.find(v=>v.name===f.name&&v.sha256===f.sha256);if(captured)bindings[p.id][f.name]??=captured.handle;}}const imported=await api('/execution/auxiliaries/import',{method:'POST',body:{artifact,files:bindings}});el('aux-handle').add(new Option(imported.handle,imported.handle));el('aux-handle').value=imported.handle;show('Auxiliary mathematics and captured model bytes bound. Independent assessment remains separate.');});
  el('compose-restate').onclick=action(()=>{if(!result)throw Error('Complete or reopen protected evidence first.');setSpec('restatement',{result_id:result,spec:{sources:[{id:'later',handle:el('later-source').value}],outcomes:{source:'later',column:el('later-outcome').value,key_columns:split(el('later-keys').value)},reason:el('restate-reason').value}});});
  async function run(kind){
    if(kind!=='cg6_inspect'&&(!draft||!inspected))throw Error('Inspect the current complete specification first.');
    if(kind==='cg6_inspect'){draft=await api('/execution/drafts',{method:'POST',body:{workflow:el('workflow').value,spec:read('spec'),config:read('config')}});}
    let j=await api('/jobs',{method:'POST',body:{kind,draft_id:draft.id,revision:draft.revision,fingerprint:inspected?.fingerprint,client_request_id:crypto.randomUUID(),retain:el('retain').checked}});active=j.id;
    while(['pending','running','cancelling'].includes(j.state)){show(`${j.kind}: ${j.state} ${j.progress?.stage||''}`);await new Promise(r=>setTimeout(r,400));j=await api(`/jobs/${j.id}`);}active=null;
    if(j.state!=='succeeded')throw Error(`${j.state}: ${j.error?.code||'Operation stopped'}`);
    if(kind==='cg6_inspect'){inspected=j.output;el('inspection').textContent=pretty(j.output);show('Inspection complete. Review identities, devices and limits before execution.');}
    else{retainHandles(j.output);result=j.output.result_id;await display();show('Completed evidence is ready for inspection.');}
  }
  for(const [button,kind] of Object.entries({inspect:'cg6_inspect',register:'cg6_register',qualify:'cg6_qualify',execute:'cg6_execute',fit:'cg6_auxiliary_fit',apply:'cg6_auxiliary_apply','aux-assess':'cg6_auxiliary_assess',run:'cg6_robustness',assess:'cg6_assess','policy-stress':'cg6_policy_stress',restate:'cg6_restate'}))el(button).onclick=action(()=>run(kind));
  el('cancel').onclick=action(async()=>{const id=active||activeJob;if(id)await api(`/jobs/${id}/cancel`,{method:'POST'});});
  el('capabilities').onclick=action(async()=>{el('hardware').textContent=pretty(await api('/execution/capabilities'));});
  function table(parent,rows){const t=document.createElement('table'),head=t.createTHead().insertRow();for(const v of ['Predictor / scope','Measurement','Value','Eligible support']){const th=document.createElement('th');th.textContent=v;head.append(th);}for(const row of rows){const tr=t.insertRow(),structured=row.value_state==='undefined'&&!row.reason&&Object.keys(row.data||{}).length;for(const v of [row.run+' / '+row.scope,row.metric,row.value_state==='finite'?row.value:structured?'See detail':row.value_state,row.denominator])tr.insertCell().textContent=String(v);const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='Population and measurement detail';pre.textContent=pretty(row);details.append(summary,pre);tr.lastChild.append(details);}parent.append(t);}
  async function more(){if(!result)throw Error('Complete or reopen evidence first.');const page=await api(`/results/${result}/execution/measurements?cursor=${cursor||0}&limit=50&audience=${el('audience').value}`);table(el('results'),page.items);cursor=page.next_cursor;el('more').disabled=!cursor;}
  async function display(){
    el('results').replaceChildren();cursor=null;const data=await api(`/results/${result}/execution/summary?audience=${el('audience').value}`),panel=data.cg6;
    el('retained-id').value=data.analysis_id;
    const line=text=>{const p=document.createElement('p');p.textContent=text;el('results').append(p);};
    line(`Evidence ID: ${data.analysis_id}. Stage: ${panel.stage.replaceAll('_',' ')}.`);
    line(panel.joint_withholding?'Dependent measurements are withheld together under the selected disclosure policy.':'Inspect eligible support and outcome relations before interpreting changes.');
    const hardware=document.createElement('table'),head=hardware.createTHead().insertRow();for(const text of ['Target','Runtime evidence']){const th=document.createElement('th');th.textContent=text;head.append(th);}
    for(const device of ['cpu','mps','cuda']){const row=hardware.insertRow();row.insertCell().textContent=device.toUpperCase();row.insertCell().textContent=String(panel.qualification?.[device]||'not established').replaceAll('_',' ');}el('results').append(hardware);
    if(panel.scenarios?.length){const t=document.createElement('table'),h=t.createTHead().insertRow();for(const text of ['Scenario','Planned / applicable','Outcome relation']){const th=document.createElement('th');th.textContent=text;h.append(th);}for(const s of panel.scenarios){const row=t.insertRow();for(const value of [s.id,`${s.planned} / ${s.applicable}`,s.outcome_relation||'unavailable'])row.insertCell().textContent=String(value);}el('results').append(t);}
    for(const claim of panel.claims||[])line(`Claim ${claim.id}: ${claim.state}${claim.reason?' — '+claim.reason.replaceAll('_',' '):''}.`);
    if(panel.membership_check)line(`Auxiliary membership: ${panel.membership_check}. Independent assessment: ${panel.independent_assessment}.`);
    const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='Methods, device realization and provenance';pre.textContent=pretty(panel);details.append(summary,pre);el('results').append(details);await more();
  }
  el('more').onclick=action(more);el('audience').onchange=action(display);
  function protocolLink(){el('protocol-result').replaceChildren();const link=document.createElement('a');link.href=`${base}/execution/protocols/${protocol.handle}/content`;link.textContent='Download protected frozen protocol';el('protocol-result').append(link);}
  el('freeze').onclick=action(async()=>{if(!result)throw Error('Run a development experiment first.');protocol=await api('/execution/protocols',{method:'POST',body:{result_id:result,...read('protocol')}});protocolLink();show('Protocol frozen. New assessment requires independent E units.');});
  el('import-protocol').onchange=action(async()=>{protocol=await api('/execution/protocols/import',{method:'POST',body:{protocol:JSON.parse(await el('import-protocol').files[0].text())}});protocolLink();});
  el('compose-assessment').onclick=action(()=>{if(!protocol)throw Error('Freeze or import a protocol first.');setSpec('assessment',{protocol_handle:protocol.handle,execution:needExecution()});});
  el('bridge').onclick=action(async()=>{const r=await api(`/results/${result}/execution/bridge`,{method:'POST',body:{scope:el('bridge-scope').value}});byId('advanced').checked=true;byId('spec').value=pretty({spec:r.spec,config:read('config')});byId('nav-evaluate').click();show('Completed keyed predictions supplied to the methods editor. No model executed.');});
  el('reopen').onclick=action(async()=>{const r=await api(`/workspace/execution/${encodeURIComponent(el('retained-id').value)}/open`,{method:'POST',body:{}});retainHandles(r);result=r.result_id;await display();});
  el('export').onclick=action(async()=>{if(!result)throw Error('Complete or reopen evidence first.');show('Exporting canonical report…');const output=await job({kind:'export',result_id:result,format:el('format').value,audience:el('audience').value});const artifacts=await api(`/results/${result}/artifacts`);el('downloads').replaceChildren();for(const a of artifacts.filter(a=>output.artifact_ids.includes(a.id))){const link=document.createElement('a');link.href=`${base}/artifacts/${a.id}/content`;link.textContent=`Download ${a.kind} (${a.audience})`;el('downloads').append(link,document.createElement('br'));}show('Canonical report exported.');});
})();
