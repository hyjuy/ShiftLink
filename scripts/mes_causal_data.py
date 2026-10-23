"""Isolated localhost causal sensor MES and role-separated dataset writer."""
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
from pathlib import Path
import random
import threading
from urllib.request import Request, urlopen

import numpy as np

from scripts.mes_causal_schema import metadata, signals, MANUAL
from scripts.mes_causal_source import SourceDynamics
from scripts.mes_causal_challenge import ChallengeDynamics

ROLES = {'fit': (8, 320), 'selection': (4, 320), 'calibration': (4, 320), 'development': (4, 320),
         'test_id': (6, 384), 'test_dynamics': (6, 384), 'test_mechanism': (6, 384), 'test_joint': (6, 384)}
INACTIVE = {'stopped', 'paused', 'recovering', 'quality_hold'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


class Session:
    def __init__(self, family, seed, run_id, events, pauses=False):
        if family not in ('A', 'B'):
            raise ValueError('unknown normal dynamics family')
        self.dynamics = (SourceDynamics if family == 'A' else ChallengeDynamics)(seed)
        self.run_id, self.events, self.pauses = run_id, events, pauses
        self.sequence = -1
        self.samples, self.latest = {}, None
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def advance(self):
        self.sequence += 1
        t = self.sequence
        at = (self.start + timedelta(seconds=t)).isoformat()
        values = self.dynamics.step(t, self.events)
        mode = 'paused' if self.pauses and 170 <= t < 182 else 'running'
        measurements = []
        for j, (key, spec) in enumerate(signals().items()):
            eq, name = key
            value, observed, quality = values[key], at, 'good'
            if name in MANUAL:
                if key not in self.samples or t % 30 == j % 30:
                    self.samples[key] = value, at
                value, observed = self.samples[key]
            if name == 'rt_lift_delay':
                value, quality = 0., 'unavailable'
            if mode != 'running' and any(token in name for token in ('speed', 'rpm', 'current')):
                value = 0.
            if t > 0 and (t + j * 13) % 113 == 0:
                quality = 'bad'
            measurements.append(dict(equipment_id=eq, signal=name, unit=spec['unit'], value=round(value, 8),
                                     quality=quality, observed_at=observed))
        self.latest = dict(run_id=self.run_id, sequence=t, simulated_at=at, line_mode=mode,
                           is_synthetic=True, config_id=metadata()['config_id'], measurements=measurements,
                           equipment=[dict(equipment_id=e['equipment_id'], operating_state=mode)
                                      for e in metadata()['equipment']])
        return self.latest

    def state(self):
        return self.latest


@contextmanager
def local_mes():
    """Dedicated sensor MES; production MES/PDA services are not touched."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, value, code=200):
            body = json.dumps(value, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/api/config':
                self.send_json(metadata())
            elif self.path == '/api/state':
                self.send_json(self.server.session.state())
            else:
                self.send_json({'error': 'unknown route'}, 404)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            if self.path == '/benchmark/reset':
                self.server.session = Session(**body)
                self.send_json({'reset': True})
            elif self.path == '/benchmark/step':
                self.send_json(self.server.session.advance())
            else:
                self.send_json({'error': 'unknown route'}, 404)

    server = HTTPServer(('127.0.0.1', 0), Handler)
    server.session = Session('A', 0, 'initial', [])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def schedule(role, index, seed):
    if role in ('fit', 'selection', 'calibration') or index == 0:
        return []
    held = role in ('test_mechanism', 'test_joint')
    drive = 'EQ-0004' if index % 2 else 'EQ-0005'
    utility = 'EQ-0001' if index % 2 else 'EQ-0003'
    sensor = [('EQ-0002', 'bus_voltage'), ('EQ-0006', 'rt_motor_current'), ('EQ-0007', 'rt_vib_rms'),
              ('EQ-0008', 'rt_clamp_press'), ('EQ-0009', 'cv_motor_current')][(index - 1) % 5]
    kinds = [('cooling_loss', drive, None), ('blockage', utility, None), ('sensor_stuck', *sensor)] if held else [
        ('friction', drive, None), ('leak', utility, None), ('sensor_bias', *sensor)]
    rng = random.Random(seed + 78)
    starts = (95, 100, 240) if index % 3 == 2 else (95, 165, 240)
    return [dict(event_id=f'event-{i}', kind=kind, equipment=eq, signal=signal, start=start,
                 end=start + rng.randint(32, 50), amplitude=rng.uniform(.7, 2.5))
            for i, ((kind, eq, signal), start) in enumerate(zip(kinds, starts))]


def generate_role(path, role, *, runs=None, ticks=None, lock=None):
    path = Path(path)
    if role.startswith('test') and (lock is None or not Path(lock).is_file()):
        raise ValueError('test generation requires a frozen candidate lock')
    if role.startswith('test'):
        fixed = json.loads(Path(lock).read_text(encoding='utf-8'))
        if fixed.get('status') != 'frozen_before_test':
            raise ValueError('candidate is not frozen')
        for file, digest in fixed['files'].items():
            if sha(file) != digest:
                raise ValueError('frozen candidate changed: ' + file)
    run_count, frame_count = ROLES[role]
    runs, ticks = runs or run_count, ticks or frame_count
    path.mkdir(parents=True, exist_ok=False)
    role_index = list(ROLES).index(role)
    family = 'B' if role in ('test_dynamics', 'test_joint') else 'A'
    ledger, entries = {}, []
    with local_mes() as server, (path / 'features.jsonl').open('x', encoding='utf-8') as target:
        base = 'http://127.0.0.1:' + str(server.server_address[1])
        def post(route, payload):
            with urlopen(Request(base + route, json.dumps(payload).encode(), method='POST'), timeout=30) as response:
                return json.load(response)
        for i in range(runs):
            seed = 701000 + role_index * 1000 + i
            run_id = hashlib.sha256(f'causal-v8:{seed}'.encode()).hexdigest()[:32]
            events = schedule(role, i, seed)
            ledger[run_id] = events
            post('/benchmark/reset', dict(family=family, seed=seed, run_id=run_id, events=events, pauses=i % 6 == 1 and role not in ('fit', 'selection', 'calibration')))
            for _ in range(ticks):
                frame = post('/benchmark/step', {})
                target.write(json.dumps(frame, separators=(',', ':'), allow_nan=False) + '\n')
            with urlopen(base + '/api/state') as response:
                assert json.load(response) == frame
            entries.append(dict(run_id=run_id, seed=seed, nonce=f'causal-v8-{seed}', frames=ticks))
    write_new(path / 'events.private.json', ledger)
    write_new(path / 'manifest.json', dict(role=role, family=family, is_synthetic=True, runs=entries,
                                         generator_files={name: sha(Path(__file__).with_name(name)) for name in (
                                             'mes_causal_data.py', 'mes_causal_schema.py', 'mes_causal_source.py', 'mes_causal_challenge.py')},
                                         features_sha256=sha(path / 'features.jsonl'),
                                         ledger_sha256=sha(path / 'events.private.json'),
                                         candidate_lock_sha256=sha(lock) if lock else None,
                                         transport='localhost HTTP POST step / GET state, one simulated second per step'))
    return entries


def read_role(path):
    path = Path(path)
    manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    if sha(path / 'features.jsonl') != manifest['features_sha256']:
        raise ValueError('features changed')
    runs = {r['run_id']: [] for r in manifest['runs']}
    with (path / 'features.jsonl').open(encoding='utf-8') as source:
        for line in source:
            frame = json.loads(line)
            rows = runs[frame['run_id']]
            if frame['sequence'] != len(rows):
                raise ValueError('nonconsecutive sequence')
            if len(frame['measurements']) != 69 or {(m['equipment_id'], m['signal']) for m in frame['measurements']} != signals().keys():
                raise ValueError('signal contract mismatch')
            rows.append(frame)
    if any(len(runs[r['run_id']]) != r['frames'] for r in manifest['runs']):
        raise ValueError('incomplete run')
    return runs, manifest


def valid_values(frame, specs=None):
    values, seen = {}, set()
    for m in frame['measurements']:
        key = m['equipment_id'], m['signal']
        if key in seen:
            raise ValueError('duplicate measurement')
        seen.add(key)
        if specs is not None and (key not in specs or m['unit'] != specs[key]['unit']):
            continue
        v = m.get('value')
        if m.get('quality') == 'good' and m.get('observed_at') == frame['simulated_at'] and isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v):
            values[key] = float(v)
    return values


def windows(runs, channels):
    inputs, keys, targets = [], [], []
    for run, frames in runs.items():
        history = deque(maxlen=64)
        previous = None
        for frame in frames:
            if previous is not None and frame['sequence'] != previous + 1:
                history.clear()
            previous = frame['sequence']
            if frame['line_mode'] in INACTIVE:
                history.clear()
                continue
            current = valid_values(frame)
            actual = [current.get(c, np.nan) for c in channels]
            if len(history) == 64:
                inputs.append(np.asarray(history, dtype=np.float32).T)
                keys.append((run, frame['sequence']))
                targets.append(actual)
            history.append(actual)
    return np.asarray(inputs, dtype=np.float32), keys, np.asarray(targets, dtype=np.float32)
