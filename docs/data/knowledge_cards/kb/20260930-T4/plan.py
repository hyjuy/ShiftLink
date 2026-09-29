"""KB-20260930-T4 사건 계획. 같은 SEED -> 같은 plan.json (바이트 동일).

시드는 이 계획만 고정한다. 사건 서술과 카드 문장은 바이트 재현되지 않으므로
실제 지시문을 prompts/ 에 두고 provenance.prompt_version(path@sha256)으로 참조한다.

설비·MES 시나리오·근거 카드 조합은 난수로 뽑지 않고 표(EVENT_DESIGN)에 명시했다.
`t4-handover-cards-assignment-20260930.md`의 "대응표로 정한 설계 규칙"이 조합을
직접 지정하기 때문이다(직접 연결 카드 6장 위주, RT는 MES 신호만, 카드 없는 영역 포함).
난수는 그 규칙이 값을 정해주지 않는 것 — 페르소나 선택, 사용 장면, 누락 항목 —
에만 쓴다.
"""

import json
import random
from pathlib import Path

SEED = 20260930
BATCH = "KB-20260930-T4"

# 인계 메모 5요소. 일부 사건에서 하나를 일부러 빼 누락 사례를 만든다.
HANDOVER_ELEMENTS = [
    "current_state",   # 현재 상태
    "prior_action",    # 앞 근무자가 한 조치(시각·결과)
    "failed_attempt",  # 시도했으나 실패한 것
    "unresolved",      # 미해결 사항
    "next_check",      # 다음 조 확인 사항
]
OMISSION_TARGET = 7  # 30건의 23% — 지시서 "20~30%"

# 설비별 담당 페르소나. seeds/personas_v0.1.yaml 의 equipment_focus 를 넘지 않는다.
PERSONA_POOL = {
    "HPU": ["V-11", "V-12"],      # V-11 주담당, V-12 보조(계측)
    "GR": ["V-11", "V-13"],       # V-11 운전, V-13 정비
    "RT": ["V-12", "V-11"],       # V-12 주담당, V-11 공급원 확인
    "CV": ["V-12", "V-13"],       # V-12 운전, V-13 정비
    "COMMON": ["V-11", "V-13"],   # PDP-01 순회(V-11) / 정비(V-13)
}

# (event_id, split, equipment, 대상설비코드, mes_scenario, signal_focus, cards_expected, design_note)
# mes_scenario=None 은 알람 없이 신호만 벗어난 사건이다(대응표: 알람은 시나리오가 걸릴 때만 난다).
EVENT_DESIGN = [
    # --- KB용 20건: 절반 이상을 대응표 '직접' 조합(K-1001·1002·1004·1024·1025·1027)으로 ---
    ("EV-0301", "kb", "HPU", "HPU-01", "hydraulic_fault", ["hpu_pressure"], ["K-1001"],
     "압력 저하 알람. 출구 압력 없음 확인 순서로 이어진다"),
    ("EV-0302", "kb", "HPU", "HPU-01", "hydraulic_fault", ["hpu_pressure", "hpu_flow"], ["K-1004"],
     "압력·유량 미달 + 소음·우유빛 거품은 작업자 관측으로만 기록(MES 신호 없음)"),
    ("EV-0303", "kb", "HPU", "HPU-01", "hydraulic_overheat", ["hpu_oil_temp"], ["K-1002"],
     "유온 상승. 냉각기 계통 확인 순서"),
    ("EV-0304", "kb", "GR", "GR-01", "gearbox_overheat", ["gr_brg_temp"], ["K-1025"],
     "베어링부 온도 상승. 오일 상태·베어링 확인"),
    ("EV-0305", "kb", "GR", "GR-01", "drive_fault", ["gr_vib_rms"], ["K-1024"],
     "진동 상승. 주 모터 정지 후 원인 확인"),
    ("EV-0306", "kb", "GR", "GR-01", "gearbox_leak", ["gr_oil_leak"], ["K-1027"],
     "누유 검출. 위치별 확인(커버·오일실·드레인·브리더)"),
    ("EV-0307", "kb", "HPU", "HPU-01", "hydraulic_fault", ["hpu_pressure", "hpu_flow"], ["K-1001", "K-1004"],
     "압력 저하가 교대 넘어 이어진 사건. 앞 조 조치 결과를 인계받아 재확인"),
    ("EV-0308", "kb", "GR", "GR-01", "gearbox_overheat", ["gr_brg_temp", "gr_current"], ["K-1024", "K-1025"],
     "온도·전류 동반 상승. 정지 판단과 정비 요청이 교대에 걸친다"),
    ("EV-0309", "kb", "HPU", "HPU-01", "hydraulic_overheat", ["hpu_oil_temp"], ["K-1002"],
     "유온 상승 재발. 앞 조 조치(쿨러 냉각수 확인) 결과 인계"),
    ("EV-0310", "kb", "GR", "GR-02", "gearbox_leak", ["gr_oil_leak"], ["K-1027"],
     "GR-02 누유. engine은 GR-02에 시나리오를 걸지 않으므로 신호는 사람이 읽은 값으로 기록"),
    ("EV-0311", "kb", "GR", "GR-01", "drive_fault", ["gr_vib_rms"], ["K-1024"],
     "진동 상승 + 갈리는 소리(관측). 정비 대기 상태를 인계"),
    ("EV-0312", "kb", "HPU", "HPU-01", "hydraulic_fault", ["hpu_pressure"], ["K-1001"],
     "압력 저하. 필터 교체 후 미회복이라 재확인 시각을 넘긴다"),
    # --- 카드 없는 영역·알람 없는 신호 이상·사람만 아는 정보 ---
    ("EV-0313", "kb", "HPU", "HPU-01", None, ["hpu_filter_dp"], [],
     "필터 차압만 상승. 카드 없음 -> 조치는 '정비 담당 확인'으로 둔다"),
    ("EV-0314", "kb", "CV", "CV-01", "downstream_block", ["cv_queue_len"], [],
     "적재 대기율 초과로 RT-03 인터록. 출측 정체는 카드 없음"),
    ("EV-0315", "kb", "CV", "CV-01", None, ["cv_belt_tension"], [],
     "벨트 장력 저하. 알람 없이 신호만 벗어난 사건"),
    ("EV-0316", "kb", "COMMON", "PDP-01", None, ["bus_voltage"], [],
     "배전반 전압 저하. V-11은 문을 열지 않고 외부 순회 관측만 기록"),
    ("EV-0317", "kb", "CV", "CAU-01", None, ["air_pressure"], [],
     "공압 저하로 CV-01 디버터 동작 지연. 카드 없음"),
    ("EV-0318", "kb", "RT", "RT-03", None, ["rt_clamp_press"], [],
     "클램프압 저하. RT는 MES 신호만 쓰고 승강부 구조를 가정하지 않는다"),
    ("EV-0319", "kb", "RT", "RT-03", None, ["rt_motor_current"], ["K-1017"],
     "모터 전류 상승 + 롤러 쪽 끽끽 소리(관측). 롤러 베어링 의심"),
    ("EV-0320", "kb", "HPU", "HPU-01", None, ["hpu_pressure"], ["K-1006"],
     "정지 상태인데 MES 압력은 정상값으로 나온다. 감압 여부는 사람이 확인해 적어야 하는 인계 정보"),
    # --- 평가용 10건: T4 카드 근거로 쓰지 않는다 ---
    ("EV-0321", "dev", "HPU", "HPU-01", "hydraulic_fault", ["hpu_pressure"], ["K-1001"],
     "평가용. 압력 저하"),
    ("EV-0322", "dev", "GR", "GR-01", "gearbox_overheat", ["gr_brg_temp"], ["K-1025"],
     "평가용. 베어링 온도 상승"),
    ("EV-0323", "dev", "CV", "CV-01", "downstream_block", ["cv_queue_len"], [],
     "평가용. 출측 정체"),
    ("EV-0324", "dev", "GR", "GR-01", "drive_fault", ["gr_vib_rms"], ["K-1024"],
     "평가용. 진동 상승"),
    ("EV-0325", "dev", "HPU", "HPU-01", "hydraulic_overheat", ["hpu_oil_temp"], ["K-1002"],
     "평가용. 유온 상승"),
    ("EV-0326", "dev", "RT", "RT-02", None, ["rt_speed", "rt_lift_delay"], [],
     "평가용. 반송 속도 저하와 승강 지연"),
    ("EV-0327", "dev", "GR", "GR-01", "gearbox_leak", ["gr_oil_leak"], ["K-1027"],
     "평가용. 누유"),
    ("EV-0328", "dev", "COMMON", "PDP-01", None, ["bus_voltage"], [],
     "평가용. 전압 저하"),
    ("EV-0329", "dev", "CV", "CV-01", None, ["cv_belt_tension", "cv_speed"], [],
     "평가용. 장력·속도 저하"),
    ("EV-0330", "dev", "HPU", "HPU-01", None, ["hpu_filter_dp"], [],
     "평가용. 필터 차압 상승"),
]

# 사용 장면. T4는 교대 인계라 S3이 기본이고, 신입·저년차 장면을 일부 섞는다.
SCENARIO_POOL = ["S3", "S3", "S3", "S1", "S2"]

# 인수 확인(acknowledgement) 장면을 넣을 KB용 사건과 그 방식.
#
# 난수로 뽑지 않는다. 대상은 "카드 11장이 각각 근거 2건 이상을 갖는 최소 집합"이라
# 계산으로 정해지고, 방식은 seeds/personas_v0.1.yaml 의 handover_style 에서 나온다
# (V-11 구두 / V-12 체크리스트 / V-13 문서). 나머지 11건은 확인 장면을 넣지 않는다 —
# 모든 인계에 확인이 있으면 비현실적이고, 있는 인계와 없는 인계를 견줄 수 없다.
ACK_DESIGN = {
    "EV-0304": ("document", "인수자가 전원 차단·재기동 방지 상태를 확인하고 정비 기록에 이름을 적음"),
    "EV-0305": ("document", "정지·재가동 보류 상태를 인수자가 정비 오더에 확인 기재"),
    "EV-0307": ("verbal", "받는 조가 '필터는 원인 아님'을 짚어 되묻고 확인"),
    # V-11 의 omission_risk(계측값·확인 시각 누락)를 그대로 따른다. 확인은 했으나 시각이 남지 않는다.
    "EV-0310": ("verbal_no_time", "구두로 짚어 넘겼으나 확인 시각을 적지 않음"),
    "EV-0312": ("checklist", "재확인 시각을 체크리스트에 적고 인수자 확인 표시"),
    "EV-0315": ("checklist", "다음 조 확인 항목에 인수자 확인 표시"),
    "EV-0317": ("document", "공압 저하 소견을 인수자가 읽고 정비 기록에 확인 기재"),
    "EV-0318": ("verbal", "공급원 확인 결과를 구두로 짚어 전달"),
    # 확인 실패 사례. 체크리스트 확인은 했으나 감압 항목이 서식에 없어 놓쳤다.
    "EV-0320": ("checklist_gap", "인수 확인은 했으나 감압 항목이 서식에 없어 확인에서 빠짐"),
}


def main() -> None:
    rng = random.Random(SEED)
    # 누락 사례를 넣을 사건을 먼저 뽑는다(전체 30건에서 균등).
    omission_idx = sorted(rng.sample(range(len(EVENT_DESIGN)), OMISSION_TARGET))
    omissions = {i: rng.choice(HANDOVER_ELEMENTS) for i in omission_idx}

    events, artifact_no = [], 301
    for i, (eid, split, eq, target, mes, signals, cards, note) in enumerate(EVENT_DESIGN):
        ack = ACK_DESIGN.get(eid)
        events.append({
            "event_id": eid,
            "split": split,
            "equipment": eq,
            "target_equipment": target,
            "scenario": rng.choice(SCENARIO_POOL),
            "persona_id": rng.choice(PERSONA_POOL[eq]),
            "mes_scenario": mes,
            "signal_focus": signals,
            "cards_expected": cards,
            "artifact_ids": [f"AR-{artifact_no:04d}", f"AR-{artifact_no + 1:04d}"],
            "omitted_handover_element": omissions.get(i),
            "ack_method": ack[0] if ack else None,
            "ack_note": ack[1] if ack else None,
            "design_note": note,
        })
        artifact_no += 2

    out = {
        "batch_id": BATCH,
        "seed": SEED,
        "generator": "plan.py",
        "handover_elements": HANDOVER_ELEMENTS,
        "card_id_start": "K-1101",
        "events": events,
    }
    # newline="\n" 고정: 기본값은 플랫폼 줄바꿈으로 바꿔 써서 Windows에서 CRLF가 된다.
    # 그러면 "같은 시드면 plan.json 바이트 동일" 요건이 OS마다 깨지고, git이 LF로
    # 저장한 내용과도 어긋난다.
    Path(__file__).with_name("plan.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )

    kb = [e for e in events if e["split"] == "kb"]
    direct = [e for e in events if set(e["cards_expected"]) & {"K-1001", "K-1002", "K-1004", "K-1024", "K-1025", "K-1027"}]
    acks = [e for e in events if e["ack_method"]]
    dev_acks = [e for e in acks if e["split"] != "kb"]
    print(f"사건 {len(events)}건 (kb {len(kb)} / dev {len(events) - len(kb)})")
    print(f"대응표 '직접' 연결 카드를 쓰는 사건: {len(direct)}건 ({len(direct) / len(events):.0%})")
    print(f"누락 사례: {len(omissions)}건 -> {[(events[i]['event_id'], v) for i, v in sorted(omissions.items())]}")
    print(f"인수 확인 장면: {len(acks)}건 / kb {len(kb)}건 중 {len(acks) / len(kb):.0%}")
    from collections import Counter
    print(f"  방식 분포: {dict(Counter(e['ack_method'] for e in acks))}")
    assert not dev_acks, f"평가용 사건에 확인 장면이 배정됨: {[e['event_id'] for e in dev_acks]}"
    print(f"artifact: AR-0301~AR-{artifact_no - 1:04d} ({len(events) * 2}건)")


if __name__ == "__main__":
    main()
