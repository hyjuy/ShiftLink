# KB-20260929-A 지식카드 ↔ 모의 MES 신호 대응표

- 작성: 2026-09-29, Claude Code. 상태: 초안. 조건 스키마 입력 자료이며 최종 스키마는 유현준이 정한다.
- 입력: `cards.json`(K-1001~K-1030), `docs/data/reference/00_plant_and_relations.json`, `shiftlink/mes/configuration.py`·`scenarios/priority.py`·`engine.py`.
- 기계 판독용: [`mes_signal_map.json`](mes_signal_map.json) (같은 내용).
- 방향 high/low는 MES `normal_min`/`normal_max` 기준 상태다. 매뉴얼 절대값(2000 cSt, 300 ppm 등)은 비고에만 둔다.
- 연결 강도: **직접** 카드 증상·조건이 신호 이상과 같은 현상 / **간접** 원인 후보·확인 항목으로만 등장 / **없음** MES로 관측 불가.

## MES 쪽 사실 (코드에서 확인)

- 현재 기본 구성의 고유 신호 28개: catalog 16개 + `scenarios/priority.expand()`가 추가한 고유 신호 12개(`gr_oil_leak` 포함). 새 신호 중 `hpu_oil_level`·`gr_oil_level`은 아래 카드의 **확인 항목**에만 연결했고 자동 검색 조건으로 삼지 않는다. 나머지 새 신호 9개는 미연결 목록에 두었다. 동일 신호가 여러 설비에 있어 실제 계측점은 46개다.
- 시나리오 9개 (`from_catalog` + `PRIORITY_SCENARIOS`):

| scenario_id | 원인 설비 | 신호 효과 | alarm_code | 전파 대상 wait_reason |
|---|---|---|---|---|
| drive_fault | GR-01 | gr_vib_rms=5.0 (high) | AL-DRV-VIB | upstream_drive_fault → RT-01·RT-02 |
| hydraulic_fault | HPU-01 | hpu_pressure=120 (low) | AL-HYD-LOW | hydraulic_supply_low → RT-01·RT-02·RT-03·CV-01 |
| downstream_block | CV-01 | cv_queue_len=95 (high) | AL-DSB-QUE | downstream_block → RT-03 (interlock) |
| gearbox_overheat | GR-01 | gr_brg_temp=85 (high) | AL-GR-HOT | upstream_drive_fault → RT-01·RT-02 |
| hydraulic_overheat | HPU-01 | hpu_oil_temp=78 (high) | AL-HYD-HOT | hydraulic_supply_low → RT-01·RT-02·RT-03·CV-01 |
| gearbox_leak | GR-01 | gr_oil_leak=1 (high) | AL-GR-LEAK | upstream_drive_fault → RT-01·RT-02 |
| coil_quality_hold | (코일) | 없음 | 없음 | quality_hold → 코일이 있는 설비 |
| cau_supply_fault | CAU-01 | air_pressure=450 (low), air_flow=70 (low), compressor_current=22 (high) | AL-AIR-LOW | pneumatic_supply_low → CV-01 |
| pdp_trip | PDP-01 | bus_voltage=90 (low), bus_current=55 (high), breaker_trip=1 (트립) | AL-PDP-TRIP | power_supply_fault → GR-01·GR-02·HPU-01 |

CAU·PDP의 수치는 가상 이상 관측값이다. 기존 승인 카드와의 연결은 미정으로 JSON의 `unlinked`에 기록한다. 실제 제조사 임계값이나 작업 안전 판정을 뜻하지 않으며, 복귀는 기존 2 ticks 모의 상태 전환을 사용한다.

- 원인 설비는 `operating_state=stopped`, `fault_level=critical`, `wait_reason=self_fault`, 알람 severity `critical`. 복구 중엔 전 설비 `waiting`/`recovery`.
- engine은 capability의 **첫 설비**에만 시나리오를 건다. GR-02는 어떤 시나리오의 원인도 되지 않는다.
- 알람은 fault_level이 normal이 아닌 설비에만 생긴다. 신호가 정상 범위를 벗어나도 시나리오 없이는 알람이 없다(임계값 기반 알람 없음).

## 대응표 (직접 6 / 간접 6 / 없음 18)

| card_id | 설비 | 카드 부품 → MES 부품 코드 | 관련 신호 (신호명, 방향, 단위) | 관련 알람 코드·fault_level·wait_reason | 관련 MES 시나리오 | 연결 강도 | 근거(카드 문구 인용) | 비고 |
|---|---|---|---|---|---|---|---|---|
| K-1001 | HPU | 주 베인펌프 → HPU-01-PMP | hpu_pressure (low, bar) @HPU-01<br>hpu_flow (low, L_min) @HPU-01 | AL-HYD-LOW · critical (HPU-01) · hydraulic_supply_low (RT-01·RT-02·RT-03·CV-01) | hydraulic_fault | **직접** | symptom: "펌프 운전 중 펌프 출구 압력계에 압력이 읽히지 않는다." / ST-08: "릴리프 밸브 탱크 라인으로 유량이 흐르는지 확인한다." | hpu_pressure low가 증상과 같은 현상(직접). hpu_flow는 릴리프 탱크 라인이 아닌 공급 유량이라 간접. 카드의 '압력 없음(0)'과 달리 hydraulic_fault 압력은 120 bar다. hpu_flow=0은 HPU 정지 결과여서 펌프 원인을 독립적으로 증명하지 않는다. 축 회전·프라이밍은 관측 불가. |
| K-1002 | HPU | 오일 쿨러 → HPU-01-CLR | hpu_oil_temp (high, degC) @HPU-01 | AL-HYD-HOT · critical (HPU-01) · hydraulic_supply_low (RT-01·RT-02·RT-03·CV-01) | hydraulic_overheat | **직접** | symptom: "냉각기 출구 포트의 오일 온도가 높거나" / rationale: "'너무 높다'의 온도 기준값은 원문에 없다." | hydraulic_overheat(component_id=cooling)가 냉각 성능 저하를 가정해 카드와 같은 방향. MES 유온은 단일 지점이라 냉각기 출구/입구 구분·오일 입출구 온도차(ST-02)·냉각수 온도(ST-05·06)·냉각기 통과 유량(ST-07)은 관측 불가. |
| K-1003 | HPU | 릴리프 밸브 → HPU-01-RLV | — | — | — | **없음** | know_how: "설정은 실무상 가능한 낮게 하고 … 펌프 최대 정격 압력보다 높게 두지 않는다." | 설치·설정 규칙(T5). 릴리프 설정값·배관 경로는 MES 신호가 아니다. hpu_pressure high(alarm_high 175 bar)는 과압과 개념상 가깝지만 카드가 증상으로 쓰지 않아 연결하지 않았다. 과압 시나리오도 없다. |
| K-1004 | HPU | 주 베인펌프 → HPU-01-PMP | hpu_flow (low, L_min) @HPU-01<br>hpu_pressure (low, bar) @HPU-01<br>hpu_oil_level (any, pct; 확인 항목) @HPU-01 | AL-HYD-LOW · critical (HPU-01) · hydraulic_supply_low (RT-01·RT-02·RT-03·CV-01) | hydraulic_fault | **직접** | symptom: "펌프 소음이 평소보다 크고, 요구 유량이나 압력이 나오지 않으며, 탱크 유면이 거품으로 우유빛(milky)을 띤다." | 유량·압력 미달은 MES low 상태와 같은 현상. hpu_oil_level은 탱크 유면 확인을 돕는 가상 pct이며 흡입구 대비 높이나 에어레이션 판정값은 아니다. 소음·우유빛 거품은 관측 불가다. hydraulic_fault는 압력을 120 bar로 낮추고 HPU를 정지시키므로 hpu_flow=0이지만 이 값은 에어레이션 증거가 아니다. |
| K-1005 | HPU | 축압기 → HPU-01-ACC | hpu_pressure (any, bar) @HPU-01 | — | — | **간접** | ST-05·06: "축압기를 유체 계통 압력까지 충전한다." → "압력 읽음이 맞는지 확인한다." | 계통 압력은 확인 항목으로만 등장(방향 없음). 가스 프리차지 압력·압력 스위치 설정은 MES에 없다. catalog failure_mode '질소압 저하'에 대응하는 신호도 없다. |
| K-1006 | HPU | HPU 전체 → (HPU-01 전체) | — | — | — | **없음** | know_how: "HPU 정비는 설비가 작동하는 상태에서 하지 않는다. 정비 전에는 반드시 해당 계통 부분의 압력을 뺀다." | 정비 안전 절차. operating_state(running/stopped)는 '작동 중' 판정 전제로 쓸 수 있으나 신호 이상과는 무관. 감압 여부는 관측 불가: engine은 HPU가 stopped여도 hpu_pressure를 정상 범위 값으로 내보낸다(zero_when_stopped는 rt_speed·cv_speed만). |
| K-1007 | HPU | 주 베인펌프 → HPU-01-PMP | hpu_oil_temp (low, degC) @HPU-01 | — | — | **간접** | conditions: fluid_viscosity > 2000 cSt / know_how: "점도를 직접 알 수 없으면 유온과 작동유 점도 자료로 담당자에게 확인한다." | [조건 판정] fluid_viscosity: MES 대응 신호 없음. hpu_oil_temp low(정상 하한 35 degC 미만)는 대리 지표일 뿐이며 점도-온도 환산표가 MES에 없다. hpu_oil_temp는 alarm_low가 null이고 저온 시나리오도 없다. 2000 cSt는 매뉴얼 절대값으로 MES 값과 섞지 않는다. 결과 증상 '토출 없음'은 hpu_flow low와 이어질 수 있으나 카드에 조건으로 쓰이지 않았다. |
| K-1008 | HPU | 작동유 → (catalog 부품 코드 없음: 작동유), HPU-01-CLR(확인 항목: 쿨러 누수) | — | — | — | **없음** | symptom: "작동유 색이 투명에서 크림색(우유빛)으로 바뀌고, 탱크나 부품에 젤라틴 같은 덩어리가 보이거나" | 외관·수분 함량(1000/500 ppm, 분석 필요) 모두 MES 신호 없음. engine COMPONENTS의 hpu/oil(유압유 상태) health_percent는 운전 시간 기반 가상 마모값이라 수분 오염과 대응하지 않는다. |
| K-1009 | CV | 컨베이어 본체(횡단 구간) → (catalog 부품 코드 없음: CV 횡단 구간) | — | — | — | **없음** | safety_basis: "근로자는 … 건널다리 및 … 통로를 제외하고는 컨베이어의 위나 아래를 횡단하지 말아야 한다." | 작업자 행동 규칙. MES는 사람 위치를 다루지 않는다. |
| K-1010 | CV | 아이들러 → CV-01-BLT(사행), (아이들러 코드 없음) | — | — | — | **없음** | symptom: "벨트가 아이들러 중앙을 벗어나 한쪽으로 치우쳐 돈다." | catalog CV-01-BLT failure_modes에 '사행'이 있으나 사행을 나타내는 MES 신호가 없다. cv_belt_tension은 카드에 등장하지 않는다. |
| K-1011 | CV | 아이들러 롤(베어링) → (catalog 코드 없음: 아이들러 롤 베어링) | — | — | — | **없음** | symptom: "아이들러 롤이 … 굼뜨게 돌거나 멈춰 있고, 평소와 다른 높은 끽끽 소리가 난다." | 롤 회전 상태·소음 성질은 관측 불가. engine COMPONENTS cv/bearing은 '구동 베어링'이라 아이들러 롤과 다르다. |
| K-1012 | CV | 벨트 → CV-01-BLT(사행) | — | — | — | **없음** | know_how: "수평을 맞춘 뒤 치우친 쪽 장력 조정 나사를 조금씩 조이며 벨트 주행을 계속 눈으로 보면서" | 좌우 편측 장력 나사 조정·수평은 관측 불가. cv_belt_tension은 단일 값이고 CV-01 장력은 유압 텐셔너(CV-01-TNS) 방식이라 카드(직접구동형 소형 컨베이어) 구조와 다르다. 연결하지 않았다. |
| K-1013 | CV | 벨트(스플라이스) → CV-01-BLT(사행·손상) | — | — | — | **없음** | symptom: "벨트의 같은 구간이 지나갈 때마다 컨베이어 모든 지점에서 한쪽으로 벗어나고" | 구간별 사행 패턴·스플라이스 상태는 관측 불가. |
| K-1014 | CV | 방호덮개·점검덮개 → (catalog 코드 없음: 방호·점검덮개) | — | — | — | **없음** | safety_basis: "부득이한 경우를 제외하고는 컨베이어의 운전 중에 방호덮개, 점검덮개 등을 개방하지 않아야 한다." | 덮개 개방 상태 신호 없음. operating_state == running은 '운전 중' 전제로만 쓸 수 있다. |
| K-1015 | CV | 컨베이어 계통(전원·안전장치) → (CV-01 계통 전체) | — | (특정 코드 없음) · critical (CV-01) · self_fault (CV-01) | — | **간접** | symptom: "운전 중 컨베이어에 오작동·고장이 발생한다." | 범용 고장 대응 절차라 특정 신호가 없다. 트리거 후보는 CV-01 fault_level != normal 뿐. 현재 MES에서 CV-01이 critical이 되는 유일한 경로는 downstream_block(적재 만재, AL-DSB-QUE)인데 이는 설비 고장이 아니므로 시나리오 연결은 하지 않았다. 전원 분리·재기동 방지·표지 상태는 관측 불가. |
| K-1016 | CV | 벨트 커버 → CV-01-BLT(손상) | — | — | — | **없음** | symptom: "벨트 커버 표면이 군데군데 점이나 줄무늬 모양으로 부풀어 있다." | 외관 점검 항목. MES 신호 없음. |
| K-1017 | RT | 롤러 세트(롤러 베어링) → RT-03-ROL(롤러 세트) | — | — | — | **없음** | symptom: "운전 중 롤러 컨베이어에서 평소와 다른 소음, 끽끽거리는 소리 또는 휘파람 같은 소리가 난다." | 소음 성질은 관측 불가. 롤러 세트 부품 코드는 RT-03에만 있다(RT-01·RT-02 없음). 카드의 2순위 원인 '모터나 기어박스 손상'에 rt_motor_current(RT-03)를 붙일 근거는 카드에 없다. engine COMPONENTS rt/bearing(롤러 베어링)은 이름만 대응. |
| K-1018 | RT | 승강부(시저 리프트) 정비용 잠금장치 → RT-02-LFT(승강 실린더) | — | — | — | **없음** | know_how: "플랫폼을 올려 정비용 잠금장치 두 개를 모두 걸고, 하강 스위치를 몇 초 더 눌러 압력이 다 빠져" | 잠금장치 체결·하중 유무·주전원 차단은 관측 불가. rt_clamp_press는 클램프 압력이라 승강 실린더 압력이 아니다. 카드의 코일카 시저 리프트와 RT-02 승강부가 같은 구조인지는 미확인. |
| K-1019 | RT | 승강부(시저 리프트) 정비 장치 → RT-02-LFT(승강 실린더) | — | — | — | **없음** | know_how: "좌우 정비 장치 두 개를 모두 끼우고, 롤러가 장치에 확실히 얹히도록 내린다." | 정비 장치 삽입 상태는 관측 불가. |
| K-1020 | RT | 승강부 유압 파워유닛 릴리프 밸브 → RT-02-LFT(승강 실린더) | rt_lift_delay (high, min) @RT-02 | — | — | **간접** | symptom: "상승 버튼을 누르는 동안 파워유닛 밸브에서 끽 하는 날카로운 소리(squealing)가 나고 플랫폼은 더 올라가지 않는다." | '더 올라가지 않음'이 승강 응답 지연(rt_lift_delay high)으로 보일 수 있으나 신호가 상승/하강·지연/불능을 구분하지 않는다. 카드는 승강부 자체 파워유닛 릴리프를 다루지만 catalog에서 RT-02 승강은 HPU-01 공급(REL-0010)이라 구조가 다를 수 있다. 소음은 관측 불가. rt_lift_delay 시나리오 없음. |
| K-1021 | RT | 승강 실린더 속도 퓨즈(velocity fuse) → RT-02-LFT(승강 실린더) | rt_lift_delay (high, min) @RT-02 | — | — | **간접** | symptom: "하강 버튼을 눌러도 리프트가 내려가지 않는다." | 하강 불능은 승강 응답 지연과 같은 계열이지만 rt_lift_delay가 방향을 구분하지 않고 '불능'과 '지연'도 구분하지 않아 간접. 속도 퓨즈 잠김·누유 여부는 관측 불가. |
| K-1022 | RT | 승강부 유압 파워유닛 펌프·모터 → RT-02-LFT(승강 실린더) | rt_lift_delay (high, min) @RT-02 | — | — | **간접** | symptom: "상승 버튼을 눌러도 리프트가 오르지 않고, 모터가 웅웅거리기만 하거나 과부하 보호장치의 퓨즈가 끊어진다." | 상승 불능만 rt_lift_delay와 이어진다. 카드의 모터는 승강 파워유닛 모터라 rt_motor_current(RT-03 롤러 모터)·bus_voltage와 연결하지 않았다. 퓨즈 트립 신호 없음. |
| K-1023 | RT | 승강부 하강 솔레노이드 밸브 → RT-02-LFT(승강 실린더: 내부 누유) | — | — | — | **없음** | symptom: "올려 둔 리프트가 버튼을 누르지 않았는데도 서서히 내려앉는다." | 리프트 위치(높이) 신호가 없어 자연 하강을 관측할 수 없다. rt_lift_delay는 명령 응답 지연이라 무명령 하강과 다르다. catalog failure_mode '내부 누유'와 원인만 대응. |
| K-1024 | GR | 감속 기어박스 → GR-01-GBX | gr_brg_temp (high, degC) @GR-01/GR-02<br>gr_vib_rms (high, mm_s) @GR-01/GR-02 | AL-GR-HOT · critical (GR-01) · upstream_drive_fault (RT-01·RT-02)<br>AL-DRV-VIB · critical (GR-01) · upstream_drive_fault (RT-01·RT-02) | gearbox_overheat, drive_fault | **직접** | know_how: "운전 중 온도 상승, 소음, 진동처럼 정상 운전과 다른 변화가 생기고 판단이 서지 않으면 주 모터를 끈다." | 온도·진동 상승은 MES high 상태와 같은 현상. gr_brg_temp는 베어링 온도라 카드의 '감속기 온도'와 측정 위치가 다를 수 있다. 소음은 관측 불가. 시나리오 효과는 engine이 capability=drive 첫 설비(GR-01)에만 적용하므로 GR-02에서는 재현되지 않는다. |
| K-1025 | GR | 감속기 베어링부 → GR-01-BRG | gr_brg_temp (high, degC) @GR-01/GR-02<br>gr_oil_level (any, pct; 확인 항목) @GR-01/GR-02 | AL-GR-HOT · critical (GR-01) · upstream_drive_fault (RT-01·RT-02) | gearbox_overheat | **직접** | symptom: "감속기 베어링부 온도가 평소보다 높다." | 온도 증상과 gr_brg_temp가 같은 현상이다. gr_oil_level은 본문의 유면 확인을 돕는 가상 pct 관측이며 사이트글라스 중간·딥스틱 적정 범위와 동일한 매뉴얼 수치가 아니다. gearbox_overheat는 냉각 계통을 원인으로 가정하지만 카드 원인 후보는 오일 부족·과다·노후·베어링 손상이다. 점도·오염 상태는 관측 불가다. |
| K-1026 | GR | 감속 기어박스 → GR-01-BRG, GR-01-GBX | — | — | — | **없음** | symptom: "감속기에서 평소와 다른 규칙적인 운전음이 난다." | 소음 성질(갈림/두드림)은 관측 불가. gr_vib_rms가 함께 오를 수 있으나 카드가 진동을 언급하지 않아 연결하지 않았다. |
| K-1027 | GR | 감속 기어박스 → GR-01-GBX | gr_oil_leak (high, bool) @GR-01/GR-02<br>gr_oil_level (any, pct; 확인 항목) @GR-01/GR-02 | AL-GR-LEAK · critical (GR-01) · upstream_drive_fault (RT-01·RT-02) | gearbox_leak | **직접** | symptom: "감속기 커버판·하우징 커버·베어링 커버·장착 플랜지·오일실 또는 드레인 플러그·밸브·브리더 플러그에서 오일이 샌다." | gr_oil_leak는 기본 catalog JSON에 없고 priority.expand()가 drive 설비에 추가하는 0/1 신호(정상 0). high = 1(감지). gr_oil_level은 본문의 오일 과다 여부 확인에 쓰는 보조 관측일 뿐 누유 원인·위치의 증거가 아니다. 누유 위치·길들이기 24시간 예외는 표현 불가다. catalog GR-01-GBX failure_modes에 누유 항목이 없다. |
| K-1028 | GR | 감속 기어박스 → GR-01-GBX | — | — | — | **없음** | symptom: "감속기에서 평소와 다른 불규칙한 운전음이 난다." | 소음 성질(불규칙)과 오일 속 이물은 관측 불가. |
| K-1029 | GR | 감속 기어박스 → GR-01-GBX | — | — | — | **없음** | conditions: installation_outdoor_or_humid == true / know_how: "수분 함량은 0.03 %(300 ppm)를 넘으면 안 된다." | [조건 판정] installation_outdoor_or_humid: MES·catalog에 대응 필드 없음. 설비 location_text(예: '입측 조작반 좌측 5 m')는 자유 문장이라 옥외/다습 판정에 쓸 수 없다. 오일 수분 ppm·운전 3000시간 카운터도 신호가 아니다(engine component operating_seconds는 가상 마모 카운터). |
| K-1030 | GR | 감속 기어박스 → GR-01-GBX(장착부) | — | — | — | **없음** | symptom: "감속기 장착부 주변에서 평소와 다른 소리가 난다." | 소음·볼트 체결 상태는 관측 불가. |

## 카드 기존 conditions 판정

| card_id | 카드 조건 | MES 대응 | 판정 |
|---|---|---|---|
| K-1007 | `fluid_viscosity > 2000 cSt` | 없음. 대리 지표 `hpu_oil_temp` low(< 35 degC)만 있고 점도-온도 환산표가 MES에 없다 | 그대로는 MES로 평가 불가 |
| K-1029 | `installation_outdoor_or_humid == true` | 없음. catalog `location_text`는 자유 문장 | 설비 정적 속성 추가 필요 |

## 어느 카드에도 연결되지 않은 MES 항목 (다음 카드 배치의 빈 곳)

- 신호 19/28개: `hpu_filter_dp`, `hpu_pump_current`, `bus_voltage`, `bus_current`, `breaker_trip`, `air_pressure`, `air_flow`, `compressor_current`, `gr_current`, `gr_rpm`, `rt_speed`, `rt_clamp_press`, `rt_motor_current`, `rt_vib_rms`, `cv_speed`, `cv_belt_tension`, `cv_queue_len`, `cv_motor_current`, `cv_vib_rms`
- 알람: `AL-DSB-QUE`
- 시나리오: `downstream_block`, `coil_quality_hold`
- wait_reason: `downstream_block`, `quality_hold`, `recovery` (`self_fault`는 K-1015 간접 연결만 있음)
- 설비 단위로 보면 PDP-01(`bus_voltage`)·CAU-01(`air_pressure`)·CV-02 카드가 0장이고, RT 카드 7장은 전부 승강부·롤러 소음이라 RT 반송(`rt_speed`)·클램프(`rt_clamp_press`, catalog 부품 RT-01/03-CLP)·모터(`rt_motor_current`)와 이어지지 않는다.
- HPU 필터(`hpu_filter_dp`, HPU-01-FLT)는 catalog 매뉴얼 절 MS-0005에 조건까지 있는데 카드가 없다.

## MES에 없어서 카드 조건을 표현할 수 없는 관측 (신호 추가 검토 후보)

| 관측 | 해당 카드 | 추가 후보(제안) |
|---|---|---|
| 소음 성질(규칙/불규칙, 끽끽·휘파람·갈림·두드림) | K-1004, K-1011, K-1017, K-1020, K-1026, K-1028, K-1030 | 음향·이상음 이벤트 신호(예: 설비별 abnormal_noise 0/1) 또는 순회 점검 입력 필드 |
| 작동유 외관·수분 함량(우유빛·거품·젤라틴, ppm) | K-1004, K-1008, K-1029 | 오일 분석 결과(수분 ppm)를 주기 입력으로 받는 필드 |
| 작동유 점도(cSt) | K-1007 | fluid_viscosity 입력 또는 유종별 점도-온도 환산표 + hpu_oil_temp |
| 설치 환경(옥외/다습) | K-1029 | equipment 정적 속성(예: installation_env) |
| 벨트 사행·좌우 편차 | K-1010, K-1012, K-1013 | cv_belt_drift(편차 mm) 또는 사행 스위치 0/1 |
| 승강부 위치·동작 방향(상승/하강 불능, 무명령 하강) | K-1020, K-1021, K-1022, K-1023 | rt_lift_position 또는 rt_lift_delay를 상승/하강으로 분리 |
| 잔압·감압 확인(정지 시 계통 압력) | K-1006, K-1018 | 정지 시 hpu_pressure가 실제로 떨어지게 하거나 별도 잔압 신호 |
| 누유 위치 | K-1027 | gr_oil_leak(0/1)에 위치 코드 추가 |
| 축압기 프리차지 압력·압력 스위치 설정 | K-1005 | hpu_acc_precharge(bar) |
| 오일 냉각기 입출구 유온차·냉각수 온도 | K-1002 | hpu_oil_temp_in/out, 냉각수 입출구 온도 |
| 안전 상태(잠금장치 체결, LOTO, 덮개 개방, 주전원 차단) | K-1006, K-1009, K-1014, K-1015, K-1018, K-1019 | LOTO·인터록 상태 이벤트(정비 모드) |
| 승강 파워유닛 모터 퓨즈 트립 | K-1022 | RT-02 승강 모터 과부하 트립 0/1 |

## 제안: 조건 표기 형식 예시 (최종 스키마는 유현준 결정)

catalog `manual_sections[].applies_conditions`가 이미 `{field, op, value}`를 쓰고 있어 그 모양을 따랐다.

1. **정상범위 상태** — 절대값 대신 MES 정상범위 기준 상태로 쓴다. 매뉴얼 수치와 MES 가상 수치를 섞지 않는다.
   ```json
   {"field": "gr_brg_temp_state", "equipment": "GR-01", "op": "eq", "value": "high"}
   ```
   읽기: `gr_brg_temp_state == "high"` (state = low | normal | high, normal_min/max로 계산). K-1025 적용 예.
2. **알람·대기 사유** — 시나리오가 만드는 이벤트로 조건을 건다.
   ```json
   {"field": "active_alarm_code", "op": "in", "value": ["AL-HYD-LOW"]}
   {"field": "wait_reason", "equipment": "RT-03", "op": "eq", "value": "hydraulic_supply_low"}
   ```
   K-1001(원인 설비 HPU-01) / 하류 RT에서 '원인이 상류 유압'임을 거르는 용도.
3. **MES 밖 관측 명시** — MES로 평가할 수 없는 조건은 출처를 표시해 엔진이 건너뛰고 사람 확인으로 넘긴다.
   ```json
   {"field": "installation_env", "source": "static_attr", "op": "in", "value": ["outdoor", "humid"]}
   {"field": "fluid_viscosity", "source": "manual_input", "op": "gt", "value": 2000, "unit": "cSt"}
   ```
   K-1029·K-1007 기존 조건을 옮긴 예. `source`가 `mes`가 아니면 자동 매칭 대상에서 뺀다.
