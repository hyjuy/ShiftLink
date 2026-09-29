# KB 카드 배치 KB-20260929-A

- 시드: `20260929` — [`plan.py`](plan.py)가 이 시드로 슬롯(카드 ID·설비·유형)을 정한다. 같은 시드면 [`plan.json`](plan.json)이 바이트 단위로 같다.
- 생성: Claude Code 서브에이전트(general-purpose), 모델 `claude-opus-5-5`, 2026-09-29.
- 프롬프트: [`prompt_template.md`](prompt_template.md) → [`render_prompts.py`](render_prompts.py) → `prompts/<설비>.md`. 해시는 [`prompts/index.json`](prompts/index.json).
- 서브에이전트에게 준 지시는 프롬프트 파일을 읽고 따르라는 한 줄뿐이다(`index.json`의 `dispatch.wrapper`). 실제 지시 내용은 프롬프트 파일과 같다.
- **재현성 한계**: 시드는 슬롯 계획만 고정한다. LLM이 쓴 카드 본문은 같은 프롬프트로 다시 돌려도 똑같이 나오지 않는다. 그래서 프롬프트 원문과 해시, 카드별 근거 페이지를 남긴다.
- 모든 카드는 `status=draft`, `grade=L0`, `split=kb`이다. accepted 여부는 사람이 검수해 정한다.

## 카드 → 프롬프트 추적표

각 카드의 `provenance.prompt_version` = `<프롬프트 경로>@sha256:<해시>`, `provenance.seed_ids` = `["KB-20260929-A:seed=20260929", "slot:<Sxx>"]`.

| 카드 | 슬롯 | 설비 | 유형 | 제목 | 생성 프롬프트 | 프롬프트 sha256 | 근거 |
|---|---|---|---|---|---|---|---|
| K-1001 | S01 | HPU | T3 | 기어·베인 펌프 출구 압력이 없을 때 확인 순서 — Algo A.1 좌측 분기 | [prompts/HPU.md](prompts/HPU.md) | `189597764cf4` | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf PDF p.17 / 인쇄 p.17 / Algo A.1 System test for gear and vane pumps |
| K-1002 | S02 | HPU | T3 | 수냉식 오일 쿨러 출구 유온 확인 순서 — Algo J.2 | [prompts/HPU.md](prompts/HPU.md) | `189597764cf4` | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf PDF p.29 / 인쇄 p.29 / Algo J.2 System test for coolers |
| K-1003 | S03 | HPU | T5 | 용적형 펌프 과압 보호 없이 운전 금지·릴리프 설정을 펌프 최대 정격 위로 두지 않기 | [prompts/HPU.md](prompts/HPU.md) | `189597764cf4` | HY13-PMDSPS1M_US.pdf PDF p.15 / 인쇄 p.11 / §3.7.2 Relief Valve, DANGER |
| K-1004 | S04 | HPU | T1 | 베인펌프 소음 증가와 유면 우유빛 거품 — 에어레이션 징후 | [prompts/HPU.md](prompts/HPU.md) | `189597764cf4` | HY29-0022-UK.pdf PDF p.24~27 / 인쇄 p.25~28 / §2.4 2) Air contamination - a) Aeration, b) Consequences of aeration; HY29-0022-UK.pdf PDF p.36 / 인쇄 p.37 / §6 Consequences of water contamination |
| K-1005 | S05 | HPU | T3 | 축압기 프리차지·충전 압력 확인 순서 — Algo J.1 | [prompts/HPU.md](prompts/HPU.md) | `189597764cf4` | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf PDF p.28 / 인쇄 p.28 / Algo J.1 System test for accumulators |
| K-1006 | S06 | HPU | T5 | 유압 파워 유닛 운전 중 정비 금지·정비 전 해당 계통 감압 | [prompts/HPU.md](prompts/HPU.md) | `189597764cf4` | MAN-C-012.pdf PDF p.4 / 인쇄 p.5 / §1 Maintenance, WARNING |
| K-1007 | S07 | HPU | T2 | 작동유 점도 2000 cSt 초과(저온 등) 시 운전 전 워밍업 | [prompts/HPU.md](prompts/HPU.md) | `189597764cf4` | HY29-0022-UK.pdf PDF p.37 / 인쇄 p.38 / §7 Viscosity failures; AX189986484780en-000501.pdf PDF p.37 / 인쇄 p.37 / Troubleshooting: Excessive Noise and/or Vibration, Low Pump Output Flow — Hydraulic fluid viscosity above acceptable limits |
| K-1008 | S08 | HPU | T1 | 작동유가 크림색·우유빛으로 변하고 탱크에 젤라틴 덩어리 — 수분 오염 징후 | [prompts/HPU.md](prompts/HPU.md) | `189597764cf4` | HY29-0022-UK.pdf PDF p.35 / 인쇄 p.36 / §5 Water contamination; HY29-0022-UK.pdf PDF p.26 / 인쇄 p.27 / §2.4 2) b) Consequences of aeration (우유빛 거품 구분용) |
| K-1009 | S09 | CV | T5 | 건널다리·지정 통로 밖에서 컨베이어 위·아래 횡단 금지 — 2012년 지침 요약 | [prompts/CV.md](prompts/CV.md) | `55a5055cc649` | M-101-2012 컨베이어의 안전에 관한 기술지침.pdf PDF p.8 / 인쇄 p.6 / 4.3 사용 (12); M-101-2012 컨베이어의 안전에 관한 기술지침.pdf PDF p.6 / 인쇄 p.4 / 4.2 설치 (8) |
| K-1010 | S10 | CV | T3 | 벨트 사행 시 빈 벨트 운전으로 정렬부터 보고, 풀리가 아닌 상류 아이들러로 잡는다 | [prompts/CV.md](prompts/CV.md) | `55a5055cc649` | Martin_C4_CR_18_09_4_Manual.pdf PDF p.7 / 인쇄 p.5 / Belt Training 1~3 |
| K-1011 | S11 | CV | T1 | 아이들러 롤이 굼뜨고 고음 끽끽 소리가 나면 베어링 고장 임박 신호 | [prompts/CV.md](prompts/CV.md) | `55a5055cc649` | Martin_C4_CR_18_09_4_Manual.pdf PDF p.8 / 인쇄 p.6 / Conveyor Inspection 4 |
| K-1012 | S12 | CV | T3 | 직접구동형 소형 벨트 컨베이어 사행 보정은 수평부터 맞추고 치우친 쪽 장력 나사를 조금씩 | [prompts/CV.md](prompts/CV.md) | `55a5055cc649` | conveyor-manual-0323-en.pdf PDF p.62 / 인쇄 p.58 / 8.3 Alignment Correction, 8.3.1 Direct Drive Conveyors |
| K-1013 | S13 | CV | T1 | 벨트의 특정 구간만 모든 지점에서 한쪽으로 벗어나면 스플라이스·벨트 휨을 의심 | [prompts/CV.md](prompts/CV.md) | `55a5055cc649` | Martin_C4_CR_18_09_4_Manual.pdf PDF p.10 / 인쇄 p.8 / Particular Section of the Belt Runs Off to One Side at All Points; Martin_C4_CR_18_09_4_Manual.pdf PDF p.7 / 인쇄 p.5 / Belt Training 2 |
| K-1014 | S14 | CV | T5 | 운전 중 방호덮개·점검덮개 개방 금지 — 2012년 지침 요약 | [prompts/CV.md](prompts/CV.md) | `55a5055cc649` | M-101-2012 컨베이어의 안전에 관한 기술지침.pdf PDF p.8 / 인쇄 p.6 / 4.3 사용 (10) |
| K-1015 | S15 | CV | T3 | 운전 중 고장 대응 순서: 전원 분리·재기동 방지·표지 후 조치, 시운전 뒤 인계 | [prompts/CV.md](prompts/CV.md) | `55a5055cc649` | conveyor-manual-0323-en.pdf PDF p.69 / 인쇄 p.65 / 10. Fault Clearance, 10.1·10.2 |
| K-1016 | S16 | CV | T1 | 벨트 커버가 점·줄무늬로 부풀면 기름·그리스 오염과 아이들러 과급유를 의심 | [prompts/CV.md](prompts/CV.md) | `55a5055cc649` | Martin_C4_CR_18_09_4_Manual.pdf PDF p.14 / 인쇄 p.12 / Belt Covers Swell in Spots or Streaks |
| K-1017 | S17 | RT | T1 | 롤러 컨베이어에서 소음·끽끽·휘파람 소리가 나면 즉시 세우고 롤러 베어링을 의심한다 | [prompts/RT.md](prompts/RT.md) | `794ff2becaa8` | 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf PDF p.52 / Troubleshooting 표 'Noise development/squeaking/whistling'; 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf PDF p.11 / Safety – Dangers 'Stop the module at once … unusual noise' |
| K-1018 | S18 | RT | T5 | 하중을 실은 채로 리프트를 차단하지 않는다 — 하중 제거·양쪽 잠금·주전원 차단 후에만 플랫폼 아래로 | [prompts/RT.md](prompts/RT.md) | `794ff2becaa8` | 830CC-V1.pdf PDF p.12 / Lift Blocking Instructions 1~6, DANGER; 830CC-V1.pdf PDF p.5 / Dangers, Warnings & Cautions 'Do not work under lift without maintenance device' |
| K-1019 | S19 | RT | T5 | 코일카 아래 작업이나 유량 조절 전에는 좌우 정비 장치를 둘 다 끼운다 | [prompts/RT.md](prompts/RT.md) | `794ff2becaa8` | Coil-Cars.pdf PDF p.7~8 / Safe Servicing of the Lift, Figure 1 WARNING; Coil-Cars.pdf PDF p.9 / HAZARDS – WARNING(flow control, both maintenance devices) |
| K-1020 | S20 | RT | T1 | 상승 버튼을 누를 때 끽 하는 날카로운 소리가 나면 릴리프가 열린 것이다 — 몇 초 넘게 계속 누르지 않는다 | [prompts/RT.md](prompts/RT.md) | `794ff2becaa8` | 830CC-V1.pdf PDF p.7 / Dangers, Warnings & Cautions – CAUTION(relief, squealing sound); 830CC-V1.pdf PDF p.28 / General Maintenance – Lift Up-Stop Valve, CAUTION; 830CC-V1.pdf PDF p.6 / Dangers, Warnings & Cautions – CAUTION(UP button, not raising or fully raised); 830CC-V1.pdf PDF p.17 / Operating Instructions – CAUTION(UP button), CAUTION(relief, squealing sound) |
| K-1021 | S21 | RT | T3 | 리프트가 내려가지 않고 속도 퓨즈 잠김이 의심될 때의 4단계 복구 순서 | [prompts/RT.md](prompts/RT.md) | `794ff2becaa8` | 830CC-V1.pdf p.34 / Troubleshooting Analysis – Lift won’t lower, velocity fuse steps 1~4 | https://autoquip.com/wp-content/uploads/2018/03/830CC-V1.pdf; 830CC-V1.pdf p.6 / Dangers, Warnings & Cautions, WARNING | https://autoquip.com/wp-content/uploads/2018/03/830CC-V1.pdf |
| K-1022 | S22 | RT | T1 | 상승이 안 되면서 모터가 웅웅거리기만 하거나 퓨즈가 끊기면 펌프 고착을 의심한다 | [prompts/RT.md](prompts/RT.md) | `794ff2becaa8` | 830CC-V1.pdf PDF p.33 / Troubleshooting Analysis – 'Lift does not raise' (pump seized); 830CC-V1.pdf PDF p.6 / Dangers, Warnings & Cautions – CAUTION(UP button) |
| K-1023 | S23 | RT | T3 | 올린 리프트가 서서히 내려앉을 때 하강 솔레노이드 코일을 떼어 다운 밸브 카트리지를 판정한다 | [prompts/RT.md](prompts/RT.md) | `794ff2becaa8` | 830CC-V1.pdf p.32 / Troubleshooting Analysis – Lift raises, then lowers back slowly, DANGER | https://autoquip.com/wp-content/uploads/2018/03/830CC-V1.pdf |
| K-1024 | S24 | GR | T5 | 감속기 온도·소음·진동이 평소와 다르면 주 모터를 멈추고 원인을 확인한다 | [prompts/GR.md](prompts/GR.md) | `744fbbdd221d` | 26867443.pdf PDF p.5 / 인쇄 p.5 / §2 Safety Notes, Startup/operation |
| K-1025 | S25 | GR | T3 | 감속기 베어링부 온도가 높을 때 오일 상태와 베어링을 확인한다 | [prompts/GR.md](prompts/GR.md) | `744fbbdd221d` | 26867443.pdf p.45 §9.1 Bearing point temperatures too high; 26867443.pdf p.42–43 §8.3 Checking the oil level, Checking the oil |
| K-1026 | S26 | GR | T1 | 감속기 규칙적 이상음: 갈리는 소리는 베어링, 두드리는 소리는 치형을 의심한다 | [prompts/GR.md](prompts/GR.md) | `744fbbdd221d` | 26867443.pdf PDF p.45 / 인쇄 p.45 / §9.1 Gear unit malfunctions, Unusual, regular running noise |
| K-1027 | S27 | GR | T3 | 감속기 누유 위치별 확인: 커버·오일실·드레인·브리더 원인에 따라 조치한다 | [prompts/GR.md](prompts/GR.md) | `744fbbdd221d` | 26867443.pdf PDF p.45 / 인쇄 p.45 / §9.1 Gear unit malfunctions, Oil leaking (각주 1 포함) | https://download.sew-eurodrive.com/download/pdf/26867443.pdf |
| K-1028 | S28 | GR | T1 | 감속기 불규칙 이상음은 오일 속 이물을 의심하고 구동을 멈춘다 | [prompts/GR.md](prompts/GR.md) | `744fbbdd221d` | 26867443.pdf PDF p.45 / 인쇄 p.45 / §9.1 Gear unit malfunctions, Unusual, irregular running noise |
| K-1029 | S29 | GR | T2 | 옥외·다습 환경 감속기는 오일 수분을 확인하고 300 ppm을 넘기지 않는다 | [prompts/GR.md](prompts/GR.md) | `744fbbdd221d` | 26867443.pdf PDF p.41 / 인쇄 p.41 / §8.1 Inspection and maintenance intervals, Every 3000 hours / 6 months |
| K-1030 | S30 | GR | T1 | 감속기 장착부 주변 이상음은 장착 볼트 풀림을 의심한다 | [prompts/GR.md](prompts/GR.md) | `744fbbdd221d` | 26867443.pdf PDF p.45 / 인쇄 p.45 / §9.1 Gear unit malfunctions, Unusual noise in the area of the gear unit mounting |

## 미작성 슬롯 (0)

없음 — 사유는 `out/<설비>_notes.md`.
