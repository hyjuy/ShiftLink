"""Validation for PDA work reports; saved through the existing durable outbox."""
from datetime import datetime


def _text(value, label, limit=4000, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'{label}: 문자열 길이와 필수 입력을 확인해 주세요.')


def _ids(value, allowed, label, required=True):
    if not isinstance(value, list) or len(value) > len(allowed) or (required and not value):
        raise ValueError(f'{label}: 대상 설비를 확인해 주세요.')
    if any(not isinstance(item, str) or item not in allowed for item in value) or len(set(value)) != len(value):
        raise ValueError(f'{label}: 대상에 없는 설비 또는 중복 설비입니다.')
    return set(value)


def validate(body, known_ids):
    if not isinstance(body, dict) or body.get('kind') != 'work_log' or 'resolution' in body:
        raise ValueError('근무일지 요청 형식을 확인해 주세요.')
    targets = _ids(body.get('equipment_ids'), known_ids, '일지')
    expected = next(iter(targets)) if len(targets) == 1 else None
    if body.get('equipment_id') != expected:
        raise ValueError('일지 대상 설비가 일치하지 않습니다.')
    context = body.get('required_context')
    if not isinstance(context, dict):
        raise ValueError('근무정보를 확인해 주세요.')
    _text(context.get('author'), '작성자', 100, True)
    for key in ('start_at', 'end_at'):
        _text(context.get(key), '근무시간', 40, True)
    try:
        start, end = (datetime.fromisoformat(context[key]) for key in ('start_at', 'end_at'))
        if end < start:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('근무 시작·종료 시간을 확인해 주세요.') from None
    report = body.get('work_report')
    if not isinstance(report, dict) or not isinstance(report.get('records'), list) or len(report['records']) > 50:
        raise ValueError('근무일지 추가 기록 형식을 확인해 주세요.')
    _text(report.get('legacy_memo'), '기존 조치사항')
    _text(report.get('mes_context'), 'MES 근거', 50000)
    for record in report['records']:
        if not isinstance(record, dict):
            raise ValueError('추가 기록 형식을 확인해 주세요.')
        _ids(record.get('equipment'), targets, '추가 기록')
        _text(record.get('story'), '상황·조치', required=True)
        if record.get('type') not in ('추가 기록', '이상증상', '고장·정비', 'PMS 정비'):
            raise ValueError('기록 구분을 확인해 주세요.')
        if type(record.get('candidate')) is not bool:
            raise ValueError('지식카드 후보 표시를 확인해 주세요.')
        for key in ('result', 'pms'):
            if record.get(key) is not None:
                _text(record[key], key)
        causes = record.get('causes')
        if not isinstance(causes, list) or len(causes) > 50:
            raise ValueError('원인 기록 형식을 확인해 주세요.')
        for cause in causes:
            if not isinstance(cause, dict) or cause.get('certainty') not in ('추정', '확인', '배제'):
                raise ValueError('원인 확인 상태를 확인해 주세요.')
            _ids(cause.get('equipment'), targets, '원인', required=False)
            _text(cause.get('note'), '원인·조치')
