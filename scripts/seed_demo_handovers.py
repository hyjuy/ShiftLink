"""발표·시연용 근무일지(PDA 인계사항 전체보기)를 로컬 MES 저장소에 적재한다.

    python scripts/seed_demo_handovers.py [--db mes_data/mock-mes.sqlite3] [--reset] [--status uploaded]

- 이야기: EV-0031(상류 GR-01 이상이 하류 RT-03 증상으로 나타난 사건)의 인계 4건 + 다른 설비 8건 = 9줄(조치 필요 5·해결완료 4).
- 시각은 실행한 날 기준으로 1~5일 전에 맞춘다. 해결완료는 7일이 지나면 홈에서 사라지므로 발표 당일에 다시 실행한다.
- 저장 형식은 PDA가 보내는 /api/handover 본문과 같고, 저장 전에 서버와 같은 검증(work_reports.validate)을 거친다.
- --reset: 이 저장소의 인계 기록(handover_outbox)과 딸린 사건 연결을 모두 지우고 다시 넣는다. 서버를 끈 뒤 실행.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shiftlink.mes import configuration, work_reports  # noqa: E402
from shiftlink.mes.storage import MesStorage  # noqa: E402

CATALOG = ROOT / "docs" / "data" / "reference" / "00_plant_and_relations.json"
SHIFTS = {"A": ("08:00", 8), "B": ("16:00", 8), "C": ("00:00", 8)}   # 시작 시각, 근무 시간(PDA의 A·B·C조 구분과 같다)
HPU, PDP, CAU, GR01, GR02, RT01, RT02, RT03, CV01, CV02 = (f"EQ-{n:04d}" for n in range(1, 11))   # catalog 순서


def step(at, action, result, worker, failed=False):
    return {"action": action, "observed_result": result, "failed": failed, "worker": worker, "performed_at": at}


def sample(value, at):
    return {"source": "manual", "value": value, "observed_at": at}


def cause(eq, certainty, note, signal=None, value=None, unit=None, at=None):
    c = {"equipment": [eq], "certainty": certainty, "note": note}
    if signal:
        c["sensor_ref"] = {"equipment_id": eq, "signal": signal}
        c["sensor_reading"] = {"value": value, "unit": unit, "observed_at": at}
    return c


def sensor(eq, signal, unit, problem, before=None, after=None):
    s = {"equipment_id": eq, "signal": signal, "unit": unit, "problem": problem}
    if before:
        s["before"] = before
    if after:
        s["after"] = after
    return s


def fault(day, hhmm, equipment, story, **kw):
    """고장·정비/이상증상 기록. 기본값은 조치 안 한 미해결 기록."""
    steps = kw.pop("steps", [])
    record = {"type": kw.pop("type", "고장·정비"), "equipment": equipment, "story": story, "causes": kw.pop("causes", []),
              "pms": None, "candidate": False, "auto_candidate": False, "capture_version": 1,
              "occurred_at": f"{day}T{hhmm}", "action_steps": steps, "restart_performed": False, "restart_type": "unknown",
              "outcome": "open", "symptom": "", "operating_context": "", "safety_notes": "", "safety_action": "",
              "safety_basis": "", "follow_up": "", "references": "", "remaining_issue": "", "next_check": "",
              "next_check_at": "", "fault_sensors": [], "sensor_unknown": False,
              "solution": "\n".join(f"{i}. {s['action']}" for i, s in enumerate(steps, 1)),
              "result": steps[-1]["observed_result"] if steps else None}
    record.update(kw)
    if record["fault_sensors"] == [] and record["type"] in work_reports.FAULT_TYPES:
        record["sensor_unknown"] = True
    return record


def pms(day, hhmm, equipment, story, **kw):
    steps = kw.pop("steps", [])
    record = fault(day, hhmm, equipment, story, type="PMS 정비", steps=steps, **kw)
    record.update(candidate=False, parts=kw.get("parts", []), no_parts_used=not kw.get("parts"))
    record.pop("fault_sensors"), record.pop("sensor_unknown")
    return record


def build(today: date) -> list[dict]:
    """(일지 정의) 순서가 곧 저장 순서다. 같은 사건을 잇는 일지는 follows=앞 일지 id."""
    d = lambda n: (today + timedelta(days=n)).isoformat()   # noqa: E731
    han, oh, yun, choi = "허재원", "유현준", "전혜민", "최재영"   # 등록된 계정
    pair = [RT03, GR01]
    rows = []

    def add(rid, day, shift, author, targets, records, mes, follows=None, work_type="고장·이상 대응"):
        rows.append(dict(id=rid, day=day, shift=shift, author=author, targets=targets, records=records,
                         mes=mes, follows=follows, work_type=work_type))

    # ── 사건 A: EV-0031 — RT-03 사행·전류 상승의 원인이 상류 GR-01 베어링 (5일 전 → 3일 전 해결) ──────────────
    add("HO-DEMO-A1", -5, "B", han, pair, [fault(d(-5), "16:20", pair,
        "출측 RT-03 29~32번 롤러 구간에서 소재가 처지며 사행. RT-03 모터 전류가 17.8 A로 평소보다 높다.",
        symptom="출측 소재 처짐·사행, RT-03 모터 전류 상승",
        causes=[cause(GR01, "추정", "상류 GR-01 진동이 정상 상한에 가까워 RT-01·02 이송 속도가 흔들린 것으로 본다. RT-03 자체 이상은 아니다.",
                      "gr_vib_rms", 3.4, "mm_s", f"{d(-5)}T16:27"),
                cause(RT03, "배제", "RT-03 직접 구동 감속기 진동 1.9 mm/s로 정상 → RT-03 자체 원인 아님")],
        steps=[step(f"{d(-5)}T16:35", "GR-01 진동·베어링 온도 재측정(16:35, 16:45)",
                    "진동 3.4→3.6 mm/s, 베어링 온도 64.5→65.2 ℃. 상승 추세", han),
               step(f"{d(-5)}T17:05", "반장 승인 후 GR-01 감속기 윤활 보충, 라인 속도 96→80 m/min 하향",
                    "17:40 처짐·사행 완화, RT-03 전류 16.4 A. GR-01 진동 3.1 mm/s로 남아 있음", han)],
        outcome="temporary", normal_run_status="observing", normal_run_minutes=240,
        normal_run_evidence="17:40~21:40 속도 80 m/min 운전. 처짐·사행 재발 없음, RT-03 전류 16.0~16.4 A",
        result="처짐·사행 완화(전류 17.8→16.4 A). 원인은 해소되지 않았고 속도 80 m/min 임시 유지",
        operating_context="속도 하향은 반장 승인을 받은 임시 조치다. 임의로 96 m/min으로 되돌리지 않는다.",
        remaining_issue="라인 속도 96→80 m/min 임시 하향 중. GR-01 진동 3.1 mm/s(정상 0.5~2.8) 원인 미해소",
        next_check="GR-01 진동·베어링 온도를 4시간 간격으로 재측정(경보 기준 진동 4.5 mm/s, 온도 72 ℃)",
        next_check_at="다음 근무(C조) 시작부터",
        fault_sensors=[sensor(GR01, "gr_vib_rms", "mm_s", "진동이 정상 상한(2.8)을 넘음", sample(3.4, f"{d(-5)}T16:27"), sample(3.1, f"{d(-5)}T17:40")),
                       sensor(RT03, "rt_motor_current", "A", "모터 전류가 정상 상한(16)을 넘음", sample(17.8, f"{d(-5)}T16:24"), sample(16.4, f"{d(-5)}T17:40"))])],
        "RT-03 모터 전류 17.8 A(정상 8~16), 출측 롤러 처짐·사행 육안 확인. GR-01 진동 3.4 mm/s(정상 0.5~2.8), 베어링 온도 64.5 ℃.")

    add("HO-DEMO-A2", -4, "C", oh, pair, [fault(d(-4), "00:30", pair,
        "GR-01 4시간 간격 재측정. 02:00 진동 3.3 mm/s·온도 66 ℃, 06:00 진동 3.5 mm/s·온도 68 ℃로 오르는 중. 속도 80 m/min 유지, 처짐 재발 없음.",
        symptom="GR-01 진동·온도 상승 추세",
        causes=[cause(GR01, "추정", "진동과 온도가 함께 오르므로 입력측 베어링 초기 열화 가능성이 높다.", "gr_brg_temp", 68, "degC", f"{d(-4)}T06:00")],
        steps=[step(f"{d(-4)}T02:00", "GR-01 진동·베어링 온도 재측정", "진동 3.3 mm/s, 온도 66 ℃", oh),
               step(f"{d(-4)}T06:00", "GR-01 진동·베어링 온도 재측정, 반장에게 추세 보고", "진동 3.5 mm/s, 온도 68 ℃. 계획 정지 앞당김 협의 요청", oh)],
        outcome="temporary", normal_run_status="observing", normal_run_minutes=420,
        normal_run_evidence="00:00~07:00 속도 80 m/min 운전. 처짐 없음, RT-03 전류 15.8~16.2 A",
        remaining_issue="GR-01 진동 3.5 mm/s·온도 68 ℃로 상승 중. 경보(4.5 mm/s, 72 ℃) 전에 정지·점검 필요",
        next_check="계획 정지 일정에 GR-01 입력측 베어링 점검 등록 여부 확인", next_check_at="A조 시작 즉시",
        followup_from={"handover_id": "HO-DEMO-A1", "record_index": 0},
        fault_sensors=[sensor(GR01, "gr_brg_temp", "degC", "베어링 온도 상승 추세", sample(66, f"{d(-4)}T02:00"), sample(68, f"{d(-4)}T06:00"))])],
        "GR-01 진동 3.5 mm/s, 베어링 온도 68 ℃(06:00). RT-03 전류 15.8~16.2 A.", follows="HO-DEMO-A1")

    add("HO-DEMO-A3", -3, "A", yun, pair, [fault(d(-3), "10:00", pair,
        "계획 정지 중 GR-01 입력측 베어링 교체. 탈거한 베어링 내륜에서 초기 박리 확인. 시운전 후 속도 96 m/min 복귀.",
        symptom="GR-01 입력측 베어링 열화(진동·온도 상승)",
        causes=[cause(GR01, "확인", "입력측 베어링 내륜 표면 피로 박리를 탈거 후 확인. RT-03 증상은 이 열화로 상류 이송 속도가 흔들린 결과.")],
        steps=[step(f"{d(-3)}T10:00", "라인 정지, GR-01 구동 차단기 OFF·잠금·꼬리표 부착", "무전압 확인 후 작업 시작", yun),
               step(f"{d(-3)}T11:40", "입력측 베어링 교체, 감속기 윤활유 교체", "탈거한 베어링 내륜에 초기 박리 확인", yun),
               step(f"{d(-3)}T13:30", "잠금 해제 후 시운전, 속도 80→96 m/min 복귀", "진동 1.7 mm/s, 베어링 온도 46 ℃, RT-03 전류 11.8 A", yun)],
        restart_performed=True, restart_type="maintenance_restart", outcome="resolved",
        normal_run_status="observing", normal_run_minutes=150,
        normal_run_evidence="13:30~16:00 속도 96 m/min 운전. 진동 1.6~1.8 mm/s, 온도 46~49 ℃",
        safety_notes="베어링 탈거 중 회전체 접근 금지. 구동 차단·잠금·무전압 확인 후에만 작업",
        safety_action="GR-01 구동 차단기 OFF, 잠금·꼬리표 부착, 무전압 확인", safety_basis="사내 정지·잠금(LOTO) 절차에 따름",
        remaining_issue="정상 운전 확인 시간이 짧다(150분). 다음 근무에서 장시간 운전 확인 필요",
        next_check="속도 96 m/min 유지 상태에서 GR-01 진동·온도, RT-03 전류 확인", next_check_at="B조 시작부터 매시간",
        followup_from={"handover_id": "HO-DEMO-A2", "record_index": 0},
        fault_sensors=[sensor(GR01, "gr_vib_rms", "mm_s", "베어링 교체 전 진동 상승", sample(3.5, f"{d(-4)}T06:00"), sample(1.7, f"{d(-3)}T13:30"))])],
        "교체 후 GR-01 진동 1.7 mm/s, 베어링 온도 46 ℃. RT-03 전류 11.8 A.", follows="HO-DEMO-A2")

    add("HO-DEMO-A4", -3, "B", han, pair, [fault(d(-3), "16:10", pair,
        "베어링 교체 후 정상 운전 확인. 속도 96 m/min 연속 운전 중 처짐·사행 재발 없음.",
        symptom="GR-01 베어링 교체 후 정상 운전 확인",
        causes=[cause(GR01, "확인", "입력측 베어링 박리가 원인. 교체 후 진동·온도가 정상 범위로 유지됨.")],
        steps=[step(f"{d(-3)}T16:10", "GR-01 진동·베어링 온도, RT-03 전류를 1시간 간격으로 확인",
                    "진동 1.6~1.9 mm/s, 온도 48~52 ℃, RT-03 전류 11~12 A로 정상 범위", han)],
        outcome="resolved", normal_run_status="no_recurrence", normal_run_minutes=600,
        normal_run_evidence="13:30~23:30 속도 96 m/min 연속 운전. 진동 1.6~1.9 mm/s, 온도 48~52 ℃, RT-03 전류 11~12 A, 처짐·사행 재발 없음",
        result="정상 운전 10시간 확인, 재발 없음",
        followup_from={"handover_id": "HO-DEMO-A3", "record_index": 0},
        fault_sensors=[sensor(RT03, "rt_motor_current", "A", "교체 후 전류 확인", sample(17.8, f"{d(-5)}T16:24"), sample(11.6, f"{d(-3)}T22:00"))])],
        "GR-01 진동 1.6~1.9 mm/s, 베어링 온도 48~52 ℃. RT-03 전류 11~12 A.", follows="HO-DEMO-A3")

    # ── 해결완료: HPU-01 필터 차압, CV-01 벨트 장력, CAU-01 정기 점검 ──────────────────────────────────
    add("HO-DEMO-B1", -4, "A", yun, [HPU], [fault(d(-4), "09:10", [HPU],
        "HPU-01 리턴 필터 차압이 1.35 bar로 상승(정상 0~1.2). 유압 압력은 148 bar로 유지.",
        symptom="HPU-01 필터 차압 상승",
        causes=[cause(HPU, "확인", "리턴 필터 엘리먼트 막힘. 교체한 엘리먼트에서 슬러지 확인.", "hpu_filter_dp", 1.35, "bar", f"{d(-4)}T09:10")],
        steps=[step(f"{d(-4)}T10:20", "펌프 정지·잔압 0 bar 확인 후 리턴 필터 엘리먼트 교체", "교체 후 차압 0.3 bar로 하락", yun),
               step(f"{d(-4)}T10:50", "펌프 재기동, 압력·유량 확인", "압력 152 bar, 유량 42 L/min 정상", yun)],
        restart_performed=True, restart_type="maintenance_restart", outcome="resolved",
        normal_run_status="no_recurrence", normal_run_minutes=180,
        normal_run_evidence="11:00~14:00 필터 차압 0.3~0.4 bar, 압력 150~153 bar 유지",
        safety_notes="필터 교체 전 펌프 정지와 잔압 0 bar 확인. 고온 유압유 접촉 주의",
        fault_sensors=[sensor(HPU, "hpu_filter_dp", "bar", "필터 차압이 정상 상한(1.2)을 넘음", sample(1.35, f"{d(-4)}T09:10"), sample(0.3, f"{d(-4)}T10:50"))])],
        "HPU-01 필터 차압 1.35 bar(정상 0~1.2), 압력 148 bar.")

    add("HO-DEMO-C1", -2, "A", oh, [CV01], [fault(d(-2), "09:30", [CV01],
        "CV-01 벨트 장력이 365 kPa로 저하(정상 380~460). 벨트 슬립음, 유휴 롤러 속도비 82 %.",
        symptom="CV-01 벨트 슬립음, 장력 저하",
        causes=[cause(CV01, "확인", "장력 조정 볼트 풀림.", "cv_belt_tension", 365, "kPa", f"{d(-2)}T09:30")],
        steps=[step(f"{d(-2)}T10:10", "정지·잠금 후 장력 조정 볼트 재조임, 장력 410 kPa로 재설정", "장력 410 kPa 확인", oh),
               step(f"{d(-2)}T10:40", "시운전 10분, 슬립음과 속도비 확인", "슬립음 없음, 속도비 97 %", oh)],
        restart_performed=True, restart_type="maintenance_restart", outcome="resolved",
        normal_run_status="no_recurrence", normal_run_minutes=240,
        normal_run_evidence="10:50~14:50 장력 405~412 kPa, 속도비 96~98 % 유지, 슬립음 없음",
        safety_notes="볼트 조임 전 컨베이어 정지·잠금. 벨트 회전부 접근 금지",
        fault_sensors=[sensor(CV01, "cv_belt_tension", "kPa", "장력이 정상 하한(380) 미만", sample(365, f"{d(-2)}T09:30"), sample(410, f"{d(-2)}T10:40"))])],
        "CV-01 벨트 장력 365 kPa(정상 380~460), 속도비 82 %.")

    add("HO-DEMO-D1", -1, "A", yun, [CAU], [pms(d(-1), "09:00", [CAU],
        "CAU-01 정기 점검: 흡입 필터 청소, 응축수 드레인 배출, 오일 레벨 확인. 이상 없음.",
        steps=[step(f"{d(-1)}T09:00", "압축기 정지 후 흡입 필터 청소, 드레인 배출, 오일 레벨 점검", "오염 경미, 오일 레벨 정상", yun),
               step(f"{d(-1)}T10:30", "재기동 후 토출 압력·온도 확인", "토출 압력 620 kPa, 온도 80 ℃ 정상", yun)],
        outcome="resolved", maintenance_status="completed", normal_run_status="no_recurrence", normal_run_minutes=120,
        normal_run_evidence="10:30~12:30 토출 압력 610~640 kPa, 토출 온도 78~82 ℃ 유지",
        maintenance_items="흡입 필터 청소, 응축수 드레인 배출, 오일 레벨 점검(정상)", parts_used="없음",
        next_maintenance="다음 정기 점검은 4주 뒤. 미완료 작업 없음")],
        "CAU-01 토출 압력 620 kPa, 토출 온도 80 ℃.", work_type="정비 작업")

    # ── 조치 필요: 임시 복구 · 미해결 · 실패 · 정비 일부 완료 ───────────────────────────────────────────
    add("HO-DEMO-E1", -1, "B", choi, [RT02], [fault(d(-1), "18:20", [RT02],
        "RT-02 클램프 압력이 91 bar로 저하(정상 95~115)되며 소재 이송이 간헐적으로 미끄러짐. 레귤레이터로 105 bar로 재설정해 임시 복구.",
        symptom="RT-02 클램프 압력 저하, 이송 미끄러짐",
        causes=[cause(RT02, "추정", "클램프 실린더 씰 마모로 내부 누설이 의심된다. 외부 누유는 없다.", "rt_clamp_press", 91, "bar", f"{d(-1)}T18:20")],
        steps=[step(f"{d(-1)}T18:40", "클램프 압력 레귤레이터를 105 bar로 재설정", "압력 104~106 bar, 미끄러짐 멈춤", choi),
               step(f"{d(-1)}T19:00", "클램프 실린더 외부 누유 육안 점검", "외부 누유 없음. 내부 누설 의심", choi)],
        outcome="temporary", normal_run_status="observing", normal_run_minutes=150,
        normal_run_evidence="19:00~21:30 클램프 압력 103~106 bar 유지, 미끄러짐 재발 없음",
        remaining_issue="클램프 압력을 수동으로 재설정한 상태. 실린더 씰 점검 필요",
        next_check="클램프 압력이 100 bar 이상 유지되는지 2시간 간격 확인", next_check_at="다음 근무(C조) 시작부터",
        fault_sensors=[sensor(RT02, "rt_clamp_press", "bar", "클램프 압력이 정상 하한(95) 미만", sample(91, f"{d(-1)}T18:20"), sample(105, f"{d(-1)}T18:40"))])],
        "RT-02 클램프 압력 91 bar(정상 95~115)에서 105 bar로 재설정.")

    add("HO-DEMO-F1", -1, "A", yun, [GR02], [fault(d(-1), "13:20", [GR02],
        "GR-02 감속기 오일 수분 함량이 380 ppm으로 상승(정상 0~300). 호흡기(브리더) 실리카겔 변색 확인.",
        symptom="GR-02 오일 수분 함량 상승",
        causes=[cause(GR02, "추정", "브리더 실리카겔이 포화되어 습기가 들어온 것으로 본다.", "gr_oil_water_content", 380, "ppm", f"{d(-1)}T13:20")],
        steps=[step(f"{d(-1)}T13:40", "오일 샘플 채취(상부·하부)", "약한 유백색 혼탁. 분석 의뢰", yun)],
        outcome="open", result="분석 결과 대기",
        remaining_issue="오일 수분 분석 결과 대기. 380 ppm이 유지되면 계획 정지 때 오일 교체",
        next_check="수분 함량을 4시간 간격으로 재측정하고 분석 결과 확인", next_check_at="B조 시작부터",
        fault_sensors=[sensor(GR02, "gr_oil_water_content", "ppm", "수분 함량이 정상 상한(300)을 넘음", sample(380, f"{d(-1)}T13:20"))])],
        "GR-02 오일 수분 380 ppm(정상 0~300).")

    add("HO-DEMO-G1", -1, "C", choi, [CV02], [fault(d(-1), "02:40", [CV02],
        "CV-02 대기율이 82 %로 상승(정상 0~70). 하류 적재가 늦어 소재가 쌓임. 속도를 올렸지만 개선되지 않음.",
        symptom="CV-02 대기율 상승, 소재 정체",
        causes=[cause(CV02, "추정", "CV-02 자체 이상보다 하류 적재 처리 지연으로 본다.", "cv_queue_len", 82, "pct", f"{d(-1)}T02:40")],
        steps=[step(f"{d(-1)}T03:00", "CV-02 속도를 10→12 m/min로 상향", "대기율 82→81 %로 거의 변화 없음", choi, failed=True),
               step(f"{d(-1)}T03:30", "CV-02 말단 적재 위치 이물 확인", "이물 없음", choi)],
        outcome="failed", result="속도 상향 효과 없음. 정체 지속",
        remaining_issue="속도 상향 후에도 대기율 81 %로 정체 지속. 적재 측 확인 필요",
        next_check="적재 담당에게 처리 지연 확인 요청, 대기율이 70 % 이하로 돌아오는지 확인", next_check_at="A조 시작 즉시",
        fault_sensors=[sensor(CV02, "cv_queue_len", "pct", "대기율이 정상 상한(70)을 넘음", sample(82, f"{d(-1)}T02:40"), sample(81, f"{d(-1)}T03:30"))])],
        "CV-02 대기율 82 %(정상 0~70).")

    add("HO-DEMO-H1", -1, "B", choi, [PDP], [fault(d(-1), "21:15", [PDP],
        "PDP-01 차단기 L2 극 온도가 49 ℃로 상승(정상 30~45). 부하 전류는 38 A로 정상 범위 안.",
        symptom="PDP-01 차단기 L2 극 온도 상승",
        causes=[cause(PDP, "추정", "단자 체결 풀림 또는 접촉 저항 증가가 의심된다.", "breaker_pole_l2_temp", 49, "degC", f"{d(-1)}T21:15")],
        steps=[step(f"{d(-1)}T21:20", "L1·L3 극 온도와 비교", "L1 41 ℃, L3 42 ℃로 L2만 높음", choi),
               step(f"{d(-1)}T21:30", "부하 전류 확인", "38 A(정상 20~40 A)로 상단", choi)],
        outcome="open", result="원인 미확인",
        safety_notes="활선 상태에서 단자·차단기 접촉 금지. 점검은 정지·잠금 후 전기 담당이 실시",
        remaining_issue="L2 극 온도 상승 원인 미확인. 전기 담당의 열화상 점검 필요",
        next_check="L2 극 온도를 1시간 간격으로 확인하고 계속 오르면 반장에게 즉시 보고", next_check_at="다음 근무(C조) 시작부터",
        fault_sensors=[sensor(PDP, "breaker_pole_l2_temp", "degC", "L2 극 온도가 정상 상한(45)을 넘음", sample(49, f"{d(-1)}T21:15"))])],
        "PDP-01 L2 극 온도 49 ℃, L1 41 ℃, L3 42 ℃. 부하 전류 38 A.")

    add("HO-DEMO-I1", -2, "B", yun, [RT01], [pms(d(-2), "17:00", [RT01],
        "RT-01 정기 정비: 상·하 베어링 그리스 보충은 마쳤고, 클램프 실린더 씰 교체는 씰 키트가 부족해 하지 못함.",
        steps=[step(f"{d(-2)}T17:00", "상·하 베어링 그리스 보충(각 2회)", "토출 확인, 이상음 없음", yun),
               step(f"{d(-2)}T18:30", "클램프 실린더 씰 교체", "씰 키트 1세트 부족으로 미실시", yun)],
        maintenance_status="partial", outcome="open",
        parts=[{"equipment_id": RT01, "name": "베어링 그리스", "part_number": "", "unit": "g", "usage": "상·하 베어링 보충", "quantity": 60}],
        maintenance_items="베어링 그리스 보충 완료, 클램프 실린더 씰 교체 미완료",
        parts_used="그리스 60 g",
        next_maintenance="클램프 실린더 씰 교체 미완료(씰 키트 입고 대기). 입고 후 다음 계획 정지에 교체. 그때까지 클램프 압력 95 bar 이상 확인")],
        "RT-01 베어링 그리스 보충 완료. 클램프 실린더 씰 교체 대기.", work_type="정비 작업")
    return rows


def payload(row: dict, today: date, config) -> dict:
    start_hhmm, hours = SHIFTS[row["shift"]]
    day = today + timedelta(days=row["day"])
    start = datetime.fromisoformat(f"{day.isoformat()}T{start_hhmm}")
    end = start + timedelta(hours=hours)
    code = {eq.equipment_id: eq.code for eq in config.equipment}
    names = ", ".join(code[i] for i in row["targets"])
    summary = "\n".join(f"기록 {i} · {r['type']} · {', '.join(code[e] for e in r['equipment'])} · {r['story']}"
                        for i, r in enumerate(row["records"], 1))
    targets = row["targets"]
    return {"kind": "work_log", "handover_id": row["id"], "memo_text": summary[:4000],
            "equipment_id": targets[0] if len(targets) == 1 else None, "equipment_ids": targets,
            "attempts": [], "observations": [],
            "work_report": {"form_version": 2, "work_type": row["work_type"], "remarks": "", "legacy_memo": "",
                            "records": row["records"], "mes_context": "[시연용 MES 값] " + row["mes"]},
            "required_context": {"author": row["author"], "start_at": start.strftime("%Y-%m-%dT%H:%M"),
                                 "end_at": end.strftime("%Y-%m-%dT%H:%M"), "recipient_role": "다음 근무자",
                                 "timing": f"{start:%Y-%m-%dT%H:%M} ~ {end:%Y-%m-%dT%H:%M}", "channel": "근무일지",
                                 "acknowledgement": "인계 사항에서 읽음 확인",
                                 "context": f"대상 장비: {names}\n[시연용 MES 값] {row['mes']}"},
            "_saved_at": (end - timedelta(minutes=10)).astimezone().isoformat()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=ROOT / "mes_data" / "mock-mes.sqlite3")
    parser.add_argument("--reset", action="store_true", help="기존 인계 기록을 모두 지우고 넣는다")
    parser.add_argument("--status", default="pending", choices=("pending", "uploaded"),
                        help="uploaded 로 넣으면 업로더가 중앙 DB로 올리지 않는다(Jetson 시연용)")
    args = parser.parse_args()

    config = configuration.from_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))
    known = {eq.equipment_id for eq in config.equipment}
    assets = {eq.equipment_id: eq.asset_id for eq in config.equipment}
    today = date.today()
    storage = MesStorage(args.db)
    connection = storage.connection
    existing = connection.execute("SELECT COUNT(*) FROM handover_outbox").fetchone()[0]
    if existing and not args.reset:
        sys.exit(f"인계 기록이 이미 {existing}건 있습니다. 지우고 다시 넣으려면 --reset 을 붙이세요.")
    if args.reset:
        with connection:
            for table in ("work_report_candidates", "work_report_sensor_evidence", "incident_records"):
                connection.execute(f"DELETE FROM {table}")
            connection.execute("DELETE FROM incident_queries")
            connection.execute("DELETE FROM incidents")
            connection.execute("DELETE FROM handover_outbox")
        print(f"기존 인계 기록 {existing}건을 지웠습니다.")

    incident_of: dict[str, str] = {}   # 일지 id → 그 일지 기록 0번의 사건 id
    for row in build(today):
        body = payload(row, today, config)
        saved_at = body.pop("_saved_at")
        if row["follows"]:
            body["work_report"]["records"][0]["incident_id"] = incident_of[row["follows"]]
        work_reports.validate(body, known, config)
        saved = storage.save_work_report(body, assets, config.config_id)
        links = saved["incidents"]
        if links:
            incident_of[row["id"]] = links[0]["incident_id"]
        with connection:
            connection.execute("UPDATE handover_outbox SET created_at = ?, status = ? WHERE handover_id = ?",
                               (saved_at, args.status, row["id"]))
            if not row["follows"]:
                connection.execute("UPDATE incidents SET created_at = ? WHERE incident_id IN "
                                   "(SELECT incident_id FROM incident_records WHERE handover_id = ?)", (saved_at, row["id"]))
        print(f"{row['id']}  {saved_at[:16]}  {row['author']}  {body['memo_text'].splitlines()[0][:50]}")
    storage.close()


if __name__ == "__main__":
    main()
