# 배치 C 통합·검수 흐름 독립 검증

검증 시점: 2026-09-30. 아래 초기 재현과 루트 에이전트 수정 후 재검증을 구분한다. 운영 KB와 카드 내용은 수정하지 않았다. `eval/` 파일은 읽지 않았다. Python 3.10.21, Pydantic 2.9.2, 기존 로컬 캐시와 `.test-deps`를 사용했다.

## 수정 후 독립 재검증

루트 에이전트가 C의 verify, merge, build_docs를 수정한 뒤 `workflow_recheck.py`를 실행했다. 결과는 `workflow-recheck-results.json`에 남겼다.

- accepted/L1 상태는 정상 검증된다. 실제 사람 승인 및 정책 적합성 확인은 별도 절차로 남아 있다.
- 문서 재생성 시 사람 판정과 사람 판정 근거가 모두 보존된다.
- 카드 슬롯 누락, 잘못된 Pydantic 조건 연산자, 카드가 인용하는 프롬프트 훼손, stage-a-records 프롬프트 훼손은 모두 병합 전에 실패한다. 네 경우 모두 기존 cards.json과 prompts/index.json 바이트가 그대로 유지된다.
- KB 사건 관측투영의 action 변경은 `KB event observation projection differs from ledger`, KB 기록 text 변경은 `KB artifact projection differs from ledger`로 실패한다.

초기에 재현한 네 결함은 수정 후 검증에서 해소됐다. 아래 초기 기록은 판정과 수정 근거를 보존하기 위한 것이다. 승인 절차의 실제 사람 판정, 출처 등록, 근거 그룹 및 KB/dev 분리, CI 검색 성능은 여전히 별도로 판단해야 한다.

## 결론

현재 draft 배치는 `verify.py`를 통과한다. 기존 K- ID 충돌은 없다. 임시 경로에서 C 19장을 accepted/L1로 바꾸고 상위 빌더에 추가하면 60장 KB가 생성되고 실제 로더가 60장을 읽는다. 구조와 로더의 직접 충돌은 재현되지 않았다.

초기 검증에서는 승인 상태 검증, 사람 판정 근거 보존, 검증 전 병합 쓰기, 추출 입력과 원장 동기화의 네 결함을 재현했다. 수정 후 재검증에서 네 결함은 해소됐다. 이번 결과는 승인이나 검색 성능 충족을 뜻하지 않는다.

## 재현된 문제와 최소 수정 범위

| 우선순위 | 위치 | 확인 결과 | 배치 C 내 수정 제안 |
|---|---|---|---|
| 높음 | `docs/data/knowledge_cards/kb/20260930-C/verify.py:58` | 19장을 accepted/L1로 바꾸면 첫 카드 `K-1201`에서 `AssertionError` 발생. 기존 T4 검증기는 draft/L0와 accepted/L1을 모두 허용한다. | 두 조합을 허용하고 accepted 카드마다 사람의 승인 판정과 비어 있지 않은 판정 근거가 존재하는지 검증한다. |
| 높음 | `docs/data/knowledge_cards/kb/20260930-C/build_docs.py:12`, `:29` | 기존 사람 판정 `accepted | AUDIT`는 보존되지만 `AUDIT essential evidence` 근거는 재생성 후 사라진다. | 카드 블록별 판정과 판정 근거를 함께 보존한다. |
| 높음 | `docs/data/knowledge_cards/kb/20260930-C/merge.py:10`, `:21` | 입력 `[{"card_id":"K-AUDIT"}]`도 `cards.json`으로 정상 저장한다. Pydantic/19슬롯/유형/출처 검증을 하지 않는다. | 파일 쓰기 전에 스키마와 슬롯 계약을 검증한다. 프롬프트 핀도 검증한 뒤 인덱스와 cards를 기록한다. |
| 높음 | `docs/data/knowledge_cards/kb/20260930-C/verify.py:31`~`:35` | records/kb_events 첫 시도의 action을 바꾸거나 records/kb_artifacts 첫 text를 바꿔도 검증이 PASS이다. ID 집합만 검사하므로 카드 추출 입력과 검증 원장이 달라도 통과한다. | events에서 정답 필드 세 개를 제거한 KB 투영과 records/kb_events가 전체 값 기준으로 같고, artifacts의 KB 필터와 records/kb_artifacts가 같은지 검사한다. |

`workflow_probe.py`는 운영 파일을 읽고 입력을 메모리에서 바꾸거나 `artifacts/batch-c-conflict/`에만 임시 복사한다. 원본 데이터를 바꾸지 않고 각 결함을 재현했다. 결과는 `workflow-probe-results.json`에 남겼다.

## 흐름별 검증 결과

- `plan.py`는 T2 10장과 T6 9장, K-1201~1219를 고정한다. 본문은 시드로 재생성되지 않는다는 제한을 README와 plan 주석에 명시했다.
- C 전용 `apply_review.py`는 없다. A의 승격기는 A의 고정 경로와 `**판정**` 형식을 사용하므로 C의 `**사람 판정**`에 그대로 실행할 수 없다. 사람 승인 후 `out/*.json`의 해당 카드 status/grade를 바꾸고 merge/verify/build_docs를 실행하는 구체 절차가 필요하다. `cards.json`만 바꾸면 merge가 이전 out 내용으로 덮어쓴다.
- 상위 `build_kb.py:14`의 BATCHES는 A와 T4만 포함한다. 사람 검수 전 C 제외는 의도한 상태다. 승인 후 목록에 C를 추가하고 빌더를 실행해야 `tests/test_kb_cards.py`의 통합 파일 동등성 검사와 실제 로더가 새 카드를 사용한다.
- 임시 통합 결과는 60장이며 유형별 T1 11, T2 12, T3 10, T4 11, T5 7, T6 9다. 실제 `load_card_provider`의 seen 역시 60이다.
- 기존 카드 충돌 검사는 `docs/data`의 C 외 JSON에서 실제 카드 구조를 갖는 레코드와 대조했다. 결과는 0건이다. eval 디렉터리와 C 자체 out/records 중복은 제외했다.
- 프롬프트 경로는 현재 `prompts/*.md` 세 개로 하위 디렉터리가 없다. 카드의 프롬프트 해시는 verify가 검사하며, 수정된 merge는 stage-a-records를 포함한 기존 인덱스와 실제 해시 일치도 검사한다. 하위 디렉터리를 추가하면 glob 수집 범위를 바꿔야 한다. 현재 구조에는 이 문제가 없다.
- 기존 `tests/test_kb_cards.py`는 accepted 통합 KB만 검증한다. draft 상태 C는 CI pytest에 의해 자동으로 배치 계약 검증되지 않는다. C용 verify는 별도 실행이 필요하다.

## CI 확인과 판정 한계

`git show origin/main:.github/workflows/ci.yml`로 실제 main CI를 확인했다. Python 3.10, requirements 설치, `python -m pytest -q`, route_score를 실행하며 dev_route_acc >=20, sanity_route_acc >=28을 요구한다. 현재 작업 트리에는 `.github/workflows/ci.yml`이 없다.

기존 C validation 기록은 pytest 445 passed, route_score dev 18/30와 sanity 26/30을 보고한다. 이 문서는 과거 보고값을 인용한 것이며 평가 파일을 읽거나 평가를 다시 실행하지 않았다. 루트 에이전트가 수행한 현재 테스트 결과와 합쳐 판단해야 한다. 구조적으로 60장을 로딩한 사실만으로 route_score 하한 충족을 주장할 수 없다.

다른 독립 검증의 출처 승인기록, 근거 그룹, KB/dev 템플릿 분리 문제와 사람의 설비 적용성 검수를 함께 해소하기 전에는 KB 편입을 보류한다. 이 검증에서는 실제 accepted 승격, 상위 BATCHES 변경, 운영 KB 재생성을 하지 않았다.

## 재현 명령

```powershell
$env:PYTHONPATH='C:/Users/hyjuy/AppData/Local/uv/cache/archive-v0/griEm9zYawKxZPtY;.test-deps'
& 'C:/Users/hyjuy/AppData/Roaming/uv/python/cpython-3.10.21-windows-x86_64-none/python.exe' artifacts/batch-c-conflict/workflow_probe.py
```
