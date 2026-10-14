"""Full populations and compatible comparisons with privacy-qualified evidence."""
from collections import Counter
import hashlib
import json

from datatrust.image_annotations import normalize, compatible, absent, canonical
from datatrust.image_assets import error
from datatrust.text_normalization import get,MISSING


class Evidence:
    def __init__(self,store):
        self.store=store; self.records=[]; self.checks=[]; self.findings=[]; self.coverage={}; self.definitions={}
    def opaque(self,kind,value):
        ref=kind+'_'+hashlib.sha256((self.store.audit_id+'\0'+canonical(value)).encode()).hexdigest()[:24]
        self.definitions[ref]={'kind':kind,'value':value}
        return ref
    def add(self,family,data,*,meaning='deterministic_fact',violations=0,keys=(),scope='full_population',coverage=None,applicability='applicable'):
        refs=[self.store.witness(int(k)) for k in list(keys)[:self.store.config.limits.witnesses]]
        record={'id':f'image_e{len(self.records)+1}','family':family,'meaning':meaning,'data':data,'references':refs,'scope':scope}
        self.records.append(record); self.checks.append({'id':record['id'],'family':family,'applicability':applicability,'execution':'completed' if applicability=='applicable' else 'not_run','scope':scope,'violations':violations})
        if coverage is not None: self.coverage[family]=coverage
        if violations:
            self.findings.append({'id':record['id'],'family':family,'meaning':meaning,'count':violations,'references':refs,
                                  'action': 'Inspect verified local images and supplied declarations; similarity does not prove leakage or identify a correct annotation.' if family in {'near_duplicates','embeddings','annotation_disagreement'} else 'Resolve retained evidence, review the applicable declaration, and re-audit preserved sources.'})
        return record


def required(e,store):
    con=store.con; config=store.config
    con.execute('CREATE TABLE normalized(oid BIGINT PRIMARY KEY, payload VARCHAR, normalized_hash VARCHAR, payload_hash VARCHAR, comparable BOOLEAN)')
    decoded=Counter(); formats=Counter(); modes=Counter(); visual=Counter(); total_pixels=0; asset_count=0; eligible=0; extension_mismatches=0; dims=[]; metrics={k:[] for k in ('contrast','mean_luminance','dark_fraction','bright_fraction','entropy','sharpness')}; exclusions=Counter()
    cursor=con.cursor().execute('SELECT path,payload FROM assets ORDER BY path')
    for batch in iter(lambda:cursor.fetchmany(128),[]):
        for path,raw in batch:
            a=json.loads(raw); asset_count+=1; decoded[a['decode']]+=1; formats[a.get('format','unknown')]+=1; modes[a.get('mode','unknown')]+=1
            extension_mismatches+=a.get('extension_mismatch',False)
            total_pixels+=a.get('pixels',0); eligible+=bool(a.get('visual_eligible')); exclusions[a.get('visual_exclusion',a['decode'])]+=not a.get('visual_eligible',False)
            if 'width' in a: dims.append((a['width'],a['height']))
            for k in metrics:
                if a.get(k) is not None: metrics[k].append(a[k])
        store.work.check('image structural populations')
    if total_pixels>config.limits.decoded_pixels: error('decoded_pixel_work_limit')
    populations=[{'source':store.sources[sid],'role':next(x.role for x in store.spec.inputs if x.id==sid),'occurrences':n} for sid,n in con.execute('SELECT sid,count(*) FROM occurrences GROUP BY sid ORDER BY sid').fetchall()]
    physical=len({tuple(v['signature'][:2]) for p,v in store.files.items() if any(p in s for s in store.media.values())})
    e.add('inventory',{'occurrences':store.count,'directory_entries':sum(v['entries'] for v in store.memberships.values()),'image_locations':asset_count,'physical_media_files':physical,'physical_alias_locations':len(store.media_locations())-physical,'source_populations':populations,'logical_media_bytes':sum(store.media_bytes.values()),'metadata_bytes':sum(store.metadata_bytes.values())},coverage={'required_occurrences':store.count,'inventory_complete':True})
    e.add('decode',{'asset_states':dict(decoded),'format_extension_mismatches':extension_mismatches,'encoded_formats':dict(formats),'modes':dict(modes),'decoded_pixels':total_pixels,'dimensions_observed':len(dims),'frame_policy':'single frame only'},violations=decoded['corrupt_or_truncated']+decoded['unreadable'])
    import numpy as np
    distributions={k:{'population':len(v),'minimum':min(v),'median':float(np.median(v)),'maximum':max(v)} for k,v in metrics.items() if v}
    distributions['width']={'population':len(dims),'minimum':min((w for w,h in dims),default=None),'maximum':max((w for w,h in dims),default=None)}
    distributions['height']={'population':len(dims),'minimum':min((h for w,h in dims),default=None),'maximum':max((h for w,h in dims),default=None)}
    e.add('visual_quality',{'eligible_assets':eligible,'exclusions':dict(exclusions),'metrics':distributions,'representation':'oriented opaque RGB; preview longest side 512; no arbitrary ICC conversion','quality_score':None},meaning='contextual_observation',coverage={'eligible':eligible,'examined':eligible,'ineligible':asset_count-eligible})
    extremes=[]
    for metric in ('contrast','sharpness','entropy','dark_fraction','bright_fraction'):
        for direction in ('ASC','DESC'):
            rows=con.execute(f"SELECT min(o.oid),json_extract(a.payload,'$.{metric}')::DOUBLE AS metric_value FROM assets a JOIN occurrences o ON o.path=a.path WHERE json_extract(a.payload,'$.visual_eligible')::BOOLEAN AND json_extract(a.payload,'$.{metric}') IS NOT NULL GROUP BY a.path,a.payload ORDER BY metric_value {direction},a.path LIMIT ?",[config.limits.witnesses]).fetchall()
            extremes.append({'metric':metric,'end':'lowest' if direction=='ASC' else 'highest','examples':[{'reference':store.witness(oid),'value':value} for oid,value in rows]})
    e.add('visual_extremes',{'examples':extremes,'interpretation':'Contextual extremes in eligible preview representations, not proof of unusability.'},meaning='contextual_observation',scope='bounded',coverage={'eligible':eligible,'maximum_examples_per_metric_end':config.limits.witnesses})
    ann_states=Counter(); validity=Counter(); reasons=Counter(); blocked_checks=Counter(); status=Counter(); labels=Counter(); cardinality=Counter(); splits=Counter(); occurrence_labels=Counter(); boxareas=[]; crowd=0; mask_pixels=0; empty_masks=0; invalid_oids=[]; quality_oids=[]; refs_bad=[]; visited=0
    location_stats={k:{'population':0,'minimum':None,'maximum':None,'sum':0.0} for k in ('center_x_fraction','center_y_fraction','width_fraction','height_fraction','mask_foreground_fraction')}
    def observe(key,value):
        v=location_stats[key]; v['population']+=1; v['minimum']=value if v['minimum'] is None else min(v['minimum'],value); v['maximum']=value if v['maximum'] is None else max(v['maximum'],value); v['sum']+=value
    items={x.id:x for x in store.spec.inputs}
    cursor=con.cursor().execute('SELECT o.oid,o.sid,o.split,o.logical,o.payload,a.payload FROM occurrences o LEFT JOIN assets a ON o.path=a.path ORDER BY oid')
    for batch in iter(lambda:cursor.fetchmany(128),[]):
        for oid,sid,split,logical,raw,asset_raw in batch:
            item=items[sid]; payload=json.loads(raw); asset=json.loads(asset_raw) if asset_raw else {}
            if payload['reasons']: refs_bad.append(oid); reasons.update(payload['reasons'])
            if not absent(payload['checksum']) and payload['checksum'] is not None and payload['checksum']!=asset.get('sha256'): reasons['supplied_checksum_mismatch']+=1; refs_bad.append(oid)
            if item.annotations.associated_source:
                rows=con.execute('SELECT payload FROM associated WHERE sid=? AND logical=? LIMIT 2',[sid,logical]).fetchall()
                if len(rows)==1:
                    record=json.loads(rows[0][0])
                    for key in ('labels','objects','mask','status'):
                        value=get(record,getattr(item.mapping,key))
                        payload[key]={'__absent__':True} if value is MISSING else value
                else: reasons['associated_annotation_ambiguous_or_missing']+=1
            objects=None
            if item.source.format=='coco':
                rows=con.execute('SELECT payload FROM coco_annotations WHERE sid=? AND image_key=?',[sid,logical]).fetchall()
                if sum(len(r[0]) for r in rows)>config.execution.max_record_bytes: error('annotation_collection_limit')
                objects=[json.loads(r[0]) for r in rows]
                if item.annotations.derive_coco_labels:
                    values=list(dict.fromkeys(x.get('category_id') for x in objects))
                    payload['labels']=values if item.task.kind=='multilabel_classification' else values[0] if len(values)==1 else None
            if item.source.format=='yolo':
                from dataclasses import replace
                item=replace(item,annotations=replace(item.annotations,box_format='normalized_cxcywh'))
            normalized=normalize(store,item,oid,payload,asset,objects)
            validity[normalized['validity']]+=1; blocked_checks.update(normalized['blocked_checks'])
            visited+=1; ann_states[normalized['observation']]+=1; status[normalized['status']]+=1; reasons.update(normalized['reasons'])
            if normalized['reasons'] and len(invalid_oids)<config.limits.details: invalid_oids.append(oid)
            labels.update(canonical([sid,v]) for v in normalized['labels']); occurrence_labels.update(set(canonical([sid,v]) for v in normalized['labels'])); cardinality[len(set(map(canonical,normalized['labels'])))]+=1; splits[split]+=1
            for obj in normalized['objects']:
                if 'bbox' in obj:
                    a,b,c,d=obj['bbox']; boxareas.append((c-a)*(d-b)); crowd+=obj.get('crowd',0)
                    ow,oh=normalized['oriented_size']
                    for k,v in zip(('center_x_fraction','center_y_fraction','width_fraction','height_fraction'),((a+c)/(2*ow),(b+d)/(2*oh),(c-a)/ow,(d-b)/oh)): observe(k,v)
            for segment in normalized['segmentation']:
                pixels=segment.get('pixels') or (normalized['frame']['width']*normalized['frame']['height'] if normalized.get('frame') else 0)
                area=segment.get('area')
                if 'foreground_pixels' in segment: area=segment['foreground_pixels']
                elif 'occupancy' in segment:
                    excluded={'background',*map(str,item.annotations.background+item.annotations.ignore)}
                    area=sum(v for k,v in segment['occupancy'].items() if k not in excluded)
                if pixels and area is not None: observe('mask_foreground_fraction',area/pixels)
            mask_pixels+=sum(s.get('pixels',0) for s in normalized['segmentation']); empty_masks+=sum(s.get('empty',False) for s in normalized['segmentation'])
            con.execute('INSERT INTO annotations VALUES (?,?,?,?)',[oid,sid,normalized['annotation_ref'],json.dumps({'scheme':normalized['scheme'],'validity':normalized['validity'],'normalized_sha256':normalized['normalized_sha256']})])
            con.execute('INSERT INTO normalized VALUES (?,?,?,?,?)',[oid,json.dumps(normalized,allow_nan=False),normalized['normalized_sha256'],normalized['payload_sha256'],normalized['comparable']])
            for key,bound in config.quality_expectations.items():
                observed=asset.get({'min_width':'width','min_height':'height','min_contrast':'contrast','min_sharpness':'sharpness','max_dark_fraction':'dark_fraction','max_bright_fraction':'bright_fraction'}[key])
                if observed is not None and ((key.startswith('min_') and observed<bound) or (key.startswith('max_') and observed>bound)):
                    if len(quality_oids)<config.limits.details: quality_oids.append(oid)
                    visual[key]+=1
        store.work.check('annotation normalization')
    unresolved_coco=con.execute('SELECT count(*) FROM coco_annotations a WHERE NOT EXISTS (SELECT 1 FROM occurrences o WHERE o.sid=a.sid AND o.logical=a.image_key)').fetchone()[0]
    duplicate_ann_ids=con.execute('SELECT coalesce(sum(n-1),0) FROM (SELECT count(*) n FROM coco_annotations WHERE annotation_key IS NOT NULL GROUP BY sid,annotation_key HAVING count(*)>1)').fetchone()[0]
    reasons['unresolved_coco_image_reference']+=unresolved_coco; reasons['duplicate_annotation_id']+=duplicate_ann_ids
    e.add('annotations',{'occurrence_states':dict(ann_states),'validity':dict(validity),'blocked_geometric_checks':dict(blocked_checks),'supplied_status':dict(status),'invalidity_reasons':{k:v for k,v in reasons.items() if v},'normalized_occurrences':visited,'object_visits':store.annotation_visits,'mask_pixels':mask_pixels,'empty_masks':empty_masks,'segmentation_raster_pixels':store.segment_budget[0]},violations=sum(reasons.values()),keys=invalid_oids+refs_bad,coverage={'occurrences_examined':visited,'segmentation_raster_work':store.segment_budget[0],'segmentation_raster_limit':config.limits.segmentation_pixels,'topology_and_semantic_correctness':'not assessed'})
    if visual: e.add('quality_expectations',{'declared_violations':dict(visual)},meaning='declared_violation',violations=sum(visual.values()),keys=quality_oids)
    for value in location_stats.values():
        value['mean']=value.pop('sum')/value['population'] if value['population'] else None
    categories=[{'source':store.sources[json.loads(k)[0]],'category':e.opaque('category',{'source':store.sources[json.loads(k)[0]],'value':json.loads(k)[1]}),'annotation_instances':n,'image_occurrences':occurrence_labels[k]} for k,n in labels.most_common(config.limits.details)]
    e.add('composition',{'categories':categories,'distinct_source_categories':len(labels),'category_detail_omissions':max(0,len(labels)-len(categories)),'label_cardinality':dict(cardinality),'splits':[{'split':e.opaque('split',k),'occurrences':v} for k,v in splits.items()],'box_area':{'population':len(boxareas),'minimum':min(boxareas,default=None),'maximum':max(boxareas,default=None),'median':float(np.median(boxareas)) if boxareas else None},'crowd_objects':crowd,'object_locations_and_sizes':{k:v for k,v in location_stats.items() if k!='mask_foreground_fraction'},'mask_occupancy':location_stats['mask_foreground_fraction'],'mask_occupancy_population':'Each examined mask independently; overlapping instance areas are not a union.','category_count_policy':'Well-formed supplied members; taxonomy violations remain separately accounted.','group_populations':[{'source':store.sources[sid],'groups_declared':bool(items[sid].mapping.groups),'complete_group_occurrences':complete if items[sid].mapping.groups else None,'incomplete_group_occurrences':n-complete if items[sid].mapping.groups else None,'distinct_complete_groups':distinct if items[sid].mapping.groups else None} for sid,n,complete,distinct in con.execute("SELECT o.sid,count(*),count(*) FILTER (WHERE g.complete),count(DISTINCT CASE WHEN g.complete THEN g.value END) FROM occurrences o LEFT JOIN group_vectors g USING(oid) GROUP BY o.sid").fetchall()]},meaning='contextual_observation')
    multilabel_pairs(e,store)
    duplicates(e,store)
    versions(e,store)
    logical_bad=con.execute('SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM occurrences WHERE logical IS NOT NULL GROUP BY sid,logical HAVING count(*)>1)').fetchone()[0]
    e.add('logical_identity',{'occurrences_with_duplicate_source_keys':logical_bad},violations=logical_bad)


def duplicates(e,store):
    con=store.con; representations={'bytes':'sha256','native':'native_sha256','oriented':'oriented_sha256'}
    for representation,key in representations.items():
        query=f"SELECT json_extract_string(a.payload,'$.{key}') ident,count(*) n,min(o.oid) example,count(DISTINCT o.split) splits FROM occurrences o JOIN assets a ON o.path=a.path WHERE json_extract_string(a.payload,'$.{key}') IS NOT NULL GROUP BY ident HAVING count(*)>1"
        totals=con.execute(f'SELECT count(*),coalesce(sum(n),0),coalesce(sum(CASE WHEN splits>1 THEN n ELSE 0 END),0) FROM ({query})').fetchone()
        examples=con.execute(query+' ORDER BY n DESC,ident LIMIT ?',[store.config.limits.details]).fetchall()
        e.add('exact_duplicates_'+representation,{'groups':totals[0],'participating_occurrences':totals[1],'cross_split_occurrences':totals[2],'examples':[{'reference':store.witness(oid),'occurrences':n,'split_count':splits} for _,n,oid,splits in examples]},meaning='contextual_observation',violations=totals[2],keys=[r[2] for r in examples],coverage={'representation':representation,'eligible_occurrences':con.execute(f"SELECT count(*) FROM occurrences o JOIN assets a ON o.path=a.path WHERE json_extract_string(a.payload,'$.{key}') IS NOT NULL").fetchone()[0],'group_detail_omissions':max(0,totals[0]-len(examples))})
    # Exact oriented repetitions establish a shared displayed raster, not annotation truth.
    query="SELECT json_extract_string(a.payload,'$.oriented_sha256') ident,min(o.oid) oid,count(DISTINCT n.normalized_hash) variants FROM occurrences o JOIN assets a ON o.path=a.path JOIN normalized n USING(oid) WHERE json_extract_string(a.payload,'$.oriented_sha256') IS NOT NULL AND json_extract_string(n.payload,'$.task')<>'unlabeled' GROUP BY ident HAVING count(DISTINCT n.payload_hash)>1 OR count(DISTINCT n.normalized_hash)>1"
    disagreements=blocked=0; details=[]
    cur=con.cursor().execute(query)
    for batch in iter(lambda:cur.fetchmany(64),[]):
        for ident,oid,_ in batch:
            anns=con.execute("SELECT DISTINCT n.payload FROM occurrences o JOIN assets a ON o.path=a.path JOIN normalized n USING(oid) WHERE json_extract_string(a.payload,'$.oriented_sha256')=? LIMIT ?",[ident,store.config.limits.details+1]).fetchall()
            if len(anns)>store.config.limits.details:
                blocked+=1; reason='annotation_variant_comparison_bound'
            else:
                values=[json.loads(x[0]) for x in anns]; checks=[compatible(values[0],v) for v in values[1:]]
                reason=next((r for ok,r in checks if not ok),None)
                if reason: blocked+=1
                elif len({v['normalized_sha256'] for v in values})>1: disagreements+=1
            if len(details)<store.config.limits.details: details.append({'reference':store.witness(oid),'geometric_comparison_blocked':bool(reason),'reason':reason})
    e.add('annotation_disagreement',{'compatible_exact_raster_groups_with_differences':disagreements,'payload_difference_groups_blocked':blocked,'details':details,'correct_label_identified':False},meaning='contextual_observation',violations=disagreements,coverage={'variant_comparisons_are_bounded':True})
    split_overlaps(e,store)


def split_overlaps(e,store):
    con=store.con
    for requirement in store.spec.split_requirements:
        args=[requirement.left,requirement.left,requirement.right,requirement.right]
        scopes="WITH l AS (SELECT oid FROM occurrences WHERE sid=? OR split=?), r AS (SELECT oid FROM occurrences WHERE sid=? OR split=?)"
        left_count,right_count=con.execute(scopes+' SELECT (SELECT count(*) FROM l),(SELECT count(*) FROM r)',args).fetchone()
        asset_matches="SELECT o.oid FROM occurrences o JOIN l USING(oid) JOIN assets a ON o.path=a.path WHERE EXISTS (SELECT 1 FROM occurrences c JOIN r USING(oid) JOIN assets b ON c.path=b.path WHERE json_extract_string(a.payload,'$.sha256')=json_extract_string(b.payload,'$.sha256'))"
        overlap=con.execute(scopes+' SELECT count(*) FROM ('+asset_matches+')',args).fetchone()[0]
        # Typed values are SQL NULL only when absent/invalid. A string containing
        # "null" is a valid ID. Selectors are named keys, never positional slots.
        def population(side,other):
            return {key:(total,valid,aligned) for key,total,valid,aligned in con.execute(scopes+f" SELECT a.selector,count(*),count(*) FILTER (WHERE a.value IS NOT NULL),count(*) FILTER (WHERE a.value IS NOT NULL AND EXISTS (SELECT 1 FROM group_values b JOIN {other} USING(oid) WHERE b.value IS NOT NULL AND a.namespace=b.namespace AND a.selector=b.selector)) FROM group_values a JOIN {side} USING(oid) GROUP BY a.selector",args).fetchall()}
        left=population('l','r'); right=population('r','l')
        per_key_matches="SELECT a.oid,a.selector FROM group_values a JOIN l USING(oid) WHERE a.value IS NOT NULL AND EXISTS (SELECT 1 FROM group_values b JOIN r USING(oid) WHERE a.namespace=b.namespace AND a.selector=b.selector AND a.value=b.value)"
        composite_matches="SELECT a.oid FROM group_vectors a JOIN l USING(oid) WHERE a.complete AND EXISTS (SELECT 1 FROM group_vectors b JOIN r USING(oid) WHERE b.complete AND a.namespace=b.namespace AND a.key_set=b.key_set AND a.value=b.value)"
        matched={key:n for key,n in con.execute(scopes+' SELECT selector,count(*) FROM ('+per_key_matches+') GROUP BY selector',args).fetchall()}
        per_key=[]
        for key in sorted(set(left)|set(right)):
            lt,lv,la=left.get(key,(0,0,0)); rt,rv,ra=right.get(key,(0,0,0))
            state='blocked' if not la or not ra else 'applicable' if la==lt and ra==rt else 'partial'
            per_key.append({'key':e.opaque('group_key',key),'declared_left':lt,'declared_right':rt,'valid_left':lv,'valid_right':rv,'comparable_left':la,'comparable_right':ra,'overlap_left_occurrences':matched.get(key,0),'applicability':state})
        complete_left,complete_right=con.execute(scopes+' SELECT (SELECT count(*) FROM group_vectors JOIN l USING(oid) WHERE complete),(SELECT count(*) FROM group_vectors JOIN r USING(oid) WHERE complete)',args).fetchone()
        composite_overlap=con.execute(scopes+' SELECT count(*) FROM ('+composite_matches+')',args).fetchone()[0]
        if requirement.group_mode=='composite':
            matches=composite_matches
            comparable_left,comparable_right=con.execute(scopes+" SELECT (SELECT count(*) FROM group_vectors a JOIN l USING(oid) WHERE a.complete AND EXISTS (SELECT 1 FROM group_vectors b JOIN r USING(oid) WHERE b.complete AND a.namespace=b.namespace AND a.key_set=b.key_set)),(SELECT count(*) FROM group_vectors a JOIN r USING(oid) WHERE a.complete AND EXISTS (SELECT 1 FROM group_vectors b JOIN l USING(oid) WHERE b.complete AND a.namespace=b.namespace AND a.key_set=b.key_set))",args).fetchone()
            applicability='blocked' if not comparable_left or not comparable_right else 'applicable' if comparable_left==left_count and comparable_right==right_count else 'partial'
        else:
            matches='SELECT DISTINCT oid FROM ('+per_key_matches+')'
            applicability='blocked' if not any(x['comparable_left'] and x['comparable_right'] for x in per_key) else 'applicable' if all(x['applicability']=='applicable' and x['declared_left']==left_count and x['declared_right']==right_count for x in per_key) else 'partial'
        groups=con.execute(scopes+' SELECT count(*) FROM ('+matches+')',args).fetchone()[0]
        complete_overlap=con.execute(scopes+' SELECT count(*) FROM ('+matches+') m JOIN group_vectors g USING(oid) WHERE g.complete',args).fetchone()[0]
        keys=[]
        if overlap and requirement.asset_separation:
            keys=[x[0] for x in con.execute(scopes+' '+asset_matches+' ORDER BY o.oid LIMIT ?',args+[store.config.limits.witnesses]).fetchall()]
        elif groups and requirement.group_separation:
            keys=[x[0] for x in con.execute(scopes+' '+matches+' ORDER BY oid LIMIT ?',args+[store.config.limits.witnesses]).fetchall()]
        e.add('split_requirements',{'left':e.opaque('split',requirement.left),'right':e.opaque('split',requirement.right),'left_occurrences':left_count,'right_occurrences':right_count,'complete_group_population_left':complete_left,'complete_group_population_right':complete_right,'group_mode':requirement.group_mode,'group_separation_applicability':applicability,'group_keys':per_key,'exact_asset_overlap_occurrences':overlap,'declared_group_overlap_occurrences':groups,'complete_declared_group_overlap_occurrences':complete_overlap,'composite_group_overlap_occurrences':composite_overlap,'overlap_count_unit':'Left occurrences, counted once even when multiple keys overlap; asset and group violations are separate reasons.','asset_separation_required':requirement.asset_separation,'group_separation_required':requirement.group_separation},meaning='declared_violation' if requirement.asset_separation or requirement.group_separation else 'contextual_observation',violations=(overlap if requirement.asset_separation else 0)+(groups if requirement.group_separation else 0),keys=keys)


def versions(e,store):
    con=store.con
    for spec in store.spec.comparisons:
        counts={sid:con.execute('SELECT count(*) FROM occurrences WHERE sid=?',[sid]).fetchone()[0] for sid in (spec.reference,spec.current)}
        bad=con.execute('SELECT count(*) FROM (SELECT sid,logical,count(*) n FROM occurrences WHERE sid IN (?,?) GROUP BY sid,logical HAVING logical IS NULL OR count(*)>1)',[spec.reference,spec.current]).fetchone()[0]
        exact_overlap=con.execute("SELECT count(*) FROM occurrences r JOIN assets a ON r.path=a.path WHERE r.sid=? AND EXISTS (SELECT 1 FROM occurrences c JOIN assets b ON c.path=b.path WHERE c.sid=? AND json_extract_string(a.payload,'$.sha256')=json_extract_string(b.payload,'$.sha256'))",[spec.reference,spec.current]).fetchone()[0]
        result={'population_delta':counts[spec.current]-counts[spec.reference],'reference_exact_content_overlap_occurrences':exact_overlap,'reference':store.sources[spec.reference],'current':store.sources[spec.current],'reference_population':counts[spec.reference],'current_population':counts[spec.current]}
        if not spec.align_logical_keys or bad:
            e.add('versions',result|{'alignment':'blocked','reason':'logical_keys_absent_or_ambiguous' if bad else 'population_comparison_only'},applicability='blocked',coverage={'aligned':0}); continue
        result.update(added=con.execute('SELECT count(*) FROM occurrences c WHERE c.sid=? AND NOT EXISTS (SELECT 1 FROM occurrences r WHERE r.sid=? AND r.logical=c.logical)',[spec.current,spec.reference]).fetchone()[0],removed=con.execute('SELECT count(*) FROM occurrences r WHERE r.sid=? AND NOT EXISTS (SELECT 1 FROM occurrences c WHERE c.sid=? AND c.logical=r.logical)',[spec.reference,spec.current]).fetchone()[0])
        changes=Counter(); details=[]; aligned=0
        cur=con.cursor().execute('SELECT r.oid,c.oid,r.split,c.split,r.groups,c.groups,a.payload,b.payload,n.payload,m.payload FROM occurrences r JOIN occurrences c ON r.logical=c.logical LEFT JOIN assets a ON r.path=a.path LEFT JOIN assets b ON c.path=b.path JOIN normalized n ON n.oid=r.oid JOIN normalized m ON m.oid=c.oid WHERE r.sid=? AND c.sid=?',[spec.reference,spec.current])
        for batch in iter(lambda:cur.fetchmany(128),[]):
            for roid,coid,rs,cs,rg,cg,ar,br,nr,mr in batch:
                aligned+=1; a=json.loads(ar) if ar else {}; b=json.loads(br) if br else {}; left=json.loads(nr); right=json.loads(mr)
                changes['taxonomy_changes']+=left.get('taxonomy_identity')!=right.get('taxonomy_identity')
                changes['byte_changes']+=a.get('sha256')!=b.get('sha256'); changes['native_raster_changes']+=a.get('native_sha256')!=b.get('native_sha256'); changes['oriented_raster_changes']+=a.get('oriented_sha256')!=b.get('oriented_sha256')
                changes['split_changes']+=rs!=cs; changes['group_changes']+=rg!=cg; changes['annotation_state_changes']+=(left['observation'],left['status'])!=(right['observation'],right['status'])
                # A path-valued annotation payload can be identical while its captured
                # mask pixels differ. Both identities are comparison triggers; frame
                # and taxonomy compatibility still gate any geometric claim.
                if left['payload_sha256']!=right['payload_sha256'] or left['normalized_sha256']!=right['normalized_sha256']:
                    ok,reason=compatible(left,right,spec.category_mapping)
                    if ok:
                        if spec.category_mapping:
                            left=dict(left); left['labels']=[spec.category_mapping.get(str(x),x) for x in left['labels']]
                            left['objects']=[dict(o,category=spec.category_mapping.get(str(o.get('category')),o.get('category'))) for o in left['objects']]
                            lh=canonical({'labels':sorted(left['labels'],key=canonical),'objects':sorted([{k:v for k,v in o.items() if k not in {'annotation_ref','segmentation_source','mask_path'}} for o in left['objects']],key=canonical)})
                            rh=canonical({'labels':sorted(right['labels'],key=canonical),'objects':sorted([{k:v for k,v in o.items() if k not in {'annotation_ref','segmentation_source','mask_path'}} for o in right['objects']],key=canonical)})
                            differs=lh!=rh
                        else: differs=left['normalized_sha256']!=right['normalized_sha256']
                        changes['compatible_annotation_changes']+=differs
                    else: changes['annotation_payload_changes_blocked']+=1
                    if len(details)<store.config.limits.details: details.append({'reference':store.witness(roid),'current':store.witness(coid),'compatible':ok,'reason':reason})
            store.work.check('version comparisons')
        e.add('versions',result|{'alignment':'explicit_logical_keys','aligned':aligned,'changes':dict(changes),'details':details},meaning='contextual_observation',coverage={'aligned':aligned,'detail_omissions':max(0,aligned-len(details))})



def multilabel_pairs(e,store):
    import itertools
    con=store.con
    populations=con.execute("SELECT o.sid,count(*) FROM normalized n JOIN occurrences o USING(oid) WHERE json_extract_string(n.payload,'$.task')='multilabel_classification' AND json_extract_string(n.payload,'$.validity')='valid' GROUP BY o.sid").fetchall()
    if not populations: return
    con.execute("CREATE TABLE label_presence AS SELECT DISTINCT o.sid,n.oid,unnest(json_extract(n.payload,'$.labels')::JSON[])::VARCHAR AS category_key FROM normalized n JOIN occurrences o USING(oid) WHERE json_extract_string(n.payload,'$.task')='multilabel_classification' AND json_extract_string(n.payload,'$.validity')='valid'")
    jobs=[]; candidate_count=0
    for sid,population in populations:
        categories=con.execute('SELECT category_key,count(*) n FROM label_presence WHERE sid=? GROUP BY category_key ORDER BY n DESC,category_key LIMIT 32',[sid]).fetchall()
        pairs=list(itertools.combinations([x[0] for x in categories],2)); candidate_count+=len(pairs)
        jobs.append((sid,population,iter(pairs)))
    jobs.sort(key=lambda value:hashlib.sha256(f'{store.config.seed}:{value[0]}'.encode()).digest())
    rows=[]; work=0; active=list(jobs)
    while active and len(rows)<128:
        next_round=[]
        for sid,population,pairs in active:
            pair=next(pairs,None)
            if pair is None or work+population>20000000: continue
            left,right=pair
            overlap=con.execute('SELECT count(*) FROM label_presence a JOIN label_presence b ON a.sid=b.sid AND a.oid=b.oid WHERE a.sid=? AND a.category_key=? AND b.category_key=?',[sid,left,right]).fetchone()[0]
            source=store.sources[sid]
            rows.append({'source':source,'left':e.opaque('category',{'source':source,'value':json.loads(left)}),'right':e.opaque('category',{'source':source,'value':json.loads(right)}),'both_present':overlap,'complete_annotation_population':population})
            work+=population; next_round.append((sid,population,pairs))
            if len(rows)>=128: break
        active=next_round
    e.add('multilabel_composition',{'pairs':rows,'complete_population':sum(n for sid,n in populations),'pair_population_not_label_correctness':True},meaning='contextual_observation',scope='bounded',coverage={'selected_pairs':len(rows),'candidate_pairs_in_top32_per_source':candidate_count,'charged_population_visits':work,'work_limit':20000000,'selection':'source-scoped top32 categories, seeded round-robin pairs; namespaces are not inferred'})
