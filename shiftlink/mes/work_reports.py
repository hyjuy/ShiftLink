"""Validation for PDA work reports; saved through the existing durable outbox."""
from datetime import datetime
from math import isfinite

from . import field_draft
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.data.card_lint import lint_card


def _text(value, label, limit=4000, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'{label}: 문자열 길이와 필수 입력을 확인해 주세요.')


def _ids(value, allowed, label, required=True):
    if not isinstance(value, list) or len(value) > len(allowed) or (required and not value):
        raise ValueError(f'{label}: 대상 설비를 확인해 주세요.')
    if any(not isinstance(item, str) or item not in allowed for item in value) or len(set(value)) != len(value):
        raise ValueError(f'{label}: 대상에 없는 설비 또는 중복 설비입니다.')
    return set(value)


def validate(body, known_ids, config=None):
    if not isinstance(body, dict) or body.get('kind') != 'work_log' or 'resolution' in body:
        raise ValueError('근무일지 요청 형식을 확인해 주세요.')
    targets = _ids(body.get('equipment_ids'), known_ids, '일지')
    expected = next(iter(targets)) if len(targets) == 1 else None
    if body.get('equipment_id') != expected:
        raise ValueError('일지 대상 설비가 일치하지 않습니다.')
    context = body.get('required_context')
    if not isinstance(context, dict):
        raise ValueError('근무정보를 확인해 주세요.')
    _text(context.get('author'), '근무자', 100, True)
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
        if 'occurred_at' in record:
            _text(record['occurred_at'], '발생시각', 40)
            if record['occurred_at']:
                try:
                    if len(record['occurred_at']) < 16 or record['occurred_at'][10] != 'T':
                        raise ValueError()
                    datetime.fromisoformat(record['occurred_at'])
                except ValueError:
                    raise ValueError('발생시각을 확인해 주세요.') from None
        if record.get('type') not in ('추가 기록', '이상증상', '고장·정비', 'PMS 정비'):
            raise ValueError('기록 구분을 확인해 주세요.')
        if 'capture_version' in record:
            validate_capture(record)
        if 'query_id' in record:
            _text(record['query_id'], '질문 ID', 64, True)
        if 'incident_id' in record:
            _text(record['incident_id'], '사건 ID', 64, True)
            if record['type'] not in ('고장·정비','이상증상'):
                raise ValueError('사건 연결은 고장·정비 기록에서만 가능합니다.')
            if not record.get('followup_from'):
                raise ValueError('기존 사건을 이어 쓸 때는 이전 인계 기록을 연결해 주세요.')
        if 'followup_from' in record:
            source=record['followup_from']
            if not isinstance(source,dict) or not record.get('incident_id'):
                raise ValueError('이전 인계의 사건 연결을 확인해 주세요.')
            _text(source.get('handover_id'),'이전 일지 ID',64,True)
            if type(source.get('record_index')) is not int or not 0<=source['record_index']<50:
                raise ValueError('이전 인계 기록 번호를 확인해 주세요.')
        if 'normal_run_status' in record and record['normal_run_status'] not in ('unconfirmed','observing','no_recurrence','recurred'):
            raise ValueError('정상 운전 확인 상태를 확인해 주세요.')
        minutes=record.get('normal_run_minutes')
        if minutes is not None:
            if type(minutes) not in (int,float) or not isfinite(minutes) or minutes<0:
                raise ValueError('정상 운전 지속시간은 0 이상의 유효한 분 단위 숫자여야 합니다.')
            if record.get('normal_run_status','unconfirmed')=='unconfirmed':
                raise ValueError('미확인 상태에서는 정상 운전 지속시간을 확정할 수 없습니다.')
            _text(record.get('normal_run_evidence'),'정상 운전 확인 근거',required=True)
        elif 'normal_run_evidence' in record:
            _text(record['normal_run_evidence'],'정상 운전 확인 근거')
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
            reference=cause.get('sensor_ref')
            if reference is not None:
                if not isinstance(reference,dict) or set(reference)!={'equipment_id','signal'}:
                    raise ValueError('원인 판단에 참고한 센서를 확인해 주세요.')
                _text(reference['equipment_id'],'센서 설비',100,True)
                _text(reference['signal'],'센서 신호',200,True)
                eq=next((eq for eq in config.equipment if eq.equipment_id==reference['equipment_id']),None) if config else None
                if reference['equipment_id'] not in record['equipment'] or eq is None or not any(sensor.signal==reference['signal'] for sensor in eq.signals):
                    raise ValueError('해당 기록의 설비에 등록된 센서를 선택해 주세요.')
    if 'form_version' in report:
        if type(report['form_version']) is not int or report['form_version'] != 2:
            raise ValueError('지원하지 않는 근무일지 양식입니다.')
        validate_typed(report, config)



WORK_TYPES = ('정상 근무','정비 작업','고장·이상 대응')
FAULT_TYPES = ('고장·정비','이상증상')
OUTCOMES = ('open','resolved','temporary','failed')
RESTART_TYPES = ('normal_stop_restart','abnormal_stop_restart','maintenance_restart','unknown')


def has_incident(record):
    return record['type'] in FAULT_TYPES or (record['type']=='PMS 정비' and record.get('capture_version')==1
                                           and (record.get('restart_performed') is True or record.get('candidate') is True))


def validate_capture(record):
    if type(record['capture_version']) is not int or record['capture_version']!=1:
        raise ValueError('지원하지 않는 조치 기록 양식입니다.')
    steps=record.get('action_steps')
    if not isinstance(steps,list) or len(steps)>50:
        raise ValueError('조치 내용·결과는 50단계 이내로 기록해 주세요.')
    for step in steps:
        if not isinstance(step,dict):raise ValueError('조치 단계 형식을 확인해 주세요.')
        for key in ('action','observed_result'):_text(step.get(key),'조치 내용·결과')
        if type(step.get('failed')) is not bool:raise ValueError('실패 시도 표시를 확인해 주세요.')
        if 'worker' in step:_text(step['worker'],'근무자',100)
        if 'performed_at' in step:
            _text(step['performed_at'],'조치시각',40)
            if step['performed_at']:
                try:
                    if len(step['performed_at'])<16 or step['performed_at'][10]!='T':raise ValueError()
                    datetime.fromisoformat(step['performed_at'])
                except ValueError:
                    raise ValueError('조치시각의 날짜와 시간을 확인해 주세요.') from None
    if type(record.get('restart_performed')) is not bool or record.get('restart_type') not in RESTART_TYPES:
        raise ValueError('재가동 여부와 정지 구분을 확인해 주세요.')
    for key in ('operating_context','safety_notes','follow_up','references'):
        _text(record.get(key,''),key)
    if record['type'] in (*FAULT_TYPES,'PMS 정비') and record.get('outcome') not in OUTCOMES:
        raise ValueError('조치 상태를 선택해 주세요.')


def capture_missing(record):
    missing=[]
    steps=[step for step in record['action_steps'] if step['action'].strip() or step['observed_result'].strip()]
    if not steps or any(not step['action'].strip() or not step['observed_result'].strip() for step in steps):
        missing.append('단계별 조치 내용·결과')
    if steps and all(step['failed'] for step in steps):missing.append('효과를 확인한 조치')
    if not any(cause['note'].strip() for cause in record['causes']):missing.append('원인 또는 원인 미확인 기록')
    if record.get('outcome')!='resolved':missing.append('해결 확인')
    if record.get('normal_run_status')!='no_recurrence' or not record.get('normal_run_minutes') or not record.get('normal_run_evidence','').strip():
        missing.append('정상 운전 관찰 종료·지속시간·근거')
    if len(record['equipment'])!=1:missing.append('후보 대상 설비 한 대')
    return missing


def step_worker_time(step):
    return f"근무자: {step.get('worker') or '미기재'} · 조치시각: {step.get('performed_at') or '미기재'}"


def capture_candidate_from(record, config, report_id, record_index, card_id, now):
    """Observed outcomes are draft evidence, not an approved procedure or proof of continuous MES operation."""
    eq=next(eq for eq in config.equipment if eq.equipment_id==record['equipment'][0])
    steps=[step for step in record['action_steps'] if step['action'].strip() or step['observed_result'].strip()]
    restarting=record['restart_performed']
    payload={'restart_type':record['restart_type'], 'tried_and_failed':[
        {'attempt_id':f'AT-{i+1:04d}','restart_type':record['restart_type'],'action':step['action'],
         'observed_result':step['observed_result'],'failure_reason':None}
        for i,step in enumerate(steps) if step['failed']]} if restarting else {'steps':[
            {'step_id':f'ST-{i+1:02d}','order':i+1,'action':step['action'],'expected_result':step['observed_result']}
            for i,step in enumerate(steps)]}
    normal={'minutes':record['normal_run_minutes'],'status':record['normal_run_status'],
            'evidence':record['normal_run_evidence'],'source':'worker'}
    card={'card_id':card_id,'version':'1','grade':'L0','status':'draft','tacit_type':'T6' if restarting else 'T3',
          'equipment':eq.code.split('-')[0],'component':eq.name,'mes_equipment_id':eq.equipment_id,'scenario':'S1',
          'title':f"[근무일지 후보] {eq.code} — {record['story']}"[:80],'symptom':record['story'],
          'know_how':'\n'.join(f"{i+1}. {step_worker_time(step)}\n{step['action']} → 현장에서 확인한 결과: {step['observed_result']}" for i,step in enumerate(steps)),
          'rationale':'\n'.join([*(f"원인({c['certainty']}): {c['note']}" for c in record['causes']),
              f"정상 운전 {normal['minutes']}분(근무자 확인): {normal['evidence']}",
              '단계의 결과는 현장 관측 원문이며 재사용·안전 타당성과 MES 연속 운전은 미검증.']),
          'conditions':[],'safety_flag':False,'safety_basis':None,'confidence':0.0,'split':'dev','type_payload':payload,
          'provenance':{'seed_ids':[],'persona_id':'field-work-report','event_ids':[],'generator':'work-report-capture-v1',
              'generated_at':now.isoformat(),'extraction_method':'rule','schema_version':field_draft.SCHEMA_VERSION,
              'sources':[{'source_id':report_id,'locator':f'work_report.records[{record_index}]'}]}}
    card=KnowledgeCard.model_validate(card).model_dump(mode='json')
    risk=record.get('safety_notes','')
    flags={'work_report':{'handover_id':report_id,'record_index':record_index},'normal_operation':normal,
           'action_steps':steps,'reported_causes':record['causes'],'operating_context':record.get('operating_context',''),
           'references':record.get('references',''),'safety_report':{'text':risk,'status':'needs_document_review' if risk else 'not_reported'},
           'needs_safety_review':bool(risk) or any(word in card['know_how'] for word in field_draft.SAFETY_WORDS),
           'scenario_default':'S1 기본 분류·검토 필요','lint':lint_card(card,known_fields=set(KnowledgeCard.model_fields)),
           'completeness':{'missing':[],'operator':['재사용 타당성·적용 조건·안전 근거 판정'],'ready':False}}
    return {'status':'pending_review','card':card,'review_flags':flags}


def handover_resolved(record):
    return record.get('outcome')=='resolved' and record.get('normal_run_status')=='no_recurrence' and \
        bool(record.get('normal_run_minutes')) and bool(record.get('normal_run_evidence','').strip())


def handover_chain(records, source):
    by_source={(item['handover_id'],item['record_index']):item for item in records}
    chain=[];seen=set()
    while source:
        key=(source['handover_id'],source['record_index'])
        if key in seen or key not in by_source:raise ValueError('이전 인계의 연결 이력을 확인해 주세요.')
        seen.add(key);item=by_source[key];chain.append(item);source=item['record'].get('followup_from')
    return list(reversed(chain))


def handover_capture(chain):
    record=dict(chain[-1]['record']);steps=[];causes=[]
    for item in chain:
        r=item['record'];causes.extend(r.get('causes',[]))
        if r.get('capture_version')==1:steps.extend(r['action_steps'])
        elif r.get('solution') and r.get('result'):
            steps.append({'action':r['solution'],'observed_result':r['result'],'failed':r.get('outcome')=='failed'})
    record.update(causes=causes,action_steps=steps,restart_performed=False,restart_type='unknown')
    for key in ('operating_context','safety_notes','references'):
        record[key]='\n'.join(dict.fromkeys(item['record'].get(key,'') for item in chain if item['record'].get(key)))
    return record


def handover_missing(chain):
    missing=capture_missing(handover_capture(chain))
    if len(chain)<2 or chain[0]['record'].get('outcome') not in ('open','temporary','failed'):
        missing.append('최초 미해결 기록과 후속 인계 기록')
    return missing


def handover_candidate_from(chain, config, card_id, now):
    last=chain[-1];first=chain[0];record=handover_capture(chain)
    draft=capture_candidate_from(record,config,last['handover_id'],last['record_index'],card_id,now)
    card=draft['card'];flags=draft['review_flags']
    context=last['required_context'];period=f"{first['required_context']['start_at']} ~ {context['end_at']}"
    history=[]
    for item in chain:
        r=item['record'];ctx=item['required_context']
        history.append('\n'.join([f"{ctx['start_at']} ~ {ctx['end_at']} · {ctx['author']}",r['story'],
            *(f"원인({c['certainty']}): {c['note']}" for c in r.get('causes',[])),
            *(f"{step_worker_time(s)}\n조치: {s['action']} → 결과: {s['observed_result']}" for s in r.get('action_steps',[]) if s['action'].strip() or s['observed_result'].strip()),
            *([f"조치: {r['solution']}"] if not r.get('capture_version') and r.get('solution') else []),
            f"결과: {r.get('result') or '미기재'}",f"후속 확인: {r.get('follow_up') or '미기재'}"]))
    card.update(tacit_type='T4',title=f"[인계 사례 후보] {first['record']['story']}"[:80],know_how='\n\n'.join(history),
        type_payload={'handover_method':{
            'required_context':[first['record']['story'],*history],
            'recipient_role':'후속 조치 담당 근무자', 'timing':period,'channel':'근무일지·인계사항',
            'acknowledgement':f"{context['author']}의 이전 기록 연결·후속 조치 기록. 정상 운전 {record['normal_run_minutes']}분(근무자 확인): {record['normal_run_evidence']}"}})
    card['provenance']['generator']='work-report-handover-v1'
    card['provenance']['sources']=[{'source_id':item['handover_id'],'locator':f"work_report.records[{item['record_index']}]"} for item in chain]
    card['provenance']['sources'].extend({'source_id':item['handover_id'],'locator':'server_sensor_evidence'} for item in chain if item['record'].get('capture_version')==1)
    flags.update(handover_chain=chain,period={'start_at':first['required_context']['start_at'],'end_at':context['end_at']},
        acknowledgement_source='followup_record',needs_safety_review=any(item['record'].get('safety_notes') for item in chain) or flags['needs_safety_review'])
    flags['completeness']['operator']=['인계 방법의 재사용 타당성·적용 조건·안전 근거 판정']
    draft['card']=KnowledgeCard.model_validate(card).model_dump(mode='json')
    flags['lint']=lint_card(draft['card'],known_fields=set(KnowledgeCard.model_fields))
    return draft


def _manual_sample(sample):
    if sample is None:
        return
    if not isinstance(sample,dict) or sample.get('source') != 'manual':
        raise ValueError('직접 기록한 센서값의 출처를 확인해 주세요.')
    value=sample.get('value')
    if type(value) not in (int,float) or not isfinite(value):
        raise ValueError('센서값은 유효한 숫자여야 합니다.')
    try:
        datetime.fromisoformat(sample['observed_at'])
    except (KeyError,TypeError,ValueError):
        raise ValueError('센서 관측 시각을 확인해 주세요.') from None


def validate_typed(report, config):
    if report.get('work_type') not in WORK_TYPES:
        raise ValueError('근무 유형을 선택해 주세요.')
    _text(report.get('remarks',''), '추가 메모')
    records=report['records']
    kinds={r['type'] for r in records}
    if report['work_type']=='정상 근무' and kinds-{'추가 기록'}:
        raise ValueError('정비·고장 기록에 맞는 근무 유형을 선택해 주세요.')
    if report['work_type']=='정비 작업' and 'PMS 정비' not in kinds:
        raise ValueError('정비 기록을 추가해 주세요.')
    if report['work_type']=='고장·이상 대응' and not kinds.intersection(FAULT_TYPES):
        raise ValueError('이상·고장 기록을 추가해 주세요.')
    for r in records:
        if r['type']=='PMS 정비':
            parts=r.get('parts')
            if not isinstance(parts,list) or len(parts)>50 or type(r.get('no_parts_used')) is not bool:
                raise ValueError('사용 부속품 기록을 확인해 주세요.')
            if not parts and not r['no_parts_used']:
                raise ValueError('사용 부속품을 추가하거나 사용 없음을 선택해 주세요.')
            if parts and r['no_parts_used']:
                raise ValueError('부속품 사용 없음과 사용 내역을 동시에 선택할 수 없습니다.')
            for part in parts:
                if not isinstance(part,dict): raise ValueError('부속품 기록을 확인해 주세요.')
                _ids([part.get('equipment_id')],set(r['equipment']),'부속품')
                for key in ('name','unit','usage'):
                    _text(part.get(key), '부속품 '+key, 200, True)
                _text(part.get('part_number',''),'부품 번호',200)
                qty=part.get('quantity')
                if type(qty) not in (int,float) or not isfinite(qty) or qty<=0:
                    raise ValueError('부속품 수량은 0보다 큰 유효한 숫자여야 합니다.')
        if r['type'] in FAULT_TYPES:
            sensors=r.get('fault_sensors')
            if not isinstance(sensors,list) or len(sensors)>50 or type(r.get('sensor_unknown')) is not bool:
                raise ValueError('문제 센서 기록을 확인해 주세요.')
            if not sensors and not r['sensor_unknown']:
                raise ValueError('문제 센서를 선택하거나 미확인을 선택해 주세요.')
            if sensors and r['sensor_unknown']:
                raise ValueError('문제 센서 미확인과 센서 선택을 동시에 사용할 수 없습니다.')
            seen=set()
            for sensor in sensors:
                if not isinstance(sensor,dict): raise ValueError('센서 기록을 확인해 주세요.')
                _ids([sensor.get('equipment_id')],set(r['equipment']),'문제 센서')
                eq=next(e for e in config.equipment if e.equipment_id==sensor['equipment_id'])
                spec=next((x for x in eq.signals if x.signal==sensor.get('signal')),None)
                key=(eq.equipment_id,sensor.get('signal'))
                if spec is None or sensor.get('unit')!=spec.unit or key in seen:
                    raise ValueError('센서 신호·단위·중복 선택을 확인해 주세요.')
                seen.add(key)
                _text(sensor.get('problem'),'센서 문제',200,True)
                _manual_sample(sensor.get('before'));_manual_sample(sensor.get('after'))
            if r.get('outcome') not in OUTCOMES:
                raise ValueError('조치 결과를 선택해 주세요.')
            _text(r.get('solution',''),'수행 조치',4000,r['outcome']!='open')
            if r['outcome']=='resolved':
                _text(r.get('result'),'해결 확인 근거',4000,True)


def sensor_evidence(snapshot, config, equipment_ids):
    measurements={(m['equipment_id'],m['signal']):m for m in snapshot['measurements']}
    rows=[]
    for eq in config.equipment:
        if eq.equipment_id not in equipment_ids: continue
        for spec in eq.signals:
            m=measurements.get((eq.equipment_id,spec.signal))
            rows.append({'equipment_id':eq.equipment_id,'asset_id':eq.asset_id,'signal':spec.signal,'name':spec.name,
                'value':m['value'] if m else None,'unit':m['unit'] if m else spec.unit,
                'quality':m['quality'] if m else 'missing','observed_at':m['observed_at'] if m else None,
                'normal_min':spec.normal_min,'normal_max':spec.normal_max})
    return {'scope':'save_snapshot','run_id':snapshot['run_id'],'config_id':config.config_id,
            'simulated_at':snapshot['simulated_at'],'measurements':rows}


def candidate_from(record, query, config, report_id, record_index, card_id, now):
    """Keep the existing form as a proposal; reviewers supply reusable steps and verify outcomes."""
    eq = next(eq for eq in config.equipment if eq.equipment_id == query['equipment_id'])
    abnormal = field_draft.out_of_range(eq, query['evidence'])
    card = {
        'card_id':card_id, 'version':'1', 'grade':'L0', 'status':'draft', 'tacit_type':'T3',
        'equipment':eq.code.split('-')[0], 'component':eq.name, 'mes_equipment_id':eq.equipment_id,
        'scenario':'S1', 'title':f"[근무일지 후보] {eq.code} — {query['question']}"[:80],
        'symptom':query['question'], 'know_how':record['story'] + ('\n수행 조치: ' + record['solution'] if record.get('solution') else ''),
        'rationale':f"근무일지 {report_id} 기록 {record_index + 1}. 작업자 결과 원문: {record.get('result') or '미기재'}. MES 해결 검증 없음.",
        'conditions':[{'signal':f"{item['signal']}_state", 'op':'==', 'value':item['state'], 'unit':None} for item in abnormal],
        'safety_flag':False, 'confidence':0.0, 'split':'dev',
        'type_payload':{'steps':[{'step_id':'ST-01', 'order':1,
            'action':'검토 전: 원문에서 재사용 조치 절차를 확정해야 함', 'expected_result':field_draft.PLACEHOLDER}]},
        'provenance':{'seed_ids':[], 'persona_id':'field-work-report', 'event_ids':[],
            'generator':'field-work-report-v1', 'generated_at':now.isoformat(), 'extraction_method':'rule',
            'schema_version':field_draft.SCHEMA_VERSION,
            'sources':[{'source_id':report_id, 'locator':f'work_report.records[{record_index}]'},
                       {'source_id':query['query_id'], 'locator':'query_log'}]}}
    flags = {
        'records':[{'handover_id':report_id, 'record_index':record_index, 'relation':'origin',
                    'result':'unconfirmed', 'mes_recovered':False}],
        'work_report':{'handover_id':report_id, 'record_index':record_index, 'query_id':query['query_id']},
        'reported_causes':record['causes'], 'worker_result_text':record.get('result'),
        'worker_outcome':record.get('outcome'), 'fault_sensors':record.get('fault_sensors',[]),
        'unstructured_work_report':True, 'scenario_default':'S1 기본값: 검토에서 적용 시나리오 확인',
        'missing_worker_result':not bool((record.get('result') or '').strip())}
    return field_draft._finish(card, flags)
