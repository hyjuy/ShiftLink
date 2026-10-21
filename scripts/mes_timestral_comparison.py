"""Offline, causally evaluated Timestral-28M comparison with the frozen EWMA."""

def causal_windows(*args, **kwargs):
    raise NotImplementedError('causal forecast windows')

def channel_scores(*args, **kwargs):
    raise NotImplementedError('quantile-normalized residual')

def normal_window_keys(*args, **kwargs):
    raise NotImplementedError('clean train windows')

def calibrate(*args, **kwargs):
    raise NotImplementedError('train-only threshold')

def threshold_alerts(*args, **kwargs):
    raise NotImplementedError('equipment alert mapping')

def aggregate_failures(*args, **kwargs):
    raise NotImplementedError('comparison gates')
