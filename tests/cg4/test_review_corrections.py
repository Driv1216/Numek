"""Founder-authorized regressions from the independent H1/H2/M1/L1 review."""
import copy
import csv
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

from confidenceguard import (ReliabilityWorkspace, WorkspaceConfig, InvestigationSpec, EvaluationError,
    ConfirmationSpec, investigate, freeze_hypotheses, inspect_confirmation, confirm_investigation)
from confidenceguard.contracts import digest
from confidenceguard.features import FEATURE_TIME_POLICY, normalize, missing_cell
from confidenceguard.feature_contracts import FeatureField
from confidenceguard.investigation import arguments, prepared
from confidenceguard.investigation_replay import replay_investigation, _population
from confidenceguard.evidence_use import EvidenceUseLedger, population_identifiers
from .helpers import binary
from tests.backend_support import stored_evidence


def declaration():
    return ConfirmationSpec(upstream_independence='declared_independent', external_exposure='declared_unexposed',
        declaration_author='Independent review regression', declaration_reason='Synthetic independent entities; explicit isolated fixture.')


def retained_input(tmp_path, *, cutoff=None, content='2026-01-01T12:00:00Z', owner='opportunity', offset=0, namespace=None,retain_features=True):
    tmp_path.mkdir(exist_ok=True)
    original=binary(tmp_path)
    path=tmp_path/'predictions.csv'
    with path.open() as stream:values=list(csv.DictReader(stream))
    for row in values:
        row.update(id=str(int(row['id'])+offset), entity=str(int(row['entity'])+offset),
            when='2026-01-02T00:00:00Z', content_at=content, cutoff=cutoff or '', label_at='2026-01-04T00:00:00Z')
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=values[0]);writer.writeheader();writer.writerows(values)
    value=original.to_dict()
    value['evaluation']['runs'][0]['prediction_at']={'column':'when'}
    value['evaluation']['outcomes']['available_at']={'column':'label_at'}
    value['roles']['namespace']=namespace or original.roles.namespace
    if cutoff is not None:
        value['features']=[{'id':'context','run':'model','owner':owner,'availability':'dated',
            'information_cutoff':{'column':'cutoff'}, 'fields':[
                {'id':field,'column':field,'kind':'categorical','available_at':{'column':'content_at'}} for field in ('x','z')]}]
    live=InvestigationSpec.from_dict(value)
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    ws.ingest({'schema_version':'confidenceguard.prediction_batch_spec/2.0','evaluation':value['evaluation'],
        'namespace':live.roles.namespace,'outcome_definition_version':'v1','bindings':[{'run':'model'}],
        'feature_views':value['features'] if retain_features else []})
    variant=ws.models()[0]['id'];history=live.to_dict();history.pop('evaluation');history['roles'].pop('column')
    history['objectives'][0]['run']=variant
    for view in history['features']:
        if view.get('run'):view['run']=variant
    history['history']={'workspace_path':str(ws.path),'selection':{'namespace':live.roles.namespace,'variants':[variant],
        'as_of':'2026-02-01T00:00:00Z','windows':[{'id':'jan','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'}]}}
    return ws,live,InvestigationSpec.from_dict(history)


def feature_states(spec):
    s,c,roots=arguments(spec,None,None)
    with prepared(s,c,roots) as p:return {key:[cell['state'] for cell in cells] for key,cells in p.features.items()}


@pytest.mark.parametrize('owner',['opportunity','prediction_revision'])
@pytest.mark.parametrize('cutoff,content,expected',[
    ('2026-01-01T00:00:00Z','2026-01-01T12:00:00Z','unavailable'),
    ('2026-01-03T00:00:00Z','2026-01-02T12:00:00Z','observed'),
    ('','2026-01-01T12:00:00Z','unavailable'),
    ('invalid','2026-01-01T12:00:00Z','unavailable'),
])
def test_declared_owner_cutoff_live_retained_parity(tmp_path,owner,cutoff,content,expected):
    ws,live,history=retained_input(tmp_path,cutoff=cutoff,content=content,owner=owner)
    assert feature_states(live)==feature_states(history)
    assert all(set(states)=={expected} for states in feature_states(history).values())
    facts=list(ws.catalog.iter_facts('feature'))
    assert all(f['payload']['information_cutoff']['policy']==FEATURE_TIME_POLICY for f in facts)
    # A later reconstruction never alters the original immutable feature objects.
    before=stored_evidence(ws,hashed=True)
    feature_states(history)
    assert before==stored_evidence(ws,hashed=True)


def test_original_temporal_counterexample_cannot_generate_a_confirmable_gate(tmp_path):
    _,live,history=retained_input(tmp_path,cutoff='2026-01-01T00:00:00Z')
    for spec in (live,history):
        result=investigate(spec)
        assert result.data['investigation']['candidates']==[]
        with pytest.raises(EvaluationError):freeze_hypotheses(result,confirmation=declaration())


@pytest.mark.parametrize('packet_state',['absent','invalid','fractional','boolean','noncanonical'])
def test_old_or_invalid_retained_cutoff_is_unavailable_without_rewriting(tmp_path,packet_state):
    from confidenceguard.history_storage import EvidenceWriter
    from confidenceguard.investigation_history import envelope
    ws,live,history=retained_input(tmp_path,cutoff='2026-01-03T00:00:00Z')
    # Publish a synthetic legacy-shaped view through the real immutable codec.
    # Parent monkeypatches would not reach spawned ingestion workers.
    legacy=[]
    for fact in ws.catalog.iter_facts('feature'):
        payload=copy.deepcopy(fact['payload']);payload['view']['id']='legacy'
        if packet_state=='absent':payload.pop('information_cutoff',None)
        else:payload['information_cutoff']['tick_ns']={
            'invalid':'invalid','fractional':1767398400000000000.5,'boolean':True,
            'noncanonical':'001767398400000000000'}[packet_state]
        from confidenceguard.investigation_history import retained_cutoff
        assert retained_cutoff(live.features[0],payload)[1]!='valid'
        payload['normalization']='typed_feature_v1'
        legacy.append(envelope('feature',[live.roles.namespace,'legacy',payload['owner_key']],payload))
    with ws.catalog.operation():
        operation,_=ws.catalog.begin('legacy-cutoff-fixture','same')
        writer=EvidenceWriter(ws.path/'staging'/operation,ws.catalog.config,operation)
        writer.add_features(legacy,('x','z'));writer.finish({'capture_stages':['synthetic_legacy_view']})
        ws.catalog.commit_capture(operation)
    history=replace(history,features=tuple(replace(v,id='legacy') for v in history.features))
    before=stored_evidence(ws)
    assert all(set(v)=={'observed'} for v in feature_states(live).values())
    assert all(set(v)=={'unavailable'} for v in feature_states(history).values())
    assert before==stored_evidence(ws)


def test_old_cutoff_discoveries_and_frozen_claims_remain_readable_but_cannot_confirm(tmp_path):
    _,live,_=retained_input(tmp_path,cutoff='2026-01-03T00:00:00Z')
    result=investigate(live);frozen=freeze_hypotheses(result,confirmation=declaration())
    assert all(h['feature_time_policy']==FEATURE_TIME_POLICY for h in frozen.data['hypotheses'])
    original=result.to_private_dict()
    old=copy.deepcopy(result);old.data['investigation'].pop('feature_time_policy');old.seal()
    with pytest.raises(EvaluationError,match='predates corrected'):freeze_hypotheses(old,confirmation=declaration())
    packet=frozen.to_dict()
    for h in packet['hypotheses']:
        h.pop('feature_time_policy');h['id']=digest({k:v for k,v in h.items() if k!='id'})
    from confidenceguard.investigation_contracts import confirmation_family_digest,FrozenHypothesisSet
    packet['family_digest']=confirmation_family_digest(packet['hypotheses'],declaration())
    packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'})
    legacy=FrozenHypothesisSet.from_dict(packet)
    assessed=confirm_investigation(legacy)
    assert all(a['state']=='statistically_inadmissible' and not a['H_outcomes_disclosed'] and
        'legacy_information_cutoff_interpretation_unqualified' in a['reason'] for a in assessed.data['investigation']['assessments'])
    assert result.to_private_dict()==original


@pytest.mark.parametrize('tracking',[False,True])
@pytest.mark.parametrize('H_only',[False,True])
def test_replay_aliases_refuse_renamed_source_but_preserve_disjoint_populations(tmp_path,monkeypatch,tracking,H_only):
    import confidenceguard.evidence_use as uses
    monkeypatch.setattr(uses,'_SESSION_USES',[])
    (tmp_path/'origin').mkdir();origin_spec=binary(tmp_path/'origin')
    namespace='review-replay-'+tmp_path.name
    origin_spec=replace(origin_spec,roles=replace(origin_spec.roles,namespace=namespace))
    origin=investigate(origin_spec)
    ws,live,history=retained_input(tmp_path/'target',offset=1000,namespace=namespace)
    if tracking:ws.evidence_tracking(True)
    s,c,roots=arguments(history,None,None)
    reserved=_population(s,c,roots,H_only).data
    with prepared(s,c,roots,identity_only=True) as p:
        indices=[i for i,key in enumerate(p.keys) if not H_only or p.roles[key]=='H']
        assert (reserved['events'],reserved['units'])==population_identifiers(p,indices)
        assert reserved['planned_records']==len(indices)
        if H_only:
            other=[i for i,key in enumerate(p.keys) if p.roles[key]!='H']
            assert not set(reserved['events'])&set(population_identifiers(p,other)[0])
    replay=replay_investigation(origin,history,reason='Reviewer counterexample: explicit prior outcome disclosure.',H_only=H_only)
    assert replay.data['coverage']['planned']==reserved['planned_records']
    assert replay.data['investigation']['history']
    if tracking:
        # Simulate process loss; durable refusal must not depend on the session supplement.
        monkeypatch.setattr(uses,'_SESSION_USES',[])
    renamed=replace(live,roles=replace(live.roles,namespace=namespace+'-renamed'))
    discovery=investigate(renamed,workspace=ws if tracking else None)
    frozen=freeze_hypotheses(discovery,confirmation=declaration())
    preview=inspect_confirmation(frozen,workspace=ws if tracking else None)
    assert any(reason in preview['admissibility_reasons'] for reason in ('known_session_exposure','previously_exposed_confirmation_population'))
    assessed=confirm_investigation(frozen,workspace=ws if tracking else None)
    assert all(a['state']=='statistically_inadmissible' and not a['H_outcomes_disclosed'] for a in assessed.data['investigation']['assessments'])
    _,disjoint,_=retained_input(tmp_path/'disjoint',offset=2000,namespace=namespace+'-renamed')
    clean=inspect_confirmation(frozen,confirmation_input=disjoint,workspace=ws if tracking else None)
    assert clean['admissibility_reasons']==[]
    assert all(row['admissibility_reasons']==[] for row in clean['membership'])


def test_old_replay_reservations_require_explicit_gap_handling_and_keep_bytes(tmp_path,monkeypatch):
    import confidenceguard.evidence_use as uses
    monkeypatch.setattr(uses,'_SESSION_USES',[])
    ws,live,_=retained_input(tmp_path)
    ws.evidence_tracking(True);ledger=EvidenceUseLedger(ws)
    ledger.record('outcome_disclosure',events=[digest('old')],units=[],population_digest=digest('legacy-replay'),
        metadata={'purpose':'historical_replay','origin':'old-record'})
    before=stored_evidence(ws)
    assert 'exposure_history_incomplete' in ledger.overlap([digest('unrelated')],[])
    monkeypatch.setattr(uses,'_SESSION_USES',[])
    frozen=freeze_hypotheses(investigate(live),confirmation=declaration())
    preview=inspect_confirmation(frozen,workspace=ws)
    assert 'exposure_history_gap_requires_current_declaration' in preview['admissibility_reasons']
    assert before==stored_evidence(ws)
    uses.record_session('outcome_disclosure',[digest('old')],[],metadata={'purpose':'outcome_restatement'})
    assert 'session_replay_exposure_history_incomplete' in inspect_confirmation(frozen)['admissibility_reasons']


@pytest.mark.parametrize('kind',['integer','decimal','float','timestamp','categorical','boolean'])
def test_state_only_columns_are_searched_with_availability_and_budget_bounds(kind):
    from confidenceguard.discovery_rules import propose
    from confidenceguard.investigation_contracts import InvestigationLimits
    from confidenceguard.investigation_membership import apply
    field=FeatureField('x','x',kind)
    cells=[normalize('',field) for _ in range(60)]+[normalize('\ud800',field) for _ in range(60)]
    cells += [missing_cell(kind,'unavailable'),missing_cell(kind,'not_retained')]
    objective=SimpleNamespace(spec=SimpleNamespace(direction='higher',metric='error_rate'),identity={})
    eligible=np.ones(len(cells),bool);loss=np.r_[np.zeros(60),np.ones(60),0,0]
    proposals,status=propose({'context.x':cells},eligible,loss,objective,InvestigationLimits())
    assert status['atoms']==2 and status['search_complete']
    gate=next(p['artifact'] for p in proposals if p['artifact']['parameters'].get('clauses')==[
        {'field':'context.x','op':'state','value':'invalid','kind':kind}])
    mask=apply(gate,{'context.x':cells},{})
    assert int(mask['member'].sum())==60 and int(mask['available'].sum())==120
    _,limited=propose({'context.x':cells},eligible,loss,objective,InvestigationLimits(max_nodes=1))
    assert limited['nodes']==1 and not limited['search_complete']


def test_historical_approximation_local_shareable_reopening_matches_canonical_warning(tmp_path):
    from datatrust.web import create_app
    from confidenceguard import EvaluationConfig
    from confidenceguard.investigation_result import InvestigationResult
    from jinja2 import Environment,FileSystemLoader,select_autoescape
    root=Path(__file__).resolve().parents[2]
    summary=json.loads((root/'validation/cg4/results/objective-ranking-ap-summary-v1.json').read_text())
    trial=json.loads((root/summary['trials'][0]['path']).read_text());row=trial['assessments'][0];before=copy.deepcopy(row)
    payload={'schema_version':'confidenceguard.confirmation_assessment/1.0','methodology_id':'failure_investigation_v1',
        'analysis_id':'a'*32,'generated_at':'2026-10-29T00:00:00Z','name':'Historical approximation fixture',
        'task':{'kind':'binary_classification','classes':['0','1']},'runs':[],'outcomes':{'scope':'observed_labels'},
        'comparison':None,'measurements':[],'checks':[],'findings':[],'coverage':{'populations':[]},
        'investigation':{'stage':'confirmation','candidates':[],'strategies':[],'overlap':[],'assessments':[row],'history':[],'notes':[]}}
    private={'schema':'confidenceguard.investigation_private/1.0','analysis_id':'a'*32,'files':{},'artifacts':{},'models':{},'locators':{},'config':EvaluationConfig().to_dict()}
    result=InvestigationResult(payload,private,{'status':'completed','peak_workspace_bytes':0}).seal()
    app=create_app(tmp_path/'host',data_roots=(tmp_path,));client=app.test_client();base='/api/confidenceguard/v1'
    displayed=[]
    try:
        headers={'X-CSRF-Token':client.get(base+'/session').json['data']['csrf_token']}
        for audience in ('local','shareable'):
            data=result.to_dict(audience=audience)
            uploads={'result':(io.BytesIO(json.dumps(data).encode()),'result.json')}
            if audience=='local':uploads['manifest']=(io.BytesIO(json.dumps(result.private).encode()),'manifest.json')
            # Each import owns its session and is reopened through the public route.
            session=app.test_client();headers={'X-CSRF-Token':session.get(base+'/session').json['data']['csrf_token']}
            loaded=session.post(base+'/results/import',headers=headers,data=uploads)
            assert loaded.status_code==201,loaded.json
            shown=session.get(base+'/results/'+loaded.json['data']['result_id']+'/investigation/summary').json['data']
            assert shown['investigation']['assessments'][0]['state']==row['state']
            assert shown['investigation']['assessments'][0]['effect']==row['effect']
            displayed.append(shown)
            environment=Environment(loader=FileSystemLoader(root/'src/confidenceguard/templates'),autoescape=select_autoescape(['html']))
            html=environment.get_template('investigation_sections.html').render(result=data)
            assert 'Historical approximate assessment' in html and 'does not establish a new formal confirmation' in html
        assert row==before
        fixture=tmp_path/'reopening.json';fixture.write_text(json.dumps(displayed))
        node=os.environ.get('NUMEK_TEST_NODE') or shutil.which('node')
        if not node:pytest.skip('Node required for actual browser renderer check; API and canonical assertions passed.')
        process=subprocess.run([node,str(root/'tests/cg4/browser_numeric_controls.cjs'),str(root/'src/confidenceguard/static/investigation-client.js'),str(fixture)],capture_output=True,text=True,timeout=20,check=True)
        assert 'Historical approximation local/shareable rendering passed' in process.stdout
    finally:app.extensions['confidenceguard_store'].cleanup()


@pytest.mark.parametrize('cutoff,content,retain_cutoff,retain_view,expected',[
    ('2026-01-01T00:00:00Z','2026-01-01T12:00:00Z',True,True,False),
    ('2026-01-03T00:00:00Z','2026-01-02T12:00:00Z',True,True,True),
    ('2026-01-03T00:00:00Z','2026-01-01T12:00:00Z',False,True,False),
    ('2026-01-03T00:00:00Z','2026-01-01T12:00:00Z',True,False,False),
])
def test_retained_encoded_content_uses_declared_cutoff_without_loading_a_model(tmp_path,cutoff,content,retain_cutoff,retain_view,expected):
    from confidenceguard import DiscoveryRepresentationSpec
    from confidenceguard.history_storage import EvidenceWriter
    from confidenceguard.investigation_history import envelope
    from confidenceguard.history_contracts import instant
    ws,_,history=retained_input(tmp_path,cutoff=cutoff,content=content,retain_features=retain_view)
    predictions=list(ws.catalog.iter_facts('prediction'));variant=history.objectives[0].run
    # Synthetic retained encoder outputs isolate the historical availability path;
    # this is not an encoder inference or publisher-authentication qualification.
    with ws.catalog.operation():
        operation,_=ws.catalog.begin('retained-encoder-fixture','same')
        writer=EvidenceWriter(ws.path/'staging'/operation,ws.catalog.config,operation)
        locations=writer.add_vectors(np.ones((1,384),dtype='<f4'))
        records=[]
        for fact in predictions:
            owner=digest([fact['key'],fact['revision']])
            payload={'namespace':history.roles.namespace,'representation':'encoded','owner':'prediction_revision',
                'owner_key':owner,'opportunity_key':fact['payload']['opportunity_key'],'variant':variant,
                'values':{},'state':'observed','reason':'','dimensions':384,'vector_digest':locations[0]['vector_digest'],
                'spec':{'kind':'e5_text','field':'context.x','model_digest':None},
                'content_available':[str(instant(content)),'valid'],'content_availability_declaration':'dated'}
            if retain_cutoff:payload['content_information_cutoff']={'policy':FEATURE_TIME_POLICY,
                'clock':history.features[0].information_cutoff.to_dict(),'tick_ns':str(instant(cutoff)),'state':'valid'}
            records.append(envelope('representation',[history.roles.namespace,'encoded',owner],payload))
        writer.add_features(records,());writer.finish({'capture_stages':['synthetic_retained_encoder_output']})
        ws.catalog.commit_capture(operation)
    selection=replace(history,representations=(DiscoveryRepresentationSpec('encoded',kind='retained',dimensions=384),))
    s,c,roots=arguments(selection,None,None)
    with prepared(s,c,roots) as p:
        assert p.representations['encoded']['available'].tolist()==[expected]*len(p.records)
