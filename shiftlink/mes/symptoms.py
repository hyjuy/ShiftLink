"""Research-informed screening hypotheses; numeric bands remain synthetic."""
from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite

from .contracts import ScenarioSpec, SignalEffect


HPU = "https://doi.org/10.5162/sensor2015/D8.1"
CAU = "https://doi.org/10.1016/j.clet.2021.100355"
GR = "https://doi.org/10.1155/2016/5467643"
CV = "https://doi.org/10.1371/journal.pone.0277352"
PDP = "https://doi.org/10.1007/s44163-026-01336-7"


@dataclass(frozen=True)
class Pattern:
    pattern_id: str
    family: str
    symptom: str
    states: dict[str, str]
    candidates: tuple[str, ...]
    checks: tuple[str, ...]
    sources: tuple[str, ...]
    limitation: str


PATTERNS = (
    Pattern("hpu_delivery", "HPU", "유압 압력·유량 저하",
        {"hpu_pressure": "low", "hpu_flow": "low", "hpu_filter_dp": "normal"},
        ("펌프 공급 능력 저하", "내부 누설 또는 제어 설정 문제"),
        ("동일 부하 구간의 압력·유량 이력 비교", "센서 위치와 누설·제어 계통 기록 확인"), (HPU,), "논문의 입력전력 W를 전류 A로 환산하지 않으며 원인별 학습 모델을 재현하지 않았다."),
    Pattern("hpu_restriction", "HPU", "유압 공급 저하와 차압 상승",
        {"hpu_pressure": "low", "hpu_flow": "low", "hpu_filter_dp": "high"},
        ("필터 또는 유로 저항 증가", "저온 점도 등 운전 조건 영향"),
        ("필터 표시·유온·점도와 차압 측정 위치 확인", "실제 필터 모델 기준 대조"), (HPU,), "차압 조합은 프로젝트 가설이며 논문이 1.2 bar 기준을 제시한 것은 아니다."),
    Pattern("hpu_heat", "HPU", "유압유 온도 상승",
        {"hpu_oil_temp": "high", "hpu_flow": "normal", "hpu_pump_current": "normal"},
        ("냉각 성능 저하", "운전 부하·주변 온도 영향"),
        ("동일 운전 구간의 온도 추세 확인", "냉각기 입출구 온도와 유체 상태 자료 추가 확인"), (HPU,), "냉각 회로 센서와 효율 데이터가 없어 냉각기 고장을 확정할 수 없다."),
    Pattern("cau_supply", "CAU", "공압 압력·유량 저하",
        {"air_pressure": "low", "air_flow": "low", "compressor_current": "high"},
        ("공급 능력 저하", "공급 경로 제한 또는 제어 문제"),
        ("유량 측정 위치와 수요·압축기 운전 모드 확인", "상하류 압력 및 공급 경로 기록 비교"), (CAU,), "압력↓·유량↓만으로 누설을 판정하지 않는다. 전류 분기는 프로젝트 가설이다."),
    Pattern("cau_flow_demand", "CAU", "공압 압력 저하와 공급 유량 증가",
        {"air_pressure": "low", "air_flow": "high", "compressor_current": "high"},
        ("공기 누설 가능성", "정상 수요 증가 또는 동시 소비"),
        ("공급 총유량 센서인지 확인하고 동일 수요 기준과 비교", "무수요 압력 감쇠·계통 체적·온도 자료 추가 확인"), (CAU,), "공급 측 총유량이라는 가상 가정이다. 수요 상태·체적이 없어 누설량 계산과 위치 확정은 보류한다."),
    Pattern("gr_lubrication", "GR", "감속기 진동·온도 상승과 유면 저하",
        {"gr_vib_rms": "high", "gr_brg_temp": "high", "gr_oil_level": "low", "gr_current": "normal", "gr_rpm": "normal"},
        ("윤활 상태 불량", "회전부 저항 또는 베어링 문제"),
        ("유면·윤활 이력과 동일 부하 상태 비교", "원시 진동·전류 파형 및 회전속도별 스펙트럼 추가 확인"), (GR,), "유면·온도 분기는 프로젝트 가설이며 RMS만으로 베어링 부위나 기어 결함을 확정하지 않는다."),
    Pattern("gr_load", "GR", "감속기 회전속도 저하와 전류 상승",
        {"gr_current": "high", "gr_rpm": "low", "gr_vib_rms": "normal", "gr_brg_temp": "normal"},
        ("부하 증가", "구동 저항 또는 제어 문제"),
        ("속도 지령·부하 이력 확인", "동일 속도 조건의 전류·진동 파형 추가 확인"), (GR,), "스펙트럼 기반 논문의 고장 분류기를 재현하지 않은 요약값 조합이다."),
    Pattern("rt_resistance", "RT", "롤러 이송 속도 저하와 전류·진동 상승",
        {"rt_speed": "low", "rt_motor_current": "high", "rt_vib_rms": "high", "rt_clamp_press": "normal"},
        ("이송 부하·기계 저항 증가", "구동 계통 이상"),
        ("속도 지령·소재 부하·상위 구동 관계 확인", "회전부 파형과 정지 이력 추가 확인"), (GR,), "RT 직접 검증 논문을 확보하지 못했다. 회전기계 방법을 참고한 프로젝트 가설이다."),
    Pattern("rt_clamp", "RT", "클램프 압력 저하",
        {"rt_clamp_press": "low", "rt_speed": "normal", "rt_motor_current": "normal"},
        ("상위 유압 공급 문제", "클램프 유압 회로 손실 또는 제어 문제"),
        ("실제 공급 관계와 HPU 압력·유량 비교", "클램프 회로와 운전 지령 기록 확인"), (HPU,), "RT 설치 구조 미확정이며 HPU 연구를 RT 전용 검증으로 간주하지 않는다."),
    Pattern("rt_lift", "RT", "승강 지연과 압력 저하",
        {"rt_lift_delay": "high", "rt_clamp_press": "low", "rt_motor_current": "normal"},
        ("유압 공급·제어 문제", "승강 회로 또는 하중 영향"),
        ("HPU 공급 관측과 승강 지령·하중 기록 비교", "승강 실린더 전용 압력·위치 데이터 추가 확인"), (HPU,), "클램프 압력은 승강 실린더 압력의 대체값이 아니다. 두 증상의 동시 관측 후보이며 RT 직접 검증은 없다."),
    Pattern("cv_slip", "CV", "컨베이어 속도·장력 저하",
        {"cv_speed": "low", "cv_belt_tension": "low", "cv_motor_current": "normal"},
        ("장력 부족과 벨트 슬립 가능성", "속도 지령 또는 부하 상태 변화"),
        ("벨트·구동 드럼 속도 차이와 지령 확인", "장력 측정 위치와 적용 모델 기준 확인"), (CV,), "탄광 컨베이어 학습 모델과 장력 단위를 이식하지 않았다. 속도 차이 센서가 없어 슬립 확정은 보류한다."),
    Pattern("cv_resistance", "CV", "컨베이어 속도 저하·전류 상승·정체",
        {"cv_speed": "low", "cv_motor_current": "high", "cv_queue_len": "high"},
        ("막힘·이송 저항 증가", "소재 부하 또는 상하류 흐름 문제"),
        ("소재 부하·대기열·속도 지령 확인", "장력·구동 상태와 하류 흐름 기록 비교"), (CV,), "전류 상승을 벨트 손상으로 단정하지 않는다. 이 조합은 프로젝트 선별 가설이다."),
    Pattern("pdp_voltage", "PDP", "버스 전압 저하",
        {"bus_voltage": "low", "bus_current": "normal", "breaker_trip": "normal"},
        ("상위 전원 품질 문제", "부하 또는 계측 기준 변화"),
        ("기준 전압·RMS 여부와 3상 전압 이력 확인", "동일 시각 부하·상위 전원 기록 비교"), (PDP,), "pct를 실제 전압이나 표준 전압강하 기준으로 환산하지 않는다."),
    Pattern("pdp_current", "PDP", "버스 전류 상승, 트립 전 관측",
        {"bus_voltage": "normal", "bus_current": "high", "breaker_trip": "normal"},
        ("부하 증가 또는 기동 전류", "과전류 원인 가능성"),
        ("기동·부하 이력과 차단기 정격·설정 기록 확인", "3상 전류 파형과 보호계전 이벤트 비교"), (PDP,), "집계 전류만으로 단락·접지 고장 유형이나 보호 동작을 확정하지 않는다."),
    Pattern("pdp_trip", "PDP", "차단기 트립 후 전류 소실",
        {"bus_voltage": "normal", "bus_current": "zero", "breaker_trip": "high"},
        ("보호 동작 또는 차단 이벤트", "트립 전 기록이 없어 상세 원인 미정"),
        ("트립 직전 전압·전류와 보호계전 로그 확인", "수동 차단·보호 동작 기록 구분"), (PDP,), "차단 후 전류 0과 차단 전 과전류를 같은 시점으로 합치지 않는다. 무전압·작업 안전 판단은 제공하지 않는다."),
)


def symptom_scenarios(equipment):
    for eq in equipment:
        specs = {s.signal: s for s in eq.signals}
        for pattern in PATTERNS:
            if (not eq.active or not eq.capabilities or eq.code.split("-")[0] != pattern.family
                    or not pattern.states.keys() <= specs.keys()):
                continue
            effects = []
            for signal, state in pattern.states.items():
                s = specs[signal]
                if s.normal_min is None or s.normal_max is None:
                    break
                value = (s.normal_min + s.normal_max) / 2
                if state == "zero": value = 0
                elif state == "low": value = s.normal_min * 0.8
                elif state == "high": value = 1 if s.unit == "bool" else s.normal_max + max(abs(s.normal_max) * 0.25, 0.001)
                value = round(value, 3)
                if state == "low" and value >= s.normal_min:
                    value = round(max(0, s.normal_min - 0.001), 3)
                if ((s.unit == "bool" and value not in (0, 1))
                    or state == "low" and value >= s.normal_min
                    or state == "high" and value <= s.normal_max
                    or state == "normal" and not s.normal_min <= value <= s.normal_max):
                    break  # This configuration cannot represent the requested observation.
                effects.append(SignalEffect(eq.capabilities[0], signal, value))
            else:
                yield ScenarioSpec(f"symptom_{eq.equipment_id}_{pattern.pattern_id}", eq.capabilities[0], "", "", "AL-SYMPTOM",
                    tuple(effects), title=f"{eq.code} · {pattern.symptom}", cause_equipment_id=eq.equipment_id,
                    stop_on_fault=pattern.pattern_id == "pdp_trip")


def _states(frame, eq):
    specs = {s.signal: s for s in eq.signals}
    latest = {}
    for m in frame.get("measurements", []):
        if m.get("equipment_id") == eq.equipment_id:
            latest[m.get("signal")] = m
    states, evidence = {}, {}
    for signal, s in specs.items():
        m = latest.get(signal, {})
        value = m.get("value")
        valid = (m.get("quality") == "good" and m.get("unit") == s.unit
                 and isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
                 and (s.unit != "bool" or value in (0, 1))
                 and s.normal_min is not None and s.normal_max is not None)
        try:
            observed = m.get("observed_at")
            now = frame.get("simulated_at")
            observed = observed if isinstance(observed, datetime) else datetime.fromisoformat(observed)
            now = now if isinstance(now, datetime) else datetime.fromisoformat(now)
            valid = valid and observed.tzinfo is not None and now.tzinfo is not None and observed == now
        except (TypeError, ValueError):
            valid = False
        states[signal] = ("low" if value < s.normal_min else "high" if value > s.normal_max else "normal") if valid else None
        evidence[signal] = {"signal": signal, "value": value, "unit": m.get("unit"), "state": states[signal],
                            "normal_min": s.normal_min, "normal_max": s.normal_max}
    return states, evidence


def screen_symptoms(frames, config):
    """Use only measurements and collection context; do not read scenario/cause labels."""
    frames = [asdict(f) if not isinstance(f, dict) else f for f in frames]
    if not frames or frames[-1].get("line_mode") in {"paused", "stopped", "recovering", "quality_hold"}:
        return []
    run_id = frames[-1].get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return []
    frames = list({f.get("sequence"): f for f in frames if f.get("run_id") == run_id}.values())[-3:]
    try:
        times = [f["simulated_at"] if isinstance(f.get("simulated_at"), datetime)
                 else datetime.fromisoformat(f["simulated_at"]) for f in frames]
        consecutive = (len(frames) == 3
            and all(f.get("line_mode") not in {"paused", "stopped", "recovering", "quality_hold"} for f in frames)
            and all(b.get("sequence") == a.get("sequence") + 1 for a, b in zip(frames, frames[1:]))
            and all(a < b for a, b in zip(times, times[1:])))
    except (TypeError, ValueError, KeyError):
        consecutive = False
    records = []
    for eq in config.equipment:
        if not eq.active:
            continue
        readings = [_states(f, eq) for f in frames]
        states, evidence = readings[-1]
        for p in PATTERNS:
            if eq.code.split("-")[0] != p.family or not p.states.keys() <= states.keys():
                continue
            def matches(signal, expected, states, evidence):
                if states[signal] is None: return None
                return evidence[signal]["value"] == 0 if expected == "zero" else states[signal] == expected
            checks = [matches(s, wanted, states, evidence) for s, wanted in p.states.items()]
            abnormal = any(wanted != "normal" and matches(s, wanted, states, evidence) is True for s, wanted in p.states.items())
            if False in checks or not abnormal:
                continue
            sustained = consecutive and all(all(matches(s, wanted, st, ev) is True for s, wanted in p.states.items()) for st, ev in readings)
            status = "unverified" if None in checks else "candidate" if sustained else "observing"
            records.append({"equipment_id": eq.equipment_id, "pattern_id": p.pattern_id, "symptom": p.symptom,
                "status": status, "confirmed": False, "threshold_basis": "synthetic_config",
                "candidates": p.candidates, "checks": p.checks, "sources": p.sources, "limitation": p.limitation,
                "evidence": [evidence[s] | {"expected_state": expected} for s, expected in p.states.items()]})
    return records
