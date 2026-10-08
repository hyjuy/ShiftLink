"""Acquisition definitions for the project's synthetic measurement positions."""

MODEL = "synthetic_semantics_v1"

# References are explicit demo assumptions, not measurements of installed assets.
DEFINITIONS = {
    'hpu_pressure': ('공급 매니폴드', 'bar; 체크밸브 뒤 잔압 보유 구간'),
    'hpu_pump_outlet_pressure': ('펌프 출구, 체크밸브 앞', 'bar; 매니폴드 및 축압기 잔압 구간과 구분'),
    'hpu_oil_temp': ('유압유 탱크', 'degC; 탱크 벌크 유온'),
    'hpu_filter_dp': ('동일 펌프 순환회로 필터 전후', 'bar; 순환 정지 시 차압 0'),
    'hpu_flow': ('유압유 순환회로', 'L_min; 냉각기와 같은 직렬 순환회로'),
    'hpu_oil_level': ('유압유 탱크', 'pct; 표시 유면계의 0–100 교정 구간'),
    'hpu_pump_current': ('펌프 모터 공급선', 'A; 운전 중 전류, 정지 시 0'),
    'hpu_cooler_oil_in_temp': ('냉각기 오일 입구', 'degC; 탱크 유온을 입구 유온으로 사용하는 시연'),
    'hpu_cooler_oil_out_temp': ('냉각기 오일 출구', 'degC; 정상 순환 시 입구보다 5 degC 낮은 시연'),
    'hpu_cooler_water_in_temp': ('냉각기 냉각수 입구', 'degC; 입출구는 동일 프레임에서 비교'),
    'hpu_cooler_water_out_temp': ('냉각기 냉각수 출구', 'degC; 정상 순환 시 입구보다 5 degC 높은 시연'),
    'hpu_cooler_oil_flow': ('냉각기 오일 통과회로', 'L_min; 별도 순환펌프 없이 hpu_flow와 동일'),
    'hpu_accumulator_gas_pressure': ('축압기 가스측', 'bar; 운전 중 유체압과 같은 정적 평형, 배출 모드 프리차지 130–140'),
    'hpu_accumulator_fluid_pressure': ('축압기 유체측', 'bar; 매니폴드 잔압 구간, 프리차지 모드에서 0'),
    'hpu_return_submergence': ('탱크 리턴 관 출구와 유면', 'mm; 위치별 치수 시료, 관경 20 mm 시연 가정'),
    'hpu_suction_head': ('탱크 유면과 흡입 위치', 'mm; 위치별 높이차 시료, 압력 센서값과 구분'),
    'fluid_viscosity': ('작동유 시료', 'cSt; 40 degC로 조건화한 동점도 시료의 시연값'),
    'bus_voltage': ('차단기 전원측 버스', 'pct; 가상 선간 RMS 기준전압 400 V를 100 pct로 정의'),
    'bus_current': ('차단기 부하측 전류 계측', 'A; 전원측 버스 전압과 측정 위치 구분'),
    'breaker_trip': ('차단기 트립 상태 접점', '0 정상/1 트립; 단락 원인·무전압 확인과 구분'),
    'breaker_pole_l1_temp': ('차단기 L1극 외부 표면', 'degC; 동일 부하·동일 프레임의 세 극 표면 비교'),
    'breaker_pole_l2_temp': ('차단기 L2극 외부 표면', 'degC; 동일 부하·동일 프레임의 세 극 표면 비교'),
    'breaker_pole_l3_temp': ('차단기 L3극 외부 표면', 'degC; 동일 부하·동일 프레임의 세 극 표면 비교'),
    'air_pressure': ('공압 공급 헤더', 'kPa; 분사기 레귤레이터 앞 공급 압력'),
    'air_flow': ('압축공기 공급 회로', 'L_min; 운전 중 유량, 정지 시 0'),
    'compressor_current': ('압축기 모터 공급선', 'A; 운전 중 전류, 정지 시 0'),
    'compressor_discharge_temp': ('압축기 토출부', 'degC; 벌크 토출 온도'),
    'compressor_separator_dp': ('압축기 유분리기 전후', 'bar; 운전 중 차압, 정지 시 0'),
    'air_nozzle_pressure': ('레귤레이터 뒤 분사기 유출부', 'MPa; 공급 헤더 kPa와 위치·단위 구분'),
    'gr_vib_rms': ('감속기 베어링 하우징', 'mm_s; 진동 속도 RMS 시연 채널'),
    'gr_brg_temp': ('감속기 베어링 온도 계측부', 'degC; 외함 표면 온도와 별도 위치'),
    'gr_current': ('감속기 구동 모터 공급선', 'A; 운전 중 전류, 정지 시 0'),
    'gr_oil_water_content': ('감속기 윤활유 시료', 'ppm; 윤활유 시료의 수분 함량'),
    'gr_oil_level': ('감속기 유면계', 'pct; 표시 유면계의 0–100 교정 구간'),
    'gr_surface_temp': ('감속기 외함 표면', 'degC; 베어링 온도와 구분'),
    'gr_rpm': ('감속기 구동축', 'rpm; 출력축 환산 없이 지정 구동축 속도'),
    'gr_oil_leak': ('감속기 누유 검지부', '0 없음/1 감지; 위치별 육안 확인과 구분'),
    'rt_speed': ('롤러 이송 접선 속도', 'm_min; 정지 시 0'),
    'rt_clamp_press': ('롤러 클램프 유압회로', 'bar; 잔압 보유 구간, 클램프 힘 환산 없음'),
    'rt_lift_delay': ('리프트 상승 명령과 완료 이벤트', 'min; 완료시각−명령시각, 이벤트 없으면 unavailable'),
    'rt_motor_current': ('롤러 모터 공급선', 'A; 운전 중 전류, 정지 시 0'),
    'rt_vib_rms': ('롤러 베어링 하우징', 'mm_s; 진동 속도 RMS 시연 채널'),
    'cv_speed': ('컨베이어 벨트 접선 속도', 'm_min; 정지 시 0'),
    'cv_belt_tension': ('벨트 장력 조절기 유압회로', 'kPa; 장력 대용 압력 계측, 힘으로 환산하지 않음'),
    'cv_queue_len': ('컨베이어 코일 수용 슬롯', 'pct; 끝에 도착해 넘기지 못한 코일수/coil_capacity×100, 최대 100'),
    'cv_idler_speed_ratio': ('컨베이어 아이들러 회전 계측부', 'pct; 동일 프레임 벨트 속도에 맞춘 정상 회전=100, 정상 시연 비율 90'),
    'cv_motor_current': ('컨베이어 모터 공급선', 'A; 운전 중 전류, 정지 시 0'),
    'cv_vib_rms': ('컨베이어 구동 베어링 하우징', 'mm_s; 진동 속도 RMS 시연 채널'),
}
SAMPLES = {'fluid_viscosity', 'gr_oil_water_content', 'hpu_return_submergence', 'hpu_suction_head'}
DERIVED = {'cv_queue_len', 'cv_idler_speed_ratio'}


def definition(signal):
    """Unknown extensions remain undefined instead of acquiring invented meaning."""
    if signal not in DEFINITIONS:
        return {}
    location, reference = DEFINITIONS[signal]
    acquisition = 'manual_sample' if signal in SAMPLES else 'derived' if signal in DERIVED else 'event' if signal == 'rt_lift_delay' else 'continuous'
    applicability = ('시료값은 60초 간격 모의 수집; 채취 시각과 기준 온도를 대조'
                     if acquisition == 'manual_sample' else '리프트 완료 이벤트에서만 사용'
                     if acquisition == 'event' else '해당 측정 위치의 운전 상태와 동일 시각 관측으로 해석')
    if signal.startswith('hpu_accumulator'):
        applicability = '운전 압력과 hpu_accumulator_precharge의 유체 배출 후 프리차지 측정을 구분'
    return dict(acquisition=acquisition, location=location, reference=reference,
                applicability=applicability, model=MODEL)
