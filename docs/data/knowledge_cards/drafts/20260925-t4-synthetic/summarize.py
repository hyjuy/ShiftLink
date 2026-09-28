"""Validate independent review coverage and publish measured development scores."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
FIELDS = ('required_context', 'recipient_role', 'timing', 'channel', 'acknowledgement')


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def digest(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def main():
    policy, harness = read('batch-policy.json'), read('harness-results.json')
    cards, mapping = read('cards.json'), read('evidence-map.json')['cards']
    specs = {s['method_key']: s for name in ('specs-01-13.json', 'specs-14-25.json') for s in read(name)}
    dimensions = set(policy['rubric']['dimensions'])
    cards_hash = digest('cards.json')
    assert harness['cards_sha256'] == cards_hash
    assert harness['schema_passed'] == harness['schema_total'] == 25
    assert harness['negative_probe_passed'] == harness['negative_probe_total'] == 250
    assert harness['dev_gate_blocked'] == harness['draft_gate_excluded'] == 25
    assert harness['source_integrity_passed'] and harness['synthetic_traceability_passed']
    assert harness['pairwise_comparisons'] == 300
    assert not any(p['exact_method_duplicate'] for p in harness['all_pair_comparisons'])
    review_files = {'reviews-methods.json': set(f'M{i:02}' for i in range(14, 26)),
                    'reviews-boundary.json': set(f'M{i:02}' for i in range(1, 14)),
                    'reviews-harness.json': set(specs)}
    reviews = {key: [] for key in specs}
    reviewer_names = set()
    for filename, expected in review_files.items():
        packet = read(filename)
        assert packet['cards_sha256'] == cards_hash, filename
        assert packet['rubric_version'] == policy['policy_version'], filename
        assert packet['reviewer'] not in reviewer_names
        reviewer_names.add(packet['reviewer'])
        assert len(packet['reviews']) == len(expected)
        assert {r['method_key'] for r in packet['reviews']} == expected
        for row in packet['reviews']:
            assert set(row['scores']) == set(row['reasons']) == dimensions
            assert all(type(v) is int and 0 <= v <= 4 for v in row['scores'].values())
            assert all(isinstance(v, str) and v.strip() for v in row['reasons'].values())
            assert all(f['severity'] in {'minor', 'major'} and f['detail'].strip() for f in row['findings'])
            reviews[row['method_key']].append(dict(row, reviewer=packet['reviewer'], file=filename,
                                                  score=sum(row['scores'].values()) * 5))
    rows = []
    for card, link in zip(cards, mapping, strict=True):
        key = link['method_key']
        rr = reviews[key]
        assert card['card_id'] == link['card_id'] and len(rr) == 2
        assert all(r['card_id'] == card['card_id'] for r in rr)
        passed = all(r['score'] >= 80 and min(r['scores'].values()) >= 3
                     and not any(f['severity'] == 'major' for f in r['findings']) for r in rr)
        rows.append({'method_key': key, 'card_id': card['card_id'], 'title': card['title'],
                     'development_review_passed': passed, 'average_score': mean(r['score'] for r in rr),
                     'minimum_reviewer_score': min(r['score'] for r in rr), 'reviews': rr})
    accepted = sum(r['development_review_passed'] for r in rows)
    result = {'evaluated_at': datetime.now(timezone.utc).isoformat(), 'cards_sha256': cards_hash,
              'rubric_version': policy['policy_version'], 'reviewer_count': len(reviewer_names),
              'independent_reviews_per_card': 2, 'score_scope': 'AI assessment of synthetic method design; not factual validation',
              'development_passed': accepted, 'development_target': 25, 'development_shortfall': 25-accepted,
              'average_score': mean(r['average_score'] for r in rows),
              'minimum_card_average': min(r['average_score'] for r in rows),
              'maximum_card_average': max(r['average_score'] for r in rows),
              'original_complete_cards': harness['original_complete_cards'],
              'original_target_shortfall': 25-harness['original_complete_cards'],
              'human_source_approval': False, 'human_safety_review': False, 'adopted': False,
              'input_hashes': {n: digest(n) for n in [*review_files, 'cards.json', 'harness-results.json', 'batch-policy.json']},
              'aggregator_code_sha256': digest('summarize.py'), 'cards': rows}
    (HERE/'quality-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    report = ['# 합성 T4 지식카드 25건 — 하니스·독립 검토 결과', '',
              f"**개발용 기준 통과 {accepted}/25건. 카드별 AI 설계 점수 평균 {result['average_score']:.1f}/100, 범위 {result['minimum_card_average']:g}–{result['maximum_card_average']:g}.**", '',
              '후속 요청에 따라 부족한 인계 방법을 합성 설계했다. 모든 카드는 `status=draft`, `grade=L0`, `split=dev`이다. 점수는 재사용성·구체성·일관성·합성/승인 경계·차별성의 설계 평가이며 사실 정확도 점수가 아니다. 원문만으로 완성한 카드는 여전히 0건이다. 사람의 출처 승인·안전 검토·채택은 미완료다.', '',
              '## A. 검토한 원문과 근거 위치', '',
              'PDF 26개(1,047쪽)와 HTML 1개의 분류·파일명·쪽/절은 [기존 원문 보고서](../20260925-t4-evidence-review/review.md#A-검토한-원문과-근거-위치)와 [원문 근거 원장](../20260925-t4-evidence-review/sources.json)에 보존했다. 제품 매뉴얼·일반 지침·공개 사례를 구분하며 확인된 실제 현장 사건 수는 0건이다. 이번 검증은 원문 파일 해시도 대조했다.', '',
              '## B. 카드별 다섯 필드의 근거', '',
              '아래 `합성`은 독립 사실 근거가 없는 설계 제안이다. 원문 표지는 기존 원장에 파일·쪽/절·발췌가 있다. 값과 필드별 원문/합성 참조는 [evidence-map.json](evidence-map.json), 합성 설계 전문은 [synthetic-sources.json](synthetic-sources.json)에 있다. 배경 자료를 필드의 직접 근거로 세지 않았다.', '',
              '| 방법 | required_context | recipient_role | timing | channel | acknowledgement |',
              '|---|---|---|---|---|---|']
    for link in mapping:
        labels = [', '.join(link['fields'][f]['original_evidence_refs']) if link['fields'][f]['kind']=='original' else '합성' for f in FIELDS]
        report.append('| '+link['method_key']+' | '+' | '.join(labels)+' |')
    report += ['', '직접 원문 필드 5/125(4%), 합성 보완 필드 120/125(96%). `confidence`는 원문 직접 일치 필드 수/5의 계산값(0, 0.2, 0.4)이며 AI 설계 점수와 다르다. 페르소나 v0.2 V-11~V-13은 [합성 연습 인계문](narratives.json)의 관점·문체에만 사용하며 각각 `persona_id`와 합성 표시를 남겼다.', '',
               '## C. 스키마·중복·설계 검토를 통과한 개발용 초안', '',
               '전체 카드 전문: [cards.md](cards.md) · 스키마 입력: [cards.json](cards.json) · [하니스 실행 결과](harness-results.json) · [품질 점수 원장](quality-results.json).', '',
               '- 기존 `KnowledgeCard`와 `evaluate_category_b`로 이번 카드 25/25건 검증.',
               '- 다섯 필드별 누락·공백 변조 250/250건 거부; 해당 필드 오류 위치도 확인.',
               '- dev 입력 차단 25/25건, draft/L0의 KB 제외 25/25건 확인.',
               '- 필드 추적 125건, 원문 무결성, ID 충돌 범위, 합성 표시·계보 확인.',
               '- 300쌍의 완전 일치 검사와 텍스트 유사도 선별 수행. 의미 차이는 독립 AI 검토로 보완. 유사도 수치는 의미 중복 점수가 아니며 기존 전체 KB와의 의미 중복 검사는 아님.',
               '- 작성자가 아닌 교차 검토자 1명과 전체를 검토한 별도 하니스 검토자 1명이 각 카드를 평가. 총 3명, 카드마다 2개 독립 평가. 각 검토 80점 이상·차원별 3점 이상·미해결 major 없음이 개발용 통과 조건.', '',
               '| 방법 / 카드 | 재사용 상황과 차이 | 교차 검토 | 하니스 검토 | 평균 | 개발 기준 |',
               '|---|---|---:|---:|---:|---|']
    for row in rows:
        cross = next(r for r in row['reviews'] if r['file']!='reviews-harness.json')
        audit = next(r for r in row['reviews'] if r['file']=='reviews-harness.json')
        report.append(f"| {row['method_key']} / {row['card_id']} | {specs[row['method_key']]['distinguishing_feature'].replace('|', '/')} | {cross['score']} | {audit['score']} | {row['average_score']:g} | {'통과' if row['development_review_passed'] else '보완 대기'} |")
    report += ['', '점수별 구체적인 이유는 [교차 검토 M01–M13](reviews-boundary.json), [교차 검토 M14–M25](reviews-methods.json), [전체 하니스 검토](reviews-harness.json)에 보존했다. 동일 설비명·말투 변경을 별도 방법으로 세지 않았고 합성 자료를 25개 실제 사건으로 계산하지 않았다.', '',
               '## D. 보완 대기와 개선 의견', '',
               '현장 근거 기준에서는 25건 모두 보완 대기다. 기존 원문 후보 Q01–Q08의 부족 자료도 [기존 보고서](../20260925-t4-evidence-review/review.md)에 유지한다. 아래는 개발용 검토에서 남은 의견이며 점수에 반영되어 있다.', '']
    for row in rows:
        for review in row['reviews']:
            for finding in review['findings']:
                report.append(f"- {row['method_key']} ({review['reviewer']}, {finding['severity']}): {finding['detail']}")
    report += ['', '## E. 목표 대비 수량과 추가 자료', '',
               f'- 합성 개발 초안: {accepted}/25건 통과, 부족 {25-accepted}건.',
               '- 원문만으로 검증된 지식카드: 0/25건, 부족 25건. 확인된 실제 사건: 0건.',
               '- 추가 확보: 현장의 실제 인계 규정·양식과 적용 범위, 수신 역할과 채널, 전달 시점, 항목별 확인 응답·미응답 처리 기록, 승인권과 수신 확인의 구분, 비식별화된 송수신 원문 및 원문 접근·판본 기록. 각 방법에 해당하는 자료로 필드별 합성 제안을 검증·교체해야 한다.',
               '- 관리값은 [배치 정책](batch-policy.json)과 [실행 원장](manifest.json)에 산출 근거를 기록했다. ID는 조사한 파일 범위의 미사용 번호이며 전역 발급 승인이 아니다. 버전은 정책·명세 해시, provenance는 실제 실행 입력·시각이다. 운영 등록부·분할표·DB는 수정하지 않았다.', '',
               '재검증 명령(프로젝트 루트):', '', '```powershell',
               'python docs/data/knowledge_cards/drafts/20260925-t4-synthetic/evaluate.py',
               'python docs/data/knowledge_cards/drafts/20260925-t4-synthetic/summarize.py', '```', '',
               '`build.py`를 재실행하면 실제 생성 시각과 카드 파일 해시가 바뀐다. 그 경우 점수 파일을 그대로 재사용하지 말고 변경된 카드에 대한 독립 검토를 다시 받아야 한다. 기존 production 생성 파이프라인·사람 승인·현장 운용 성능을 통과했다는 결과가 아니다.', '']
    (HERE/'README.md').write_text('\n'.join(report), encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('development_passed','development_shortfall','average_score','minimum_card_average','maximum_card_average')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
