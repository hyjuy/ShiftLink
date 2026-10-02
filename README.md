# ShiftLink

베테랑 노하우 기반 포터블 MES 보조 에이전트 (Jetson Orin Nano 온디바이스)

## 담당
| 영역 | 담당 | 디렉토리 |
|---|---|---|
| Lead / 에이전트·스키마·통합 | 유현준 | `shiftlink/agent/` |
| AI / RAG·추출·합성데이터 생성 | 최재영 | `shiftlink/rag/`, `shiftlink/data/` |
| Embedded / Jetson·추론·저장 | 허재원 | `shiftlink/edge/` |
| 모의 MES | 유현준·허재원 | `shiftlink/mes/` (실행 DB `mes_data/`) |
| PM·QA / 검수·평가·시나리오 | 전혜민 | `eval/` |

## 지식 카드

통합 목록 `docs/data/knowledge_cards/kb/kb_cards.json`은 **86장**이다. 배치 A 30, T4 12(기존 11 + #148 인계 완료 K-1401, 배치 `20261001-handover-completion`), C 19, D 25(1~3차 21장 + 10/1 4차 K-1322~1324 + 5차 K-1325).

블라인드 2차 `eval/qa/20261001-blind2/qa_blind2.json`은 답 있음 6/25이다. `python eval/qa/route_score.py`의 `blind2_route_acc`는 이 셋의 보고 전용이라, 점수를 보고 검색을 맞추지 않는다.

## 브랜치 전략
자세한 내용은 [`docs/collaboration/branching.md`](docs/collaboration/branching.md) 참고.

## PR 올리기 전 확인

CI는 `dev_route_acc`가 20/30 미만이거나 `sanity_route_acc`가 28/30 미만이면 실패한다.

```
python -m pytest -q
python docs/data/knowledge_cards/kb/build_kb.py
python eval/qa/route_score.py
```
