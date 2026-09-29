# 모의 MES 설비별 관측 신호 보강

기본 기준정보의 `measurement_points`는 유지하고, 모의 MES의 기본 구성에 다음 신호를 더한다. 정상 범위는 화면과 테스트를 위한 **합성 기준값**이며 현장 경보·보호 설정값이 아니다. 신호 추가만으로 원인 진단이나 자동 알람이 생기지는 않는다.

모의 엔진에서 정지한 설비의 회전속도·모터 전류·유량·진동은 0으로 표시한다. 롤러 모터 전류의 합성 정상 범위는 기존 RT-03과 같은 `8–16 A`로 둔다. 현재 새 신호에 대한 별도 고장 주입·알람 규칙은 없으며, 시나리오가 바꾸는 기존 신호와 함께 관측할 수 있다.

| 설비 | 추가 신호 | 확인하려는 이상 징후 | 근거 범위 |
| --- | --- | --- | --- |
| HPU-01 | `hpu_oil_level`, `hpu_pump_current` | 유면 저하, 공급 저하와 전류 변화의 동반 여부 | [M-01 유압 펌프](../sources/manual/README.md): 유면·흡입·회전 등 확인 항목. 전류는 합성 보조 관측 |
| PDP-01 | `bus_current`, `breaker_trip` | 전원 부하 변화, 차단기 동작 | 프로젝트 시연 가정. [M-04](../sources/manual/README.md)는 인버터 코드 해석 참고이며 PDP 사양 근거가 아님 |
| CAU-01 | `air_flow`, `compressor_current` | 압력 저하와 유량·전류 변화의 동반 여부 | 프로젝트 시연 가정. `docs/sources`에 CAU 센서 사양 없음 |
| GR-01/02 | `gr_oil_level`, `gr_rpm` (기존 확장 신호 `gr_oil_leak` 유지) | 오일 부족·누유, 운전 속도에 따른 진동 차이 | [M-02 감속기](../sources/manual/README.md): 오일·냉각·누유 확인. [M-03 베어링](../sources/manual/README.md): 진동·온도는 증상 |
| RT-01/02/03 | `rt_motor_current`, `rt_vib_rms` | 이송 저항·롤러 베어링 이상 징후 | [M-03](../sources/manual/README.md)의 베어링 관측 방향과 [S-02](../sources/safety/S-02_KOSHA_GUIDE_M-101-2012.md)의 회전부 위험 맥락. 신호 수치·진단 기준은 합성 |
| CV-01/02 | `cv_motor_current`, `cv_vib_rms`; CV-02에는 `cv_speed`도 추가 | 막힘·구동부 이상 징후, 정지 상태와 속도 비교 | [S-02](../sources/safety/S-02_KOSHA_GUIDE_M-101-2012.md)의 컨베이어 위험 맥락. 신호 수치·진단 기준은 합성 |

기존 구성은 런별로 보존한다. 이전 `catalog`/`baseline` 구성을 재시작할 때는 누락된 신호만 추가하며, 사용자 초안 구성에는 자동으로 추가하지 않는다. `equipment_id`와 기존 신호 ID는 유지한다.
