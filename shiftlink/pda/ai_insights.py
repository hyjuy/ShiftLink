"""Read an optional local advisory result without changing MES observations."""
import json
from datetime import datetime, timezone
from pathlib import Path

VALIDATION = '합성 데이터 검증 완료 · 현장 검증 전'
DISCLAIMER = '고장 확정이 아닌 점검 참고 정보입니다.'
STATUSES = {'ready', 'warming_up', 'inactive', 'catching_up', 'unavailable', 'model_error', 'session_limit', 'stale', 'disabled', 'stopped'}


def stopped_equipment_for_retention(snapshot):
    # Pause is a line control change; its last equipment states may still say running.
    if snapshot.get('line_mode') in {'paused','stopped'}:
        return {e['equipment_id'] for e in snapshot.get('equipment', [])}
    alarms={a.get('equipment_id') for a in snapshot.get('active_alarms', [])}
    return {e['equipment_id'] for e in snapshot.get('equipment', [])
            if e.get('operating_state') in {'stopped', 'waiting'} and
            ((snapshot.get('line_mode')=='running' and e.get('operating_state')=='stopped') or
             snapshot.get('line_mode')=='fault' or e['equipment_id'] in alarms or
             e.get('fault_level') in {'warning', 'critical', 'fault'})}


def valid_stop_notice(row, sequence):
    stop=row.get('stop_sequence')
    checked=row.get('confirmed_sequence',row.get('sequence'))
    checked_at=row.get('confirmed_at',row.get('observed_at'))
    try:
        at=datetime.fromisoformat(row['observed_at']);stopped=datetime.fromisoformat(row['stopped_at'])
        confirmed=datetime.fromisoformat(checked_at)
        return (type(stop) is int and type(row['sequence']) is int and
                type(checked) is int and 0 <= row['sequence'] <= checked <= stop <= sequence and stop-checked <= 30 and
                confirmed.utcoffset() is not None and (confirmed-at).total_seconds()==checked-row['sequence'] and
                at.utcoffset() is not None and stopped.utcoffset() is not None and
                (stopped-at).total_seconds()==stop-row['sequence'])
    except (KeyError,TypeError,ValueError):return False


def read_insights(path, snapshot, config_id, *, now=None):
    base = dict(status='disabled', items=[], operational_notifications=False,
                validation=VALIDATION, disclaimer=DISCLAIMER)
    if path is None:
        return base
    base['status'] = 'unavailable'
    try:
        path = Path(path)
        if path.stat().st_size > 256 * 1024:
            return base
        with path.open(encoding='utf-8') as source:
            data = json.load(source)
        if (data.get('schema_version') != 1 or data.get('status') not in STATUSES
                or data.get('operational_notifications') is not False):
            return base
        generated = datetime.fromisoformat(data['generated_at'])
        age = ((now or datetime.now(timezone.utc)) - generated).total_seconds()
        if age < -5:
            return base
        if age > 10:
            return base | dict(status='stale')
        if data.get('config_id') != config_id:
            return base
        if data.get('run_id') != snapshot['run_id']:
            return base | dict(status='warming_up')
        sequence = data['sequence']
        if type(sequence) is not int or sequence > snapshot['sequence'] or sequence < 0:
            return base
        base.update(run_id=data['run_id'], config_id=config_id, sequence=sequence,
                    input_at=data['input_at'], generated_at=data['generated_at'])
        lag = snapshot['sequence'] - sequence
        if (datetime.fromisoformat(snapshot['simulated_at']) - datetime.fromisoformat(data['input_at'])).total_seconds() != lag:
            return base
        if lag > 3:
            return base | dict(status='catching_up')
        stopped=stopped_equipment_for_retention(snapshot)
        if snapshot['line_mode'] in {'paused', 'stopped', 'recovering', 'quality_hold', 'fault'} and data['status']!='stopped':
            return base | dict(status='inactive')
        base['status'] = data['status']
        if base['status'] not in {'ready','stopped'}:
            return base
        equipment = {row['equipment_id'] for row in snapshot['equipment']}
        seen = set()
        for row in data.get('items', []):
            eq = row.get('equipment_id')
            if eq not in equipment or eq in seen or row.get('state') not in {'active', 'recent', 'before_stop'}:
                continue
            if (not isinstance(row.get('event_id'), str) or type(row.get('sequence')) is not int
                    or not 0 <= row['sequence'] <= sequence or not isinstance(row.get('observed_at'), str)):
                continue
            retained=row['state']=='before_stop'
            if retained:
                if eq not in stopped or not valid_stop_notice(row,sequence):continue
            elif base['status']!='ready' or snapshot['line_mode']!='running':continue
            signals = [dict(signal=s['signal'], direction=s['direction']) for s in row.get('signals', [])
                       if isinstance(s, dict) and isinstance(s.get('signal'), str) and s.get('direction') in {'low', 'high'}][:2]
            seen.add(eq)
            base['items'].append(dict(equipment_id=eq, event_id=row['event_id'], sequence=row['sequence'],
                                      observed_at=row['observed_at'], state=row['state'], signals=signals))
            if retained:base['items'][-1].update(stop_sequence=row['stop_sequence'],stopped_at=row['stopped_at'])
            if 'confirmed_sequence' in row or 'confirmed_at' in row:
                base['items'][-1].update(confirmed_sequence=row.get('confirmed_sequence'),confirmed_at=row.get('confirmed_at'))
        return base
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return base | dict(status='unavailable', items=[])


def overlay_state(state, path):
    """Only ai_insights is Pi-owned. Missing opt-in file preserves the response."""
    if path is None or not Path(path).exists():
        return state
    return dict(state, ai_insights=read_insights(path, state, state.get('config_id')))


def overlay_response(body, path):
    try:
        state = json.loads(body)
        if not isinstance(state, dict):
            return body
        return json.dumps(overlay_state(state, path), ensure_ascii=False).encode()
    except (ValueError, TypeError):
        return body
