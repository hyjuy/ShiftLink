"""Review and quality decisions never publish cards or alter immutable source logs."""
from hashlib import sha256
import json

from shiftlink.agent.schemas import KnowledgeCard


STATUSES={'approve':'review_approved','request_changes':'changes_requested','reject':'rejected',
          'quality_pass':'quality_passed'}


def validate_decision(body):
    if not isinstance(body,dict) or set(body)-{'action','reason','expected_revision'}:
        raise ValueError('검토 요청 형식을 확인해 주세요.')
    action=body.get('action');reason=body.get('reason','');revision=body.get('expected_revision')
    if not isinstance(action,str) or action not in STATUSES:raise ValueError('검토 처리 항목을 확인해 주세요.')
    if not isinstance(reason,str) or len(reason)>2000:raise ValueError('검토 의견은 2000자 이내로 작성해 주세요.')
    if action!='approve' and not reason.strip():raise ValueError('보완 요청·반려 또는 검수 통과의 근거를 입력해 주세요.')
    if type(revision) is not int or revision<0:raise ValueError('최신 후보 정보를 다시 불러와 주세요.')
    return action,STATUSES[action],reason.strip(),revision


def quality_artifact(draft, actor, checked_at):
    """Prepare an approved copy; only a later embedding worker may consume it."""
    if draft['status'] != 'review_approved':
        raise ValueError('심사 승인된 최신 후보만 검수 통과할 수 있습니다.')
    raw = draft['card']
    if set(raw) - KnowledgeCard.model_fields.keys():
        raise ValueError('지식카드 스키마에 없는 항목이 있습니다.')
    card = KnowledgeCard.model_validate({**raw, 'status':'accepted', 'grade':'L1', 'split':'kb'}).model_dump(mode='json')
    canonical = json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    # Include typed procedures and limits as well as the prose; no generated facts.
    text = '\n'.join([card['title'], '설비: '+card['equipment'], '부품: '+card['component'],
        '증상: '+(card['symptom'] or ''), card['know_how'], card['rationale'],
        '적용 조건: '+json.dumps(card['conditions'], ensure_ascii=False, sort_keys=True),
        '제외 조건: '+json.dumps(card['exclusions'], ensure_ascii=False, sort_keys=True),
        '유형별 지식: '+json.dumps(card['type_payload'], ensure_ascii=False, sort_keys=True),
        '안전 근거: '+(card['safety_basis'] or '')])
    return {'state':'embedding_pending', 'searchable':False, 'card':card, 'embed_text':text,
            'content_hash':sha256(canonical.encode('utf-8')).hexdigest(),
            'review_revision':draft['revision']+1, 'quality_checked_by':actor['id'],
            'quality_checked_at':checked_at}


def detail(storage,draft_id):
    draft=storage.get_card_draft(draft_id)
    if draft is None:raise KeyError('후보를 찾을 수 없습니다.')
    references=[source['source_id'] for source in draft['card'].get('provenance',{}).get('sources',[])]
    origin=draft['review_flags'].get('work_report',{}).get('handover_id')
    if origin:references.append(origin)
    sources=[]
    for reference in dict.fromkeys(references):
        saved=storage.get_handover(reference)
        if saved:
            sources.append({**saved['payload'],'created_at':saved['created_at'],
                            'server_sensor_evidence':storage.work_report_sensors(reference)})
    return {**draft,'sources':sources}
