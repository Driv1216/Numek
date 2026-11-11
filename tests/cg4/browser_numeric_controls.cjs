/* Exercise the actual browser composers with a minimal DOM, without APIs or analytics. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.argv[2],'utf8');
function setup(response){
  const elements=new Map();let calls=0;
  class Element{
    constructor(id){this.id=id;this.value='';this.textContent='';this.checked=false;this.hidden=false;this.children=[];this.parentElement={hidden:false};}
    addEventListener(){}
    setAttribute(){}
    removeAttribute(){}
    replaceChildren(...children){this.children=children;}
    append(...children){this.children.push(...children);}
    querySelectorAll(){return this.id==='cg4-strategies'?[{value:'structured'}]:[];}
  }
  const byId=id=>{if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);};
  const values={'name':'Synthetic input contract','namespace':'synthetic-contract','seed':'0','role-unit':'independent_rows',
    'role-column':'role','objective':'error_rate','direction':'higher','comparator':'ceiling','ceiling':'0.1','delta':'0.15',
    'features':'[]','representations':'[]','time-view':'at_decision','spec':'UNCHANGED_SPEC','confirmation':'UNCHANGED_PROTOCOL',
    'method':'finite','sampling':'independent_rows','upstream':'unknown','external':'unknown','membership-scope':'full_population',
    'coverage':'1','replicates':'20000','maximum-replicates':'200000','replicate-policy':'nominal_admission'};
  for(const [id,value] of Object.entries(values))byId('cg4-'+id).value=value;
  const context={byId,Node:Element,document:{createElement:tag=>new Element(tag),querySelectorAll:()=>[]},window:{},structuredClone,
    sources:[],base:'/api/confidenceguard/v1',showResult:async()=>{},split:value=>value.split(',').filter(Boolean),
    current:()=>({spec:{task:{kind:'binary_classification'},sources:[],runs:[{id:'model'}]}}),
    api:async path=>{calls++;if(response)return response(path);throw Error('Unexpected backend/H request during input composition');}};
  vm.runInNewContext(source,context,{timeout:1000});
  const text=element=>[element.textContent,...element.children.map(child=>typeof child==='string'?child:text(child))].join(' ');
  return {get:id=>byId('cg4-'+id),calls:()=>calls,open:context.window.openConfidenceGuardInvestigation,text:id=>text(byId('cg4-'+id))};
}
(async()=>{
  for(const value of ['', ' ', 'NaN', 'Infinity', '-Infinity', 'abc']){
    const s=setup();s.get('ceiling').value=value;await s.get('compose').onclick();
    assert.match(s.get('status').textContent,/explicit finite ceiling/);
    assert.equal(s.get('spec').value,'UNCHANGED_SPEC');assert.equal(s.calls(),0);
    assert.match(s.get('inspection').textContent,/inspect again/);
  }
  for(const value of ['0','0.25','-2.5']){
    const s=setup();s.get('ceiling').value=value;await s.get('compose').onclick();
    assert.equal(JSON.parse(s.get('spec').value).objectives[0].ceiling,Number(value));assert.equal(s.calls(),0);
  }
  for(const field of ['coverage','replicates','maximum-replicates']){
    const s=setup();s.get(field).value='';s.get('family-download').children=['stale download'];
    await s.get('compose-confirmation').onclick();
    assert.match(s.get('status').textContent,/explicit finite/);
    assert.equal(s.get('confirmation').value,'UNCHANGED_PROTOCOL');assert.deepEqual(s.get('family-download').children,[]);assert.equal(s.calls(),0);
  }
  const zero=setup();zero.get('coverage').value='0';await zero.get('compose-confirmation').onclick();
  assert.equal(JSON.parse(zero.get('confirmation').value).minimum_membership_coverage,0);
  const nominal=setup();nominal.get('comparator').value='complement';nominal.get('direction').value='nominal_shortfall';nominal.get('nominal').value='';
  await nominal.get('compose').onclick();assert.match(nominal.get('status').textContent,/explicit finite nominal coverage/);assert.equal(nominal.calls(),0);
  for(const scope of ['observed_labels','complete_population',undefined]){
    const value={name:'Synthetic selective outcome assessment',coverage:{},outcomes:{scope},investigation:{
      stage:'confirmation',candidate_count:0,assessments:[{objective:{metric:'error_rate'},state:'inconclusive',support:{planned:240,available:240,members:240,conditional_members:120,conditional_nonmembers:0,unavailable:0},strength:'finite_sample'}]}};
    const shown=setup(path=>path.endsWith('/summary')?value:{items:[],next_cursor:null});await shown.open('synthetic');
    assert.match(shown.text('assessment'),scope==='observed_labels'?/observed labels only.*do not establish failure rates/:scope==='complete_population'?/complete frozen population.*Incomplete required outcomes/:/exact outcome scope was not retained/);
    assert.match(shown.text('assessment'),/Planned 240; applicable 240; members 240; metric 120 \/ 0; membership unavailable 0/);
  }
  for(const inPanel of [true,false]){
    const partial={local_separation:'partially_checked',local_identity_scope:'canonical_history_keys_original_aliases_incomplete'};
    const assessment={state:'inconclusive',independence_qualification:partial};
    const value={coverage:{},investigation:{stage:'confirmation',candidate_count:0,assessments:[assessment],...(inPanel?{independence:partial}:{})}};
    const shown=setup(path=>path.endsWith('/summary')?value:{items:[],next_cursor:null});await shown.open('synthetic-partial');
    assert.match(shown.text('assessment'),/missing overlap records do not prove prior evidence was untouched/);
  }
  const historical=process.argv[3]?JSON.parse(fs.readFileSync(process.argv[3],'utf8')):[
    {coverage:{},investigation:{stage:'confirmation',candidate_count:0,assessments:[{objective:{metric:'average_precision'},state:'confirmed',strength:'approximate',effect:.694,interval:{lower:.67,upper:.71},practical_threshold:.2}]}}];
  for(const value of historical){
    const before=JSON.stringify(value),row=value.investigation.assessments[0];
    const shown=setup(path=>path.endsWith('/summary')?value:{items:[],next_cursor:null});await shown.open('historical-approximation');
    assert.match(shown.text('assessment'),/Historical approximate assessment/);
    assert.match(shown.text('assessment'),/recorded finding: confirmed/);
    assert.match(shown.text('assessment'),/does not establish a new formal confirmation/);
    assert.ok(shown.text('assessment').includes(String(row.effect)));
    assert.equal(JSON.stringify(value),before,'Rendering must not rewrite historical values or finding states');
  }
  console.log('Historical approximation local/shareable rendering passed without changing recorded evidence.');
  console.log('Actual composer handlers passed: blanks/nonfinite refused, explicit zeros preserved, stale family controls invalidated, no backend/H requests.');
  console.log('Actual assessment renderer preserves observed-label, complete-population and missing historical scope qualifications with mocked display-only responses.');
})().catch(error=>{console.error(error);process.exitCode=1;});
