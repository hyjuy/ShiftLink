"""Normal-only head retraining, locked baselines and first-use factorial tests."""
import argparse
import copy
from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import sys
import time

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import numpy as np

from scripts import mes_causal_data as d
from scripts import mes_causal_score as scorer
from scripts.mes_causal_schema import ROOT, signals


def check_disjoint(manifests):
    for field in ('run_id', 'seed', 'nonce'):
        seen = set()
        for manifest in manifests:
            values = [r[field] for r in manifest['runs']]
            if len(values) != len(set(values)) or seen.intersection(values):
                raise ValueError('role overlap: ' + field)
            seen.update(values)


def fit_statistics(runs):
    samples = {c: [] for c in signals()}
    total = 0
    for frames in runs.values():
        for frame in frames:
            if frame['line_mode'] != 'running':
                continue
            total += 1
            for c, value in d.valid_values(frame, signals()).items():
                samples[c].append(value)
    channels = sorted(c for c, values in samples.items() if len(values) / max(total, 1) >= .95)
    if not channels:
        raise ValueError('no usable fit channels')
    stats = {}
    for c in channels:
        spec = signals()[c]
        band = (spec['normal_max'] or 0) - (spec['normal_min'] or 0)
        stats[c] = float(np.mean(samples[c])), max(float(np.std(samples[c])), .05 * band, .001)
    return channels, stats


def forecast(model, inputs, *, batch=16):
    import torch
    output, calls = [], []
    start = time.perf_counter()
    with torch.inference_mode():
        for i in range(0, len(inputs), batch):
            tick = time.perf_counter()
            result = model.forecast(inputs[i:i + batch], prediction_length=1)
            output.append(np.stack([result.quantile(q).detach().cpu().numpy()[:, :, 0] for q in (.01, .5, .99)], axis=-1))
            calls.append(time.perf_counter() - tick)
            if i % 128 == 0:
                print('forecast', min(i + batch, len(inputs)), '/', len(inputs), flush=True)
    return np.concatenate(output), dict(windows=len(inputs), batch=batch, seconds=time.perf_counter() - start,
                                        batch_call_p95_seconds=float(np.quantile(calls, .95)))


def aggregate(values, channels):
    equipment = sorted({e for e, _ in channels})
    return np.stack([np.max(np.where(np.isnan(values[:, ix]), -np.inf, values[:, ix]), axis=1)
                     for e in equipment for ix in [[i for i, c in enumerate(channels) if c[0] == e]]], axis=1)


def calibrate(values):
    result = []
    for column in values.T:
        column = column[np.isfinite(column)]
        if len(column) < 1:
            raise ValueError('empty normal calibration')
        result.append(max(1., float(np.quantile(column, .995, method='higher'))))
    return np.array(result)


def normal_scores(runs, channels, stats, model):
    from scripts.mes_timestral_comparison import channel_scores
    x, keys, actual = d.windows(runs, channels)
    q, timing = forecast(model, x)
    scales = np.array([stats[c][1] for c in channels])
    ts = aggregate(channel_scores(actual, q[:, :, 1], q[:, :, 0], q[:, :, 2], scales), channels)
    naive = aggregate(np.abs(actual - x[:, :, -1]) / scales, channels)
    centers = np.array([stats[c][0] for c in channels])
    lookup, smoothed = {}, {}
    for run, frames in runs.items():
        state = np.zeros(len(channels))
        for f in frames:
            if f['line_mode'] in d.INACTIVE:
                state[:] = 0
            values = d.valid_values(f, signals())
            z = np.array([abs(values[c] - centers[i]) / scales[i] if c in values else np.nan for i, c in enumerate(channels)])
            state = np.where(np.isfinite(z), .4 * z + .6 * state, state)
            lookup[(run, f['sequence'])] = state.copy()
    ewma = aggregate(np.asarray([lookup[k] for k in keys]), channels)
    return dict(keys=keys, actual=actual, ts=ts, naive=naive, ewma=ewma, timing=timing,
                forecast=q)


def policy_data(runs, channels, stats, computed, limits):
    equipment = sorted({e for e, _ in channels})
    ready = {key: i for i, key in enumerate(computed['keys'])}
    keys, raw, signed, ratio, reset, observations = [], [], [], [], [], []
    baseline = {}
    for run, frames in runs.items():
        was_ready = None
        for f in frames:
            key = run, f['sequence']
            index = ready.get(key)
            enabled = index is not None and f['line_mode'] == 'running'
            values = d.valid_values(f, signals())
            z = np.array([(values[c] - stats[c][0]) / stats[c][1] if c in values else np.nan for c in channels])
            signed.append(z)
            keys.append(key)
            current_raw = [max([abs(z[i]) for i, c in enumerate(channels) if c[0] == e and np.isfinite(z[i])], default=np.nan) for e in equipment]
            raw.append(current_raw if enabled else [np.nan] * len(equipment))
            ratio.append(computed['ts'][index] / limits['timestral'] if enabled else np.full(len(equipment), np.nan))
            baseline[key] = {e for i, e in enumerate(equipment) if enabled and computed['ewma'][index, i] >= limits['ewma'][i]}
            reset.append(f['sequence'] == 0 or not enabled or enabled != was_ready)
            was_ready = enabled
            observations.append(dict(run=run, sequence=f['sequence'], at=f['simulated_at'], inactive=f['line_mode'] != 'running'))
    return dict(keys=keys, equipment=equipment, channels=channels, raw_z=np.asarray(raw), signed_z=np.asarray(signed),
                ratio=np.asarray(ratio), resets=reset, baseline=baseline, observations=observations)


def predict_policies(runs, channels, stats, computed, limits, settings):
    from scripts import mes_timestral_pda_bridge as bridge
    from scripts import mes_timestral_tail_guarded as guarded
    tools = bridge.load_tools().base
    notice = tools.notice_module
    base_data = policy_data(runs, channels, stats, computed, limits)

    def hybrid(data):
        preserve = notice.previous.preserve.predict(data, notice.previous.previous.CURRENT)
        full = notice.previous.predict(data, preserve, settings['fast_params'])
        current = tools.symptom.previous.evidence.previous.predict(data, full, settings['current_params'])
        floor, _ = tools.symptom.previous.predict_and_notify(data, current)
        display, _ = bridge.add_early(data, floor, **settings['source_params'])
        return display, guarded.notifications(data, display, floor, settings['notice_params'])

    displays, notifications = {}, {}
    displays['timestral_ewma'], notifications['timestral_ewma'] = hybrid(base_data)
    neutral = dict(base_data, ratio=np.where(np.isfinite(base_data['raw_z']), 1., np.nan))
    displays['no_timestral'], notifications['no_timestral'] = hybrid(neutral)
    displays['ewma'] = base_data['baseline']
    notifications['ewma'] = guarded.notifications(neutral, displays['ewma'], displays['ewma'], settings['notice_params'])
    lookup = {key: row / limits['persistence'] for key, row in zip(computed['keys'], computed['naive'])}
    naive_data = dict(base_data, ratio=np.array([lookup.get(key, np.full(len(base_data['equipment']), np.nan)) for key in base_data['keys']]))
    displays['persistence'] = {key: {e for i, e in enumerate(base_data['equipment']) if naive_data['ratio'][j, i] > 1}
                               for j, key in enumerate(base_data['keys'])}
    notifications['persistence'] = guarded.notifications(naive_data, displays['persistence'], displays['persistence'], settings['notice_params'])
    return displays, notifications


def audit(runs):
    from collections import Counter
    count, stale, outside, bad = Counter(), Counter(), Counter(), Counter()
    for frames in runs.values():
        for frame in frames:
            for m in frame['measurements']:
                c = m['equipment_id'], m['signal']
                count[c] += 1
                stale[c] += m['observed_at'] != frame['simulated_at']
                bad[c] += m['quality'] != 'good'
                spec = signals()[c]
                outside[c] += int(m['quality'] == 'good' and spec['normal_min'] is not None and (m['value'] < spec['normal_min'] or m['value'] > spec['normal_max']))
    return dict(measurements=sum(count.values()), stale=sum(stale.values()), bad_or_unavailable=sum(bad.values()),
                normal_range_excursions=sum(outside.values()),
                by_channel={f'{c[0]}/{c[1]}': dict(count=count[c], stale=stale[c], bad=bad[c], outside=outside[c]) for c in count})


def model_settings():
    old = json.loads((ROOT / 'output/mes-timestral-tail-confirmation-20261022/result.json').read_text(encoding='utf-8'))['lock']
    prior = json.loads((ROOT / 'output/mes-timestral-ablation-development-20261021/result.json').read_text(encoding='utf-8'))
    return dict(fast_params=prior['fast_params'], current_params=old['current_params'],
                source_params=old['selected_source'], notice_params=old['selected_notification'])


def train(out, dataset):
    import torch
    from timestral import TimestralForecaster
    from scripts import mes_timestral_finetune as ft
    output = out / 'training'
    output.mkdir(exist_ok=False)
    torch.set_num_threads(1)
    roles, manifests = {}, []
    for role in ('fit', 'selection', 'calibration', 'development'):
        roles[role], manifest = d.read_role(dataset / role)
        manifests.append(manifest)
    check_disjoint(manifests)
    channels, stats = fit_statistics(roles['fit'])
    d.write_new(output / 'input-audit.json', {role: audit(runs) for role, runs in roles.items()})
    pretrained = ROOT / 'output/mes-timestral-20261021/hub/models--mistralai--Timestral-28M/snapshots/49b26409ac87b5935539a5d8ffe7f397b720db47'
    model = TimestralForecaster.from_pretrained(pretrained, device='cpu', local_files_only=True)
    for parameter in model.model.parameters():
        parameter.requires_grad_(False)
    backbone_before = ft.state_hash(model.model, False)
    head_before = ft.state_hash(model.model, True)
    caches, features = {}, {}
    for role in ('fit', 'selection'):
        wrapped = {run: [(f, {'faults': []}) for f in frames] for run, frames in roles[role].items()}
        caches[role], _, features[role] = ft.collect(wrapped, channels, lambda f: d.valid_values(f, signals()), model,
                                                    output / f'{role}-features.npz', thin=8)
    torch.set_num_threads(4)
    head, history = ft.fit_head(model.model.head, caches['fit'], caches['selection'])
    model.model.head.load_state_dict(head.state_dict())
    assert ft.state_hash(model.model, False) == backbone_before
    assert ft.state_hash(model.model, True) != head_before
    checkpoint = output / 'checkpoint'
    ft.save_checkpoint(model, checkpoint)
    del caches
    gc.collect()
    calibration = normal_scores(roles['calibration'], channels, stats, model)
    limits = {name: calibrate(calibration[field]) for name, field in (
        ('timestral', 'ts'), ('ewma', 'ewma'), ('persistence', 'naive'))}
    settings = model_settings()
    d.write_new(output / 'calibration.json', dict(channels=channels, stats=[[*c, *stats[c]] for c in channels],
        thresholds={k: v.tolist() for k, v in limits.items()}, settings=settings,
        calibration_windows=len(calibration['keys']), quantile=.995, model_source=str(pretrained)))
    # Exercise the whole candidate before locking or generating any test data.
    development = normal_scores(roles['development'], channels, stats, model)
    displays, notices = predict_policies(roles['development'], channels, stats, development, limits, settings)
    d.write_new(output / 'development-contract.json', dict(methods=list(notices),
        keys={k: len(v) for k, v in notices.items()}, target_labels_read=False))
    d.write_new(output / 'result.json', dict(training=history, features=features, channels=len(channels),
        omitted_channels=sorted(signals().keys() - set(channels)), backbone_unchanged=True, head_changed=True,
        pretrained_backbone_sha256=backbone_before, head_sha256_before=head_before,
        checkpoint_sha256=d.sha(checkpoint / 'model.safetensors'), test_rows_read=0,
        calibration_timing=calibration['timing'], development_timing=development['timing']))
    files = [Path(__file__), ROOT / 'docs/research/mes-causal-v8-prereg-20261022.md',
             ROOT / 'docs/data/reference/mes-causal-v8-signals.json', output / 'calibration.json',
             checkpoint / 'model.safetensors', checkpoint / 'config.json']
    files += [ROOT / 'scripts' / name for name in ('mes_causal_data.py', 'mes_causal_schema.py', 'mes_causal_source.py',
        'mes_causal_challenge.py', 'mes_causal_score.py')]
    files += [ROOT / 'scripts' / name for name in ('mes_timestral_pda_bridge.py', 'mes_timestral_tail_guarded.py',
        'mes_timestral_symptom.py', 'mes_timestral_evidence_entry.py', 'mes_timestral_evidence.py',
        'mes_timestral_recent_entry.py', 'mes_timestral_close.py', 'mes_timestral_notifications.py',
        'mes_timestral_continuity.py', 'mes_timestral_rearm.py', 'mes_timestral_preserve.py',
        'mes_timestral_stateful.py', 'mes_timestral_pi_followup.py', 'mes_timestral_finetune.py',
        'mes_timestral_comparison.py')]
    for role in ('fit', 'selection', 'calibration', 'development'):
        files += [dataset / role / name for name in ('features.jsonl', 'events.private.json', 'manifest.json')]
    d.write_new(out / 'candidate-lock.json', dict(status='frozen_before_test', created_at=datetime.now(timezone.utc).isoformat(),
        files={str(p.resolve()): d.sha(p) for p in files}, training_roles=[r['runs'] for r in manifests],
        protocol='normal-only training, no fault-metric parameter selection, 4 first-use test folds'))
    print('FROZEN BEFORE TEST', flush=True)


def evaluate(out, dataset):
    import torch
    from timestral import TimestralForecaster
    torch.set_num_threads(4)
    lock = out / 'candidate-lock.json'
    if not lock.exists():
        raise ValueError('train and freeze first')
    output = out / 'evaluation'
    output.mkdir(exist_ok=False)
    calibration = json.loads((out / 'training/calibration.json').read_text(encoding='utf-8'))
    channels = [tuple(c) for c in calibration['channels']]
    stats = {(e, s): (center, scale) for e, s, center, scale in calibration['stats']}
    limits = {k: np.array(v) for k, v in calibration['thresholds'].items()}
    model = TimestralForecaster.from_pretrained(out / 'training/checkpoint', device='cpu', local_files_only=True)
    manifests = [json.loads((dataset / role / 'manifest.json').read_text(encoding='utf-8')) for role in ('fit', 'selection', 'calibration', 'development')]
    results = {}
    for role in ('test_id', 'test_dynamics', 'test_mechanism', 'test_joint'):
        print('FIRST USE', role, flush=True)
        d.generate_role(dataset / role, role, lock=lock)
        runs, manifest = d.read_role(dataset / role)
        manifests.append(manifest)
        check_disjoint(manifests)
        computed = normal_scores(runs, channels, stats, model)
        with (output / f'{role}-forecasts.npz').open('xb') as target:
            np.savez_compressed(target, keys=np.array(computed['keys'], dtype=str), forecasts=computed['forecast'], actual=computed['actual'])
        displays, notices = predict_policies(runs, channels, stats, computed, limits, calibration['settings'])
        d.write_new(output / f'{role}-predictions.json', {method: [[r, s, sorted(v)] for (r, s), v in rows.items()] for method, rows in notices.items()})
        # Open the private event ledger only after every method's predictions are saved.
        ledger = json.loads((dataset / role / 'events.private.json').read_text(encoding='utf-8'))
        eligible = set(computed['keys'])
        results[role] = dict(notifications={name: scorer.evaluate(runs, ledger, rows, eligible) for name, rows in notices.items()},
                             display={name: scorer.evaluate(runs, ledger, rows, eligible) for name, rows in displays.items()},
                             input_audit=audit(runs), timing=computed['timing'], family=manifest['family'])
        d.write_new(output / f'{role}-result.json', results[role])
        print(json.dumps({name: {k: m[k] for k in ('events', 'detected_events', 'duplicate_notifications', 'p95_injection_delay_seconds')}
                          for name, m in results[role]['notifications'].items()}), flush=True)
    protected = json.loads((out / 'original-files.json').read_text(encoding='utf-8'))
    assert all(d.sha(ROOT / path) == sha for path, sha in protected.items())
    frozen = json.loads(lock.read_text(encoding='utf-8'))
    assert all(d.sha(path) == sha for path, sha in frozen['files'].items())
    d.write_new(output / 'result.json', dict(folds=results, original_files_preserved=True, protected_files=len(protected),
        candidate_lock_sha256=d.sha(lock), frozen_files_unchanged=True,
        limits='First-use synthetic tests, shared catalog/qualitative assumptions/author. Not field validation; injection-time delay, source-equipment matching.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--phase', choices=('train', 'evaluate'), required=True)
    args = parser.parse_args()
    (train if args.phase == 'train' else evaluate)(args.out, args.data)
