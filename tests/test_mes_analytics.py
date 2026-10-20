"""대시보드 분석: 저장 이력에 심어 둔 이야기가 계산으로 다시 나오는지, 지금 실행 사건이 같은 계산에 합쳐지는지."""
import json
from datetime import timedelta
from pathlib import Path

from shiftlink.mes import analytics
from shiftlink.mes.configuration import from_catalog

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
RELATIONS, ROUTE = from_catalog(CATALOG).relations, from_catalog(CATALOG).route
STANDARD = CATALOG["production_lines"][0]["production_standard"]
# 집계는 달력 주(월~일) 기준이다. 저장 이력(28일)이 달력 4주 안에 다 들어오게 이력 끝을 일요일 밤으로 옮겨 계산한다.
END = analytics._dt("2026-10-18T23:00:00+09:00")


def test_calendar_weeks_start_on_monday():
    wed = analytics._dt("2026-10-14T06:00:00+09:00")
    assert analytics.calendar_weeks(wed, 1) == (analytics._dt("2026-10-12T00:00:00+09:00"), analytics._dt("2026-10-19T00:00:00+09:00"))
    assert analytics.calendar_weeks(wed, 4)[0] == analytics._dt("2026-09-21T00:00:00+09:00")
    # 시작점은 지금 시각에 따라 흔들리지 않는다 — 같은 주 안이면 같다
    assert analytics.calendar_weeks(analytics._dt("2026-10-18T23:59:00+09:00"), 4) == analytics.calendar_weeks(wed, 4)
    out = analytics.summary([], [], wed)
    assert (out["week_start"], out["week_end"], out["window_start"]) ==         ("2026-10-12T00:00:00+09:00", "2026-10-19T00:00:00+09:00", "2026-09-21T00:00:00+09:00")


def test_cause_suggestions_rank_same_alarm_then_confirmed():
    c = lambda certainty, note: {"certainty": certainty, "note": note}
    incidents = [
        {"equipment_id": "EQ-1", "alarm_code": "AL-A", "causes": [c("추정", "유량 부족")]},
        {"equipment_id": "EQ-1", "alarm_code": "AL-A", "causes": [c("확인", "스케일"), c("배제", "유량 부족")]},
        {"equipment_id": "EQ-1", "alarm_code": "AL-B", "causes": [c("확인", "다른 경보 원인"), c("확인", "다른 경보 원인")]},
        {"equipment_id": "EQ-1", "alarm_code": None, "causes": [c("배제", "배제만"), c("추정", " ")]},
        {"equipment_id": "EQ-2", "alarm_code": "AL-A", "causes": [c("확인", "다른 설비")]},
    ]
    assert analytics.cause_suggestions(incidents, "EQ-1", ["AL-A"]) == ["스케일", "유량 부족", "다른 경보 원인"]
    assert analytics.cause_suggestions(incidents, "EQ-1", []) == ["다른 경보 원인", "스케일", "유량 부족"]
    assert analytics.cause_suggestions(incidents, "EQ-1", ["AL-A"], limit=1) == ["스케일"]


def test_past_actions_rank_same_alarm_then_frequency():
    s = lambda action: {"action": action, "observed_result": ""}
    incidents = [
        {"equipment_id": "EQ-1", "alarm_code": "AL-B", "action_steps": [s("자주 한 조치"), s(" ")]},
        {"equipment_id": "EQ-1", "alarm_code": "AL-B", "action_steps": [s("자주 한 조치")]},
        {"equipment_id": "EQ-1", "alarm_code": "AL-A", "action_steps": [s("같은 경보 조치")]},
        {"equipment_id": "EQ-2", "alarm_code": "AL-A", "action_steps": [s("다른 설비")]},
        {"equipment_id": "EQ-1", "alarm_code": None},
    ]
    assert analytics.past_actions(incidents, "EQ-1", ["AL-A"]) == ["같은 경보 조치", "자주 한 조치"]
    assert analytics.past_actions(incidents, "EQ-1", []) == ["자주 한 조치", "같은 경보 조치"]


def _summary(extra=(), now=END):
    return analytics.summary([*analytics.load_history(END), *extra], RELATIONS, now, route=ROUTE, standard=STANDARD)


def test_planted_stories():
    out = _summary()
    # 정지 손실 = 라인을 세운 시간 × 표준 속도(1,500,000 t ÷ 7,000 h ÷ 20 t ≈ 시간당 10.7개). 대기 설비 수는 곱하지 않는다
    assert round(analytics.coils_per_hour(STANDARD), 1) == 10.7
    assert [(r["equipment_id"], r["stop_min"], r["coils"], r["halts_line"]) for r in out["loss"]] == \
        [("EQ-0001", 97, 17, True), ("EQ-0007", 51, 9, True), ("EQ-0009", 41, 7, True),
         ("EQ-0003", 39, 7, True), ("EQ-0005", 33, 6, True), ("EQ-0008", 23, 4, True)]
    assert out["production"] == {"planned": 1800, "lost": 51, "produced": 1749, "current": 1739, "coils_per_hour": 10.7}
    # 4주 이력에 설비 10대가 모두 나온다
    assert len({i["equipment_id"] for i in out["incidents"]}) == 10

    groups = {(g["equipment_id"], g["alarm_code"]): g for g in out["repeats"]}
    assert [(g["equipment_id"], g["count"], g["recurred"]) for g in out["repeats"]] == \
        [("EQ-0009", 8, 7), ("EQ-0004", 5, 4), ("EQ-0002", 4, 3), ("EQ-0007", 4, 2), ("EQ-0001", 3, 1),
         ("EQ-0005", 2, 0), ("EQ-0003", 2, 0)]
    # CV-01·PDP-01은 '해결'로 닫았는데 재발 → 근본 원인 미확인. 임시 조치 재발(GR-01·RT-02·HPU-01)은 세지 않는다
    assert [(g["equipment_id"], g["resolved_recurred"]) for g in out["repeats"]] == \
        [("EQ-0009", 7), ("EQ-0004", 0), ("EQ-0002", 3), ("EQ-0007", 0), ("EQ-0001", 0), ("EQ-0005", 0), ("EQ-0003", 0)]
    # 설비 MTBF·MTTR(4주, 설비 단위 — GR-02는 누유 2회 + 진동 1회 = 고장 3회)
    rel = {r["equipment_id"]: r["reliability"] for r in out["loss"]}   # 정지 손실 줄에 붙는다
    assert all(r["reliability"] for r in out["loss"]) and "reliability" not in out["repeats"][0]
    assert rel["EQ-0009"] == {"failures": 8, "mttr_min": 25, "mtbf_h": 83}   # (월 0시~일 23시 671h − 정지) ÷ 8
    assert rel["EQ-0005"]["failures"] == 3
    pdp = {a["action"]: a for a in groups[("EQ-0002", "AL-PDP-TRIP")]["actions"]}
    assert (pdp["차단기 재투입"]["recurred"], pdp["접속부 열화상 점검·단자 재체결"]["held"]) == (2, 1)   # K-1317로 고침
    gr = {a["action"]: a for a in groups[("EQ-0004", "AL-GR-HOT")]["actions"]}
    assert (gr["냉각팬 청소"]["count"], gr["냉각팬 청소"]["recurred"]) == (4, 4)
    assert (gr["윤활유 교체"]["recurred"], gr["윤활유 교체"]["held"], gr["윤활유 교체"]["card_ids"]) == (0, 1, ["K-1025"])
    hpu = {a["action"]: a for a in groups[("EQ-0001", "AL-HYD-HOT")]["actions"]}
    assert hpu["오일 쿨러 튜브 스케일 세정"]["watching"] == 1   # 복구 뒤 7일이 안 됐다 — 재발 없음으로 보지 않는다
    assert "response" not in out   # 대응 시간은 대시보드에서 뺐다(10/15 팀 합의)


def test_live_incident_joins_same_math():
    at = END + timedelta(minutes=10)
    iso = lambda m: (at + timedelta(minutes=m)).isoformat()
    events = [{"event_type": "alarm_raised", "equipment_id": "EQ-0004", "observation": "AL-GR-HOT", "occurred_at": iso(0), "sequence": 1},
              {"event_type": "alarm_raised", "equipment_id": "EQ-0004", "observation": "AL-SYMPTOM", "occurred_at": iso(0), "sequence": 1},
              {"event_type": "alarm_cleared", "equipment_id": "EQ-0004", "observation": "AL-GR-HOT", "occurred_at": iso(30), "sequence": 9}]
    sessions = [{"session_id": "RS-1", "equipment_id": "EQ-0004", "status": "saved",
                 "data": {"card_ids": ["K-1025"], "steps": [
                     {"action": "모터 전원을 차단하고 재기동을 방지한다", "simulated_at": iso(4), "result_text": "센서값 변화 없음",
                      "card_step": {"card_id": "K-1025", "step_id": "ST-01", "n": 1}},
                     {"action": "오일 교환", "simulated_at": iso(20), "result_text": "감속기 베어링 온도 85→58",
                      "card_step": {"card_id": "K-1025", "step_id": "ST-04", "n": 4}}]}}]
    handovers = [{"handover_id": "HO-x", "resolution": {"session_id": "RS-1", "result": "resolved", "cause": "윤활유 열화"}}]
    live = analytics.live_incidents(events, sessions, handovers)
    assert len(live) == 1 and (live[0]["handover_id"], live[0]["result"], live[0]["card_id"]) == ("HO-x", "resolved", "K-1025")

    out = _summary(live, now=at + timedelta(minutes=40))
    gr = next(r for r in out["loss"] if r["equipment_id"] == "EQ-0004")
    assert (gr["stop_min"], gr["coils"], gr["halts_line"]) == (30, 5, True)   # GR-01은 RT-01·RT-02를 구동 → 라인 정지 30분 ≈ 5.4개
    inc = next(i for i in out["incidents"] if i["incident_id"] == live[0]["incident_id"])
    assert (inc["down_min"], inc["outcome"]) == (30, "watching")

    # 카드 단계로 한 조치 → 카드 방법, 이름은 카드와 단계 번호. 센서를 움직였으니 '변화 없이 닫음'이 아니다
    assert (inc["action"], inc["card_method"], inc["no_change"]) == ("K-1025 1·4단계", True, False)
    gr = next(g for g in out["repeats"] if g["equipment_id"] == "EQ-0004")
    assert gr["methods"] == {"card": {"count": 2, "recurred": 0, "no_change": 0},
                             "other": {"count": 4, "recurred": 4, "no_change": 0}}


def test_method_split_and_no_change():
    at = END + timedelta(minutes=10)
    iso = lambda m: (at + timedelta(minutes=m)).isoformat()
    events = [{"event_type": "alarm_raised", "equipment_id": "EQ-0004", "observation": "AL-GR-HOT", "occurred_at": iso(0), "sequence": 1},
              {"event_type": "alarm_cleared", "equipment_id": "EQ-0004", "observation": "AL-GR-HOT", "occurred_at": iso(30), "sequence": 2}]
    # 카드를 봤지만 직접 입력만 했고 센서가 그대로 → 카드 밖 방법, 변화 없이 닫음
    sessions = [{"session_id": "RS-2", "equipment_id": "EQ-0004", "status": "saved",
                 "data": {"card_ids": ["K-1025"], "steps": [
                     {"action": "냉각팬 청소", "simulated_at": iso(5), "result_text": "센서값 변화 없음"}]}}]
    live = analytics.live_incidents(events, sessions, [])
    assert (live[0]["action"], live[0]["card_method"], live[0]["no_change"], live[0]["card_id"]) == \
        ("냉각팬 청소", False, True, "K-1025")
    out = _summary(live, now=at + timedelta(minutes=40))
    gr = next(g for g in out["repeats"] if g["equipment_id"] == "EQ-0004")
    assert gr["methods"]["other"] == {"count": 5, "recurred": 4, "no_change": 1}


def test_knowledge_gap_counts_real_records_only():
    queries = [{"no_knowledge": True}, {"no_knowledge": False, "cited_card_ids": ["K-7000", "K-1002"]},
               {"no_knowledge": True}, {"review_queue": True}, {"cited_card_ids": ["K-7001"]}]
    drafts = [{"status": "pending_review", "card": {"card_id": "K-7000"}},
              {"status": "pending_review", "card": {"card_id": "K-7001"}},
              {"status": "invalid", "card": {"card_id": "K-7002"}}]
    # 승격 도구는 초안 상태를 그대로 두고 카드 묶음에만 넣는다 → 묶음에 있으면 승인
    assert analytics.knowledge_gap(queries, drafts, {"K-1025", "K-7000"}) == \
        {"no_knowledge": 2, "drafts": 3, "pending": 1, "approved": 1, "approved_ids": ["K-7000"], "answered": 1}


def test_line_halt_follows_relations_over_several_steps():
    edges = {"PDP": ["GR"], "GR": ["RT1"], "CAU": ["CV2"], "X": []}
    route = {"RT1", "CV1"}
    assert analytics._halts_line("PDP", edges, route)        # 배전반 → 감속기 → 롤러(경로)
    assert analytics._halts_line("RT1", edges, route)        # 경로 설비 자체
    assert not analytics._halts_line("CAU", edges, route)    # 분기(CV2)만 세우면 출측 생산은 계속
    assert not analytics._halts_line("X", edges, route)


def test_current_production_follows_the_week_clock():
    # 현재 생산 = 월요일 0시부터 지금까지 정상이면 만들었을 양 − 손실. 월요일 0시엔 0, 10시간 뒤 약 107개
    def at(stamp):
        return analytics.summary([], [], analytics._dt(stamp), route=ROUTE, standard=STANDARD)["production"]["current"]
    assert at("2026-10-12T00:00:00+09:00") == 0
    assert at("2026-10-12T10:00:00+09:00") == 107
    assert at("2026-10-12T10:00:00+09:00") < at("2026-10-12T11:00:00+09:00")
