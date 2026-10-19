/* CG2 client projects backend evidence; it performs no statistical calculations. */
'use strict';
let importedMethodHandles=[];
const cg1Compose=compose;
for(let i=1;i<=2;i++){
  const div=document.createElement('details');
  div.innerHTML=`<summary>Run ${i}: calibration / distribution input bindings</summary><div class="row"><label>Logical run ID<input id="m${i}-run-id" value="run${i}"></label><label>Model ID<input id="m${i}-model-id" value="model${i}"></label><label>Entity / cluster key columns<input id="m${i}-entities"></label><label>Binary log-odds column<input id="m${i}-binary-logit"></label><label>Complete class-to-logit JSON<input id="m${i}-logits" placeholder='{"0":"z0","1":"z1"}'></label></div><div class="row"><label>Positive scale column<input id="m${i}-scale"></label><label>Scale predictor ID<input id="m${i}-scale-model"></label><label>Scale predictor version<input id="m${i}-scale-version" value="v1"></label><label>Ordered quantile fields (JSON)<input id="m${i}-quantiles" placeholder='[{"level":"0.05","column":"q05"},{"level":"0.95","column":"q95"}]'></label><label>Quantile predictor ID<input id="m${i}-quantile-model"></label><label>Quantile predictor version<input id="m${i}-quantile-version" value="v1"></label></div><div class="row"><label>Long predictive-sample source<select id="m${i}-samples" data-source></select></label><label>Sample event keys<input id="m${i}-sample-keys" placeholder="id"></label><label>Draw ID column<input id="m${i}-sample-draw" placeholder="draw"></label><label>Sample value column<input id="m${i}-sample-value" placeholder="value"></label><label>Sample meaning<select id="m${i}-sample-meaning"><option value="empirical_distribution">Empirical predictive distribution</option><option value="iid_monte_carlo">Declared IID Monte Carlo draws</option></select></label></div>`;
  byId(`run${i}-fields`).append(div);
}
compose=function(){
  const request=cg1Compose();
  if(byId('method-workflow').value==='cg1')return request;
  const evaluation=request.spec,methods=[],representations=[],selections=[];
  const rename={};
  evaluation.runs.forEach((run,index)=>{
    const i=index+1,get=k=>byId(`m${i}-${k}`).value;
    rename[run.id]=get('run-id');run.id=get('run-id');run.model.id=get('model-id');
    if(get('entities'))run.entity_columns=split(get('entities'));
    const rep={run:run.id};
    if(get('binary-logit'))rep.binary_logit=get('binary-logit');
    if(get('logits'))rep.logits=JSON.parse(get('logits'));
    if(get('scale')){rep.scale=get('scale');rep.scale_model={id:get('scale-model'),version:get('scale-version')};}
    if(get('quantiles')){rep.quantiles=JSON.parse(get('quantiles'));rep.quantile_model={id:get('quantile-model'),version:get('quantile-version')};}
    if(get('samples')){
      let source=evaluation.sources.find(s=>s.handle===get('samples'));
      if(!source){source={id:`source${evaluation.sources.length+1}`,handle:get('samples')};evaluation.sources.push(source);}
      rep.samples={source:source.id,key_columns:split(get('sample-keys')),draw_column:get('sample-draw'),value_column:get('sample-value'),meaning:get('sample-meaning')};
    }
    if(Object.keys(rep).length>1)representations.push(rep);
    if(['apply','evaluate'].includes(byId('method-workflow').value))return;
    const calibrators=split(byId('method-calibrators').value);
    for(const kind of calibrators){
      const method={id:`${run.id}:${kind}`,kind,run:run.id};
      if(['platt','isotonic'].includes(kind))method.input=byId('method-scalar-input').value;
      if(kind==='temperature')method.input=byId('method-temperature-input').value;
      if(kind==='dirichlet')method.regularization=Number(byId('method-dirichlet-ridge').value);
      methods.push(method);
    }
    if(byId('method-select-calibration').checked&&calibrators.length){selections.push({id:`selection:${run.id}`,candidates:calibrators.map(k=>`${run.id}:${k}`),objective:byId('method-selection-objective').value});}
    for(const kind of split(byId('method-conformal').value)){
      const method={id:`${run.id}:${kind}`,kind,run:run.id,levels:split(byId('method-levels').value)};
      if(kind==='split')method.input='point';
      else if(kind==='normalized')method.input='normalized';
      else if(kind==='cqr'){method.input='quantiles';method.lower_quantile=byId('method-cqr-lower').value;method.upper_quantile=byId('method-cqr-upper').value;}
      else if(byId('method-parent').value)method.parent=byId('method-parent').value==='selected'?`selected:selection:${run.id}`:`${run.id}:${byId('method-parent').value}`;
      if(kind==='raps'){method.penalty=Number(byId('method-raps-penalty').value);method.k_reg=Number(byId('method-raps-k').value);}
      methods.push(method);
    }
  });
  if(evaluation.comparison){evaluation.comparison.left=rename[evaluation.comparison.left];evaluation.comparison.right=rename[evaluation.comparison.right];}
  for(const policy of evaluation.policies||[])policy.run=rename[policy.run];
  const roles={namespace:byId('method-namespace').value,unit:byId('method-role-unit').value};
  if(byId('method-workflow').value==='apply')roles.proportions={E:1};else roles.column=byId('method-role-column').value;
  const spec={schema_version:'confidenceguard.study_spec/1.0',evaluation,roles,methods,representations,selections,
    separation:{base_predictions_independent:byId('method-base-independent').checked,evaluation_independent:byId('method-evaluation-independent').checked,exchangeable_scores:byId('method-exchangeable').checked,labels_representative:byId('method-representative').checked},
    inference:{mode:byId('method-inference').value,metrics:split(byId('method-inference-metrics').value),replicates:Number(byId('method-replicates').value),adjustment:byId('method-adjustment').value},
    calibration_strategy:byId('method-bin-strategy').value};
  if(importedMethodHandles.length)spec.method_handles=[...importedMethodHandles];
  return {spec,config:request.config};
};
byId('method-workflow').onchange=()=>{
  byId('confirm').checked=false;
  const workflow=byId('method-workflow').value;
  byId('evaluate').textContent=workflow==='cg1'?'Evaluate confirmed revision':workflow==='apply'?'Apply to new inputs (unvalidated)':workflow==='fit'?'Fit confirmed methods':workflow==='study'?'Fit and independently evaluate':'Evaluate supplied uncertainty';
};
byId('method-import').onchange=handle(async()=>{
  const file=byId('method-import').files[0];if(!file)return;
  const form=new FormData();form.append('file',file);
  const result=await api('/methods/import',{method:'POST',body:form});importedMethodHandles=result.method_handles;
  const summaries=await Promise.all(importedMethodHandles.map(id=>api(`/methods/${id}`)));
  byId('method-import-status').textContent=JSON.stringify(summaries,null,2);
  if(summaries.length){const first=summaries[0];byId('m1-run-id').value=first.run;byId('m1-model-id').value=first.model.id;byId('r1-version').value=first.model.version;byId('task').value=first.task.kind;byId('definition').value=first.task.outcome_definition;byId('classes').value=first.task.classes.join(',');byId('positive').value=first.task.positive_class||'';byId('units').value=first.task.units||'';byId('horizon').value=first.task.horizon||'';}
  for(const summary of summaries){const signature=summary.input_signature||{};if(signature.scale_model){byId('m1-scale-model').value=signature.scale_model.id;byId('m1-scale-version').value=signature.scale_model.version;}if(signature.quantile_model){byId('m1-quantile-model').value=signature.quantile_model.id;byId('m1-quantile-version').value=signature.quantile_model.version;}}
  byId('confirm').checked=false;status('Methods imported as fitted-only. New applications are unvalidated.');
});
function evidenceTable(parent,headers,values){
  const table=document.createElement('table'),head=document.createElement('thead'),body=document.createElement('tbody'),row=document.createElement('tr');
  for(const title of headers){const cell=document.createElement('th');cell.textContent=title;row.append(cell);}head.append(row);
  for(const valuesRow of values){const tr=document.createElement('tr');for(const value of valuesRow){const cell=document.createElement('td');cell.textContent=String(value??'Unavailable');tr.append(cell);}body.append(tr);}
  table.append(head,body);parent.append(table);
}
const cg1ShowResult=showResult;
showResult=async function(id){
  await cg1ShowResult(id);
  const summary=await api(`/results/${id}/summary`),panel=byId('method-evidence');panel.replaceChildren();
  if(!summary.cg2)return;
  const cg=summary.cg2;
  byId('findings').textContent=summary.findings.map(f=>`${f.priority}: ${f.message}`).join('\n')||'No additional finding was emitted. Review population retention and availability below.';
  const title=document.createElement('h3');title.textContent='Method and application evidence';panel.append(title);
  const notice=document.createElement('p');notice.textContent='Independent evaluation applies to this exact application and population. Reapplication remains unvalidated. Neither state proves improvement or future coverage.';panel.append(notice);
  const states=cg.evidence_views||Object.fromEntries((Array.isArray(cg.methods)?cg.methods:[]).map(m=>[m.id,{method_state:m.method_evidence_state,application_state:m.application_evidence_state}]));
  evidenceTable(panel,['Variant','Method evidence','Current application'],Object.entries(states).map(([key,v])=>[key,v.method_state,v.application_state]));
  for(const selection of cg.selections||[]){const p=document.createElement('p');p.textContent=`Selection ${selection.id}: ${selection.selected||'no eligible choice'} using ${selection.objective}; common S support ${selection.common_population?.denominator??'protected'}. Selection evidence is not independent evaluation.`;panel.append(p);}
  const roles=document.createElement('p');roles.textContent='Role support: '+Object.entries(cg.roles||{}).map(([key,v])=>`${key}: ${JSON.stringify(v.counts)}`).join('; ');panel.append(roles);
  const infer=document.createElement('p');infer.textContent=`Inference: ${cg.inference.status}. Fixed-artifact intervals exclude training, fitting and selection variability. Missing intervals do not establish equality.`;panel.append(infer);
  const matched=await api(`/results/${id}/measurements?family=comparison&limit=1000`);
  const comparisons=matched.items.filter(m=>m.data.left_run&&m.data.right_run&&m.scope==='paired'&&m.metric.endsWith('_right_minus_left'));
  const priority=m=>/coverage@|efficiency@/.test(m.metric)?0:/^(brier|log_loss)_/.test(m.metric)?1:/^(mae|rmse)_/.test(m.metric)?2:3;
  comparisons.sort((a,b)=>priority(a)-priority(b));
  const heading=document.createElement('h3');heading.textContent='Original versus transformed — matched populations';panel.append(heading);
  evidenceTable(panel,['Comparison / metric / scope','Right minus left','Planned / paired support','Qualification'],comparisons.slice(0,24).map(m=>[`${m.data.left_run} → ${m.data.right_run}: ${m.metric} (${m.scope})`,m.value_state==='finite'?m.value:m.value_state,`${m.data.planned_common_input_support??'see detail'} / ${m.denominator}`,m.reason||m.data.comparison_qualification||m.basis]));
  const caption=document.createElement('p');caption.textContent=`Showing ${Math.min(24,comparisons.length)} overall paired deltas from ${matched.total} comparison records, prioritizing coverage, efficiency and proper losses. Native measurements below can use different populations; full metric-specific definitions remain in measurement details and exports.`;panel.append(caption);
  const detail=document.createElement('details'),label=document.createElement('summary'),pre=document.createElement('pre');label.textContent='Exact roles, inference admission and population evidence';pre.textContent=JSON.stringify({roles:cg.roles,prior_membership:cg.prior_membership_checks,inference:cg.inference,comparisons:cg.comparisons},null,2);detail.append(label,pre);panel.append(detail);
};
byId('evaluate').onclick=handle(async()=>{
  if(!evaluation||!fingerprint||!byId('confirm').checked||JSON.stringify(current())!==confirmedBody)throw Error('Inspect and confirm the current configuration first.');
  const mode=byId('method-workflow').value;
  const output=await job({kind:mode==='cg1'?'evaluate':mode,evaluation_id:evaluation.id,revision:evaluation.revision,fingerprint});
  await showResult(output.result_id);
  if(output.artifact_ids){
    const artifacts=await api(`/results/${output.result_id}/artifacts`);
    for(const a of artifacts.filter(a=>output.artifact_ids.includes(a.id))){const link=document.createElement('a');link.href=`${base}/artifacts/${a.id}/content`;link.textContent=`Download ${a.kind} (${a.audience}; unvalidated application)`;byId('downloads').append(link);}
  }
  status(mode==='apply'?'Application completed; new predictions remain unvalidated.':'Completed evidence is ready.');
});
