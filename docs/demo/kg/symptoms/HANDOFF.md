# 증상 담당 인계 (HANDOFF)

- 역할: 증상 담당 / 브랜치 `codex/kg-symptoms`
- 기준 커밋 B: `5167376b5ded1e33725394f2b65cb6977c121dec` (작업 시작 시 HEAD 일치 확인)
- 계약: `kg-demo-v1`, `docs/demo/kg/schema.md` SHA-256 `ad460fc639146d17d448457a5c0a7908bf4aaca92f4098860456401fe0b81613`
- 입력: `docs/data/knowledge_cards/kb/kb_cards.json` SHA-256 `05cfc4e79a3087e3544fc01e6b830268b542f55ae3be31bd6ad7601fc1d6dd3a` (실행 전후 동일)
- `symptom_concepts.json` SHA-256 `C1765E5F82EFA3DC11E7C84F663B7A33385A1719ED0C2758535E4074E3B76556`
- 적용되는 `AGENTS.md`는 저장소에서 찾지 못했다(없음).

## 만든 파일 (모두 `docs/demo/kg/symptoms/`)

| 파일 | 목적 |
|---|---|
| `symptom_concepts.json` | concepts 18, card_map 86, needs_review 86 |
| `review.md` | 카드별 원문 증상·후보·보류 사유, 병합/비병합 판단, 사람 확인 사항 |
| `build_symptom_concepts.py` | 판단 표(개념·연결·보류)에서 위 두 파일을 생성. 안전·null 보류는 KB 플래그로 강제. assert 자가 점검 포함 |
| `check_symptoms.py` | 독립 검증. 위반 사례를 거부하는 assert 자가 점검 포함 |
| `HANDOFF.md` | 이 문서 |

## 실행 명령과 결과

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONDONTWRITEBYTECODE='1'
python docs/demo/kg/symptoms/build_symptom_concepts.py   # written
python docs/demo/kg/symptoms/check_symptoms.py
# cards=86 safety=56 null=13 held_union=58 non_safety_string=28 linked=18 unlinked=10 concepts=18
# ok
python scripts/check_knowledge_publication.py            # ok: true, errors: []
```

검증 범위: 카드 집합 일치(86), 중복·누락, 미정의 개념 참조, 미참조 개념, 안전·null 카드 연결 0, needs_review 86개 고유·사유 비어 있지 않음, KB 해시 불변. 자가 점검은 안전/null 연결, 미정의 개념, 누락 카드, 빈 사유를 거부하는지 확인한다.
`git diff --check` 이상 없음. 추적 파일 변경 없음(신규 파일만).

## 집계

| 구분 | 카드 수 | card_map |
|---|---:|---|
| safety_flag=true | 56 | 빈 배열 |
| symptom=null | 13 (안전 11 + 비안전 2) | 빈 배열 |
| 위 두 집합 합집합 | 58 | 빈 배열 |
| 나머지 비안전·문자열 | 28 | 연결 후보 18, 보류 10 |

- 보류 10장: K-1101, 1102, 1104, 1106, 1107, 1108, 1109, 1111, 1324, 1401 (인계·절차 서술, 사유는 review.md)
- 연결 후보 18장은 개념 18개를 참조하며, K-1323만 3개, 나머지는 1개다. K-1201+1202, K-1301+1303은 한 개념을 공유한다.
- 안전 카드 45장(증상 문자열 있음)의 후보는 review.md 4절에만 있다.

## 사람이 검수할 사항

review.md 7절 참조. 요점: 복합 개념(K-1004, K-1011, K-1323) 단위, K-1301의 '출력 저하' 처리, 병합 2건, 보류 카드 중 K-1105/K-1107 판단, 안전 카드 후보의 후속 연결, 정의 문장에 들어간 프로젝트 설정 임계값.

## 한계

- 모든 연결은 사람 검수 전이며 의미 정확성이나 안전성을 보증하지 않는다.
- 판단은 카드 원문(symptom, 필요 시 know_how) 읽기에 근거하며 외부 모델·임베딩을 쓰지 않았다.
- `build/graph.json`은 만들거나 수정하지 않았다. 계약 변경 요청 없음.
- 커밋·push는 하지 않았다.
