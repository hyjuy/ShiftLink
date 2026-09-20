"""Manual-informed synthetic scenarios, not field maintenance instructions."""
from dataclasses import replace

from ..contracts import RecoveryAction as Action, ScenarioSpec, SignalEffect, SignalSpec

SEW = "https://download.sew-eurodrive.com/download/html/31981496/en-EN/25440305419.html"
PARKER = "https://www.parker.com/content/dam/Parker-com/Literature/PMDE/Service_Manuals/Vane_Pumps/HY29-0035-UK.pdf"
SAP = "https://learning.sap.com/courses/configuring-sap-digital-manufacturing-for-execution-basic-data-and-configuration/controlling-production-buyoff-hold-release-"

PRIORITY_SCENARIOS = (
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


def expand(config):
    """Add missing priority scenarios to the catalog baseline; preserve old run configs."""
    from ..configuration import finalize
    existing = {s.scenario_id for s in config.scenarios}
    available = {cap for eq in config.equipment if eq.active for cap in eq.capabilities}
    additions = tuple(s for s in PRIORITY_SCENARIOS if s.scenario_id not in existing and s.cause_capability in available)
    equipment = tuple(replace(eq, signals=eq.signals + (
        SignalSpec("gr_oil_leak", "누유 감지 (0 없음 / 1 감지)", "bool", 0, 0),
    )) if "drive" in eq.capabilities and not any(s.signal == "gr_oil_leak" for s in eq.signals) else eq for eq in config.equipment)
    return finalize(replace(config, equipment=equipment, scenarios=config.scenarios + additions))
