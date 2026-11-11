"""Frozen geometric fallback and original, explicitly unqualified landmark search."""
import heapq
import json
from itertools import combinations
import numpy as np
from .investigation_contracts import LANDMARK_PROMOTION_EVIDENCE
from .contracts import EvaluationError,digest
from .discovery_rules import heads
from .investigation_membership import seal,transform_vectors,distances,distance_block_rows


def components(selected,adjacency):
    remaining=set(map(int,selected));out=[]
    while remaining:
        seed=min(remaining);remaining.remove(seed);found=[seed];todo=[seed]
        while todo:
            node=todo.pop()
            for other in sorted(set(adjacency[node])&remaining):remaining.remove(other);found.append(other);todo.append(other)
        out.append(sorted(found))
    return out


def graph_neighbors(squared_distances,count):
    ordered=np.argsort(squared_distances,axis=1,kind='stable')
    return [row[row!=i][:min(count,len(row)-1)] for i,row in enumerate(ordered)]


def propose(representation,eligible,loss,objective,limits,*,strategy='geometric',check=lambda *args:None,models=None,memory_budget=2*1024**3):
    raw=np.asarray(representation['vectors']);good=np.array(representation['available'],bool)&np.isfinite(raw).all(axis=1)
    ids=np.flatnonzero(good)
    if len(ids)>limits.geometric_rows:ids=ids[np.linspace(0,len(ids)-1,limits.geometric_rows,dtype=int)]
    if len(ids)<limits.minimum_discovery_support:return [],{'strategy':strategy,'reason':'insufficient_represented_D_support','execution':'not_run'}
    if len(ids)*raw.shape[1]*8*4>memory_budget:raise EvaluationError('Normalized geometry exceeds its working-memory share.','geometry_transform_memory_admission')
    normalization=representation.get('normalization','none');transforms=[{'normalization':normalization,'mean':None,'components':None}]
    normalized=transform_vectors(raw[ids],transforms[0]);finite=np.isfinite(normalized).all(axis=1);ids=ids[finite];normalized=normalized[finite]
    if len(ids)<limits.minimum_discovery_support:return [],{'strategy':strategy,'reason':'invalid_normalized_D_geometry','execution':'not_run'}
    if normalized.shape[1]>limits.pca_dimensions:
        from scipy.linalg import svd
        sample=normalized[:4096]
        size=sample.shape[0]*sample.shape[1]*8
        if size*6>memory_budget:raise EvaluationError('PCA working-memory admission exceeded.','geometry_pca_memory_admission')
        mean=sample.mean(axis=0)
        if not np.isfinite(mean).all() or not np.isfinite(sample-mean).all():raise EvaluationError('PCA coordinates exceed the finite numerical range.','geometry_numeric_range')
        _,_,vt=svd(sample-mean,full_matrices=False,check_finite=False,lapack_driver='gesdd')
        vectors=vt[:min(limits.pca_dimensions,len(vt))]
        for row in vectors:
            if row[np.argmax(np.abs(row))]<0:row*=-1
        transforms.append({'normalization':normalization,'mean':mean.tolist(),'components':vectors.tolist()})
    candidates=[];work=0;excluded_spaces=[]
    for transform in transforms:
        z=transform_vectors(raw[ids],transform);count=min(limits.landmarks,len(z));estimate=(len(z)*count+count*count)*z.shape[1]
        if work+estimate>limits.max_distance_operations:
            if len(transforms)>1 and transform['mean'] is None:
                excluded_spaces.append({'geometry':'original','reason':'distance_coordinate_budget','estimated_operations':estimate});continue
            raise EvaluationError('Geometric distance admission exceeded.','distance_work_limit')
        matrices=(3*len(z)*count+6*count*count)*8
        if matrices>=memory_budget:raise EvaluationError('Geometry matrices exceed working-memory admission.','geometry_memory_admission')
        block=distance_block_rows(count,z.shape[1],memory_budget-matrices)
        local_eligible=eligible[ids];local_loss=loss[ids]
        # Cover plus loss seeds; no claim of optimal landmark selection.
        cover=np.linspace(0,len(z)-1,max(1,count//2),dtype=int).tolist()
        risk=np.where(local_eligible,np.abs(local_loss),-np.inf)
        risk_order=np.argsort(-risk,kind='stable')
        chosen=list(dict.fromkeys(cover+[int(i) for i in risk_order]))[:count]
        # Geometric centroids can represent a center in an empty interior (for
        # example an annular failure), which sampled observation centers miss.
        centroids=[z.mean(axis=0)]
        for _,target in heads(objective,local_loss):
            baseline=float(np.mean(target[local_eligible])) if np.any(local_eligible) else 0.
            weight=np.where(local_eligible,np.maximum(target-baseline,0),0.)
            maximum=float(np.max(weight)) if len(weight) else 0.
            if maximum>0:
                weight=weight/maximum;centroids.append(np.average(z,axis=0,weights=weight))
        centroids=centroids[:max(1,min(len(centroids),count//4 or 1))]
        centers=np.concatenate((np.array(centroids),z[chosen[:count-len(centroids)]]))
        if not np.isfinite(centers).all():raise EvaluationError('Geometric centers exceed the finite numerical range.','geometry_numeric_range')
        d2=np.empty((len(z),count),dtype=float)
        for start in range(0,len(z),block):
            d2[start:start+block]=distances(z[start:start+block],centers);check('D geometric distances')
        if not np.isfinite(d2).all():raise EvaluationError('D distances exceed the finite numerical range.','geometry_numeric_range')
        work+=estimate;nearest=np.min(d2,axis=1)
        support=max(float(np.sqrt(np.quantile(nearest,.995,method='linear')))*1.5,float(np.finfo(float).eps))
        nn=min(limits.neighbors,count)
        cd=np.empty((count,count),dtype=float)
        for start in range(0,count,block):cd[start:start+block]=distances(centers[start:start+block],centers);check('landmark graph distances')
        order=graph_neighbors(cd,nn)
        adjacency=[set(map(int,neighbors)) for neighbors in order]
        for i,neighbors in enumerate(order):
            for j in neighbors:adjacency[int(j)].add(i)
        positive=cd[cd>0];bandwidth=float(np.sqrt(np.median(positive))) if len(positive) else 1.
        base={'transform':transform,'centers':centers.tolist(),'radii':[support]*count,'inner':[0.]*count,
              'components':[],'threshold':.5,'neighbors':nn,'bandwidth':max(bandwidth,1e-12),'support_radius':support}
        heap=[];serial=0
        for head,target in heads(objective,local_loss):
            baseline=float(np.mean(target[local_eligible])) if np.any(local_eligible) else 0.
            def retain(mask,params):
                nonlocal serial
                mask=mask&local_eligible;n=int(mask.sum())
                if n<limits.minimum_discovery_support:return
                utility=(float(np.mean(target[mask]))-baseline)*np.sqrt(n)
                if utility<=0:return
                serial+=1;item=(utility,serial,params,head,n)
                if len(heap)<limits.candidates_per_strategy:heapq.heappush(heap,item)
                elif item[:2]>heap[0][:2]:heapq.heapreplace(heap,item)
            if strategy=='geometric':
                radii=np.sqrt(np.quantile(d2,[.025,.05,.075,.1,.15,.2,.25,.3,.35,.4,.5,.6,.8],axis=0,method='linear'))
                singles=[]
                for j in range(count):
                    for q,radius in enumerate(radii[:,j]):
                        params={**base,'radii':list(base['radii']),'inner':list(base['inner']),'components':[j]};params['radii'][j]=float(radius)
                        mask=d2[:,j]<=radius**2;retain(mask,params)
                        if q:
                            annulus={**params,'inner':list(params['inner'])};annulus['inner'][j]=float(radii[q-1,j]);retain(mask&(d2[:,j]>=radii[q-1,j]**2),annulus)
                # Bounded unions retain disconnected nonlinear failure regions.
                best=[entry for entry in sorted(heap,reverse=True) if entry[3]==head][:8]
                for size in (2,3):
                    for pieces in combinations(best,size):
                        members=[j for src in pieces for j in src[2]['components']]
                        if len(set(members))!=len(members):continue
                        params={**base,'radii':list(base['radii']),'inner':list(base['inner']),'components':sorted(members)}
                        for _,_,src,_,_ in pieces:
                            for j in src['components']:params['radii'][j]=src['radii'][j];params['inner'][j]=src['inner'][j]
                        mask=np.zeros(len(z),bool)
                        for j in params['components']:mask|=(d2[:,j]<=params['radii'][j]**2)&(d2[:,j]>=params['inner'][j]**2)
                        retain(mask,params)
            else:
                owner=np.argmin(d2,axis=1);den=np.bincount(owner,weights=local_eligible,minlength=count)
                num=np.bincount(owner,weights=np.where(local_eligible,target,0),minlength=count)
                weights=np.zeros((count,count),dtype=float)
                for j,neighbors in enumerate(adjacency):
                    for other in neighbors:weights[j,other]=np.exp(-cd[j,other]/(2*base['bandwidth']**2))
                    weights[j,j]=1
                transition=weights/weights.sum(axis=1)[:,None];a=num.copy();b=den.copy()
                near=np.argsort(d2,axis=1,kind='stable')[:,:nn];selected_dist=np.take_along_axis(d2,near,axis=1)
                kernel=np.exp(-(selected_dist-selected_dist[:,0,None])/(2*base['bandwidth']**2))
                for t in range(9):
                    if t in {0,1,3,8}:
                        risk=np.divide(a,b,out=np.full(count,-np.inf),where=b>0);valid=risk[np.isfinite(risk)]
                        if len(valid):
                            for q in (.5,.7,.85,.95):
                                selected=np.flatnonzero(risk>=np.quantile(valid,q,method='linear'))
                                for region in components(selected,adjacency):
                                    score=(kernel*np.isin(near,region)).sum(axis=1)/kernel.sum(axis=1)
                                    for threshold in (.25,.5,.75):retain(score>=threshold,{**base,'components':region,'threshold':threshold})
                    a=transition@a;b=transition@b
        for utility,_,params,head,n in sorted(heap,reverse=True):
            if models is not None:
                document=json.dumps({'schema_version':'confidenceguard.geometry/1.0','transform':params['transform'],'centers':params['centers']},ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False)
                identity=digest(document);models[identity]=document
                params={k:v for k,v in params.items() if k not in {'transform','centers'}};params['geometry_digest']=identity
            artifact=seal(strategy,params,representation=representation['id'],objective=objective.identity,models=models)
            candidates.append({'artifact':artifact,'D_proxy_utility':float(utility),'D_conditional_support':n,'head':head,'complexity':len(params['components'])})
    candidates=sorted(candidates,key=lambda c:(-c['D_proxy_utility'],c['artifact']['artifact_digest']))[:limits.candidates_per_strategy]
    return candidates,{'strategy':strategy,'execution':'completed','D_geometry_rows':len(ids),'distance_coordinate_operations':work,
                       'PCA_fitting_rows':min(4096,len(ids)) if len(transforms)>1 else 0,
                       'distance_budget_scope':'per geometric fit, including center graph distances',
                       'proposal_version':'self_excluded_landmark_graph_v2' if strategy=='landmark' else 'geometric_fallback_v1',
                       'excluded_geometry_spaces':excluded_spaces,
                       'qualification':'original_NUMEK_failed_promotion_profile' if strategy=='landmark' else 'requires_geometric_qualification',
                       **({'qualification_evidence':dict(LANDMARK_PROMOTION_EVIDENCE)} if strategy=='landmark' else {}),
                       'out_of_support':'membership_unavailable','approximate_neighbors':False}
