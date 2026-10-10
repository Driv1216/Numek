"""Binary-indicator evidence; unknown assignments are never negative labels."""
from collections import Counter
from itertools import combinations

import numpy as np
import pandas as pd

from datatrust.annotations import observation, normalize_target
from datatrust.contracts import MultilabelOptions, AnnotationOptions


def validate_options(targets, options):
    options = options or MultilabelOptions(); k = len(targets)
    references = {c for g in options.mutually_exclusive + options.requires for c in g}
    if references - set(targets):
        raise ValueError('Label constraints must reference declared labels only.')
    if any(v is not None and v > k for v in (options.minimum_positive,options.maximum_positive)):
        raise ValueError('Positive-count bounds exceed the number of labels.')
    # A conservative upper bound from each declared exclusive group.
    if options.minimum_positive is not None and any(options.minimum_positive > k - len(g) + 1 for g in options.mutually_exclusive):
        raise ValueError('Positive-count requirement contradicts an exclusive group.')
    if options.minimum_positive:
        groups=[set(g) for g in options.mutually_exclusive]
        requirements={t:set() for t in targets}
        for a,b in options.requires: requirements[a].add(b)
        stack=[(set(),set())];visited=0;feasible=False
        while stack:
            positive,negative=stack.pop();visited+=1
            if visited>100000:
                raise ValueError('Label-constraint feasibility exceeds the bounded validation work; simplify the declarations.')
            changed=True;bad=False
            while changed and not bad:
                changed=False
                for t in tuple(positive):
                    before=len(positive);positive |= requirements[t];changed |= len(positive)>before
                for group in groups:
                    present=positive & group
                    if len(present)>1:bad=True;break
                    if present:
                        before=len(negative);negative |= group-present;changed |= len(negative)>before
                if positive & negative:bad=True
            if bad or (options.maximum_positive is not None and len(positive)>options.maximum_positive):continue
            unknown=set(targets)-positive-negative
            if len(positive)+len(unknown)<options.minimum_positive:continue
            if len(positive)>=options.minimum_positive:feasible=True;break
            if unknown:
                t=next(t for t in targets if t in unknown)
                stack.append((positive.copy(),negative|{t}))
                stack.append((positive|{t},negative.copy()))
        if not feasible:raise ValueError('Contradictory label constraints: no complete binary vector satisfies the declarations.')
    return options


def repeated_inputs(data, features, targets, kind, limits, *, annotations=None):
    if not features:
        return {'status':'not_applicable','reason':'No selected input features.'}
    ids = data.groupby(features, dropna=False, sort=False).ngroup()
    sizes = ids.value_counts(sort=False); repeated = set(sizes[sizes > 1].index)
    details = []; union = np.zeros(len(data),bool)
    metadata_groups=set(); annotations=annotations or AnnotationOptions()
    for target in targets:
        obs = observation(data[target],kind)
        values = pd.Series(obs['values'] if kind == 'multilabel_classification' else data[target],index=data.index)
        grouped = values[obs['valid']].groupby(ids[obs['valid']],sort=False)
        unique = grouped.nunique(); disagreements = [i for i in unique.index if i in repeated and unique[i] > 1]
        mask = ids.isin(disagreements).to_numpy(); union |= mask
        state=normalize_target(data,target,kind,annotations.per_target.get(target,annotations.default))
        expectation_groups=pd.Series(state['expectation'],index=data.index).groupby(ids,sort=False).nunique()
        status_groups=pd.Series(state['status'],index=data.index).groupby(ids,sort=False).nunique()
        mixed_expectation={i for i in expectation_groups.index if i in repeated and expectation_groups[i]>1}
        mixed_status={i for i in status_groups.index if i in repeated and status_groups[i]>1}
        metadata_groups |= mixed_expectation | mixed_status
        details.append({'mixed_expectation_group_count':len(mixed_expectation),'mixed_status_group_count':len(mixed_status),'target':target,'varying_group_count':len(disagreements),'participating_rows':int(mask.sum()),
                        'row_ordinals':(np.flatnonzero(mask)[:limits.max_examples]+1).tolist()})
    return {'status':'completed','repeated_group_count':len(repeated),'participating_rows':int(sizes.loc[list(repeated)].sum()) if repeated else 0,
            'largest_group':int(sizes.max()) if len(sizes) else 0,'distinct_input_vectors':len(sizes),
            'varying_row_union':int(union.sum()),'mixed_metadata_group_union':len(metadata_groups),'targets':details,
            'interpretation':'Observed disagreements do not establish incorrect labels; complementary partial annotations are compatible. Metadata differences are separate evidence.'}


def multilabel_evidence(data, targets, options, limits, checkpoint):
    options = validate_options(targets, options); k = len(targets); n = len(data)
    positives = np.zeros(n,np.int32); known = positives.copy(); invalid = np.zeros(n,bool)
    labels = []
    for t in targets:
        obs = observation(data[t], 'multilabel_classification'); values = obs['values']
        positives += values == 1; known += obs['valid']; invalid |= obs['invalid']
        labels.append({'target':t,'positive':int((values==1).sum()),'negative':int((values==0).sum()),'observed':int(obs['valid'].sum()),
                       'absent':int(obs['absent'].sum()),'invalid':int(obs['invalid'].sum()),
                       'positive_share_known':int((values==1).sum())/int(obs['valid'].sum()) if obs['valid'].any() else None})
    complete = known == k
    hist = lambda values: {str(v):int(c) for v,c in sorted(Counter(values.tolist()).items())}
    partial = (known > 0) & ~complete & ~invalid
    bounds = Counter(zip(positives[partial].tolist(), (positives+k-known)[partial].tolist()))
    # Retained pattern counts are a source prefix if enumeration reaches its cap.
    patterns = Counter(); processed = 0; stopped = None
    if complete.any():
        # Iterate existing column arrays without a copied dense label matrix or
        # per-cell iloc lookups. The retained counter alone is pattern-bounded.
        rows=zip(*(iter(data[t].array) for t in targets))
        for index,raw_vector in enumerate(rows):
            if index % 512 == 0: checkpoint('multilabel combinations')
            if not complete[index]:continue
            vector=tuple(int(value) for value in raw_vector)
            if vector not in patterns and len(patterns)>=limits.max_patterns:
                stopped='planned_pattern_limit';break
            patterns[vector]+=1;processed+=1
    pairs=[]; used=0; excluded=[]; pool=targets[:limits.max_multilabel_pair_targets]
    for a,b in combinations(pool,2):
        checkpoint('multilabel pair')
        if used+n > limits.max_multilabel_comparisons:
            excluded.append({'targets':[a,b],'reason':'planned_work_limit'});continue
        used+=n
        aa=observation(data[a],'multilabel_classification')['values'];bb=observation(data[b],'multilabel_classification')['values']
        mask=(aa>=0)&(bb>=0); x,y=aa[mask],bb[mask]
        n00=int(((x==0)&(y==0)).sum());n01=int(((x==0)&(y==1)).sum());n10=int(((x==1)&(y==0)).sum());n11=int(((x==1)&(y==1)).sum());m=int(mask.sum())
        pairs.append({'targets':[a,b],'jointly_observed':m,'coverage':m/n if n else None,'n00':n00,'n01':n01,'n10':n10,'n11':n11,
                      'positive_cooccurrence_share':n11/m if m else None,'b_positive_given_a_positive':n11/(n10+n11) if n10+n11 else None,
                      'a_positive_given_b_positive':n11/(n01+n11) if n01+n11 else None,'jaccard':n11/(n01+n10+n11) if n01+n10+n11 else None,
                      'unavailable_reasons':{'positive_cooccurrence_share':None if m else 'no_jointly_observed_assignments','b_positive_given_a_positive':None if n10+n11 else 'no_observed_first_label_positives','a_positive_given_b_positive':None if n01+n11 else 'no_observed_second_label_positives','jaccard':None if n01+n10+n11 else 'no_observed_positive_union'},
                      'unavailable_reason':'no_jointly_observed_assignments' if not m else 'no_observed_positive_union' if not n01+n10+n11 else None})
    constraints=[]; violation_union=np.zeros(n,bool)
    definitions=[]
    if options.minimum_positive is not None: definitions.append(('minimum_positive',options.minimum_positive,positives+k-known < options.minimum_positive, positives>=options.minimum_positive))
    if options.maximum_positive is not None: definitions.append(('maximum_positive',options.maximum_positive,positives>options.maximum_positive,positives+k-known<=options.maximum_positive))
    for group in options.mutually_exclusive:
        p=np.zeros(n,np.int32);u=p.copy()
        for t in group:
            v=observation(data[t],'multilabel_classification')['values'];p+=v==1;u+=v<0
        definitions.append(('mutually_exclusive',list(group),p>1,p+u<=1))
    for a,b in options.requires:
        av=observation(data[a],'multilabel_classification')['values'];bv=observation(data[b],'multilabel_classification')['values']
        definitions.append(('requires',[a,b],(av==1)&(bv==0),(av==0)|(bv==1)))
    for name,declaration,bad,good in definitions:
        # Invalid assignments remain unknown in constraint reasoning. Other
        # recorded assignments can still prove a violation or satisfaction.
        violation_union |= bad
        constraints.append({'rule':name,'declaration':declaration,'violated':int(bad.sum()),'satisfied':int(good.sum()),
                            'inconclusive':int((~(bad|good)).sum()),'denominator':n,
                            'row_ordinals':(np.flatnonzero(bad)[:limits.max_examples]+1).tolist()})
    return {'labels':labels,'complete_vector_count':int(complete.sum()),'partial_vector_count':int(((known>0)&~complete).sum()),'empty_vector_count':int((known==0).sum()),
            'cardinality_distribution':hist(positives[complete]),'cardinality':float(positives[complete].mean()) if complete.any() else None,
            'density':float(positives[complete].mean())/k if complete.any() else None,'cardinality_denominator':int(complete.sum()),
            'unavailable_reasons':{'cardinality':None if complete.any() else 'no_complete_valid_observed_vectors','density':None if complete.any() else 'no_complete_valid_observed_vectors','observed_positive_fraction_known_cells':None if known.sum() else 'no_known_assignments'},
            'observed_positive_fraction_known_cells':int(positives.sum())/int(known.sum()) if known.sum() else None,
            'observed_cells':int(known.sum()),'observed_positives':int(positives.sum()),
            'partial_positive_count_bounds':[{'lower':a,'upper':b,'count':c} for (a,b),c in sorted(bounds.items())],
            'bound_excluded_invalid_vectors':int(invalid.sum()),
            'combinations':{'records':[{'vector':list(v),'count':c} for v,c in patterns.items()],'processed_complete_vectors':processed,
                            'eligible_complete_vectors':int(complete.sum()),'status':'bounded' if stopped else 'completed','stop_reason':stopped,
                            'scope':'source prefix of complete vectors' if stopped else 'all complete valid observed vectors'},
            'pairs':pairs,'pair_search':{'selected_targets':pool,'excluded_targets':targets[len(pool):],'excluded_pairs':excluded,'comparisons':used,
                                        'status':'bounded' if excluded or len(pool)<k else 'completed'},
            'constraints':constraints,'constraint_violation_row_union':int(violation_union.sum()),
            'constraint_invalid_vector_count':int(invalid.sum()),
            'interpretation':'Metrics describe supplied assignments. All-zero complete vectors are valid. Unusual combinations and low cardinality are not label errors.'}
