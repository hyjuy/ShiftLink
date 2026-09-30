# MES 증상별 관측 조합 조사 및 적용

조사·적용일: 2026-09-30. 대상: HPU, CAU, PDP, GR, RT, CV의 가상 MES 관측.

## 적용 원칙

논문은 여러 센서와 운전 조건을 함께 비교하는 방법의 근거로 사용했다. **논문의 실험 수치를 이 프로젝트의 고장 임계값으로 옮기지 않았다.** 아래 주입값과 정상 범위는 기존 MES 구성에서 생성한 가상 값이다. 실설비 고장 진단 정확도는 검증하지 않았다.

판정은 `shiftlink/mes/symptoms.py`의 관측값·단위·품질·시각으로 수행한다. 시나리오 ID, 알람, 주입한 원인 라벨을 판정 입력으로 사용하지 않는다. 3회 연속 관측은 프로젝트의 시연 설정이며 논문에서 검증된 시간 창이 아니다. 같은 run의 연속 sequence, 증가하는 시각, 유효한 수집 상태와 모든 필수 신호의 일치를 요구한다. 일시정지하면 관측 창을 비운다.

결과는 `observing`(추가 관측), `unverified`(필수 근거 미확인), `candidate`(조합 지속 관측)이다. 모두 `confirmed=False`, `threshold_basis=synthetic_config`이며 확정 진단이나 정비 승인에 사용하지 않는다. 화면에는 후보와 추가 확인 항목을 함께 표시한다. 이 결과는 MES 상태 API에 제공하며 승인 KB 카드의 조건·출처 승인·계보 등록을 대신하지 않는다.

## 확인한 논문과 적용 한계

| 대상 | 1차 출처 및 확인 범위 | 확인 내용 | 적용 및 한계 |
| --- | --- | --- | --- |
| HPU | Helwig 등(2015), *Detecting and Compensating Sensor Faults in a Hydraulic Condition Monitoring System*, DOI `10.5162/sensor2015/D8.1`. [학회 원문](https://www.ama-science.org/proceedings/getFile/ZwN3Aj==), pp. 641–646 | 압력·유량·입력전력·온도·진동 등 17채널, 60초 사이클의 구간별 특징을 이용한다. 냉각 성능, 밸브, 펌프 내부 누설, 축압기 상태를 다룬다. | 압력·유량·온도 조합을 참고했다. 입력전력 W를 전류 A로 환산하지 않았다. 필터 차압 조합은 프로젝트 가설이며 논문의 필터 임계값이 아니다. |
| CAU | Dindorf & Woś(2018), *Test of measurement device for the estimation of leakage flow rate in pneumatic pipeline systems*, DOI `10.1177/0020294018808681`. [출판사 원문](https://journals.sagepub.com/doi/10.1177/0020294018808681), 식 (6), 표 1 | 압축기와 소비 장치가 꺼진 상태에서 체적·압력 감소·시간을 이용해 누설량을 추정한다. 표 1의 한 조건은 315 K, 평균 4.87 bar, 직접 4.73 L/min·간접 4.91 L/min이다. | 위 값은 연구 장치의 측정 예이며 MES 임계값이 아니다. 현재 수요 상태·체적·온도·감쇠 이력이 없어 누설량 계산은 구현하지 않았다. |
| CAU | Abela 등(2022), *Analysis of pneumatic parameters to identify leakages and faults on the demand side of a compressed air system*, DOI `10.1016/j.clet.2021.100355`. [저자 기관 기록·초록](https://www.um.edu.mt/library/oar/handle/123456789/88627); 전문은 접근 제한 | 누설에 따른 공급 총유량 증가와 하류 압력 감소를 다룬다. 초록의 1.6 mm 누설·약 10% 압력 감소는 연구 조건이다. | 공급 측 총유량이라는 가상 측정 위치를 전제로 압력↓·유량↑를 누설 또는 수요 증가 후보로 구분한다. 전류 상승 분기는 프로젝트 가설이다. 압력↓·유량↓를 누설로 확정하지 않는다. |
| GR / RT | Saucedo-Dorantes 등(2016), DOI `10.1155/2016/5467643`. [대학 저장소 원문](https://upcommons.upc.edu/bitstreams/4d3e3f37-c9e2-490d-b869-c08a3beac3f6/download), §3.1–3.2, §4 | 진동 3 kHz·전류 4 kHz의 20초 파형과 회전 조건을 활용한다. 단순 시간 영역 진동값만으로 결함을 구분하는 데 한계가 있다. | RMS·전류 요약값은 부하·저항 등의 후보 선별에만 사용한다. 유면·온도 분기와 RT 적용은 프로젝트 가설이다. RT 직접 검증 논문은 확보하지 못했다. |
| CV | Wang 등(2023), *Research on fault diagnosis system for belt conveyor based on internet of things and the LightGBM model*, DOI `10.1371/journal.pone.0277352`. [원문](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0277352), §2.2–2.3 | 속도·전류·장력·온도 등의 입력으로 컨베이어 상태를 분류한다. | 속도·장력 저하를 슬립 가능성과 지령·부하 변화로 제시한다. 탄광 설비의 모델·장력 단위를 가상 kPa에 이식하지 않았다. 드럼과 벨트 속도 차이가 없어 슬립 확정은 보류한다. |
| PDP | Sinha & Pal(2026), *Multivariate fault classification in electrical distribution systems using empirical mode decomposition and machine learning*, DOI `10.1007/s44163-026-01336-7`. [원문](https://link.springer.com/article/10.1007/s44163-026-01336-7), §2.2, §3.1 | 3상 전압·전류 6채널의 0.3초 구간, 채널당 6000표본을 활용한다. | 집계 전압 pct·전류 A만으로 단락·접지 유형을 판정하지 않는다. 과전류 관측과 트립 후 전류 0을 별도 시나리오로 구성했다. 버스 전압 센서는 차단기 상위라는 가상 가정이며 무전압 확인 수단이 아니다. |

## 시나리오 및 숫자

기본 구성에 15개 조합을 설비별로 적용해 **22개** `symptom_<설비 ID>_<패턴 ID>`를 추가했다. HPU 3·CAU 2·PDP 3·GR 4·RT 7·CV 3개다. 기존 공정 9개와 독립 센서 시연 46개를 합하면 총 77개다.

각 신호의 정상 구간은 기존 구성이다. low는 기본 양수 하한의 80%, high는 상한의 125%, 정상 대조 신호는 구간 중간값이다. 기본 논리값은 정상 0/이상 1, PDP 트립 후 전류는 0 A이다. 값은 소수 셋째 자리로 반올림한다. **이 비율은 시연용이며 논문의 고장 임계값이 아니다.** 구성이 바뀌면 수치와 조건을 재검수해야 한다.

| 시나리오 | 명시적 주입값 (정상 대조 포함) |
| --- | --- |
| `symptom_EQ-0001_hpu_delivery` | `hpu_pressure=116 bar` · `hpu_flow=30.4 L_min` · `hpu_filter_dp=0.6 bar` |
| `symptom_EQ-0001_hpu_restriction` | `hpu_pressure=116 bar` · `hpu_flow=30.4 L_min` · `hpu_filter_dp=1.5 bar` |
| `symptom_EQ-0001_hpu_heat` | `hpu_oil_temp=72.5 degC` · `hpu_flow=42 L_min` · `hpu_pump_current=20 A` |
| `symptom_EQ-0002_pdp_voltage` | `bus_voltage=77.6 pct` · `bus_current=30 A` · `breaker_trip=0 bool` |
| `symptom_EQ-0002_pdp_current` | `bus_voltage=100 pct` · `bus_current=50 A` · `breaker_trip=0 bool` |
| `symptom_EQ-0002_pdp_trip` | `bus_voltage=100 pct` · `bus_current=0 A` · `breaker_trip=1 bool` |
| `symptom_EQ-0003_cau_supply` | `air_pressure=440 kPa` · `air_flow=80 L_min` · `compressor_current=20 A` |
| `symptom_EQ-0003_cau_flow_demand` | `air_pressure=440 kPa` · `air_flow=187.5 L_min` · `compressor_current=20 A` |
| `symptom_EQ-0004_gr_lubrication` | `gr_vib_rms=3.5 mm_s` · `gr_brg_temp=77.5 degC` · `gr_oil_level=56 pct` · `gr_current=24 A` · `gr_rpm=1000 rpm` |
| `symptom_EQ-0004_gr_load` | `gr_current=37.5 A` · `gr_rpm=720 rpm` · `gr_vib_rms=1.65 mm_s` · `gr_brg_temp=46 degC` |
| `symptom_EQ-0005_gr_lubrication` | `gr_vib_rms=3.5 mm_s` · `gr_brg_temp=77.5 degC` · `gr_oil_level=56 pct` · `gr_current=24 A` · `gr_rpm=1000 rpm` |
| `symptom_EQ-0005_gr_load` | `gr_current=37.5 A` · `gr_rpm=720 rpm` · `gr_vib_rms=1.65 mm_s` · `gr_brg_temp=46 degC` |
| `symptom_EQ-0006_rt_resistance` | `rt_speed=16 m_min` · `rt_motor_current=20 A` · `rt_vib_rms=2.25 mm_s` · `rt_clamp_press=105 bar` |
| `symptom_EQ-0006_rt_clamp` | `rt_clamp_press=76 bar` · `rt_speed=70 m_min` · `rt_motor_current=12 A` |
| `symptom_EQ-0007_rt_resistance` | `rt_speed=16 m_min` · `rt_motor_current=20 A` · `rt_vib_rms=2.25 mm_s` · `rt_clamp_press=105 bar` |
| `symptom_EQ-0007_rt_clamp` | `rt_clamp_press=76 bar` · `rt_speed=70 m_min` · `rt_motor_current=12 A` |
| `symptom_EQ-0007_rt_lift` | `rt_lift_delay=0.062 min` · `rt_clamp_press=76 bar` · `rt_motor_current=12 A` |
| `symptom_EQ-0008_rt_resistance` | `rt_speed=16 m_min` · `rt_motor_current=20 A` · `rt_vib_rms=2.25 mm_s` · `rt_clamp_press=105 bar` |
| `symptom_EQ-0008_rt_clamp` | `rt_clamp_press=76 bar` · `rt_speed=70 m_min` · `rt_motor_current=12 A` |
| `symptom_EQ-0009_cv_slip` | `cv_speed=8 m_min` · `cv_belt_tension=304 kPa` · `cv_motor_current=15 A` |
| `symptom_EQ-0009_cv_resistance` | `cv_speed=8 m_min` · `cv_motor_current=25 A` · `cv_queue_len=87.5 pct` |
| `symptom_EQ-0010_cv_resistance` | `cv_speed=6.4 m_min` · `cv_motor_current=25 A` · `cv_queue_len=87.5 pct` |

모든 증상 시나리오는 지정 설비만 대상으로 하며 공급 관계 전파를 추가하지 않는다. PDP 트립을 제외하면 warning 상태로 운전을 유지해 정지 때문에 여러 센서가 0이 되는 영향을 피한다. 정상 복귀 후 후보가 사라진다.

기존 `pdp_trip`의 55 A·트립 1 동시 주입은 이전의 합성 채널 테스트로 유지한다. 이를 트립 후 실제 전류나 단락 원인의 근거로 해석하지 않는다. 새 `pdp_current`와 `pdp_trip` 패턴은 차단 전후를 구분한다.

## 아직 필요한 실측 자료

센서 설치 위치, 부하·속도 지령, 수요 상태, 원시 파형, 설비 모델과 정격, 보호 이벤트 및 정비 이력이 필요하다. 특히 RT 승강 지연과 클램프 압력은 서로 다른 관측이며 승강 실린더의 압력·위치가 추가되어야 한다. 가상 후보를 실제 진단 규칙으로 승격하려면 실측 데이터와 전문가 검증을 먼저 해야 한다.
