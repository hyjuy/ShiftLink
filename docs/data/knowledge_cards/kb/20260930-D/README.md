# KB 카드 배치 KB-20260930-D

- 시드: `20260930` — [`plan.py`](plan.py)가 이 시드로 슬롯(카드 ID·설비·유형)을 정한다. 같은 시드면 [`plan.json`](plan.json)이 바이트 단위로 같다.
- 생성: Claude Code 서브에이전트(general-purpose), 모델 `claude-opus-5-5`, 2026-09-30.
- 프롬프트: [`prompt_template.md`](prompt_template.md) → [`render_prompts.py`](render_prompts.py) → `prompts/<설비>.md`. 해시는 [`prompts/index.json`](prompts/index.json).
- 서브에이전트에게 준 지시는 프롬프트 파일을 읽고 따르라는 한 줄뿐이다(`index.json`의 `dispatch.wrapper`). 실제 지시 내용은 프롬프트 파일과 같다.
- **재현성 한계**: 시드는 슬롯 계획만 고정한다. LLM이 쓴 카드 본문은 같은 프롬프트로 다시 돌려도 똑같이 나오지 않는다. 그래서 프롬프트 원문과 해시, 카드별 근거 페이지를 남긴다.
- 모든 카드는 `status=draft`, `grade=L0`, `split=kb`이다. accepted 여부는 사람이 검수해 정한다.

## 카드 → 프롬프트 추적표

각 카드의 `provenance.prompt_version` = `<프롬프트 경로>@sha256:<해시>`, `provenance.seed_ids` = `["KB-20260930-D:seed=20260930", "slot:<Sxx>"]`.

| 카드 | 슬롯 | 설비 | 유형 | 제목 | 생성 프롬프트 | 프롬프트 sha256 | 근거 |
|---|---|---|---|---|---|---|---|
| K-1301 | S01 | CAU | T1 | 압축공기 압력 저하 — 누설과 계통 압력강하 부위 의심 | [prompts/CAU.md](prompts/CAU.md) | `9299048aa659` | compressed-air-ref-eng.pdf PDF p.79~80, 83 / 인쇄 p.79~80, 83 / 9a Compressed Air System Leaks, How to Track Down Air Leaks; compressed-air-ref-eng.pdf PDF p.85, 87 / 인쇄 p.85, 87 / 9b Lower Compressor Discharge Pressure by Minimizing Pressure Drops |
| K-1302 | S02 | CAU | T1 | 압축공기 누설음 — 청취·초음파·비눗물로 위치 찾기 | [prompts/CAU.md](prompts/CAU.md) | `9299048aa659` | compressed-air-ref-eng.pdf PDF p.82~83 / 인쇄 p.82~83 / 9a How to Track Down Air Leaks, Caution; Manual-on-Energy-Efficiency.pdf PDF p.75 / 인쇄 p.57 / 4.3.4 Energy efficiency in compressed air system — Compressed air system leaks |
| K-1303 | S03 | CAU | T3 | 압력 저하 시 누설 부하 추정 — 압축기 정지·기동 압력 하강·상승 시간 시험 | [prompts/CAU.md](prompts/CAU.md) | `9299048aa659` | compressed-air-ref-eng.pdf PDF p.81~82 / 인쇄 p.81~82 / 9a Estimating Total Air Leaks |
| K-1304 | S04 | CAU | T5 | 공기압축기 안전밸브 — 압축기·단별 설치, 전후단 차단밸브 금지, 작동 확인 | [prompts/CAU.md](prompts/CAU.md) | `9299048aa659` | 산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf PDF p.46~47 / 제2편 제2장 제4절 제261조, 제264조, 제266조; Manual-on-Energy-Efficiency.pdf PDF p.93 / 인쇄 p.75 / 5.3.1 O&M practices and schedule — Monthly: Check safety valve operation |
| K-1306 | S06 | PDP | T1 | 차단기 트립 후 재투입하니 멀쩡하면 해결이 아니라 간헐 고장 징후로 본다 | [prompts/PDP.md](prompts/PDP.md) | `3a052cb6c859` | 15001-20000_16339.pdf PDF p.103-104 / 인쇄 020-021 OF 022 / 2.7 General; 산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf PDF p.57 / 제317조제1항제5호 |
| K-1307 | S07 | PDP | T1 | 대형 모터 기동·부하 피크 때 버스 전압이 잠깐 떨어지는 것은 기동 전류에 따른 전압 강하 후보다 | [prompts/PDP.md](prompts/PDP.md) | `3a052cb6c859` | d2e0a4ea3d7e62b24193679803b73e6.pdf PDF p.6 / 인쇄 p.6 / 3. ABB Electrical System Study - Motor Starting Study; 15001-20000_16339.pdf PDF p.56 / 인쇄 046 OF 046 / 4. Network |
| K-1308 | S08 | PDP | T3 | 차단기 트립으로 급전 설비가 멈췄을 때 최초 신호부터 퓨즈·제어회로·전압 순으로 좁힌다 | [prompts/PDP.md](prompts/PDP.md) | `3a052cb6c859` | 15001-20000_16339.pdf PDF p.86-88 / 인쇄 003-005 OF 022 / 1. Trouble shooting - signals, 2.1 AC-Drives; 산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf PDF p.57-58 / 제317조제1항제5호, 제318조, 제319조 |
| K-1309 | S09 | PDP | T5 | 트립 표시나 전압 표시만 보고 배전반 충전부에 손대지 않는다 — 차단·잠금·검전 후에만 | [prompts/PDP.md](prompts/PDP.md) | `3a052cb6c859` | 산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf PDF p.57-58 / 제318조, 제319조; E-7-2012 전기작업에 관한 기술지침.pdf PDF p.9 / 인쇄 p.7 / 5.3.1; PDF p.15 / 인쇄 p.13 / 5.3.12(2) |
| K-1310 | S10 | PDP | T2 | 버스 전압 low와 차단기 트립이 겹치면 부하측 고장 단정 전에 전원측 전압 상실을 먼저 본다 | [prompts/PDP.md](prompts/PDP.md) | `3a052cb6c859` | 15001-20000_16339.pdf PDF p.36, 44, 46-47 / 인쇄 026, 034, 036-037 OF 046 / 1.10 Overcurrent protection, 2.4 High Speed Circuit Breaker; 산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf PDF p.57 / 제317조제1항제5호 |

## 미작성 슬롯 (1)

K-1305 — 사유는 `out/<설비>_notes.md`.
