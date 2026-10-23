"""Normal-only calibration for the unchanged v11 detector."""
import numpy as np
from scripts.mes_causal_v11 import predict


def calibrate(level,keys,normal_runs,original):
    normal=level[np.array([r in normal_runs for r,t in keys])]
    if not len(normal) or not np.isfinite(normal).any(axis=0).all():
        raise ValueError('finite normal calibration required for every channel')
    high=np.zeros(level.shape[1],int);triggered=np.zeros(level.shape[1],bool);previous=None
    for key,row in zip(keys,level):
        if key[0] not in normal_runs:
            high[:]=0;previous=None;continue
        if previous is None or key[0]!=previous[0] or key[1]!=previous[1]+1:high[:]=0
        high=np.where(np.isfinite(row) & (row>original),high+1,0)
        triggered |= high>=4;previous=key
    # Only recalibrate sustained normal false evidence, preserving other sensitivity.
    envelope=np.max(np.where(np.isfinite(normal),normal,-np.inf),axis=0)*1.1
    return np.where(triggered,np.maximum(original,envelope),original)
