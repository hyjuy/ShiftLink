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
from shiftlink.pda.ai_insights import fault_stopped_equipment, valid_stop_notice

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
        self.fingerprint = digest(dict(settings=settings, source=self.source_digest, version=2,
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
        if set(states) != {e for e,s in self.canonical}:raise ValueError('source equipment states required')
        measurements = [dict(found[k], quality='inactive') if states.get(k[0], 'running') != 'running' else found[k] for k in self.canonical]
        return dict(frame, config_id=self.config_id, measurements=measurements,
                    line_mode='quality_hold' if frame['line_mode']=='fault' else frame['line_mode'])


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
        self.stopped_notices = {}; self.stop_dirty = False
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
            d.last_status = dict(accepted=False, ready=d.was_ready,hold=state.get('last_hold',False))
            if type(d.last_status['hold']) is not bool:raise ValueError('checkpoint hold flag invalid')
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
            stopped=saved.get('stopped_notices',{})
            if not isinstance(stopped,dict) or not set(stopped)<=set(d.equipment):raise ValueError('checkpoint stopped equipment')
            for eq,row in stopped.items():
                if (row.get('equipment_id')!=eq or row.get('state')!='before_stop' or not valid_stop_notice(row,d.sequence)
                        or row.get('event_id')!=f"{d.run}:{row['sequence']}:{eq}"):
                    raise ValueError('checkpoint stopped notice invalid')
            self.stopped_notices=stopped
            self.detector = d; self.cursor = d.sequence if d.sequence is not None else -1; self.run = d.run; self.notices = notices
        except (KeyError, TypeError, AttributeError, OverflowError) as e:
            raise ValueError('invalid checkpoint') from e

    def flush(self):
        d = self.detector
        state = dict(run=d.run, sequence=d.sequence, at=d.at.isoformat() if d.at else None,
                     warm=d.warm, was_ready=d.was_ready,last_hold=bool(d.last_status.get('hold',False)),previous_raw=packed(d.previous_raw),
                     ewma=packed(d.ewma), ewma_valid=d.ewma_valid.tolist())
        for name in ('median','flat','thermal_history'): state[name] = [packed(row) for row in getattr(d,name)]
        state['machines'] = [{name:getattr(m,name).tolist() for name in ('on','high','low','process_sources','flat_sources')} for m in d.machines]
        atomic_json(self.journal,dict(binding=self.binding.fingerprint,detector=state,notices=self.notices,stopped_notices=self.stopped_notices))
        self.since_save = 0; self.stop_dirty = False

    def sync_stop(self, state):
        if state['run_id']!=self.run or state['sequence'] not in (self.cursor,self.cursor+1):return
        stopped=fault_stopped_equipment(state)
        held={e:r for e,r in self.stopped_notices.items() if e in stopped}
        for eq,row in self.notices.items():
            if eq in stopped and eq not in held and 0 <= state['sequence']-row['sequence'] <= 30:
                held[eq]=dict(row,state='before_stop',stop_sequence=state['sequence'],stopped_at=state['simulated_at'])
        if held!=self.stopped_notices:self.stopped_notices=held;self.stop_dirty=True

    def feed(self, frame, config_id):
        source=frame
        frame = self.binding.adapt(frame,config_id)
        notices = self.detector.step(frame)
        if not self.detector.last_status['accepted']: return set()
        if self.detector.last_status['discontinuity']:
            self.notices.clear()
            if self.stopped_notices:self.stopped_notices.clear();self.stop_dirty=True
        else:self.sync_stop(source)
        self.run,self.cursor = frame['run_id'],frame['sequence']
        if self.detector.last_status['discontinuity'] or frame['line_mode'] != 'running': self.notices.clear()
        for eq in notices:
            self.notices[eq] = dict(equipment_id=eq,event_id=f"{self.run}:{self.cursor}:{eq}",sequence=self.cursor,
                                   observed_at=frame['simulated_at'],state='recent',signals=[])
        self.since_save += 1
        # A notice is durable before publication; otherwise replay at most 29 frames.
        if not self.defer_flush and (notices or self.stop_dirty or self.since_save >= 30): self.flush()
        return notices

    def report(self, state, *, stalled=False):
        base = dict(schema_version=1,run_id=state['run_id'],config_id=self.binding.config_id,
                    sequence=max(0,self.cursor),input_at=self.detector.at.isoformat() if self.detector.at else state['simulated_at'],
                    generated_at=datetime.now(timezone.utc).isoformat(),operational_notifications=False,items=[])
        held=[dict(r) for e,r in self.stopped_notices.items() if state['run_id']==self.run and e in fault_stopped_equipment(state)]
        history=base | dict(status='stopped',items=held) if held else None
        if state['line_mode'] != 'running': return history or (base | dict(status='inactive'))
        if stalled: return base | dict(status='stale')
        if state['run_id'] != self.run: return base | dict(status='warming_up')
        if state['sequence']-self.cursor > 3: return base | dict(status='catching_up')
        if not self.detector.was_ready: return history or (base | dict(status='warming_up'))
        if self.detector.last_status.get('hold') or (self.detector.previous_raw is not None and not np.isfinite(self.detector.previous_raw[self.detector.variable]).any()):
            return history or (base | dict(status='unavailable'))
        running={e['equipment_id'] for e in state.get('equipment',[]) if e.get('operating_state')=='running'}
        return base | dict(status='ready',items=held+[dict(r) for e,r in self.notices.items() if e in running and 0 <= self.cursor-r['sequence'] <= 30])


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
        meta={};noticed=False;session.defer_flush=True
        try:
            for kind,value in replay_stream(base,f"/api/runs/{quote(state['run_id'],safe='')}/replay?sequence={cursor}"):
                if kind=='meta':meta.update([value]);continue
                frame=value
                if cursor == -1 and frame['sequence']==1:cursor=0  # MES stores ticks from 1; no observation 0 is skipped.
                if frame['run_id']!=state['run_id'] or frame['sequence']!=cursor+1:raise ValueError('replay missing or out of order')
                noticed=bool(session.feed(frame,session.binding.config_id)) or noticed;cursor=frame['sequence']
            if meta.get('config_id')!=session.binding.config_id or meta.get('config_preserved') is not True or meta.get('is_synthetic') is not True:
                raise ValueError('unapproved replay provenance')
            if cursor<state['sequence']:raise ValueError('replay incomplete; no advance past missing frame')
            if noticed or session.stop_dirty or session.since_save>=30:session.flush()
        except BaseException:
            # A bad/truncated trailer cannot commit speculative frames or notices.
            restored=AdvisorySession(session.binding,session.journal)
            session.__dict__.update(restored.__dict__)
            raise
        finally:session.defer_flush=False
    session.sync_stop(state)
    if state['line_mode']!='running' and session.detector.warm:
        session.detector._restart();session.notices.clear();session.flush()
    if session.stop_dirty:session.flush()
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
                poll_started=time.monotonic();result=poll(session,args.mes_url,state)
                result['poll_seconds']=time.monotonic()-poll_started
                result['processed_sequence']=session.cursor
                result['model']='statistical-v14c';result['torch_loaded']='torch' in sys.modules;result['timestral_loaded']='timestral' in sys.modules
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






class _JsonStream:
    """At most one bounded JSON value, not the accumulated run, is buffered."""
    def __init__(self,response):
        import codecs
        self.response=response;self.buffer='';self.position=0;self.eof=False
        self.utf8=codecs.getincrementaldecoder('utf-8')();self.decoder=json.JSONDecoder()

    def more(self):
        self.buffer=self.buffer[self.position:];self.position=0
        raw=self.response.read(64*1024)
        self.eof=not raw
        self.buffer+=self.utf8.decode(raw,final=self.eof)

    def peek(self):
        while True:
            while self.position<len(self.buffer) and self.buffer[self.position].isspace():self.position+=1
            if self.position<len(self.buffer):return self.buffer[self.position]
            if self.eof:return None
            self.more()

    def take(self,char):
        if self.peek()!=char:raise ValueError('malformed/truncated replay JSON')
        self.position+=1

    def value(self):
        if self.peek() is None:raise ValueError('truncated replay value')
        while True:
            try:
                value,end=self.decoder.raw_decode(self.buffer,self.position)
                if end<len(self.buffer) or self.eof:
                    self.position=end;return value
            except json.JSONDecodeError:
                if self.eof:raise ValueError('truncated replay value')
            if len(self.buffer)-self.position>2*1024*1024:raise ValueError('oversized individual replay value')
            self.more()


def iter_replay(response):
    stream=_JsonStream(response);stream.take('{');seen=set()
    while stream.peek()!='}':
        if seen:stream.take(',')
        key=stream.value()
        if not isinstance(key,str) or key in seen:raise ValueError('duplicate/invalid replay field')
        seen.add(key);stream.take(':')
        if key in ('snapshots','events'):
            stream.take('[');first=True
            while stream.peek()!=']':
                if not first:stream.take(',')
                value=stream.value();first=False
                if key=='snapshots':yield 'frame',value
            stream.take(']')
        else:yield 'meta',(key,stream.value())
    stream.take('}')
    if stream.peek() is not None:raise ValueError('extra replay document')
    if 'snapshots' not in seen:raise ValueError('replay snapshots required')


def replay_stream(base,path):
    with urlopen(base+path,timeout=8) as response:
        yield from iter_replay(response)


if __name__=='__main__':main()
