"""Build only this follow-up's five revised development cards; never write originals."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
KEYS = ['M07', 'M08', 'M13', 'M16', 'M18']

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    if (HERE / 'cards.json').exists():
        raise SystemExit('Existing revision preserved; use a new version directory.')
    old_specs = {s['method_key']: s for name in ['specs-01-13.json', 'specs-14-25.json']
                 for s in read(BASE / '20260925-t4-synthetic' / name)}
    specs = [deepcopy(old_specs[k]) for k in KEYS]
    by_key = {s['method_key']: s for s in specs}
    for key in ['M07', 'M08', 'M13']:
        s = by_key[key]
        s['handover_method']['acknowledgement'] += ' 대상·출처와 제공 내용·미확인 또는 충돌 상태를 정확히 되짚은 범위는 수신 확인으로 기록한다. 남은 질문의 답변이나 결측·충돌 해결은 별도 대기로 유지한다.'
        s['verification_mechanism'] += ' 정확히 인수한 정보 범위의 수신 확인과 내용 해결 상태를 별도로 대조한다.'
        s['procedure'][-1] += ' 정확한 회신 범위의 수신 확인과 미해결 항목의 보완 대기를 따로 표시한다.'
    by_key['M07']['unresolved_handling'] = '진술·로그의 부재, 비교 불가, 답변 미확인을 정확히 인수한 범위는 수신 확인할 수 있다. 자료와 답변은 보완 대기로 유지한다. 내용이 다르거나 회신이 없는 범위만 수신 확인 대기로 남기고 정정·재확인을 요청한다. 일부 회신을 전체 수신으로 확대하지 않는다. 과거 사례와의 유사성은 현재 원인의 확정 근거가 아니다.'
    by_key['M08']['unresolved_handling'] = '실제 입력과 값·단위·관측 시점의 결측을 정확히 되짚으면 그 정보 범위의 수신은 확인한다. 결측 데이터 보완은 별도 대기다. 회신이 없거나 원문과 다르게 답한 범위는 수신 확인 대기로 남긴다. 일부 회신으로 나머지 항목을 확인 처리하지 않는다. 결측값을 추정하거나 계측 수행 사실을 만들지 않는다.'
    by_key['M13']['unresolved_handling'] = '양쪽 진술과 충돌 또는 원문 한쪽의 부재를 정확히 인수한 범위는 수신 확인할 수 있다. 부재 원문 확보와 충돌 해결은 별도 대기이며 양쪽 원문을 모두 받았다고 확대하지 않는다. 원문과 다른 요약이나 회신 없는 범위만 수신 확인 대기로 남기고 정정·재확인을 요청한다. 어느 기록이 사실인지 임의 선택하지 않는다.'
    s = by_key['M16']
    s['verification_mechanism'] = '수신자가 대상·조회 범위·기록 공백과 현재 근거에 따른 승인 상태를 나누어 회신한다. 새 증빙은 원문·대상 범위·판본을 대조한 뒤 기록 상태만 갱신하며 인계 접수를 작업 승인으로 바꾸지 않는다.'
    s['handover_method']['required_context'][-1] = '현재 확인한 기록 근거와 승인 여부의 확인 범위 또는 미확인 표시'
    s['handover_method']['required_context'].append('새 증빙이 제공된 경우 그 원문 참조·대상 범위·판본 및 기존 기록과의 관계; 없는 항목은 미확인')
    s['handover_method']['acknowledgement'] = '대상 기록, 조회 범위, 빠진 항목과 현재 승인 여부 미확인을 구분해 정확히 회신한 범위는 수신 확인한다. 확인된 기록 근거 없이 승인·미승인을 단정하거나 항목이 다르면 해당 범위를 정정·재확인 대기로 둔다. 새 증빙을 포함한 회신은 무조건 거부하지 않고 원문·대상 범위·판본 대조 대상으로 연결한다. 존재와 판본 확인만으로 증빙 내용의 유효성이나 작업 승인을 확정하지 않는다. 회신 없는 범위는 수신 확인 대기다.'
    s['procedure'] = ['기록 확인 대상, 조회 범위와 누락 항목을 적고 근거 없는 승인 상태는 미확인으로 유지한다.', '기록 담당에게 증빙 확인 요청을 전달하고 요청의 정확한 인수 여부와 증빙 확인 진행 상태를 나눈다.', '새 증빙이 도착하면 기존 공백 기록을 보존한 채 원문 참조·대상 범위·판본·내용과 기존 기록의 관계를 대조한다. 충돌이나 유효성 미확인은 별도 확인 대상으로 남긴다.', '확인된 새 근거의 범위에서 기록 상태를 갱신할 수 있으나 증빙 도착이나 정보 수신을 정비 착수·운전·재가동 승인으로 전환하지 않는다.']
    s['unresolved_handling'] = '기록 공백을 정확히 인수했다면 수신 확인은 가능하고 증빙 확인 요청은 열린 상태로 둔다. 확인 역할이나 회신이 없는 범위는 수신 확인 대기다. 새 증빙의 원문·대상 범위·판본·유효성이 확인되지 않거나 서로 충돌하면 해당 내용은 확인 대기로 유지한다. 확인된 근거가 추가되어도 현재 인계 수신자의 승인권을 만들지 않는다.'
    s = by_key['M18']
    s['trigger'] = '기존 의뢰에 명시적 무응답·일부 회신 또는 회신 기록 미첨부가 있는 상태를 다음 담당에게 넘기는 연습 상황'
    s['transfer_object'] = '의뢰 식별자, 요청 원문, 대상 역할, 항목별 회신 근거, 명시적 미회신과 회신 여부 미확인, 의뢰 접수와 인계 수신의 구분'
    s['verification_mechanism'] = '수신자가 의뢰 식별자와 항목별 회신 근거를 되짚고, 명시적 미회신의 답변 대기와 기록 미첨부의 회신 여부 확인 대기를 구분한다. 그 현황을 인수한 회신은 원래 의뢰의 답변을 대신하지 않는다.'
    s['handover_method']['required_context'][3] = '항목별 회신 원문·근거: 답변 있음, 원기록에 명시된 미회신, 회신 기록 미첨부 또는 회신 여부 미확인'
    s['handover_method']['required_context'][4] = '원래 의뢰의 접수 여부·내용 답변 여부와 이번 인계 수신 여부를 구분한 상태 및 조회 범위'
    s['handover_method']['acknowledgement'] = '의뢰 식별자, 답변된 범위, 명시적 미회신 범위와 기록 미첨부 범위를 근거와 함께 정확히 되짚으면 그 현황의 인계 수신을 확인한다. 명시적 무응답은 답변 대기, 기록 미첨부는 회신 여부 확인 대기로 각각 남긴다. 현황 인수자의 회신을 원래 의뢰 대상의 회신으로 대체하지 않는다. 누락·상태 혼동은 해당 인계 범위의 정정·재확인 대기, 현황 인수자 무응답은 인계 수신 확인 대기다.'
    s['procedure'] = ['의뢰 원문과 항목별 회신 근거를 모으고 조회 범위를 적는다. 인계 자료에 응답 기록이 없다는 이유만으로 실제 무응답으로 단정하지 않는다.', '답변 있음, 원기록에 명시된 미회신, 기록 미첨부로 회신 여부 미확인을 항목별로 나눈다.', '다음 담당에게 의뢰 식별자와 각 범위의 근거·대기 종류를 되짚도록 요청한다.', '정확히 인수한 현황의 수신 확인을 기록하되 명시적 미회신은 답변 대기, 기록 미첨부는 원기록 확보와 회신 여부 확인 대기로 유지한다. 일부 회신을 전체 답변 완료로 바꾸지 않는다.']
    s['unresolved_handling'] = '원문 또는 회신 기록 미확보를 정확히 인수하면 그 상태의 수신은 확인할 수 있다. 원문·회신 기록 확보와 회신 여부 확인은 별도 대기다. 실제로 명시된 무응답만 답변 대기로 분류한다. 이번 인계 수신자의 미회신·불일치 범위는 수신 확인 대기로 남긴다. 임의 마감시간·작업 진행률·전체 해결을 추가하지 않는다.'
    for s in specs:
        s['synthetic_narrative'] += ' 후속 설계에서는 정보 공백의 수신 확인과 내용 보완 대기를 분리하며 실제 회신·해결 사실을 생성하지 않는다.'
    version = 'synthetic-followup-' + hashlib.sha256(json.dumps(specs, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    old_cards = {c['card_id']: c for c in read(BASE / '20260925-t4-synthetic/cards.json')}
    cards, sources, changes = [], [], []
    for s in specs:
        key = s['method_key']; cid = f'K-{int(key[1:]):04d}'
        c = deepcopy(old_cards[cid]); old = deepcopy(c)
        c['version'] = version
        c['know_how'] = '[합성 개발용 인계 방법] ' + ' '.join(s['procedure']) + ' 수신·미해결 처리: ' + s['unresolved_handling'] + ' ' + c['safety_basis'].split('] ', 1)[1]
        c['type_payload']['handover_method'] = deepcopy(s['handover_method'])
        sid = f'SYN-T4-FOLLOWUP-20260926-{key}'
        c['provenance'].update(seed_ids=[sid], generator='Codex /root synthetic consistency revision + revise.py', generated_at=datetime.now(timezone.utc).isoformat(), sources=[{'source_id':sid, 'locator':f'synthetic-sources.json#{key}', 'document_version':version}], prompt_version='synthetic-t4-consistency-followup-v1')
        c['generalization_evidence']['confidence_basis'] = '후속 5개 카드의 인계 방법 5필드는 모두 합성 설계이며 직접 원문 지지 0/5, confidence=0. 효과·품질 점수가 아니다. 이전 문서 설계 점수와 실험 결과를 승계하지 않는다.'
        cards.append(c)
        sources.append({'source_id':sid,'method_key':key,'is_synthetic':True,'human_approval':False,'independent_factual_evidence':False,'version':version,'field_values':deepcopy(s['handover_method']),'full_design':deepcopy(s)})
        changes.append({'method_key':key,'card_id':cid,'previous_version':old['version'],'version':version,'reason':'기존 독립 검토에서 남은 상태 표현 정합화; 실행 효과에 따른 개선 주장이 아님','spec_changes':{k:{'before':old_specs[key].get(k),'after':v} for k,v in s.items() if old_specs[key].get(k)!=v},'original_card_path':'../20260925-t4-synthetic/cards.json','original_card_file_sha256':digest(BASE/'20260925-t4-synthetic/cards.json')})
    scenarios = [deepcopy(s) for name in ['scenarios-01-13.json','scenarios-14-25.json'] for s in read(BASE/'20260926-t4-persona-scenarios'/name) if s['method_key'] in KEYS]
    links = [{'method_key':s['method_key'],'card_id':f"K-{int(s['method_key'][1:]):04d}",'card_version':version,'scenario_status':'unchanged_script_snapshot_not_execution','original_path':'../20260926-t4-persona-scenarios/'+('scenarios-01-13.json' if int(s['method_key'][1:])<=13 else 'scenarios-14-25.json')} for s in scenarios]
    for name,value in [('specs.json',specs),('cards.json',cards),('synthetic-sources.json',sources),('changes.json',changes),('linked-scenarios.json',scenarios),('scenario-links.json',links)]: write(name,value)
    original_hashes = {}
    for folder in ['20260925-t4-synthetic','20260926-t4-persona-scenarios','20260926-t4-equipment']:
        for path in sorted((BASE/folder).iterdir()):
            if path.is_file(): original_hashes[f'../{folder}/{path.name}'] = digest(path)
    write('lineage.json',{'version':version,'author':'/root','original_file_hashes':original_hashes,'revised_ids':[c['card_id'] for c in cards],'inventory':'COMMON25 중 5개 후속 버전. 원본20 COMMON+후속5 COMMON+기존장비20=45 논리 카드. 원본/후속을 별도 카드로 중복 집계하지 않음. 목표·상한 아님.','excluded':'운영 DB·등록부·split 정책·KB 채택·기존 sealed/holdout 자료 사용','prior_scores_inherited':False})
    lines = ['# COMMON 후속 5개 카드', '', f'버전: `{version}`. 전부 T4 / COMMON / draft / L0 / dev. 원본과 과거 점수는 별도 보존.', '']
    for c,s in zip(cards,specs):
        lines += [f"## {s['method_key']} / {c['card_id']} · {c['title']}",'',c['know_how'],'']
        for k,v in s['handover_method'].items(): lines += [f"- **{k}**: {'; '.join(v) if isinstance(v,list) else v}"]
        lines += ['']
    (HERE/'cards.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(version)

if __name__ == '__main__':
    main()
