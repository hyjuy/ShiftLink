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


def _rows(specs: dict, observations: list) -> list[tuple[str, str, str, str]]:
    """(name, value with unit, state word, range) per valid signal, in observation order."""
    states = {o["signal"][:-len("_state")]: o["value"] for o in observations if o["signal"].endswith("_state")}
    rows = []
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
        rows.append((name, val, state, rng))
    return rows


def _alarms(active_alarms: list, labels: dict | None) -> str:
    labels = labels or {}
    return ", ".join(f"{labels.get(c, c)}({c})" for c in active_alarms) if active_alarms else "없음"


def render(eq_code: str, specs: dict, observations: list, snapshot_at: str | None, active_alarms: list,
           labels: dict | None = None) -> str:
    """specs: signal -> SignalSpec (from_catalog); observations: QueryRequest observations (value rows + <sig>_state rows)."""
    lines = [f"{n} {v} · {s} ({r})" for n, v, s, r in _rows(specs, observations)]
    body = "\n".join([f"활성 경보: {_alarms(active_alarms, labels)}", *(lines or ["유효 관측 없음"])])
    return f'<mes id="M" eq="{eq_code}" snapshot_at="{snapshot_at or "미상"}">\n{body}\n</mes>'


NO_ACTION = "근거 자료에서 이 상황의 조치를 찾지 못했습니다. 조치는 정비 담당 확인이 필요합니다."


def summary(eq_code: str, specs: dict, observations: list, active_alarms: list, labels: dict | None = None) -> str:
    """(가) 10/21: one code-written sentence of the unit's MES state put in front of the answer (no model involved)."""
    rows = _rows(specs, observations)
    off = [f"{n} {v} {'높음' if s == '높음' else '낮음'}({r})" for n, v, s, r in rows if s in ("높음", "낮음")]
    alarm = f"활성 경보 {_alarms(active_alarms, labels)}"
    if not rows:
        return f"현재 MES({eq_code}): 유효 관측 없음, {alarm}."
    return f"현재 MES({eq_code}): {', '.join(off) if off else '측정값 모두 정상 범위'}, {alarm}."


def where(m: dict, event_label: bool = True) -> str:
    """Source label; with event_label an event chunk is a handover record, not the card it was filed under
    (10/20 event-conflict cause 1: the model could not tell event K-11xx from card K-11xx). Off = G.prompt labels."""
    if m["kind"] == "source":
        return f'{m["source"]} p.{m["page"]}'
    return f'{"인계 기록" if event_label and m["kind"] == "event" else "카드"} {m["source"]}'


def prompt(question: str, mes: str, ev: list[dict], event_label: bool = True) -> str:
    parts = [f'<source id="S{n}" from="{where(r["metadata"], event_label)}">\n{r["text"]}\n</source>' for n, r in enumerate(ev, 1)]
    return f"[질문]\n{question}\n\n[MES]\n{mes}\n\n[근거]\n" + "\n".join(parts)


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
    s = summary("HPU-01", specs, obs, ["AL-SENSOR-ANOMALY"], {"AL-SENSOR-ANOMALY": "센서값 범위 이탈"})
    assert s == "현재 MES(HPU-01): 리턴 필터 차압 1.5 bar 높음(기준 0–1.2), 누유 감지 1 높음(기준 0), 활성 경보 센서값 범위 이탈(AL-SENSOR-ANOMALY).", s
    assert summary("PDP-01", specs, [], []) == "현재 MES(PDP-01): 유효 관측 없음, 활성 경보 없음."
    assert summary("HPU-01", specs, obs[2:4], []) == "현재 MES(HPU-01): 측정값 모두 정상 범위, 활성 경보 없음."   # stopped 0
    ev = [{"text": "t", "metadata": {"kind": k, "source": s, "page": 3}} for k, s in (("event", "K-1103"), ("card", "K-1210"), ("source", "m.pdf"))]
    p = prompt("q", m, ev)
    assert p.index("[MES]") < p.index("[근거]"), p
    assert 'from="인계 기록 K-1103"' in p and 'from="카드 K-1210"' in p and 'from="m.pdf p.3"' in p, p
    assert prompt("q", m, ev, event_label=False).replace(f"\n\n[MES]\n{m}", "") == G.prompt("q", ev)   # block-only ablation
    assert RULES in SYSTEM and '"M"]' in SYSTEM


if __name__ == "__main__":
    demo()
    print("ok")
