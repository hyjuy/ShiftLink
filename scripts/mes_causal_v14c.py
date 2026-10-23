"""Normal-only calibration aligned to the fixed four-frame process patience."""
import numpy as np


def calibrate(batches):
    count=batches[0][0].shape[1];peaks=[[] for _ in range(count)]
    for scores,background in batches:
        if len(scores)<4:continue
        effective=np.where(background,np.inf,scores)
        windows=np.lib.stride_tricks.sliding_window_view(effective,4,axis=0)
        minima=np.min(windows,axis=-1);valid=~np.isnan(windows).any(axis=-1)
        if np.isinf(minima[valid]).any():raise ValueError('baseline already has sustained normal evidence')
        for j in range(count):
            values=minima[valid[:,j],j]
            if len(values):peaks[j].append(float(values.max()))
    return np.array([max(.5,max(values)*1.1) if values else 1e6 for values in peaks])
