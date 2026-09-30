"""Apply the source-backed round 1 corrections once, retaining the original fields."""
import copy
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ledger = BASE / 'review_changes.json'
assert not ledger.exists(), 'Do not overwrite the original revision history'
changes = []
for path in sorted((BASE / 'out').glob('*.json')):
    cards = json.loads(path.read_text(encoding='utf-8'))
    for card in cards:
        before = copy.deepcopy(card)
        cid = card['card_id']
        if card['tacit_type'] == 'T2':
            card['provenance']['extraction_method'] = (
                '로컬 PDF 실제 페이지 독립 텍스트 대조 및 표 렌더링 확인; AI 요약'
                if cid != 'K-1203' else
                '로컬 PDF p.17 Algo A.1 흐름도 렌더링 독립 분기 대조; AI 요약'
            )
        if cid == 'K-1202':
            card['know_how'] = card['know_how'].replace(
                '실제 교체는 현장 절차와 모델 적용성을 확인한 정비 담당자가 수행한다.',
                '교체 필요가 표시된 경우 정비 담당자에게 현장 절차·모델 적용성·작업 전 안전 조건을 확인하도록 요청한다. 이 카드는 교체 작업 방법이나 작업 허가를 정하지 않는다.'
            )
        if cid == 'K-1203':
            card['know_how'] += ' 이 흐름도는 확인 경로의 요약이며, 유량계 설치·계통 작동·밸브 조정은 담당자가 대상 모델의 작업표준과 안전 조건을 확인한 범위에서만 수행한다.'
        if cid == 'K-1207':
            card['know_how'] = card['know_how'].replace(
                '롤러가 도는데 물품이 이송되지 않으면',
                '물품이 이송되지 않는 증상에는 별도 표 항목으로'
            )
            card['know_how'] += ' 원문 두 번째 항목은 롤러가 회전 중이라고 명시하지 않으며 두 증상이 겹칠 수 있다. 구동부 관측을 함께 남겨 담당자가 관련 항목을 확인한다.'
        if cid == 'K-1208':
            card['know_how'] = card['know_how'].replace(
                '이송중량 초과가 확인되지 않으면 전기 담당자가',
                '중량 초과 여부와 별도로 전기 담당자가'
            )
            card['know_how'] += ' 중량 초과와 단락은 배타적인 원인이 아니며 중량 확인만으로 전기 점검 필요를 없애지 않는다.'
            card['provenance']['sources'][1]['locator'] = 'PDF p.51 / 인쇄 p.51 / Troubleshooting: In case of a fault (전원 차단·우발 기동 방지·전기 담당 자격)'
        if card['tacit_type'] == 'T6':
            for source in card['provenance']['sources']:
                if source['source_id'].endswith('.pdf'):
                    source['source_id'] = Path(source['source_id']).name
            card['generalization_evidence']['confidence_basis'] = (
                '서로 다른 KB 사건 ID 2건에서 해당 재가동 유형의 기록을 대조했다. '
                '일부 관측·시도 문구는 동일 합성 템플릿의 복제이므로 독립 현장 반복이나 통계적 검증 근거가 아니다. '
                '실제 현장경험·유효성 검증·사람 승인 없음; 실패 원인 진단은 미기록. '
                '독립 검토자가 KB 관측 투영과 PDF 실제 페이지로 내용 일치를 확인했다.'
            )
        if cid == 'K-1212':
            card['provenance']['sources'][-1]['locator'] = 'PDF/인쇄 p.39~40 및 p.42~43 / §7.1 Startup 및 §8.3 Checking the oil level / Changing the oil'
        if cid == 'K-1213':
            card['generalization_evidence']['generalization_scope'] += ' 원문 §8.3의 운전 중 정렬 조정은 이 카드에 이전하지 않았다. 이 카드는 승인된 시험운전 관찰·정지·담당자 보고만 다룬다.'
        if before != card:
            changed = {key: {'before': before.get(key), 'after': value}
                       for key, value in card.items() if value != before.get(key)}
            changes.append({'card_id': cid, 'file': str(path.relative_to(BASE)),
                            'basis': 'review_round1.md', 'fields': changed})
        assert card['status'] == 'draft' and card['grade'] == 'L0' and card['confidence'] == 0.0
        assert card['provenance']['prompt_version'] == before['provenance']['prompt_version']
    path.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
ledger.write_text(json.dumps({'reviewer': 'independent_review', 'round': 1,
                             'changes': changes}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'Updated {len(changes)} cards; original fields retained in review_changes.json')
