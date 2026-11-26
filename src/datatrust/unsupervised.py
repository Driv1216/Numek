"""Conditional representation/readiness evidence, without fitted models."""
from collections import Counter
import math
import numpy as np
import pandas as pd
from datatrust.numerical import finite_mask, numeric_column, target_evidence
from datatrust.contracts import TargetExpectations
from datatrust.profiler import exact_duplicate_evidence


# Readiness v2 (Stage 6C, J3): prerequisite evidence, never a readiness verdict. Thresholds are justified in the plan:
# coverage 80% matches the dependency searches' coverage gate (min_coverage 0.8), 50% the column-missingness High boundary;
# |r| >= 0.98 is the existing M4 dependency gate (m4_diagnostics); n >= 100 and 10 distinct values guard tiny or coded columns.
COVERAGE_LOW, COVERAGE_MODERATE = 0.8, 0.5
REDUNDANCY = {'abs_pearson': 0.98, 'minimum_overlap': 100, 'minimum_distinct': 10}


def complete_case_coverage(rows, complete_rows, quantitative_count):
    if not quantitative_count or not rows:
        return {'status': 'not_assessable', 'reason': 'no_quantitative_features' if not quantitative_count else 'no_rows'}
    share = complete_rows / rows
    return {'status': 'completed', 'rows': rows, 'complete_rows': complete_rows, 'share': share, 'quantitative_feature_count': quantitative_count,
            'review': 'moderate' if share < COVERAGE_MODERATE else 'low' if share < COVERAGE_LOW else None,
            'thresholds': {'low_below': COVERAGE_LOW, 'moderate_below': COVERAGE_MODERATE},
            'interpretation': 'Distance-based methods need every selected feature; rows with a missing or non-finite value must be dropped or imputed, which changes the population analysed.'}


def redundant_features(data, quantitative, checkpoint, limits=None):
    """Exact duplicates and near-collinear pairs among quantitative-geometry features, within the DependencyLimits bounds
    (features and row work). Declared quantitative features first, then source order."""
    from datatrust.contracts import DependencyLimits
    limits = limits or DependencyLimits()
    ordered = [r for r in quantitative if r['population'] == 'quantitative'] + [r for r in quantitative if r['population'] != 'quantitative']
    eligible = [r['feature'] for r in ordered if r['finite_count'] >= REDUNDANCY['minimum_overlap'] and r['distinct_count'] >= REDUNDANCY['minimum_distinct']]
    searched, unsearched_features = eligible[:limits.max_features], eligible[limits.max_features:]
    total_pairs = len(eligible) * (len(eligible) - 1) // 2
    values = {c: pd.to_numeric(data[c], errors='coerce').to_numpy(dtype=float) for c in searched}
    finite = {c: np.isfinite(v) for c, v in values.items()}
    pairs, work, done, stopped = [], 0, 0, None
    for i, a in enumerate(searched):
        for b in searched[i + 1:]:
            if work + len(data) > limits.max_row_work:
                stopped = 'planned_row_work_limit'
                break
            checkpoint('readiness redundancy pair')
            work += len(data); done += 1
            both = finite[a] & finite[b]
            n = int(both.sum())
            if n < REDUNDANCY['minimum_overlap']:
                continue
            x, y = values[a][both], values[b][both]
            if len(np.unique(x)) < REDUNDANCY['minimum_distinct'] or len(np.unique(y)) < REDUNDANCY['minimum_distinct']:
                continue
            if np.array_equal(finite[a], finite[b]) and np.array_equal(x, y):
                pairs.append({'features': [a, b], 'relation': 'exact_duplicate', 'overlap': n, 'pearson': 1.0})
                continue
            sx, sy = float(np.std(x)), float(np.std(y))
            if not sx or not sy:
                continue
            r = float(np.corrcoef(x, y)[0, 1])
            if math.isfinite(r) and abs(r) >= REDUNDANCY['abs_pearson']:
                pairs.append({'features': [a, b], 'relation': 'near_collinear', 'overlap': n, 'pearson': r})
        if stopped:
            break
    return {'status': 'bounded' if stopped or unsearched_features else 'completed', 'stopping_reason': stopped or ('planned_feature_limit' if unsearched_features else 'complete'),
            'eligible_features': eligible, 'searched_features': searched, 'unsearched_features': unsearched_features,
            'pairs_searched': done, 'unsearched_pairs': total_pairs - done, 'row_work': work,
            'limits': {'max_features': limits.max_features, 'max_row_work': limits.max_row_work}, 'gates': dict(REDUNDANCY),
            'pairs': pairs,
            'interpretation': 'These features carry nearly the same information. Distance-based methods will weight this dimension more than once. This may be intended.'}


def readiness_evidence(data, features, semantics, options, task, limits, checkpoint):
    n=len(data); quantitative=[]; declared=[]; assumed=[]; excluded=[]; complete=np.ones(n,bool)
    observed=np.zeros(n,np.int32); nonzero=np.zeros(n,np.int32); zero_cells=0; finite_cells=0
    binary=[]; categories=[]; touching=np.zeros(n,bool); touches=np.zeros(n,np.int32)
    all_observed=np.zeros(n,np.int32)
    for semantic in semantics:
        checkpoint('feature readiness')
        c=semantic['column'];s=data[c];all_observed+=s.notna().to_numpy()
        if semantic['quantitative_geometry']:
            mask=finite_mask(s).to_numpy();complete &= mask;observed+=mask
            z=(s==0).fillna(False).to_numpy() & mask;nonzero+=mask & ~z;zero_cells+=int(z.sum());finite_cells+=int(mask.sum())
            stats=target_evidence(s,TargetExpectations()) if mask.any() else None
            reason='no_finite_values' if not mask.any() else stats['precision_reason'] or ('fewer_than_20_finite' if mask.sum()<20 else 'zero_iqr' if stats['iqr']==0 else 'unsafe_spread' if stats['iqr'] is None else None)
            record={'feature':c,'population':semantic['semantic_type'],'finite_count':int(mask.sum()),'missing_count':int(s.isna().sum()),
                    'nonfinite_count':int((s.notna().to_numpy() & ~mask).sum()),'distinct_count':int(s[mask].nunique()),
                    'iqr':stats['iqr'] if stats else None,'central_90_span':stats['central_90_span'] if stats else None,
                    'scale_ineligible_reason':reason,'extremes':None}
            if task=='anomaly_detection' and stats and stats['extremes']:
                e=stats['extremes'];record['extremes']=e
                # Safe unrounded fences; if overflowed, derive comparisons in
                # normalized coordinates instead of inventing finite fences.
                finite=s[mask].to_numpy(dtype=float);scale=float(np.abs(finite).max()) or 1.;v=finite/scale
                q1,q3=np.quantile(v,[.25,.75]);iqr=q3-q1;bad=(v<q1-1.5*iqr)|(v>q3+1.5*iqr)
                rowmask=np.zeros(n,bool);rowmask[np.flatnonzero(mask)[bad]]=True;touching|=rowmask;touches+=rowmask
                counts=Counter(s[rowmask].tolist())
                record['extreme_candidate_value_multiplicities']=[{'value':v,'count':count} for v,count in counts.items()]
            quantitative.append(record)
            (declared if semantic['semantic_type']=='quantitative' else assumed).append(record)
        else:
            excluded.append({'feature':c,'reason':semantic['semantic_type']})
            counts=s.value_counts();categories.append({'feature':c,'observed_count':int(s.notna().sum()),'category_count':len(counts),
                                                      'singleton_category_count':int((counts==1).sum()),'rows_in_categories_with_fewer_than_five':int(counts[counts<5].sum()),
                                                      'rare_category_examples':[{'value':v,'count':int(count)} for v,count in counts[counts<5].head(limits.max_examples).items()],
                                                      'interpretation':'Low frequency describes observed categories, not anomaly correctness.'})
        if pd.api.types.is_bool_dtype(s) or (numeric_column(s) and s.dropna().isin([0,1]).all() and s.notna().any()):
            binary.append({'feature':c,'zero_count':int((s==0).sum()),'one_count':int((s==1).sum()),'observed_count':int(s.notna().sum()),'missing_count':int(s.isna().sum())})
    ratios=[]
    for name,population in [('declared_quantitative',declared),('assumed_quantitative',assumed)]:
        eligible=[r for r in population if not r['scale_ineligible_reason']]
        ratio=None;reason='fewer_than_two_eligible_features'
        if len(eligible)>=2:
            small=min(eligible,key=lambda r:r['iqr']);large=max(eligible,key=lambda r:r['iqr']);ratio=large['iqr']/small['iqr']
            reason=None if math.isfinite(ratio) else 'ratio_overflow'
            if reason: ratio=None
        ratios.append({'population':name,'eligible_features':[r['feature'] for r in eligible],'ratio':ratio,'unavailable_reason':reason,
                       'conditional_review':ratio is not None and ratio>=10 and options.scale_sensitive is not False,
                       'interpretation':'Scale ratios depend on representation and units; actual similarity distortion is not established.'})
    hist=lambda v:{str(k):int(c) for k,c in sorted(Counter(v.tolist()).items())}
    structural=exact_duplicate_evidence(data[features]) if features else None
    constants=[c for c in features if data[c].notna().any() and data[c].nunique()==1]
    return {'semantics':semantics,'quantitative_features':quantitative,'geometry_exclusions':excluded,'scale_ratios':ratios,
            'selected_feature_count':len(features),'variable_dimensions':sum(data[c].nunique()>1 for c in features),
            'constant_features':constants,'fully_missing_features':[c for c in features if data[c].isna().all()],
            'observed_feature_count_histogram':hist(all_observed),'finite_quantitative_count_histogram':hist(observed),
            'complete_finite_quantitative_rows':int(complete.sum()) if quantitative else None,'quantitative_feature_count':len(quantitative),
            'complete_quantitative_unavailable_reason':None if quantitative else 'no_eligible_quantitative_representation',
            'zero_density_known_quantitative_cells':zero_cells/finite_cells if finite_cells else None,'finite_quantitative_cells':finite_cells,
            'nonzero_quantitative_count_histogram':hist(nonzero),'complete_all_zero_quantitative_vectors':int((complete & (nonzero==0)).sum()) if quantitative else None,
            'binary_sparsity':binary,'categorical_frequency':categories,'feature_vector_repetition':structural,
            'distinct_feature_vectors':len(data[features].drop_duplicates()) if features else None,
            'marginal_extreme_candidate_rows':int(touching.sum()) if task=='anomaly_detection' else None,
            'extreme_candidate_feature_count_histogram':hist(touches) if task=='anomaly_detection' else None,
            'interpretation':('Repetition affects observation weighting; encoding, scales, and sparsity affect some similarity formulations.' if task=='clustering' else
                              'Rare values and marginal extremes may be legitimate. Preprocessing and repetition affect some detection methods; correctness is not established.'),
            'limitations':'No clustering quality, anomaly correctness, contamination, fitted geometry, or universal readiness verdict is inferred.',
            # readiness v2 (Stage 6C): prerequisite evidence
            'complete_case_coverage':complete_case_coverage(n,int(complete.sum()) if quantitative else 0,len(quantitative)),
            'redundant_quantitative_features':redundant_features(data,quantitative,checkpoint)}
