"""Exclusive absolute-path forecast archives and input-bound recovery chunks."""
import hashlib
import json
from pathlib import Path
import time
import numpy as np


def archive(path,**arrays):
    with Path(path).resolve().open('xb') as stream:np.savez_compressed(stream,**arrays)


def run_chunks(x,predict,root,identity,chunk=128):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    fingerprint=dict(shape=list(x.shape),dtype=str(x.dtype),input_sha256=hashlib.sha256(x.tobytes()).hexdigest(),
                     model=identity,chunk=chunk)
    stamp=root/'identity.json'
    if stamp.exists():
        if json.loads(stamp.read_text(encoding='utf-8'))!=fingerprint:raise ValueError('recovery identity mismatch')
    else:
        with stamp.open('x',encoding='utf-8') as f:json.dump(fingerprint,f)
    new,old,seconds,reused=[],[],0.,0
    started=time.perf_counter()
    for start in range(0,len(x),chunk):
        path=root/f'{start:06d}.npz'
        if path.exists():
            with np.load(path) as saved:a,b,elapsed=saved['forecast'],saved['old_head'],float(saved['seconds'])
            reused+=len(a)
        else:
            a,b,timing=predict(x[start:start+chunk]);elapsed=timing['seconds']
            assert np.isfinite(a).all() and np.isfinite(b).all()
            archive(path,forecast=a,old_head=b,seconds=np.array(elapsed))
        assert len(a)==min(chunk,len(x)-start) and a.shape==b.shape
        new.append(a);old.append(b);seconds+=elapsed
        print('SAVED CHUNK',min(start+chunk,len(x)),'/',len(x),'reused',reused,flush=True)
    return np.concatenate(new),np.concatenate(old),dict(windows=len(x),seconds=seconds,
        wall_seconds=time.perf_counter()-started,reused_windows=reused,workers=4,torch_threads=1)
