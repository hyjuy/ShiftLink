"""Bounded Pi advisory transport and query-time MES validation; never a KB source."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 16 * 1024
STATUSES = {'ready', 'warming_up', 'inactive', 'catching_up', 'unavailable', 'model_error',
            'session_limit', 'stale', 'disabled', 'stopped'}


def attach_to_query(body, path):
    """Read the current local result on each question; replace any browser-supplied copy."""
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            return body
        payload.pop('pi_analysis', None)
        try:
            if path is not None:
                with Path(path).open('rb') as source:
                    raw = source.read(MAX_BYTES + 1)
                if len(raw) <= MAX_BYTES:
                    data = json.loads(raw)
                    if isinstance(data, dict) and type(data.get('schema_version')) is int and data['schema_version'] == 1:
                        # Also reject nonstandard NaN/Infinity before crossing the HTTP boundary.
                        json.dumps(data, allow_nan=False)
                        payload['pi_analysis'] = data
        except (OSError, ValueError, TypeError, RecursionError):
            pass
        return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError):
        return body


def _instant(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError('timestamp must include timezone')
    return value


def validate_context(data, snapshot, config_id, equipment_id, *, now=None):
    """Accept only a fresh result for this captured MES run/config and selected unit."""
    try:
        if not isinstance(data, dict) or len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode()) > MAX_BYTES:
            return None
        if (type(data.get('schema_version')) is not int or data['schema_version'] != 1
                or data.get('status') not in STATUSES or data.get('operational_notifications') is not False
                or data.get('run_id') != snapshot['run_id'] or data.get('config_id') != config_id
                or not isinstance(data.get('items'), list)):
            return None
        generated, input_at = _instant(data['generated_at']), _instant(data['input_at'])
        age = ((now or datetime.now(timezone.utc)) - generated).total_seconds()
        sequence = data['sequence']
        if not -5 <= age <= 10 or type(sequence) is not int or not 0 <= snapshot['sequence'] - sequence <= 3 or sequence < 0:
            return None
        if (_instant(snapshot['simulated_at']) - input_at).total_seconds() != snapshot['sequence'] - sequence:
            return None
        equipment = next((e for e in snapshot['equipment'] if e['equipment_id'] == equipment_id), None)
        if equipment is None:
            return None
        status = data['status']
        if status == 'ready' and snapshot['line_mode'] != 'running':
            status = 'inactive'
        context = dict(source='pi_analytics', equipment_id=equipment_id, run_id=snapshot['run_id'],
                       config_id=config_id, sequence=sequence, input_at=input_at.isoformat(),
                       generated_at=generated.isoformat(), snapshot_at=_instant(snapshot['simulated_at']).isoformat(),
                       snapshot_sequence=snapshot['sequence'], line_mode=snapshot['line_mode'],
                       equipment_state=equipment['operating_state'], status=status, items=[])
        model = data.get('model')
        if isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}', model):
            context['model'] = model
        known_signals = {m['signal'] for m in snapshot['measurements'] if m['equipment_id'] == equipment_id}
        for row in data['items']:
            if not isinstance(row, dict) or row.get('equipment_id') != equipment_id:
                continue
            try:
                seq = row['sequence']
                if (type(seq) is not int or not 0 <= seq <= sequence
                        or row.get('event_id') != f"{snapshot['run_id']}:{seq}:{equipment_id}"
                        or (input_at - _instant(row['observed_at'])).total_seconds() != sequence - seq):
                    continue
                item = dict(equipment_id=equipment_id, event_id=row['event_id'], sequence=seq,
                            observed_at=_instant(row['observed_at']).isoformat(), state=row['state'], signals=[])
                if row['state'] == 'before_stop':
                    stop = row['stop_sequence']
                    # Match the Pi r5 retention contract without labelling a manual pause as a fault.
                    retained = (snapshot['line_mode'] in {'paused','stopped'} or
                                equipment['operating_state'] in {'stopped','waiting'} and (
                                    snapshot['line_mode'] == 'fault' or
                                    snapshot['line_mode'] == 'running' and equipment['operating_state'] == 'stopped' or
                                    equipment.get('fault_level') in {'warning','critical','fault'} or
                                    any(a['equipment_id'] == equipment_id for a in snapshot['active_alarms'])))
                    if (status not in {'ready','stopped'} or not retained
                            or type(stop) is not int or not seq <= stop <= sequence or stop - seq > 30
                            or (_instant(row['stopped_at']) - _instant(row['observed_at'])).total_seconds() != stop - seq):
                        continue
                    item.update(stop_sequence=stop, stopped_at=_instant(row['stopped_at']).isoformat())
                elif (row['state'] not in {'active','recent'} or status != 'ready'
                      or equipment['operating_state'] != 'running' or sequence - seq > 30):
                    continue
                signals = row.get('signals', [])
                if isinstance(signals, list):
                    item['signals'] = [dict(signal=s['signal'], direction=s['direction']) for s in signals
                                       if isinstance(s, dict) and isinstance(s.get('signal'), str)
                                       and s['signal'] in known_signals and s.get('direction') in {'low','high'}][:2]
                context['items'].append(item)
                break
            except (ValueError, TypeError, KeyError):
                continue
        return context
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return None


def prompt_block(context):
    if not context:
        return ''
    return ('[Pi 분석 참고]\n질의 시점에 검증한 통계 분석입니다. generated_at은 분석 생성 시각, '
            'input_at/observed_at은 MES 입력·징후 시각입니다. status·line_mode·equipment_state를 함께 보세요. '
            '최근/정지 전 징후는 현재 활성 고장으로 해석하지 마세요. 고장 확정이나 작업 승인을 뜻하지 않으며, '
            '알림 없음·분석 비활성은 정상의 증거가 아닙니다. 현재 센서와 지식카드를 우선하고 불일치는 명시하세요. '
            '이 블록은 지식카드·관측값·인용 출처가 아니며 기존 인용 규칙과 근거 부족 시 보류를 유지하세요.\n'
            + json.dumps(context, ensure_ascii=False, allow_nan=False))
