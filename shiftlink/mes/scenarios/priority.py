"""Manual-informed synthetic scenarios, not field maintenance instructions."""
from dataclasses import replace

from ..contracts import RecoveryAction as Action, ScenarioSpec, SignalEffect, SignalSpec

SEW = "https://download.sew-eurodrive.com/download/html/31981496/en-EN/25440305419.html"
PARKER = "https://www.parker.com/content/dam/Parker-com/Literature/PMDE/Service_Manuals/Vane_Pumps/HY29-0035-UK.pdf"
SAP = "https://learning.sap.com/courses/configuring-sap-digital-manufacturing-for-execution-basic-data-and-configuration/controlling-production-buyoff-hold-release-"

PRIORITY_SCENARIOS = (
    # Synthetic observation fixtures; not OEM fault limits or maintenance procedures.
    ScenarioSpec("cau_supply_fault", "pneumatic_supply", "pneumatic_supply", "pneumatic_supply_low", "AL-AIR-LOW",
        (SignalEffect("pneumatic_supply", "air_pressure", 450),
         SignalEffect("pneumatic_supply", "air_flow", 70),
         SignalEffect("pneumatic_supply", "compressor_current", 22)), title="압축공기 공급 이상 (가상)"),
    ScenarioSpec("pdp_trip", "power_supply", "power_supply", "power_supply_fault", "AL-PDP-TRIP",
        (SignalEffect("power_supply", "bus_voltage", 90),
         SignalEffect("power_supply", "bus_current", 55),
         SignalEffect("power_supply", "breaker_trip", 1)), title="배전반 트립 (가상)"),
    ScenarioSpec("gearbox_overheat", "drive", "drive", "upstream_drive_fault", "AL-GR-HOT",
        (SignalEffect("drive", "gr_brg_temp", 85),), title="감속기 과열", source_url=SEW, component_id="cooling",
        recovery_actions=(
            Action("inspect", "오일·냉각 상태 점검", "정지·에너지 차단 확인 후 오일량·오염·교환 이력과 냉각 상태를 점검한 것으로 기록합니다."),
            Action("repair", "확인된 냉각 문제 조치", "이 시연은 냉각 성능 저하를 가정합니다. 냉각 계통 정비 완료를 모의 기록합니다."),
            Action("verify", "온도 정상 확인", "구성의 정상 온도 범위로 회복된 모의 측정값을 생성하고 재가동 전 확인을 기록합니다."))),
    ScenarioSpec("hydraulic_overheat", "hydraulic_supply", "hydraulic_supply", "hydraulic_supply_low", "AL-HYD-HOT",
        (SignalEffect("hydraulic_supply", "hpu_oil_temp", 78),), title="유압유 과열", source_url=PARKER, component_id="cooling",
        recovery_actions=(
            Action("inspect", "유면·냉각·밸브 점검", "정지·잔압 해소 확인 후 유면, 냉각 성능, 유체 상태, 밸브 이상 여부를 점검한 것으로 기록합니다."),
            Action("repair", "냉각 성능 복구", "이 시연에서 가정한 냉각 문제의 정비 완료를 기록합니다. 실제 조치는 확인된 원인에 따라 달라집니다."),
            Action("verify", "유온·공급 정상 확인", "모의 유온을 정상 범위로 되돌리고 압력·유량의 정상 범위를 함께 확인합니다."))),
    ScenarioSpec("gearbox_leak", "drive", "drive", "upstream_drive_fault", "AL-GR-LEAK",
        (SignalEffect("drive", "gr_oil_leak", 1),), title="감속기 누유", source_url=SEW, component_id="seal",
        recovery_actions=(
            Action("inspect", "누유 위치·오일 상태 확인", "정지·에너지 차단 확인 후 씰, 접합부, 브리더와 오일량을 확인한 것으로 기록합니다."),
            Action("repair", "씰 정비·오일 상태 복구", "이 시연에서 가정한 씰 손상의 정비와 오일량 복구를 모의 기록합니다."),
            Action("verify", "누유 없음 확인", "재누유 점검 완료를 기록하고 모의 누유 신호를 0으로 되돌립니다."))),
    ScenarioSpec("coil_quality_hold", "transport", "", "quality_hold", "",
        title="영향 코일 검사·보류", source_url=SAP, product_hold=True,
        recovery_actions=(
            Action("identify", "영향 코일 확인", "시나리오 시작 시 라인 안의 코일 전체를 영향 대상으로 가정해 보류합니다. 대상 ID를 확인합니다."),
            Action("inspect", "검사·필요 조치 완료", "대상 코일이 검사 합격 또는 필요한 조치 후 재검사 합격한 것으로 모의 기록합니다."),
            Action("release", "제품 보류 해제 확인", "검사 완료와 해제 가능 여부를 확인합니다. 복귀 진행 후 대상 코일의 보류가 해제됩니다."))),
)

# These rates are a visible demo assumption, not an OEM lifetime model.
COMPONENTS = {
    "gr": (("bearing", "베어링"), ("cooling", "냉각 계통"), ("seal", "오일 씰")),
    "hpu": (("oil", "유압유 상태"), ("cooling", "냉각 계통"), ("seal", "펌프 씰")),
    "rt": (("bearing", "롤러 베어링"),),
    "cv": (("belt", "이송 벨트"), ("bearing", "구동 베어링")),
}

# Demo-only nominal bands. These are observation channels, not field limits.
ADDITIONAL_SIGNALS = {
    "HPU": (
        SignalSpec("hpu_oil_level", "유압유 탱크 유면", "pct", 70, 100),
        SignalSpec("hpu_pump_current", "유압 펌프 전류", "A", 15, 25),
        # Card-specific locations; demo bands, separate from bulk HPU readings.
        SignalSpec("hpu_cooler_oil_in_temp", "냉각기 오일 입구 온도", "degC", 35, 58),
        SignalSpec("hpu_cooler_oil_out_temp", "냉각기 오일 출구 온도", "degC", 35, 58),
        SignalSpec("hpu_cooler_water_in_temp", "냉각수 입구 온도", "degC", 15, 30),
        SignalSpec("hpu_cooler_water_out_temp", "냉각수 출구 온도", "degC", 20, 40),
        SignalSpec("hpu_cooler_oil_flow", "냉각기 통과 오일 유량", "L_min", 38, 46),
        SignalSpec("hpu_accumulator_gas_pressure", "축압기 가스측 압력", "bar", 130, 140),
        SignalSpec("hpu_accumulator_fluid_pressure", "축압기 유체측 압력", "bar", 145, 165),
        SignalSpec("hpu_return_submergence", "리턴 라인 유면 아래 잠김 깊이", "mm", 100, 200),
        SignalSpec("hpu_suction_head", "유면과 흡입 위치 높이차", "mm", 100, 200),
    ),
    "PDP": (
        SignalSpec("bus_current", "배전반 전류", "A", 20, 40),
        SignalSpec("breaker_trip", "차단기 트립 (0 정상 / 1 트립)", "bool", 0, 0),
    ),
    "CAU": (
        SignalSpec("air_flow", "압축공기 유량", "L_min", 100, 150),
        SignalSpec("compressor_current", "압축기 전류", "A", 8, 16),
    ),
    "GR": (
        SignalSpec("gr_oil_level", "감속기 오일 레벨", "pct", 70, 100),
        SignalSpec("gr_surface_temp", "감속기 표면 온도", "degC", 20, 40),
        SignalSpec("gr_rpm", "감속기 회전속도", "rpm", 900, 1100, zero_when_stopped=True),
        SignalSpec("gr_oil_leak", "누유 감지 (0 없음 / 1 감지)", "bool", 0, 0),
    ),
    "RT": (
        SignalSpec("rt_motor_current", "롤러 모터 전류", "A", 8, 16),
        SignalSpec("rt_vib_rms", "롤러 진동 RMS", "mm_s", 0.8, 1.8),
    ),
    "CV": (
        SignalSpec("cv_speed", "컨베이어 속도", "m_min", 8, 12, zero_when_stopped=True),
        SignalSpec("cv_idler_speed_ratio", "동일 조건 정상 대비 아이들러 회전 비율", "pct", 80, 100, zero_when_stopped=True),
        SignalSpec("cv_motor_current", "컨베이어 모터 전류", "A", 10, 20),
        SignalSpec("cv_vib_rms", "컨베이어 구동부 진동 RMS", "mm_s", 0.8, 1.8),
    ),
}

STOPPED_ZERO_SIGNALS = frozenset({
    "hpu_flow", "hpu_pump_current", "air_flow", "compressor_current",
    "gr_vib_rms", "gr_current", "gr_rpm", "rt_speed", "rt_motor_current",
    "rt_vib_rms", "cv_speed", "cv_motor_current", "cv_vib_rms",
})


def sensor_anomalies(equipment):
    """One synthetic numeric anomaly per bounded sensor, scoped to its installation."""
    for eq in equipment:
        if not eq.active or not eq.capabilities:
            continue
        capability = eq.capabilities[0]
        for signal in eq.signals:
            low, high = signal.normal_min, signal.normal_max
            if low is None or high is None:
                continue
            if signal.unit == "bool":
                if low <= 0 <= high and low <= 1 <= high:
                    continue  # Both legal boolean values are normal; no numeric anomaly exists.
                value = 0 if low <= 1 <= high else 1
            elif low > 0 and (signal.signal.endswith(("pressure", "press", "flow", "speed", "rpm", "oil_level"))
                              or signal.unit == "pct" and high >= 100):
                value = round(low * 0.8, 3)
                if value >= low:
                    value = round(max(0, low - 0.001), 3)
            else:
                value = round(high + max(abs(high) * 0.25, 0.001), 3)
            yield ScenarioSpec(f"sensor_anomaly_{eq.equipment_id}_{signal.signal}", capability, "", "", "AL-SENSOR-ANOMALY",
                (SignalEffect(capability, signal.signal, value),),
                title=f"{eq.code} · {signal.name} 이상 (가상)", cause_equipment_id=eq.equipment_id)


def expand(config):
    """Add missing priority scenarios to the catalog baseline; preserve old run configs."""
    from ..configuration import finalize
    existing = {s.scenario_id for s in config.scenarios}
    available = {cap for eq in config.equipment if eq.active for cap in eq.capabilities}
    additions = tuple(s for s in PRIORITY_SCENARIOS if s.scenario_id not in existing and s.cause_capability in available)
    equipment = []
    for eq in config.equipment:
        existing = {signal.signal for signal in eq.signals}
        added = (signal for signal in ADDITIONAL_SIGNALS.get(eq.code.split("-", 1)[0], ())
                 if signal.signal not in existing)
        signals = tuple(replace(signal, zero_when_stopped=True)
                        if signal.signal in STOPPED_ZERO_SIGNALS and not signal.zero_when_stopped else signal
                        for signal in (*eq.signals, *added))
        equipment.append(replace(eq, signals=signals))
    scenarios = config.scenarios + additions
    existing = {s.scenario_id for s in scenarios}
    sensors = tuple(s for s in sensor_anomalies(equipment) if s.scenario_id not in existing)
    from ..symptoms import symptom_scenarios
    symptoms = tuple(s for s in symptom_scenarios(equipment) if s.scenario_id not in existing)
    return finalize(replace(config, equipment=tuple(equipment), scenarios=scenarios + sensors + symptoms))
