"""Pinned MES source -> bounded statistical analysis -> silent PDA advisory.

No MES writes, alarm acknowledgement or haptic calls. The source configuration
and frozen settings are validated before accepting any replay frames.
"""
import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sys
import threading
import time
from urllib.parse import quote, urlparse
from urllib.request import urlopen

import numpy as np
from scripts.mes_causal_schema import ROOT, metadata, signals
from scripts.mes_causal_v14_stream import OnlineDetector

SETTINGS_SHA256 = 'e8cea07e615f1e21d4ab472554d42348d903c8df027c69a49f226b3211f3d789'
MAX_RESPONSE = 16 * 1024 * 1024


def config_digest(config):
    return hashlib.sha256(json.dumps(dict(config, config_id='placeholder'), sort_keys=True,
                                    ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(temp, 0o600)
    temp.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try: os.fsync(fd)
    finally: os.close(fd)


class BoundSource:
    def __init__(self, settings, source_config):
        self.config_id = source_config['config_id']
        if config_digest(source_config) != self.config_id:
            raise ValueError('source config hash mismatch')
        self.source_digest = digest(source_config)
        self.settings = settings
        self.canonical = list(signals())
        found = {}
        for eq in source_config['equipment']:
            for spec in eq['signals']:
                key = eq['equipment_id'], spec['signal']
                if key in found: raise ValueError('duplicate configured source channel')
                found[key] = spec
        if set(found) != set(self.canonical): raise ValueError('source channel set mismatch')
        for key, reference in signals().items():
            if any(found[key].get(k) != reference[k] for k in ('unit', 'normal_min', 'normal_max')):
                raise ValueError('source units or range mismatch')
        self.fingerprint = digest(dict(settings=settings, source=self.source_digest, version=1,
            core_sha256=hashlib.sha256((ROOT / 'scripts/mes_causal_v14_stream.py').read_bytes()).hexdigest()))
        self.new_detector()

    def validate_config(self, config):
        if config.get('config_id') != self.config_id or config_digest(config) != self.config_id or digest(config) != self.source_digest:
            raise ValueError('source configuration differs from approved binding')

    def new_detector(self):
        detector = OnlineDetector(self.settings)
        # Approved transport contract only; thresholds and model schema stay frozen.
        detector.config_id = self.config_id
        return detector

    def adapt(self, frame, batch_config_id):
        if batch_config_id != self.config_id or frame.get('config_id', self.config_id) != self.config_id:
            raise ValueError('replay config mismatch')
        found = {}
        for m in frame['measurements']:
            key = m['equipment_id'], m['signal']
            if key in found: raise ValueError('duplicate replay channel')
            found[key] = m
        if set(found) != set(self.canonical): raise ValueError('replay channel set mismatch')
        states = {e['equipment_id']:e.get('operating_state') for e in frame.get('equipment', [])}
        measurements = [dict(found[k], quality='inactive') if states.get(k[0], 'running') != 'running' else found[k] for k in self.canonical]
        return dict(frame, config_id=self.config_id, measurements=measurements)


def packed(array):
    if array is None: return None
    return np.where(np.isfinite(array), array, None).tolist()


def unpack(value, shape, kind=float):
    flat = np.asarray(value, dtype=object)
    if flat.shape != shape: raise ValueError('checkpoint array shape mismatch')
    for v in flat.flat:
        if kind is bool:
            if type(v) is not bool: raise ValueError('checkpoint boolean required')
        elif kind is int:
            if type(v) is not int or v < 0: raise ValueError('checkpoint counter required')
        elif v is not None and (type(v) not in (int, float) or not math.isfinite(v)):
            raise ValueError('checkpoint finite value required')
    return np.asarray(value, dtype=kind)


class AdvisorySession:
    def __init__(self, binding, journal):
        self.binding, self.journal = binding, Path(journal)
        self.detector = binding.new_detector()
        self.notices = {}
        self.cursor, self.run, self.since_save = -1, None, 0
        self.defer_flush = False
        if self.journal.exists(): self._restore()

    def _restore(self):
        if self.journal.stat().st_size > 256 * 1024: raise ValueError('oversized checkpoint')
        try:
            saved = json.loads(self.journal.read_text())
            if saved['binding'] != self.binding.fingerprint: raise ValueError('checkpoint binding mismatch')
            d = self.binding.new_detector(); state = saved['detector']; n = len(d.channels)
            d.run, d.sequence = state['run'], state['sequence']
            d.at = datetime.fromisoformat(state['at']) if state['at'] else None
            if d.run is not None and (not isinstance(d.run, str) or type(d.sequence) is not int or d.sequence < 0 or d.at.utcoffset() is None):
                raise ValueError('checkpoint cursor invalid')
            if type(state['warm']) is not int or not 0 <= state['warm'] <= 64 or type(state['was_ready']) is not bool:
                raise ValueError('checkpoint readiness invalid')
            d.warm, d.was_ready = state['warm'], state['was_ready']
            d.last_status = dict(accepted=False, ready=d.was_ready)
            d.previous_raw = None if state['previous_raw'] is None else unpack(state['previous_raw'], (n,))
            d.ewma = unpack(state['ewma'], (n,)); d.ewma_valid = unpack(state['ewma_valid'], (n,), bool)
            for name, limit in [('median',5),('flat',16),('thermal_history',37)]:
                rows = state[name]
                if len(rows) > limit: raise ValueError('checkpoint history exceeds bound')
                setattr(d, name, deque([unpack(r, (n,)) for r in rows], maxlen=limit))
            if len(state['machines']) != 4: raise ValueError('checkpoint state machine count')
            for machine, values in zip(d.machines, state['machines']):
                for name, kind in [('on',bool),('high',int),('low',int),('process_sources',bool),('flat_sources',bool)]:
                    setattr(machine,name,unpack(values[name],getattr(machine,name).shape,kind))
                if np.any(machine.high > d.patience) or np.any(machine.low > 5): raise ValueError('checkpoint counter exceeds bound')
            notices = saved['notices']
            if not isinstance(notices, dict) or not set(notices) <= set(d.equipment): raise ValueError('checkpoint notice equipment')
            for eq, row in notices.items():
                if row['event_id'] != f"{d.run}:{row['sequence']}:{eq}" or type(row['sequence']) is not int or not 0 <= row['sequence'] <= d.sequence:
                    raise ValueError('checkpoint notice identity')
            self.detector = d; self.cursor = d.sequence if d.sequence is not None else -1; self.run = d.run; self.notices = notices
        except (KeyError, TypeError, AttributeError, OverflowError) as e:
            raise ValueError('invalid checkpoint') from e

    def flush(self):
        d = self.detector
        state = dict(run=d.run, sequence=d.sequence, at=d.at.isoformat() if d.at else None,
                     warm=d.warm, was_ready=d.was_ready, previous_raw=packed(d.previous_raw),
                     ewma=packed(d.ewma), ewma_valid=d.ewma_valid.tolist())
        for name in ('median','flat','thermal_history'): state[name] = [packed(row) for row in getattr(d,name)]
        state['machines'] = [{name:getattr(m,name).tolist() for name in ('on','high','low','process_sources','flat_sources')} for m in d.machines]
        atomic_json(self.journal,dict(binding=self.binding.fingerprint,detector=state,notices=self.notices))
        self.since_save = 0

    def feed(self, frame, config_id):
        frame = self.binding.adapt(frame,config_id)
        notices = self.detector.step(frame)
        if not self.detector.last_status['accepted']: return set()
        self.run,self.cursor = frame['run_id'],frame['sequence']
        if self.detector.last_status['discontinuity'] or frame['line_mode'] != 'running': self.notices.clear()
        for eq in notices:
            self.notices[eq] = dict(equipment_id=eq,event_id=f"{self.run}:{self.cursor}:{eq}",sequence=self.cursor,
                                   observed_at=frame['simulated_at'],state='recent',signals=[])
        self.since_save += 1
        # A notice is durable before publication; otherwise replay at most 29 frames.
        if not self.defer_flush and (notices or self.since_save >= 30): self.flush()
        return notices

    def report(self, state, *, stalled=False):
        base = dict(schema_version=1,run_id=state['run_id'],config_id=self.binding.config_id,
                    sequence=max(0,self.cursor),input_at=self.detector.at.isoformat() if self.detector.at else state['simulated_at'],
                    generated_at=datetime.now(timezone.utc).isoformat(),operational_notifications=False,items=[])
        if state['line_mode'] != 'running': return base | dict(status='inactive')
        if stalled: return base | dict(status='stale')
        if state['run_id'] != self.run: return base | dict(status='warming_up')
        if state['sequence']-self.cursor > 3: return base | dict(status='catching_up')
        if not self.detector.was_ready: return base | dict(status='warming_up')
        return base | dict(status='ready',items=[dict(r) for r in self.notices.values() if 0 <= self.cursor-r['sequence'] <= 30])


def get_json(base, path):
    with urlopen(base+path,timeout=8) as r:
        data=r.read(MAX_RESPONSE+1)
    if len(data)>MAX_RESPONSE: raise ValueError('replay exceeds bounded response; no frames were skipped')
    return json.loads(data)


def poll(session, base, state):
    if state.get('is_synthetic') is not True or state.get('config_id') != session.binding.config_id:
        raise ValueError('unapproved source state')
    cursor=session.cursor if state['run_id']==session.run else -1
    if state['sequence'] > cursor:
        batch=get_json(base,f"/api/runs/{quote(state['run_id'],safe='')}/replay?sequence={cursor}")
        if batch.get('config_id')!=session.binding.config_id or batch.get('config_preserved') is not True or batch.get('is_synthetic') is not True:
            raise ValueError('unapproved replay provenance')
        frames=batch['snapshots']
        if not isinstance(frames,list):raise ValueError('replay snapshots required')
        for frame in frames:
            if frame['run_id']!=state['run_id'] or frame['sequence']!=cursor+1:raise ValueError('replay missing or out of order')
            session.feed(frame,batch['config_id']);cursor=frame['sequence']
        if cursor<state['sequence']:raise ValueError('replay incomplete; no advance past missing frame')
    return session.report(state)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mes-url',required=True);p.add_argument('--source-config',type=Path,required=True)
    p.add_argument('--settings',type=Path,default=ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json')
    p.add_argument('--output',type=Path);p.add_argument('--state-dir',type=Path,required=True);p.add_argument('--once',action='store_true');args=p.parse_args()
    output=args.output or args.state_dir/'latest.json'
    url=urlparse(args.mes_url)
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        p.error('explicit MES origin without credentials required')
    if hashlib.sha256(args.settings.read_bytes()).hexdigest()!=SETTINGS_SHA256:raise ValueError('frozen settings hash mismatch')
    binding=BoundSource(json.loads(args.settings.read_text()),json.loads(args.source_config.read_text()))
    stop=threading.Event();signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
    session=None;state=None;progress=time.monotonic();last_key=None;checked=0
    try:
        while not stop.is_set():
            try:
                state=get_json(args.mes_url,'/api/state')
                if (args.state_dir/'STOP').exists():
                    atomic_json(output,dict(schema_version=1,status='disabled',operational_notifications=False,items=[],
                        run_id=state['run_id'],config_id=binding.config_id,sequence=state['sequence'],input_at=state['simulated_at'],generated_at=datetime.now(timezone.utc).isoformat()))
                    return
                if time.monotonic()-checked>60:
                    payload=get_json(args.mes_url,'/api/config')
                    if payload.get('is_synthetic') is not True:raise ValueError('synthetic source required')
                    binding.validate_config(payload['config']);checked=time.monotonic()
                if session is None:session=AdvisorySession(binding,args.state_dir/'checkpoint.json')
                key=state['run_id'],state['sequence']
                if key!=last_key:progress=time.monotonic();last_key=key
                result=poll(session,args.mes_url,state)
                if state['line_mode']=='running' and time.monotonic()-progress>10:result=session.report(state,stalled=True)
                atomic_json(output,result)
            except Exception as e:
                print(json.dumps(dict(event='analysis_error',error=type(e).__name__,detail=str(e)[:160])),file=sys.stderr,flush=True)
                if state:
                    result=dict(schema_version=1,status='model_error',operational_notifications=False,items=[],run_id=state['run_id'],
                        config_id=binding.config_id,sequence=state['sequence'],input_at=state['simulated_at'],generated_at=datetime.now(timezone.utc).isoformat())
                    atomic_json(output,result)
                if args.once:raise
                # Rebuild uncommitted in-memory progress from the last durable state.
                session=None
            if args.once:return
            stop.wait(1)
    finally:
        if session:session.flush()


if __name__=='__main__':main()


def iter_replay(response):
    raise NotImplementedError('bounded replay streaming is not implemented')
