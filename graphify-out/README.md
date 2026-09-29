# graphify-out — 저장소 지식그래프

[graphify](https://github.com/safishamsi/graphify)로 만든 ShiftLink 저장소 지식그래프다. 코드·문서·원문 PDF에서 개념과 관계를 뽑아 그래프로 묶었다.

| 파일 | 내용 |
|---|---|
| `graph.html` | 브라우저로 여는 인터랙티브 그래프 (설치 불필요) |
| `GRAPH_REPORT.md` | 커뮤니티·핵심 노드·의외의 연결 요약 |
| `graph.json` | 그래프 원본 (경로는 저장소 기준 상대 경로) |
| `manifest.json`, `cache/` | 증분 갱신(`--update`)용. 바뀐 파일만 다시 추출하게 해 준다 |

## 1. 보기만 할 때 — 설정 없음

`graph.html`을 브라우저로 연다.

## 2. 질의할 때 — graphify 설치만

```bash
uv tool install graphifyy          # 또는 pip install graphifyy
cd <저장소 루트>
graphify query "KnowledgeCard 스키마가 바뀌면 어디가 영향을 받나"
graphify explain "K-1024"          # 카드 → 생성 프롬프트(sha256) → 근거 PDF
graphify path "K-1024" "Prompt KB-20260929-A/GR"
```

## 3. 갱신할 때 — 내 PC 경로 2개만 만든다

`.graphify_python`, `.graphify_root`는 PC마다 다르므로 커밋하지 않는다(`.gitignore`). 저장소 루트에서 한 번만 실행한다.

```bash
uv tool run --from graphifyy python -c "import sys; open('graphify-out/.graphify_python','w',encoding='utf-8').write(sys.executable)"
python -c "import os; open('graphify-out/.graphify_root','w',encoding='utf-8').write(os.getcwd().replace(chr(92),'/'))"
```

그다음 Claude Code에서 `/graphify . --update`를 실행한다. 바뀐 파일만 다시 추출한다(코드는 LLM 없이 AST, 문서·PDF는 LLM).

## 저장소에 없는 원문 PDF

`docs/manual/`의 Parker·Bosch·SKF(BR) PDF 4개는 커밋하지 않는다. 팀원이 각자 같은 경로·파일명으로 보유하고 있다. 그래프에는 이 문서들의 짧은 요약(최대 약 180자)만 들어 있고, 파일이 없는 PC에서 `--update`를 돌리면 해당 노드가 지워진다.

## 주의
- 그래프는 **만든 시점의 스냅샷**이다. 최신 코드와 다를 수 있으니 `GRAPH_REPORT.md` 머리의 날짜를 확인한다.
- 커밋하면 저장소 크기가 매번 수 MB씩 늘어난다. 갱신본은 필요할 때만 올린다.
