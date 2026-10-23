"""Local, bounded Timestral+EWMA advisory bridge; never writes operational alarms."""
import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from urllib.parse import urlparse
from urllib.request import urlopen

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


class SessionLimit(RuntimeError):
    pass


def add_early(data, floor, sensor_z, ratio_cutoff, lookback):
    """Frozen stage5 source policy, copied without its development CLI."""
    keys, equipment = data['keys'], data['equipment']
    groups = [[j for j, channel in enumerate(data['channels']) if channel[0] == eq] for eq in equipment]
    absolute = np.where(np.isfinite(data['signed_z']), np.abs(data['signed_z']), -np.inf)
    dominant = np.empty((len(keys), len(equipment)), dtype=np.int32)
    strength = np.empty((len(keys), len(equipment)))
    for j, indices in enumerate(groups):
        chosen = np.asarray(indices)[np.argmax(absolute[:, indices], axis=1)]
        dominant[:, j] = chosen * 2 + (data['signed_z'][np.arange(len(keys)), chosen] < 0)
        strength[:, j] = absolute[np.arange(len(keys)), chosen]
    def states():
        return [dict(last_sig=None, consecutive=0, normal=-10**9, fired=False, ratios=[]) for _ in equipment]
    state, previous, output, pulses = states(), None, {}, {}
    for i, key in enumerate(keys):
        if data['resets'][i] or previous is None or key[0] != previous[0] or key[1] != previous[1] + 1:
            state = states()
        added = set()
        for j, eq in enumerate(equipment):
            st = state[j]
            raw, ratio = data['raw_z'][i, j], data['ratio'][i, j]
            if not np.isfinite(raw) or not np.isfinite(ratio) or not np.isfinite(strength[i, j]):
                st.update(last_sig=None, consecutive=0, normal=-10**9, fired=False, ratios=[])
                continue
            st['ratios'] = (st['ratios'] + [float(ratio)])[-lookback:]
            if raw <= 1.5:
                st['normal'], st['fired'] = key[1], False
            sig = int(dominant[i, j]) if strength[i, j] >= sensor_z else None
            st['consecutive'] = st['consecutive'] + 1 if sig is not None and sig == st['last_sig'] else int(sig is not None)
            st['last_sig'] = sig
            if st['consecutive'] >= 2 and not st['fired'] and key[1] - st['normal'] <= 8 and any(v > ratio_cutoff for v in st['ratios']):
                st['fired'] = True
                if eq not in floor[key]:
                    added.add(eq)
        output[key], pulses[key], previous = set(floor[key]) | added, added, key
    return output, pulses


def load_tools():
    sys.path.insert(0, str(ROOT))
    from scripts import mes_timestral_symptom as symptom
    return SimpleNamespace(base=SimpleNamespace(symptom=symptom, add_early=add_early,
                           notice_module=symptom.previous.evidence.previous.close.previous))


def load_context():
    runtime = ROOT / 'output/mes-diagnostic-runtime-20261021'
    sys.path[:0] = [str(runtime), str(ROOT)]
    from scripts import evaluate_mes_fault_models as scorer
    assert Path(scorer.__file__).resolve().is_relative_to(runtime)
    tools = load_tools()
    saved = json.loads((ROOT / 'output/mes-timestral-tail-confirmation-20261022/result.json').read_text())
    base = tools.base
    digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    assert digest(ROOT / 'output/mes-timestral-tail-develop-stage5-20261022.py') == saved['lock']['source_sha256']
    assert digest(ROOT / 'output/mes-timestral-tail-develop-20261022.py') == saved['lock']['stage1_sha256']
    assert digest(base.symptom.__file__) == saved['lock']['symptom_sha256']
    for name, expected in saved['lock']['helper_sha256'].items():
        assert digest(ROOT / 'scripts' / name) == expected
    p, config, specs, stats, ref, ft, prior = base.notice_module.model_context()
    assert ft['checkpoint_sha256'] == saved['lock']['checkpoint_sha256']
    return dict(tools=tools, config_id=config.config_id, specs=specs, stats=stats,
                channels=[tuple(c) for c in ref['channels']], thresholds=ft['thresholds']['finetuned'],
                fast_params=prior['fast_params'], current_params=saved['lock']['current_params'],
                source_params=saved['lock']['selected_source'], notice_params=saved['lock']['selected_notification'],
                checkpoint=p['ft'] / 'checkpoint')


class Detector:
    def __init__(self, context, forecast, *, limit=3600):
        self.context, self.forecast, self.limit = context, forecast, limit
        self.equipment = sorted({eq for eq, _ in context['channels']})
        self.frames, self.raw, self.ratios, self.signed, self.resets = [], [], [], [], []
        self.history, self.smoothed, self.baseline = deque(maxlen=64), {}, {}
        self.ready, self.display, self.notices = [], {}, {}

    def feed(self, frame):
        if self.frames:
            last = self.frames[-1]
            if frame['run_id'] == last['run_id'] and frame['sequence'] <= last['sequence']:
                return
            continuous = (frame['run_id'] == last['run_id'] and frame['sequence'] == last['sequence'] + 1
                          and (datetime.fromisoformat(frame['simulated_at']) - datetime.fromisoformat(last['simulated_at'])).total_seconds() == 1)
            if not continuous:
                self.__init__(self.context, self.forecast, limit=self.limit)
        if len(self.frames) >= self.limit:
            raise SessionLimit('bounded local analysis session exhausted')
        tools = self.context['tools'].base.notice_module
        from scripts.evaluate_mes_fault_models import valid_values
        values = valid_values(frame, self.context['specs'])
        channels = self.context['channels']
        actual = np.array([values.get(c, np.nan) for c in channels])
        signed = np.array([(values[c] - self.context['stats'][c][0]) / self.context['stats'][c][1]
                           if c in values else np.nan for c in channels])
        inactive = frame.get('line_mode') in tools.base.INACTIVE
        if inactive:
            self.history.clear()
        ready = len(self.history) == 64 and not inactive
        ratio = np.full(len(self.equipment), np.nan)
        if ready:
            quantiles = np.asarray(self.forecast(np.asarray(self.history, dtype=np.float32).T))
            if quantiles.shape != (len(channels), 3):
                raise ValueError('forecast channel/quantile shape differs')
            scores = tools.base.channel_scores(actual, quantiles[:, 1], quantiles[:, 0], quantiles[:, 2],
                                               np.array([self.context['stats'][c][1] for c in channels]))
            ratio = np.array([np.max(np.where(np.isnan(scores[ix]), -np.inf, scores[ix])) / self.context['thresholds'][eq]
                              for eq in self.equipment for ix in [[i for i, c in enumerate(channels) if c[0] == eq]]])
        raw = [max([abs(signed[i]) for i, c in enumerate(channels) if c[0] == eq and np.isfinite(signed[i])], default=np.nan)
               if not inactive else np.nan for eq in self.equipment]
        if inactive:
            self.smoothed.clear()
        else:
            for channel, value in values.items():
                if channel in self.context['stats']:
                    center, scale = self.context['stats'][channel]
                    self.smoothed[channel] = .4 * abs(value - center) / scale + .6 * self.smoothed.get(channel, 0.)
        key = frame['run_id'], frame['sequence']
        self.baseline[key] = {eq for eq in self.equipment if not inactive and any(
            c[0] == eq and c in values and value >= 3 for c, value in self.smoothed.items())}
        self.resets.append(not self.frames or inactive or self.ready[-1] != ready)
        self.frames.append(frame)
        self.raw.append(raw); self.ratios.append(ratio); self.signed.append(signed); self.ready.append(ready)
        if not inactive:
            self.history.append(actual)

    def report(self):
        from scripts import mes_timestral_tail_guarded as guarded
        tools = self.context['tools'].base.notice_module
        frame = self.frames[-1]
        base = dict(schema_version=1, run_id=frame['run_id'], config_id=self.context['config_id'],
                    sequence=frame['sequence'], input_at=frame['simulated_at'],
                    generated_at=datetime.now(timezone.utc).isoformat(), operational_notifications=False, items=[])
        if frame.get('line_mode') in tools.base.INACTIVE:
            return base | dict(status='inactive')
        if not self.ready[-1]:
            return base | dict(status='warming_up', window_fill=len(self.history))
        # shortcut: bounded full-prefix replay preserves research state exactly; use an incremental runner before long-lived deployment.
        data = dict(keys=[(f['run_id'], f['sequence']) for f in self.frames], raw_z=np.asarray(self.raw),
                    ratio=np.asarray(self.ratios), signed_z=np.asarray(self.signed), resets=self.resets,
                    baseline=self.baseline, equipment=self.equipment, channels=self.context['channels'],
                    observations=[dict(run=f['run_id'], sequence=f['sequence'], at=f['simulated_at'],
                                       inactive=f.get('line_mode') in tools.base.INACTIVE) for f in self.frames])
        preserve = tools.previous.preserve.predict(data, tools.previous.previous.CURRENT)
        full = tools.previous.predict(data, preserve, self.context['fast_params'])
        current = self.context['tools'].base.symptom.previous.evidence.previous.predict(data, full, self.context['current_params'])
        floor, _ = self.context['tools'].base.symptom.previous.predict_and_notify(data, current)
        self.display, _ = self.context['tools'].base.add_early(data, floor, **self.context['source_params'])
        self.notices = guarded.notifications(data, self.display, floor, self.context['notice_params'])
        key = data['keys'][-1]
        for eq in self.equipment:
            notices = [i for i, k in enumerate(data['keys']) if eq in self.notices[k]]
            last_notice = notices[-1] if notices else None
            active = eq in self.display[key]
            if not active and (last_notice is None or frame['sequence'] - self.frames[last_notice]['sequence'] > 30):
                continue
            index = len(self.frames) - 1 if active else last_notice
            candidates = sorted([i for i, c in enumerate(self.context['channels']) if c[0] == eq and np.isfinite(self.signed[index][i])],
                                key=lambda i: abs(self.signed[index][i]), reverse=True)[:2]
            source = self.frames[index]
            notice_seq = self.frames[last_notice]['sequence'] if last_notice is not None else source['sequence']
            base['items'].append(dict(equipment_id=eq, event_id=f"{frame['run_id']}:{notice_seq}:{eq}",
                                      sequence=source['sequence'], observed_at=source['simulated_at'],
                                      state='active' if active else 'recent', signals=[
                                          dict(signal=self.context['channels'][i][1], direction='high' if self.signed[index][i] >= 0 else 'low') for i in candidates]))
        return base | dict(status='ready')


def write_result(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mes-url', default='http://127.0.0.1:8000')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--max-frames', type=int, default=3600)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if urlparse(args.mes_url).hostname not in {'127.0.0.1', 'localhost', '::1'} or not 65 <= args.max_frames <= 3600:
        parser.error('this bridge supports localhost and 65..3600 frames per analysis session')
    context = load_context()
    import torch
    from timestral import TimestralForecaster
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    model = TimestralForecaster.from_pretrained(context['checkpoint'], device='cpu', local_files_only=True)
    def forecast(values):
        with torch.inference_mode():
            result = model.forecast(values[None], prediction_length=1)
            return np.stack([result.quantile(q).detach().cpu().numpy()[0, :, 0] for q in (.01, .5, .99)], axis=-1)
    detector = None
    last_progress = time.monotonic()
    def get(path):
        with urlopen(args.mes_url.rstrip('/') + path, timeout=8) as response:
            return json.load(response)
    while True:
        state = None
        try:
            state = get('/api/state')
            if state.get('is_synthetic') is not True or state['config_id'] != context['config_id']:
                raise ValueError('synthetic sensor configuration differs from the frozen model')
            if detector is None or detector.frames and detector.frames[-1]['run_id'] != state['run_id']:
                detector = Detector(context, forecast, limit=args.max_frames)
                last_progress = time.monotonic()
            cursor = detector.frames[-1]['sequence'] if detector.frames else -1
            batch = get(f"/api/runs/{state['run_id']}/replay?sequence={cursor}")
            if batch.get('config_id') != context['config_id']:
                raise ValueError('replay configuration differs')
            for frame in batch['snapshots']:
                if frame['run_id'] != state['run_id']:
                    raise ValueError('replay run differs')
                detector.feed(frame)
                last_progress = time.monotonic()
                # Keep the file visibly non-ready during slow catch-up inference.
                if state['sequence'] - frame['sequence'] > 3:
                    write_result(args.out, dict(schema_version=1, status='catching_up', run_id=state['run_id'],
                                               config_id=context['config_id'], sequence=frame['sequence'], input_at=frame['simulated_at'],
                                               generated_at=datetime.now(timezone.utc).isoformat(), operational_notifications=False, items=[]))
            if detector.frames:
                result = detector.report()
                if time.monotonic() - last_progress > 10:
                    result.update(status='stale', items=[])
                write_result(args.out, result)
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            status = 'session_limit' if isinstance(error, SessionLimit) else 'model_error'
            print(f'AI insights: {type(error).__name__}: {error}', file=sys.stderr, flush=True)
            if state:
                write_result(args.out, dict(schema_version=1, status=status, run_id=state['run_id'], config_id=context['config_id'],
                                           sequence=state['sequence'], input_at=state['simulated_at'],
                                           generated_at=datetime.now(timezone.utc).isoformat(), operational_notifications=False, items=[]))
            if args.once:
                raise
        if args.once:
            break
        time.sleep(1)


if __name__ == '__main__':
    main()
