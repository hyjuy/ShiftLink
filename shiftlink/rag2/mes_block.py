"""[MES] block in the answer prompt (MES SFT design 10/21, ShiftLink-records/experiments/mesft_20261021/DESIGN.md).

The answer model reads the selected unit's current MES snapshot next to the question and the evidence: every valid
signal with value, the state the MES adapter already computed and the normal range, the active alarms and the snapshot
time. Nothing is computed here; the block only renders QueryRequest fields. The model cites it as [M].
"""
from . import generate as G

STATE_KO = {"high": "높음", "low": "낮음", "normal": "정상"}
RULES = """- [MES]는 지금 이 설비의 측정값과 활성 경보입니다. [근거]의 사건 기록은 과거 다른 시점·다른 설비일 수 있는 기록입니다.
- 질문의 "경보·알람" 표현과 MES 활성 경보를 구분하고, 둘이 다르면 그 차이를 말합니다.
- MES에 없는 신호는 모른다고 하고, 다른 신호나 과거 기록으로 채우지 않습니다.
- MES 내용을 쓴 문장에는 [M]을 붙입니다."""
SYSTEM = G.SYSTEM.replace("\n출력은 JSON 하나:", "\n" + RULES + "\n출력은 JSON 하나:", 1)
SYSTEM = SYSTEM.replace('"citations": ["S1"]}', '"citations": ["S1", "M"]}', 1)


def _num(x) -> str:
    return f"{x:g}" if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x)


def render(eq_code: str, specs: dict, observations: list, snapshot_at: str | None, active_alarms: list,
           labels: dict | None = None) -> str:
    """specs: signal -> SignalSpec (from_catalog); observations: QueryRequest observations (value rows + <sig>_state rows)."""
    states = {o["signal"][:-len("_state")]: o["value"] for o in observations if o["signal"].endswith("_state")}
    lines = []
    for o in observations:
        sig = o["signal"]
        if sig.endswith("_state") or sig not in specs:
            continue
        spec, v = specs[sig], o["value"]
        name = spec.name.split(" (")[0]
        if spec.unit == "bool":
            rng, val = f"기준 {_num(spec.normal_max)}", _num(v)
        else:
            rng, val = f"기준 {_num(spec.normal_min)}–{_num(spec.normal_max)}", f"{_num(v)} {spec.unit}"
        # same rule as s30h.state_lines: a 0 on a zero-when-stopped signal is the stopped line, not a low reading
        state = "정지 중 0" if spec.zero_when_stopped and v == 0 else STATE_KO.get(states.get(sig), "상태 없음")
        lines.append(f"{name} {val} · {state} ({rng})")
    labels = labels or {}
    alarms = ", ".join(f"{labels.get(c, c)}({c})" for c in active_alarms) if active_alarms else "없음"
    body = "\n".join([f"활성 경보: {alarms}", *(lines or ["유효 관측 없음"])])
    return f'<mes id="M" eq="{eq_code}" snapshot_at="{snapshot_at or "미상"}">\n{body}\n</mes>'


def prompt(question: str, mes: str, ev: list[dict]) -> str:
    return G.prompt(question, ev).replace("\n\n[근거]\n", f"\n\n[MES]\n{mes}\n\n[근거]\n", 1)


def demo():
    from types import SimpleNamespace as S
    specs = {"hpu_filter_dp": S(name="리턴 필터 차압 (Return filter dP)", unit="bar", normal_min=0.0, normal_max=1.2, zero_when_stopped=True),
             "hpu_flow": S(name="공급 유량", unit="L_min", normal_min=38.0, normal_max=46.0, zero_when_stopped=True),
             "gr_oil_leak": S(name="누유 감지", unit="bool", normal_min=0, normal_max=0, zero_when_stopped=False)}
    obs = [{"signal": "hpu_filter_dp", "value": 1.5}, {"signal": "hpu_filter_dp_state", "value": "high"},
           {"signal": "hpu_flow", "value": 0.0}, {"signal": "hpu_flow_state", "value": "low"},
           {"signal": "gr_oil_leak", "value": 1}, {"signal": "gr_oil_leak_state", "value": "high"}]
    m = render("HPU-01", specs, obs, "2026-10-21T00:00:00+00:00", ["AL-SENSOR-ANOMALY"], {"AL-SENSOR-ANOMALY": "센서값 범위 이탈"})
    assert "리턴 필터 차압 1.5 bar · 높음 (기준 0–1.2)" in m, m
    assert "공급 유량 0 L_min · 정지 중 0" in m, m
    assert "누유 감지 1 · 높음 (기준 0)" in m, m
    assert "활성 경보: 센서값 범위 이탈(AL-SENSOR-ANOMALY)" in m, m
    assert "유효 관측 없음" in render("PDP-01", specs, [], None, [])
    p = prompt("q", m, [])
    assert p.index("[MES]") < p.index("[근거]"), p
    assert RULES in SYSTEM and '"M"]' in SYSTEM


if __name__ == "__main__":
    demo()
    print("ok")
