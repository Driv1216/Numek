"""Parent-owned CG6 evidence reservation through the established use ledger."""
from pathlib import Path

from ..contracts import digest
from ..result import Inspection
from ..evidence_use import (source_aliases,source_scope_aliases,session_overlap,
                           record_session,EvidenceUseLedger)
from .store import PreparedExecution
from .contracts import design_fingerprint


def identity_worker(spec,config,roots,roles,options,*,progress=None):
    prepared=PreparedExecution(spec,config,roots,progress)
    try:
        events=set();units=set();query=set();canonical_events=[];canonical_units=[]
        for e in prepared.events():
            if roles is not None and e['role'] not in roles:continue
            event=digest([spec.namespace,e['event_key']]);unit=digest([spec.namespace,e['entity_key'] or e['event_key']])
            canonical_events.append(event);canonical_units.append(unit);events.add(event);units.add(unit)
            for info in prepared.store.sources.values():
                ev,un=source_aliases(info,e['event_key'],e['entity_key']);events.update(ev);units.update(un);query.update(source_scope_aliases(info))
        prepared.verify()
        return Inspection({'fingerprint':design_fingerprint(prepared.fingerprint,options),'events':sorted(events),'units':sorted(units),'query_events':sorted(events|query),
            'canonical_events':canonical_events,'canonical_units':canonical_units}, {'status':'completed','peak_workspace_bytes':prepared.work.peak})
    finally:prepared.close()


def reserve(identity,operation,options,workspace,request_id,config):
    family=(options.get('protocol') or {}).get('content_digest')
    events=identity['events'];units=identity['units'];population=identity['fingerprint']
    overlap=session_overlap(identity['query_events'],units,family=family,population=population)
    checks={'overlap':overlap,'scope':'process_scoped','external_history_verified':False,'reasons':[]}
    ledger=None
    if workspace is not None:
        from ..workspace import ReliabilityWorkspace
        ws=ReliabilityWorkspace(workspace) if isinstance(workspace,(str,Path)) else workspace
        ledger=EvidenceUseLedger(ws)
        if ledger.status()['enabled']:
            reasons=ledger.overlap(identity['query_events'],units,family_digest=family,population_digest=population)
            checks.update(scope='workspace_and_process',overlap=overlap or bool(reasons),reasons=reasons,continuity=ledger.status())
        else:ledger=None
    protocol=options.get('protocol') or {}
    qualified=family is not None and not checks['overlap'] and protocol.get('upstream_independence')=='declared_independent' and protocol.get('external_exposure')=='declared_unexposed'
    kind='confirmation' if qualified else 'discovery_selection' if operation=='auxiliary_fit' else 'outcome_disclosure'
    metadata={'purpose':'cg6_'+operation,'identity_policy':'canonical_and_original_source_aliases_v1'}
    if ledger:
        receipt=ledger.record(kind,events=events,units=units,query_events=identity['query_events'],population_digest=population,
            family_digest=family,request_id=request_id,study_id=family,alpha=1-protocol['confidence'] if qualified else None,
            total_alpha=1-protocol['confidence'] if qualified else None,metadata=metadata,session_max_bytes=config.max_rss_bytes//8)
    else:
        record_session(kind,events,units,family=family,population=population,metadata=metadata,max_bytes=config.max_rss_bytes//8)
        receipt={'kind':kind,'scope':'process_scoped','population_digest':population,'family_digest':family}
    return receipt,checks
