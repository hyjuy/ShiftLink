"""Post-prediction raw-frame, paired-quality and preservation audit."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from scripts import mes_causal_v14_run as r
from scripts.mes_causal_schema import metadata,signals


def audit(out):
    lock=out/'candidate-lock.json';r.prior.r.old.prior.require_lock(lock)
    spec=signals();order=list(spec);prefixes=stresses=frames_checked=0
    manifests=[]
    for role in ('development','test'):
        path=out/'data'/role;manifest=r.load(path/'manifest.json');events=r.load(path/'events.private.json')
        assert r.d.sha(path/'events.private.json')==manifest['ledger_sha256']
        if role=='test':assert manifest['candidate_lock_sha256']==r.d.sha(lock)
        entries={e['run_id']:e for e in manifest['runs']};starts={}
        for e in manifest['runs']:
            if events[e['run_id']]:starts[e['group_id']]=min(x['start'] for x in events[e['run_id']])
        hashes={};quality={}
        for run,frames in r.prior.batches(path):
            digest=hashlib.sha256();previous=None;entry=entries[run]
            for f in frames:
                assert f['line_mode']=='running' and f['is_synthetic'] is True
                assert f['config_id']==metadata()['config_id']
                at=datetime.fromisoformat(f['simulated_at']);assert previous is None or (at-previous).total_seconds()==1
                previous=at
                assert [(m['equipment_id'],m['signal']) for m in f['measurements']]==order
                for m,key in zip(f['measurements'],order):
                    value=m['value'];assert isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
                    assert m['unit']==spec[key]['unit'] and m['quality'] in ('good','bad','unavailable')
                    assert datetime.fromisoformat(m['observed_at'])<=at
                    if m['unit']=='bool':assert value in (0,1)
                if f['sequence']<starts.get(entry['group_id'],0):
                    digest.update(json.dumps(f['measurements'],sort_keys=True).encode())
                for q in entry['quality_stress']:
                    if f['sequence']==q['tick']:
                        m=next(m for m in f['measurements'] if (m['equipment_id'],m['signal'])==(q['equipment'],q['signal']))
                        assert m['quality']=='bad';stresses+=1
                frames_checked+=1
            hashes[run]=digest.hexdigest();quality[run]=entry['quality_stress']
        for group in starts:
            pair=[e['run_id'] for e in manifest['runs'] if e['group_id']==group]
            assert len(pair)==2 and hashes[pair[0]]==hashes[pair[1]] and quality[pair[0]]==quality[pair[1]]
            prefixes+=1
        manifests.append(manifest)
    for root in (r.PREVIOUS,r.prior.PREVIOUS,r.prior.r.PREVIOUS):
        manifests.extend(r.load(root/'data'/role/'manifest.json') for role in ('development','test'))
    manifests.append(r.load(r.ROOT/'output/mes-causal-v14b-20261023/data/test/manifest.json'))
    r.prior.r.old.prior.check_disjoint(manifests)
    r.prior.r.old.prior.require_lock(lock)
    report=dict(passed=True,protected_files=len(r.load(out/'protected.json')),frozen_files=len(r.load(lock)['files']),frames=frames_checked,
        paired_prefixes=prefixes,forced_bad_observations=stresses,raw_channels=69,analysis_channels=63,
        timestamps_units_quality_order_config=True,roles_disjoint=True,frozen_unchanged=True)
    r.d.write_new(out/'final-audit.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();audit(a.out.resolve())
