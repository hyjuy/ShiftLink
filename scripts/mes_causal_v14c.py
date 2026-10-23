"""Normal-only calibration aligned to the fixed four-frame process patience."""
import numpy as np


def calibrate(batches):
    values=np.concatenate([scores for scores,background in batches])
    return np.array([max(.5,float(col[np.isfinite(col)].max())*1.1) if np.isfinite(col).any() else 1e6 for col in values.T])
