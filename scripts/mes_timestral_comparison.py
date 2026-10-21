"""Offline, causally evaluated Timestral-28M comparison with the frozen EWMA."""
import argparse
import hashlib
import json
import platform
import sys
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np

CONTEXT = 64
INACTIVE = {'paused', 'stopped', 'recovering', 'quality_hold'}
MODEL = 'mistralai/Timestral-28M'
CODE_REVISION = 'a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff'


def causal_windows(runs, channels, values):
    """Frames only: create t's input before reading t's measurements."""
    windows, keys = [], []
    for run, frames in runs.items():
        history = deque(maxlen=CONTEXT)
        previous = None
        for frame in frames:
            at = datetime.fromisoformat(frame['simulated_at'])
            continuous = previous is None or (at - previous).total_seconds() == 1
            previous = at
            if not continuous or frame.get('line_mode') in INACTIVE:
                history.clear()
            if frame.get('line_mode') in INACTIVE:
                continue
            if len(history) == CONTEXT:
                windows.append(np.array(history, dtype=np.float32).T)
                keys.append((run, frame['sequence']))
            current = values(frame)
            history.append([current.get(key, np.nan) for key in channels])
    return np.asarray(windows, dtype=np.float32).reshape(-1, len(channels), CONTEXT), keys


def channel_scores(actual, median, lower, upper, scales):
    if (not all(np.isfinite(x).all() for x in (median, lower, upper, scales))
            or np.isinf(actual).any() or np.any(scales <= 0)
            or np.any(lower > median) or np.any(median > upper)):
        raise ValueError('invalid forecast quantiles, measurement, or scale')
    floor = .1 * scales
    value = np.maximum((actual-median)/np.maximum(upper-median, floor),
                       (median-actual)/np.maximum(median-lower, floor))
    return np.where(np.isnan(actual), np.nan, np.maximum(value, 0))


def normal_window_keys(runs):
    selected = set()
    for run, rows in runs.items():
        history = deque(maxlen=CONTEXT+1)
        for frame, label in rows:
            history.append(not label['faults'])
            if len(history) == CONTEXT+1 and all(history):
                selected.add((run, frame['sequence']))
    return selected


def calibrate(keys, values, equipment, clean):
    selected = np.array([key in clean for key in keys])
    thresholds, counts = {}, {}
    for i, eq in enumerate(equipment):
        normal = values[selected, i]
        normal = normal[np.isfinite(normal)]
        if len(normal) < 100:
            raise ValueError(f'{eq}: fewer than 100 clean calibration windows')
        thresholds[eq] = max(1., float(np.quantile(normal, .995, method='higher')))
        counts[eq] = len(normal)
    return thresholds, counts


def threshold_alerts(keys, values, equipment, thresholds):
    return {key: {eq for i, eq in enumerate(equipment) if values[j, i] > thresholds[eq]}
            for j, key in enumerate(keys)}


def aggregate_failures(before, after):
    failures = []
    for field, greater in (('detected_events', True), ('wrong_alert_equipment_seconds', False),
                           ('duplicate_alert_episodes', False), ('p95_onset_delay_seconds', False)):
        old, new = before[field], after[field]
        if (new is None and old is not None) or (new is not None and old is not None
                and (new < old if greater else new > old)):
            failures.append(field)
    if not any(after[k] is not None and before[k] is not None and
               (after[k] > before[k] if k == 'detected_events' else after[k] < before[k])
               for k in ('detected_events', 'wrong_alert_equipment_seconds',
                         'duplicate_alert_episodes', 'p95_onset_delay_seconds')):
        failures.append('no_strict_improvement')
    return failures


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as target:
        json.dump(value, target, indent=2, ensure_ascii=False, allow_nan=False)
        target.write('\n')


def verify_runtime(runtime):
    provenance = json.loads((runtime/'provenance.json').read_text(encoding='utf-8'))
    for name, expected in provenance['files'].items():
        if sha(runtime/name) != expected:
            raise ValueError(f'frozen runtime changed: {name}')
    return sha(runtime/'provenance.json')


def validate_calibration(calibration, model, channels, provenance, training):
    if (calibration['model'] != model or calibration['channels'] != [list(c) for c in channels]
            or calibration['runtime_provenance_sha256'] != provenance
            or calibration['training_provenance'] != training):
        raise ValueError('calibration provenance mismatch')


def check_manifest_pair(source, full, weak, confirmation):
    if full['runs'] != weak['runs']:
        raise ValueError('full/weak manifest pairing differs')
    training_seeds = {r['seed'] for r in source['runs'] if r['split'] == 'train'}
    validation_seeds = {r['seed'] for r in full['runs'] if r['split'] == 'validation'}
    if training_seeds & validation_seeds:
        raise ValueError('train/validation seed overlap')
    if confirmation and ({r['seed'] for r in source['runs']} & {r['seed'] for r in full['runs']}):
        raise ValueError('confirmation seed overlap')


def forecast_scores(frames, channels, stats, valid_values, forecaster, artifact, batch=1, selected=None, workers=4):
    started = time.perf_counter()
    x, keys = causal_windows(frames, channels, valid_values)
    if selected is not None:
        keep = np.array([key in selected for key in keys])
        x, keys = x[keep], [key for key in keys if key in selected]
    if not keys:
        raise ValueError('no causal windows')
    lookup = {(run, f['sequence']): f for run, rows in frames.items() for f in rows}
    observed = [valid_values(lookup[k]) for k in keys]
    actual = np.array([[row.get(c, np.nan) for c in channels] for row in observed])
    estimates, elapsed = [], []
    def call(start):
        tick = time.perf_counter()
        forecast = forecaster.forecast(x[start:start+batch], prediction_length=1)
        return (np.stack([forecast.quantile(q).detach().cpu().numpy()[:, :, 0]
                          for q in (.01, .5, .99)], axis=-1), time.perf_counter()-tick)
    forecast_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start, (estimate, seconds) in zip(range(0,len(keys),batch),pool.map(call,range(0,len(keys),batch))):
            estimates.append(estimate)
            elapsed.append(seconds)
            if start % 128 == 0:
                print(f'{artifact.stem}: {start+len(estimate)}/{len(keys)} windows', flush=True)
    forecast_seconds = time.perf_counter()-forecast_started
    quantiles = np.concatenate(estimates)
    values = channel_scores(actual, quantiles[:,:,1], quantiles[:,:,0], quantiles[:,:,2],
                            np.array([stats[c][1] for c in channels]))
    equipment = sorted({eq for eq, _ in channels})
    # At least one valid sensor is required; all-missing equipment never alerts.
    aggregated = np.stack([np.max(np.where(np.isnan(values[:, indices]), -np.inf, values[:, indices]), axis=1)
        for eq in equipment for indices in [[i for i,c in enumerate(channels) if c[0] == eq]]], axis=1)
    with artifact.open('xb') as target:
        np.savez_compressed(target, context_keys=np.array(keys, dtype=str), channels=np.array(channels),
                            quantiles=quantiles, actual=actual, equipment_scores=aggregated)
    # Same inputs are replayed independently for online, single-window timing.
    singles = []
    for i in range(min(5, len(x))):
        tick = time.perf_counter()
        forecaster.forecast(x[i:i+1], prediction_length=1)
        singles.append(time.perf_counter()-tick)
    timing = {'windows': len(keys), 'batch_size': batch, 'workers':workers,
              'forecast_seconds':forecast_seconds, 'summed_call_seconds':sum(elapsed),
              'seconds_per_window_batched':forecast_seconds/len(keys),
              'single_window_seconds': singles, 'total_seconds': time.perf_counter()-started,
              'forecast_sha256': sha(artifact)}
    return keys, aggregated, equipment, timing


def background(runs, alerts):
    counts = dict(normal_label_equipment_frames=0, prefault_equipment_frames=0,
                  normal_label_frames=0, prefault_frames=0,
                  active_source_equipment_frames=0, active_source_alert_equipment_frames=0)
    for run, rows in runs.items():
        seen = False
        for frame, label in rows:
            current = alerts[run, frame['sequence']]
            active = {f['equipment_id'] for f in label['faults'] if f['intensity'] > 0}
            counts['active_source_equipment_frames'] += len(active)
            counts['active_source_alert_equipment_frames'] += len(active & current)
            if not label['faults']:
                counts['normal_label_frames'] += 1
                counts['normal_label_equipment_frames'] += len(current)
                if not seen:
                    counts['prefault_frames'] += 1
                    counts['prefault_equipment_frames'] += len(current)
            seen |= bool(label['faults'])
    return counts


def evaluate(args):
    started = time.perf_counter()
    runtime = args.runtime.resolve()
    provenance_hash = verify_runtime(runtime)
    sys.path.insert(0, str(runtime))
    from scripts.evaluate_mes_fault_models import fit_normal, predict_ewma, score, valid_values
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.mes_diagnostic_review import pair_audit
    from scripts.mes_location_replay import replay_validation
    from scripts.mes_ewma_release_review import paired_events
    from scripts.mes_training_source import prefix_hashes
    if not Path(sys.modules['scripts.evaluate_mes_fault_models'].__file__).resolve().is_relative_to(runtime):
        raise ValueError('wrong evaluation runtime imported')
    import torch
    import timestral
    from timestral import TimestralForecaster
    from huggingface_hub import HfApi, snapshot_download
    torch.set_num_threads(1)
    torch.manual_seed(20261021)
    torch.use_deterministic_algorithms(True)
    config, source = load_train_validation(args.train_full, profile='independent')
    source_manifest = json.loads((args.train_full/'manifest.json').read_text(encoding='utf-8'))
    manifests = {name:json.loads((path/'manifest.json').read_text(encoding='utf-8'))
                 for name,path in (('full',args.full),('weak',args.weak))}
    check_manifest_pair(source_manifest,manifests['full'],manifests['weak'],args.phase=='confirmation')
    specs, stats = fit_normal(source['train'], config)
    normals = [valid_values(f, specs) for rows in source['train'].values() for f,l in rows if not l['faults']]
    channels = [c for c in sorted(stats) if sum(c in v for v in normals)/len(normals) >= .95]
    values = lambda frame: valid_values(frame, specs)
    training = {'source_prefix':prefix_hashes(args.train_full,source_manifest),
                'stats_sha256':hashlib.sha256(json.dumps([[*c,*stats[c]] for c in sorted(stats)]).encode()).hexdigest()}
    calibration = (json.loads(args.calibration.read_text(encoding='utf-8'))
                   if args.calibration.exists() else None)
    if args.phase == 'confirmation' and calibration is None:
        raise ValueError('confirmation requires fixed development calibration')
    revision = calibration['model']['revision'] if calibration else HfApi().model_info(MODEL).sha
    model_path = Path(snapshot_download(MODEL, revision=revision,
        cache_dir=str(args.artifacts/'hub'), allow_patterns=['config.json','model.safetensors','LICENSE','README.md']))
    model_meta = {'id': MODEL, 'revision': revision, 'code_revision': CODE_REVISION,
                  'files': {p.name:sha(p) for p in model_path.iterdir() if p.is_file()},
                  'torch':torch.__version__, 'numpy':np.__version__, 'python':platform.python_version(),
                  'timestral_source':str(Path(timestral.__file__).parent), 'cpu_threads_per_call':1,'workers':4}
    forecaster = TimestralForecaster.from_pretrained(str(model_path), device='cpu')
    if calibration is not None:
        validate_calibration(calibration,model_meta,channels,provenance_hash,training)
        thresholds = calibration['thresholds']
    else:
        frames = {run:[f for f,_ in rows] for run,rows in source['train'].items()}
        keys, scores, equipment, timing = forecast_scores(frames, channels, stats, values, forecaster,
            args.artifacts/'train-forecasts.npz', selected=normal_window_keys(source['train']))
        thresholds, counts = calibrate(keys, scores, equipment, normal_window_keys(source['train']))
        calibration = {'model':model_meta, 'channels':[list(c) for c in channels],
                       'thresholds':thresholds, 'clean_windows_per_equipment':counts,
                       'runtime_provenance_sha256':provenance_hash, 'timing':timing,
                       'train_source':str(args.train_full), 'training_provenance':training, 'context':CONTEXT}
        write_new(args.calibration, calibration)
    result = {'model':model_meta, 'calibration_sha256':sha(args.calibration),
              'calibration':calibration, 'runtime_provenance_sha256':provenance_hash,
              'phase':args.phase, 'arms':{}, 'test_rows_read':0, 'strict_scorer_changed':False}
    paired = None
    for arm, path, scale in (('full',args.full,1), ('weak',args.weak,.2)):
        manifest = json.loads((path/'manifest.json').read_text(encoding='utf-8'))
        if manifest['generator_version'] != 7 or manifest['response_scale'] != scale:
            raise ValueError('expected v7 full/weak data')
        other, splits = load_train_validation(path, profile='independent')
        if other.config_id != config.config_id:
            raise ValueError('configuration mismatch')
        runs = splits['validation']
        if paired is not None:
            result['pairing'] = pair_audit(paired, runs)
        paired = runs
        print(f'{arm}: verify factual replay', flush=True)
        replay = replay_validation(path, config, runs)['verification']
        frames = {run:[f for f,_ in rows] for run,rows in runs.items()}
        keys, scores, equipment, timing = forecast_scores(frames, channels, stats, values, forecaster,
            args.artifacts/f'{args.phase}-{arm}-forecasts.npz')
        candidate = {(run,f['sequence']):set() for run,rows in runs.items() for f,_ in rows}
        candidate.update(threshold_alerts(keys, scores, equipment, thresholds))
        tick = time.perf_counter()
        baseline = predict_ewma(runs, specs, stats, 3)
        baseline_seconds = time.perf_counter()-tick
        eligible = set(keys)
        aligned = {k:v if k in eligible else set() for k,v in baseline.items()}
        models = {'ewma':baseline, 'ewma_common_warmup':aligned, 'timestral':candidate}
        metrics = {name:score(runs,alerts) for name,alerts in models.items()}
        if args.reference:
            reference = json.loads(args.reference.read_text(encoding='utf-8'))
            if metrics['ewma'] != reference['arms'][arm]['models']['ewma']['strict_source']:
                raise ValueError('D16 EWMA reproduction differs')
        events = paired_events(runs, baseline, candidate, metrics['ewma'], metrics['timestral'])
        result['arms'][arm] = {'dataset':str(path), 'metrics':metrics,
            'aggregate_failures':aggregate_failures(metrics['ewma'],metrics['timestral']),
            'common_warmup_failures':aggregate_failures(metrics['ewma_common_warmup'],metrics['timestral']),
            'paired_events':events, 'background':{name:background(runs,alerts) for name,alerts in models.items()},
            'replay_verification':replay, 'prefix_sha256':prefix_hashes(path,manifest),
            'timing':timing, 'ewma_prediction_seconds':baseline_seconds,
            'alerts':{name:[[r,s,sorted(v)] for (r,s),v in alerts.items()] for name,alerts in models.items()}}
        print(json.dumps({'arm':arm, 'metrics':{name:{k:m[k] for k in ('detected_events','injected_events',
            'wrong_alert_equipment_seconds','duplicate_alert_episodes','p95_onset_delay_seconds')}
            for name,m in metrics.items()}},ensure_ascii=False),flush=True)
    verify_runtime(runtime)
    result['total_seconds'] = time.perf_counter()-started
    result['code_sha256'] = sha(__file__)
    result['limits'] = ('Synthetic running mode; oracle normal train selection; 171 overlapping clean calibration windows; '
        'weak .2 is arbitrary; 64-step context; forecast can adapt to faults. Strict wrong time includes downstream '
        'responses and post-fault memory. Delay statistics exclude missed events. No field or hardware validation.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','train-full','full','weak','artifacts','calibration','out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--phase', choices=('development','confirmation'), required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('preserve prior results: output exists')
    args.artifacts.mkdir(parents=True, exist_ok=True)
    write_new(args.out, evaluate(args))


if __name__ == '__main__':
    main()
