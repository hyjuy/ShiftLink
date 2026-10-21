"""Measure a saved checkpoint with one CPU thread and one window at a time."""
import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path

# Set these before importing the numerical runtimes.
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import numpy as np
import torch
from timestral import TimestralForecaster


def peak_rss_bytes():
    if platform.system() != 'Windows':
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if platform.system() == 'Darwin' else value * 1024)
    import ctypes
    class Memory(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in (
                'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Memory), ctypes.c_ulong]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    value = Memory()
    value.cb = ctypes.sizeof(value)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(value), value.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(value.PeakWorkingSetSize)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    with np.load(args.predictions, allow_pickle=False) as data:
        examples = data['examples'].copy()
        expected = data['adapted'][:len(examples)].copy()
    if examples.shape != (3, 68, 64) or expected.shape != (3, 68, 21):
        raise ValueError('expected three saved 68-channel, 64-step windows')
    tick = time.perf_counter()
    model = TimestralForecaster.from_pretrained(args.checkpoint, device='cpu', local_files_only=True)
    load_seconds = time.perf_counter() - tick
    errors = []
    durations = []
    with torch.inference_mode():
        # The first three calls verify parity and warm up each distinct context.
        for index, context in enumerate(examples):
            actual = model.forecast(context[None], prediction_length=1).quantiles[0, :, 0].numpy()
            np.testing.assert_allclose(actual, expected[index], rtol=1e-5, atol=1e-5)
            errors.append(float(np.max(np.abs(actual - expected[index]))))
        for index in range(12):
            tick = time.perf_counter()
            model.forecast(examples[index % 3][None], prediction_length=1)
            durations.append(time.perf_counter() - tick)
    peak = peak_rss_bytes()
    assert peak > 0
    weights = args.checkpoint / 'model.safetensors'
    result = {
        'host': platform.platform(), 'architecture': platform.machine(),
        'device': 'cpu', 'threads': 1, 'interop_threads': 1, 'workers': 1, 'batch': 1,
        'channels': 68, 'context': 64, 'horizon': 1, 'dtype': 'float32',
        'symmetric_averaging': True, 'clip_nonnegative': True,
        'samples': 12, 'distinct_contexts': 3, 'load_seconds': load_seconds,
        'seconds': durations, 'p50_seconds': float(np.quantile(durations, .5)),
        'p95_seconds': float(np.quantile(durations, .95)), 'peak_rss_bytes': peak,
        'checkpoint_bytes': weights.stat().st_size,
        'checkpoint_sha256': hashlib.sha256(weights.read_bytes()).hexdigest(),
        'max_forecast_abs_error': max(errors),
        'limits': 'Three saved contexts; no new event recall evaluation; no CPU architecture emulation. '
                  'Peak RSS is this process only, not the complete PDA/CNN/OS workload.'}
    with args.out.open('x', encoding='utf-8') as target:
        json.dump(result, target, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
