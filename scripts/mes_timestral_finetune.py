"""PC-only quantile-head adaptation with held-out normal calibration and weak faults."""
import argparse
import copy
import gc
import hashlib
import importlib.util
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
from timestral import TimestralForecaster
from timestral.scaler import denormalize_quantiles
from safetensors.torch import save_file

ROOT=Path(__file__).resolve().parents[1]
_spec=importlib.util.spec_from_file_location('timestral_comparison_utils',ROOT/'scripts/mes_timestral_comparison.py')
base=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
SEED=20261021
_HOOK_LOCK=threading.Lock()


def partition_normal(splits):
    train=list(splits['train'])
    if len(train)!=6 or len(splits['validation'])!=6:
        raise ValueError('expected six normal runs per split')
    roles={'fit':{k:splits['train'][k] for k in train[:4]},
           'selection':{k:splits['train'][k] for k in train[4:]},
           'calibration':splits['validation']}
    for rows in roles.values():
        if any(label['faults'] for run in rows.values() for _,label in run):
            raise ValueError('normal corpus has injected faults')
    sets=[set(v) for v in roles.values()]
    if any(a&b for i,a in enumerate(sets) for b in sets[i+1:]):
        raise ValueError('normal roles overlap')
    return roles


def require_disjoint(*groups):
    for i,left in enumerate(groups):
        for right in groups[i+1:]:
            if any({v[field] for v in left}&{v[field] for v in right} for field in ('run_id','seed')):
                raise ValueError('run or seed overlap')


def normalized_targets(actual,cache,use_asinh):
    signed=np.stack([actual,-actual],axis=1)
    y=(signed-cache['loc'])/cache['scale']
    return np.arcsinh(y).astype('float32') if use_asinh else y.astype('float32')


def pinball(prediction,target,levels):
    mask=torch.isfinite(target)
    if not mask.any():
        raise ValueError('no finite target')
    safe=torch.where(mask,target,torch.zeros_like(target))
    error=safe[...,None]-prediction
    q=torch.as_tensor(levels,dtype=prediction.dtype,device=prediction.device)
    loss=torch.maximum(q*error,(q-1)*error)
    return (loss*mask[...,None]).sum()/(mask.sum()*len(levels))


def capture_one(context,forecaster):
    """Cache only past-derived features; targets are not accepted here."""
    with _HOOK_LOCK:
        if not hasattr(forecaster,'_head_cache_tls'):
            tls=threading.local()
            def hook(module,args):
                destination=getattr(tls,'hidden',None)
                if destination is not None:
                    destination.append(args[0][:,0].detach().cpu().numpy().copy())
            forecaster._head_cache_tls=tls
            forecaster._head_cache_handle=forecaster.model.head.register_forward_pre_hook(hook)
    tls=forecaster._head_cache_tls
    tls.hidden=[]
    try:
        forecast=forecaster.forecast(context[None],prediction_length=1)
        hidden=np.stack(tls.hidden)
    finally:
        tls.hidden=None
    if hidden.shape[0]!=2:
        raise ValueError('expected symmetric positive and negative passes')
    if np.any(~np.isfinite(context).any(axis=-1)):
        raise ValueError('all-missing context channel')
    locations,scales,cap_scales=[],[],[]
    with torch.no_grad():
        for sign in (1,-1):
            x=torch.from_numpy((sign*context).copy())
            _,loc,scale=forecaster.model.scale(torch.nan_to_num(x),torch.isfinite(x))
            locations.append(loc[:,-forecaster.patch_size].numpy().copy())
            scales.append(scale[:,-forecaster.patch_size].numpy().copy())
            cap_scales.append(scale[:,-1].numpy().copy())
    minimum=np.nanmin(context,axis=-1)
    maximum=np.nanmax(context,axis=-1)
    return {'hidden':hidden,'loc':np.stack(locations),'scale':np.stack(scales),
        'cap_scale':np.stack(cap_scales),'minimum':np.stack([minimum,-maximum]),
        'maximum':np.stack([maximum,-minimum]),'nonnegative':np.all(np.isnan(context)|(context>=0),axis=-1),
        'reference':forecast.quantiles[0,:,0].detach().cpu().numpy().copy()}


def reconstruct(head,cache,use_asinh,cap_k):
    hidden=torch.as_tensor(cache['hidden'],dtype=torch.float32)
    n,signs,variates,width=hidden.shape
    normalized=head(hidden.reshape(-1,1,width))[:,0].reshape(n,signs,variates,-1)
    loc=torch.as_tensor(cache['loc'],dtype=torch.float32)[...,None]
    scale=torch.as_tensor(cache['scale'],dtype=torch.float32)[...,None]
    raw=denormalize_quantiles(normalized,loc,scale,use_asinh)
    if cap_k>0:
        cap=torch.as_tensor(cache['cap_scale'],dtype=torch.float32)[...,None]*cap_k
        low=torch.as_tensor(cache['minimum'],dtype=torch.float32)[...,None]-cap
        high=torch.as_tensor(cache['maximum'],dtype=torch.float32)[...,None]+cap
        raw=raw.clamp(low,high)
    result=.5*(raw[:,0]-raw[:,1].flip(-1))
    eligible=torch.as_tensor(cache['nonnegative'],dtype=torch.bool)[...,None]
    return torch.where(eligible,result.clamp_min(0),result)


def fit_head(original,train,selection,epochs=5,batch=512):
    torch.manual_seed(SEED)
    head=copy.deepcopy(original)
    head._forward_pre_hooks.clear()  # Discard this experiment's feature-capture hook.
    for p in head.parameters():p.requires_grad_(True)
    head.train()
    def tensors(cache):
        x=torch.from_numpy(cache['hidden'].reshape(-1,cache['hidden'].shape[-1]).copy())
        y=torch.from_numpy(normalized_targets(cache['actual'],cache,head.config.use_asinh).reshape(-1).copy())
        return x,y
    x,y=tensors(train);vx,vy=tensors(selection)
    levels=head.config.quantile_knots
    def evaluate():
        numerator=denominator=0
        with torch.no_grad():
            for start in range(0,len(vx),batch):
                target=vy[start:start+batch]
                count=int(torch.isfinite(target).sum())
                if not count:continue
                prediction=head(vx[start:start+batch,None])[:,0]
                numerator+=float(pinball(prediction,target,levels))*count
                denominator+=count
        if not denominator:raise ValueError('no finite selection targets')
        return numerator/denominator
    history={'original_selection_loss':evaluate(),'epochs':[],
             'trainable_parameters':sum(p.numel() for p in head.parameters())}
    optimizer=torch.optim.AdamW(head.parameters(),lr=1e-4,weight_decay=.01)
    generator=torch.Generator().manual_seed(SEED)
    best,best_state=float('inf'),None
    for epoch in range(1,epochs+1):
        indices=torch.randperm(len(x),generator=generator)
        numerator=denominator=0
        for start in range(0,len(x),batch):
            idx=indices[start:start+batch]
            target=y[idx]
            count=int(torch.isfinite(target).sum())
            if not count:continue
            optimizer.zero_grad(set_to_none=True)
            prediction=head(x[idx,None])[:,0]
            loss=pinball(prediction,target,levels)
            if not torch.isfinite(loss):raise ValueError('nonfinite training loss')
            loss.backward()
            norm=torch.nn.utils.clip_grad_norm_(head.parameters(),1.,error_if_nonfinite=True)
            optimizer.step()
            numerator+=float(loss.detach())*count;denominator+=count
        val=evaluate()
        row={'epoch':epoch,'training_loss':numerator/denominator,'selection_loss':val}
        history['epochs'].append(row)
        print(json.dumps(row),flush=True)
        if val<best:
            best=val;best_state=copy.deepcopy(head.state_dict());history['selected_epoch']=epoch
    head.load_state_dict(best_state)
    head.eval()
    return head,history


def save_checkpoint(forecaster,out):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=False)
    forecaster.config.save(out/'config.json')
    save_file({k:v.detach().cpu().contiguous() for k,v in forecaster.model.state_dict().items()},
              str(out/'model.safetensors'))


def requested_improvement(before,after):
    return (after['detected_events']>before['detected_events'] and
            after['wrong_alert_equipment_seconds']<before['wrong_alert_equipment_seconds'])


def collect(runs,channels,valid_values,forecaster,out,thin=1,head=None,keep_hidden=True):
    started=time.perf_counter()
    frames={run:[f for f,_ in rows] for run,rows in runs.items()}
    x,keys=base.causal_windows(frames,channels,valid_values)
    counts={};selected=[]
    for i,(run,_) in enumerate(keys):
        ordinal=counts.get(run,0);counts[run]=ordinal+1
        if ordinal%thin==0:selected.append(i)
    x=x[selected];keys=[keys[i] for i in selected]
    if not keys:raise ValueError('no feature windows')
    lookup={(run,f['sequence']):f for run,rows in frames.items() for f in rows}
    observed=[valid_values(lookup[k]) for k in keys]
    actual=np.array([[v.get(c,np.nan) for c in channels] for v in observed],dtype='float32')
    def work(i):
        item=capture_one(x[i],forecaster)
        packed={k:v[None] for k,v in item.items() if k!='reference'}
        with torch.no_grad():
            reconstructed=reconstruct(forecaster.model.head,packed,forecaster.config.use_asinh,
                                      forecaster.quantile_real_cap_k).numpy()[0]
            np.testing.assert_allclose(reconstructed,item['reference'],rtol=1e-5,atol=1e-5)
            item['max_reconstruction_error']=np.max(np.abs(reconstructed-item['reference']))
            if head is not None:
                item['adapted']=reconstruct(head,packed,forecaster.config.use_asinh,
                                            forecaster.quantile_real_cap_k).numpy()[0]
        if not keep_hidden:del item['hidden']
        return item
    output=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,item in enumerate(pool.map(work,range(len(keys)))):
            output.append(item)
            if i%128==0:print(f'{out.stem}: {i+1}/{len(keys)}',flush=True)
    cache={k:np.stack([v[k] for v in output]) for k in output[0]}
    cache.update(actual=actual,keys=np.array(keys,dtype=str),channels=np.array(channels),examples=x[:3])
    with out.open('xb') as target:np.savez_compressed(target,**cache)
    meta={'windows':len(keys),'seconds':time.perf_counter()-started,'sha256':base.sha(out),
          'max_official_reconstruction_error':float(np.max(cache['max_reconstruction_error']))}
    return cache,keys,meta


def state_hash(model,head):
    digest=hashlib.sha256()
    for name,value in model.state_dict().items():
        if name.startswith('head.')!=head:continue
        digest.update(name.encode());digest.update(value.detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def scores(quantiles,actual,channels,stats,levels):
    indices=[levels.index(q) for q in (.01,.5,.99)]
    q=quantiles[:,:,indices]
    values=base.channel_scores(actual,q[:,:,1],q[:,:,0],q[:,:,2],np.array([stats[c][1] for c in channels]))
    equipment=sorted({c[0] for c in channels})
    aggregated=np.stack([np.nanmax(values[:,[i for i,c in enumerate(channels) if c[0]==eq]],axis=1)
                         for eq in equipment],axis=1)
    return aggregated,equipment


def official_check(forecaster,cache,expected):
    errors=[]
    for i,x in enumerate(cache['examples']):
        actual=forecaster.forecast(x[None],prediction_length=1).quantiles[0,:,0].numpy()
        np.testing.assert_allclose(actual,expected[i],rtol=1e-5,atol=1e-5)
        errors.append(float(np.max(np.abs(actual-expected[i]))))
    return {'windows':len(errors),'max_abs_error':max(errors)}


def evaluate(args):
    started=time.perf_counter()
    runtime=args.runtime.resolve()
    runtime_hash=base.verify_runtime(runtime)
    sys.path.insert(0,str(runtime))
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.evaluate_mes_fault_models import fit_normal,predict_ewma,score,valid_values
    from scripts.mes_training_source import prefix_hashes
    from scripts.mes_location_replay import replay_validation
    from scripts.mes_ewma_release_review import paired_events
    if not Path(sys.modules['scripts.evaluate_mes_fault_models'].__file__).resolve().is_relative_to(runtime):
        raise ValueError('incorrect frozen scorer')
    manifests={name:json.loads((path/'manifest.json').read_text(encoding='utf-8'))
               for name,path in (('source',args.source),('normal',args.normal),('weak',args.weak))}
    require_disjoint(*(v['runs'] for v in manifests.values()))
    if (manifests['normal']['hazard']!=0 or manifests['weak']['response_scale']!=.2
            or any(v['generator_version']!=7 or v['profile']!='independent' for v in manifests.values())):
        raise ValueError('incorrect corpus contract')
    reference=json.loads(args.reference_calibration.read_text(encoding='utf-8'))
    if base.sha(args.model/'model.safetensors')!=reference['model']['files']['model.safetensors']:
        raise ValueError('pretrained weights differ')
    config,source=load_train_validation(args.source,profile='independent')
    specs,stats=fit_normal(source['train'],config)
    stats_hash=hashlib.sha256(json.dumps([[*c,*stats[c]] for c in sorted(stats)]).encode()).hexdigest()
    if stats_hash!=reference['training_provenance']['stats_sha256']:
        raise ValueError('original normalization differs')
    channels=[tuple(c) for c in reference['channels']]
    values=lambda frame:valid_values(frame,specs)
    del source;gc.collect()
    normal_config,normal=load_train_validation(args.normal,profile='independent')
    if normal_config.config_id!=config.config_id:raise ValueError('normal config differs')
    roles=partition_normal(normal)
    _,matched_stats=fit_normal(roles['fit'],config)
    torch.set_num_threads(1);torch.manual_seed(SEED);torch.use_deterministic_algorithms(True)
    forecaster=TimestralForecaster.from_pretrained(args.model,device='cpu',local_files_only=True)
    for parameter in forecaster.model.parameters():parameter.requires_grad_(False)
    original_state=copy.deepcopy(forecaster.model.head.state_dict())
    initial_backbone=state_hash(forecaster.model,False)
    initial_head=state_hash(forecaster.model,True)
    caches,cache_keys,feature_meta={},{},{}
    for role in ('fit','selection'):
        caches[role],cache_keys[role],feature_meta[role]=collect(roles[role],channels,values,forecaster,
            args.out_dir/f'{role}-features.npz',thin=2)
    torch.set_num_threads(4)
    tick=time.perf_counter()
    trained,history=fit_head(forecaster.model.head,caches['fit'],caches['selection'])
    history['seconds']=time.perf_counter()-tick
    base.write_new(args.out_dir/'training.json',history)
    del caches;gc.collect()
    torch.set_num_threads(1)
    calibration,cal_keys,feature_meta['calibration']=collect(roles['calibration'],channels,values,forecaster,
        args.out_dir/'calibration-features.npz',thin=2,head=trained)
    thresholds={};counts={}
    for name,field in (('pretrained','reference'),('finetuned','adapted')):
        current,equipment=scores(calibration[field],calibration['actual'],channels,stats,forecaster.quantile_levels)
        thresholds[name],counts[name]=base.calibrate(cal_keys,current,equipment,set(cal_keys))
    base.write_new(args.out_dir/'calibration.json',{'thresholds':thresholds,'counts':counts,
        'roles':{role:list(runs) for role,runs in roles.items()},'history':history,
        'runtime_sha256':runtime_hash,'normal_prefix':prefix_hashes(args.normal,manifests['normal'])})
    forecaster.model.head.load_state_dict(trained.state_dict())
    if state_hash(forecaster.model,False)!=initial_backbone:raise AssertionError('backbone changed')
    trained_hash=state_hash(forecaster.model,True)
    if trained_hash==initial_head:raise AssertionError('head weights did not change')
    checkpoint=args.out_dir/'checkpoint'
    save_checkpoint(forecaster,checkpoint)
    restored=TimestralForecaster.from_pretrained(checkpoint,device='cpu',local_files_only=True)
    checks={'calibration_checkpoint_forecast':official_check(restored,calibration,calibration['adapted'])}
    if state_hash(restored.model,False)!=initial_backbone or state_hash(restored.model,True)!=trained_hash:
        raise AssertionError('checkpoint state mismatch')
    del restored
    forecaster.model.head.load_state_dict(original_state)
    del calibration,normal,roles;gc.collect()
    # The final fault data is opened only after weight and threshold selection.
    other,splits=load_train_validation(args.weak,profile='independent')
    if other.config_id!=config.config_id:raise ValueError('weak config differs')
    runs=splits['validation'];del splits['train'];del splits
    print('fresh weak: verifying factual replay',flush=True)
    verification=replay_validation(args.weak,config,runs)['verification']
    cache,keys,feature_meta['weak']=collect(runs,channels,values,forecaster,
        args.out_dir/'weak-predictions.npz',head=trained,keep_hidden=False)
    alerts={};metrics={}
    for name,field in (('pretrained','reference'),('finetuned','adapted')):
        current,equipment=scores(cache[field],cache['actual'],channels,stats,forecaster.quantile_levels)
        alerts[name]={(run,f['sequence']):set() for run,rows in runs.items() for f,_ in rows}
        alerts[name].update(base.threshold_alerts(keys,current,equipment,thresholds[name]))
    alerts['ewma_current']=predict_ewma(runs,specs,stats,3)
    alerts['ewma_normal_refit']=predict_ewma(runs,specs,matched_stats,3)
    eligible=set(keys)
    alerts['ewma_common_warmup']={k:v if k in eligible else set() for k,v in alerts['ewma_current'].items()}
    for name,prediction in alerts.items():metrics[name]=score(runs,prediction)
    pairs={name:paired_events(runs,alerts[name],alerts['finetuned'],metrics[name],metrics['finetuned'])
           for name in ('ewma_current','ewma_normal_refit','pretrained')}
    forecaster.model.head.load_state_dict(trained.state_dict())
    restored=TimestralForecaster.from_pretrained(checkpoint,device='cpu',local_files_only=True)
    checks['weak_checkpoint_forecast']=official_check(restored,cache,cache['adapted'])
    base.verify_runtime(runtime)
    result={'experiment':'Timestral-28M head-only fine-tuning','model_revision':reference['model']['revision'],
        'code_revision':base.CODE_REVISION,'model_parameters':sum(p.numel() for p in forecaster.model.parameters()),
        'training':history,'feature_meta':feature_meta,'thresholds':thresholds,'calibration_counts':counts,
        'metrics':metrics,'paired_events':pairs,
        'requested_improvement_vs':{name:requested_improvement(metrics[name],metrics['finetuned'])
            for name in ('ewma_current','ewma_normal_refit','pretrained')},
        'aggregate_failures_vs':{name:base.aggregate_failures(metrics[name],metrics['finetuned'])
            for name in ('ewma_current','ewma_normal_refit','pretrained')},
        'background':{name:base.background(runs,prediction) for name,prediction in alerts.items()},
        'alerts':{name:[[r,s,sorted(v)] for (r,s),v in prediction.items()] for name,prediction in alerts.items()},
        'checks':checks,'replay_verification':verification,'test_rows_read':0,
        'prefix_sha256':{name:prefix_hashes(path,manifests[name]) for name,path in
            (('source',args.source),('normal',args.normal),('weak',args.weak))},
        'runtime_sha256':runtime_hash,'backbone_sha256_before_after':initial_backbone,
        'head_sha256_before':initial_head,'head_sha256_after':trained_hash,
        'checkpoint_sha256':base.sha(checkpoint/'model.safetensors'),
        'training_script_sha256':base.sha(__file__),'comparison_script_sha256':base.sha(ROOT/'scripts/mes_timestral_comparison.py'),
        'total_seconds':time.perf_counter()-started,
        'limits':'Head-only adaptation, normal-only synthetic running data, no field or full-model fine-tuning validation.'}
    print(json.dumps({'metrics':{name:{k:m[k] for k in ('detected_events','injected_events',
        'wrong_alert_equipment_seconds','duplicate_alert_episodes','p95_onset_delay_seconds')}
        for name,m in metrics.items()},'requested_improvement':result['requested_improvement_vs']}),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','source','normal','weak','model','reference-calibration','out-dir'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=False)
    base.write_new(args.out_dir/'result.json',evaluate(args))


if __name__=='__main__':main()
