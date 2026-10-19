"""Review decisions are separate from publishing and from immutable source logs."""
STATUSES={'approve':'review_approved','request_changes':'changes_requested','reject':'rejected'}


def validate_decision(body):
    if not isinstance(body,dict) or set(body)-{'action','reason','expected_revision'}:
        raise ValueError('검토 요청 형식을 확인해 주세요.')
    action=body.get('action');reason=body.get('reason','');revision=body.get('expected_revision')
    if not isinstance(action,str) or action not in STATUSES:raise ValueError('검토 처리 항목을 확인해 주세요.')
    if not isinstance(reason,str) or len(reason)>2000:raise ValueError('검토 의견은 2000자 이내로 작성해 주세요.')
    if action!='approve' and not reason.strip():raise ValueError('보완 요청·반려 사유를 입력해 주세요.')
    if type(revision) is not int or revision<0:raise ValueError('최신 후보 정보를 다시 불러와 주세요.')
    return action,STATUSES[action],reason.strip(),revision


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
