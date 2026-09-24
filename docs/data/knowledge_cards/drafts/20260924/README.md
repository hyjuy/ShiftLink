# 원문 기반 지식카드 초안 — 2026-09-24

사용자가 승인한 `docs/data/knowledge_cards` 아래의 기본 보관본이다. 기존 작업 폴더 `artifacts/knowledge-card-team-20260924/`는 생성·검증 당시 기록으로 남겼다. 앞으로 이 초안의 검토는 이 디렉터리의 파일을 기준으로 한다.

- [카드 JSON](cards.json): K-0301~0303, draft/L0. 컨베이어 보조설비 안전·재기동에 관한 2012년 문헌 요약이다.
- [카드 읽기](cards.md) 및 [페르소나별 설명](persona-review/cards-by-persona.md)
- [사용자 원문 일치 확인](human-review.json)
- [원문 근거](source-packet.json) 및 [필드별 근거 연결](evidence-map.json)
- [독립 검토](review.md) 및 [분석](analysis.md)
- [기존 생성 검증 기록](validation.json) 및 [보관 검증](storage-manifest.json)

이번 승인은 보관 위치 승인이다. 원문 일치에 대한 사용자 확인은 완료됐으나, 냉간코일 공정 적용성·현장 안전 검토·출처 이용 범위·운영 KB 채택은 별도 미확인이다. `accepted/L1`로 변경하지 않았다.

원문 PDF·페이지 이미지는 기존 원문·작업 위치에 유지했다. JSON 내부의 저장소 상대 원문 경로는 저장소 루트를 기준으로 해석한다. `validation.json`과 검토 파일의 해시는 생성 당시 기록이며 이번 보관 검증과 구분한다. 원래 검증 스크립트는 `artifacts/knowledge-card-team-20260924/validate.py`에 있다.

이 경로는 Git 추적 가능한 위치이며, 이번 작업에서는 커밋·푸시하지 않았다.
