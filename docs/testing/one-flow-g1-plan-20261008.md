# 한 흐름 시험 계획 (G1 · W2-1) — 2026-10-08

**무엇을 보는가**: Unity 가상 공장에서 작업자가 PDA로 설비를 찍으면, 그 사진이 파이 CNN에서 클래스명이 되고, Jetson이 그 설비로 기록한 뒤, 실물 PDA에서 그 설비 기준 답이 나오는가. 사람이 설비를 고르지 않고 끝까지 간 **1건 이상의 기록**이 목표다.

```
[Unity PDA 촬영 PNG+JSON] → send_unity_captures.py → [파이 classify --listen] → POST /api/equipment/scan → [Jetson MES]
                                                                                                         ↓
                                     [실물 PDA 스캔 화면이 그 설비를 자동 선택] → 증상 질의 → /api/query(scan_id) → 답 화면
```

루브릭: W2-1 "클래스명이 `eq_id`로 바뀌어 Jetson 답변 화면까지 간 1건의 기록", G1 "W2-1과 같은 종류의 증거, 화면이 Jetson 답". 수동 선택(직접 선택)은 세지 않는다.

## 0. 선행 조건 (모두 되어야 시작)

| 항목 | 확인 방법 | 담당 |
|---|---|---|
| 실제 Unity 이미지로 학습한 FP32 모델이 파이 `~/shiftlink/models/cnn`에 있다 | `labels.txt` 6클래스, 시험셋 클래스별 정확도 기록 있음(G5) | Claude |
| 확신도 기준 `--min-conf`를 **검증셋**으로 정했다(시험 중 바꾸지 않음) | 결정 값과 근거를 결과에 적음 | Claude |
| 파이 수신 서버 실행: `classify --model ~/shiftlink/models/cnn --listen 8090 --server http://<jetson>:8000 --device-id pi-01 --min-conf <값>` | 로그 첫 줄 `사진 수신: …` | Claude |
| 다른 장치가 인식을 보내지 않는다 | `/api/equipment/scan/recent`의 최근 기록이 `pi-01`뿐(10/8 오전 `pi-01-c3` 기록 출처 미확인) | Claude |
| Jetson `shiftlink-mes` active, 예열 끝, 데스크톱 꺼짐 | `preflight.sh`의 Jetson 항목 또는 `systemctl is-active` | Claude |
| 실물 PDA 로그인, **대시보드에 다녀오지 않은 상태** | 대시보드 왕복 뒤 카메라가 안 열리는 문제(10/8) 회피 | 재영 |
| Unity PC에서 감시 실행: `python scripts/send_unity_captures.py --dir <Unity 촬영 폴더> --pi http://<파이>:8090` | `감시: … (기존 N장 건너뜀)` 출력 | 현준 |

## 1. 절차 (설비 1개당 약 3분, HPU → GR → CV)

| 단계 | 누가 | 하는 일 | 기록 |
|---|---|---|---|
| 1 | 재영 | PDA 홈 → **설비 스캔** 화면을 띄워 둔다(인식 대기) | 화면 사진 |
| 2 | 현준 | Unity에서 작업자를 목표 설비 앞으로 옮겨 PDA로 **촬영·저장** | Unity 화면 사진, 저장 파일 이름 |
| 3 | 자동 | 감시 스크립트가 사진을 파이로 보냄 | 감시 출력 한 줄: `파일: 클래스 conf ms 확정 Jetson전송` |
| 4 | 자동 | 파이가 확정 → Jetson에 인식 기록 | 파이 로그 `확정 … sent=True`, Jetson `scan_id`·`class`·`conf`·`equipment_id` |
| 5 | 재영 | PDA 스캔 화면이 그 설비를 **스스로** 고르는지 본다 → 작업 선택 → 증상 질의 | PDA 화면 사진(설비 이름·코드) |
| 6 | 재영 | 그 설비의 시연 질문(`docs/planning/시연_질문_9개_20261006.md`) 1개를 보낸다 | 질문 문장 |
| 7 | 자동 | Jetson 답 | PDA 답 화면 사진(안전 카드 → 답 → 근거 카드 ID), Jetson `query_log`의 `query_id`·`equipment_id`·`cited_card_ids`·시각 |

`query_log`에는 `scan_id`가 없다. 질의와 인식은 **같은 `equipment_id`와 시각 순서**(인식 → 질의, 1분 이내)로 잇는다.

## 2. 통과 조건 (미리 고정)

한 건이 통과하려면 모두 맞아야 한다.
1. Unity에서 찍은 설비 = 파이 인식 클래스 = Jetson `equipment_id`의 설비 = PDA에 표시된 설비.
2. PDA에서 사람이 설비를 고르지 않았다(스캔 화면에서 자동 선택).
3. 답 화면이 Jetson 응답이다: 근거 카드 ID가 있고, 그 설비의 안전 카드가 답보다 앞이다(G2와 같은 조건).
4. 기록 4종(Unity 사진·감시 출력·Jetson 인식·Jetson 질의)이 같은 설비·시각 순서로 이어진다.

**판정**: 3대 중 1건 이상 통과 → W2-1 2점, G1 통과. 3대 모두의 결과(통과·실패와 이유)를 그대로 적는다.

## 3. 실패했을 때

| 상황 | 할 일 |
|---|---|
| 보류(확신도가 기준 미만) | 같은 설비를 다른 각도로 한 번 더 찍는다. 기준값은 바꾸지 않는다. 보류 횟수를 적는다 |
| 오분류 | 실패로 적고 다음 설비로 넘어간다. 이 시험에서 모델·기준을 고치지 않는다 |
| PDA가 설비를 안 고름 | Jetson 인식 기록이 있는지 먼저 본다. 있으면 PDA 문제, 없으면 파이·전송 문제로 나눠 적는다 |
| 질의 실패(503 등) | 30초 뒤 같은 질문을 한 번 다시 보낸다. 다시 실패하면 실패로 적는다 |
| 카메라·화면 멈춤 | 키오스크 재시작 후 1단계부터. 재시작한 사실을 적는다 |

## 4. 결과 기록

- 저장소 밖 `ShiftLink-records/experiments/g1_<날짜>/RESULT.md`: 설비별 표(시각, Unity 파일, 인식 클래스·확신도, `scan_id`, `equipment_id`, PDA 표시, 질문, `query_id`, 근거·안전 카드, 판정) + 사진.
- 요약은 이 문서 아래 "결과" 절에 덧붙인다.
- 이어서 같은 모델·기준으로 `bench/camera_flow_bench.py`(W3-1, 20건)를 돌린다. 한 흐름은 사람이 보는 화면 증거, 20건은 성공 수·p95다.

## 5. 이 시험이 보여 주지 않는 것

- CNN 정확도(G5·W3-2): 시험셋 클래스별 정확도로 따로 낸다.
- 실제 카메라 사진: 입력은 Unity 렌더 사진이다. 발표에는 "Unity 이미지 기준"이라고 적는다.
- 지연 p95(W3-1): 20건 측정에서 낸다.
