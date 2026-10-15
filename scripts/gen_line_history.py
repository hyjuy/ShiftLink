"""PDA 대시보드 분석용 4주 사건 이력(합성)을 만든다.

    python scripts/gen_line_history.py  →  docs/data/analytics/line_history.json

사건 하나 = 경보 → 조치 시작 → 복구. 손실·재발·조치 효과·대응 시간은 저장하지 않고
shiftlink/mes/analytics.py 가 이 기록에서 계산한다. 심어 둔 이야기와 기대값은
docs/design/pda_ui/dashboard_analytics_20261014.md 와 tests/test_mes_analytics.py 에 있다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "data" / "analytics" / "line_history.json"
END = datetime.fromisoformat("2026-10-14T06:00:00+09:00")
START = END - timedelta(days=28)
ADOPTED = END - timedelta(days=14)

# (일차, 시각, 설비, 경보, 탐색 분, 조치 분, 조치, 원인, 결과, 카드)
#   탐색 = 경보 → 조치 시작, 조치 = 조치 시작 → 복구. 카드는 SHIFTLINK 도입(14일차) 뒤에만.
ROWS = [
    # A. GR-01 감속기 과열 — 냉각팬 청소(임시)로 닫혀 3일마다 재발, 도입 뒤 K-1025로 윤활유 교체 후 재발 없음
    (1, "14:20", "EQ-0004", "AL-GR-HOT", 28, 45, "냉각팬 청소", "냉각팬 먼지 막힘", "temporary", None),
    (4, "09:10", "EQ-0004", "AL-GR-HOT", 31, 40, "냉각팬 청소", "냉각팬 먼지 막힘", "temporary", None),
    (7, "22:40", "EQ-0004", "AL-GR-HOT", 35, 50, "냉각팬 청소", "냉각팬 먼지 막힘", "temporary", None),
    (10, "15:05", "EQ-0004", "AL-GR-HOT", 26, 42, "냉각팬 청소", "냉각팬 먼지 막힘", "temporary", None),
    (16, "10:30", "EQ-0004", "AL-GR-HOT", 9, 55, "윤활유 교체", "윤활유 열화", "resolved", "K-1025"),
    # B. HPU-01 유압유 과열 — 직접 정지는 짧지만 RT-01~03·CV-01 네 대를 세워 이번 주 손실 1위
    (5, "03:15", "EQ-0001", "AL-HYD-HOT", 24, 38, "냉각수 밸브 개도 조정", "냉각수 유량 부족", "temporary", None),
    (22, "13:40", "EQ-0001", "AL-HYD-HOT", 8, 35, "냉각수 밸브 개도 조정", "냉각수 유량 부족", "temporary", None),
    (24, "20:10", "EQ-0001", "AL-HYD-HOT", 6, 48, "오일 쿨러 튜브 스케일 세정", "쿨러 튜브 스케일", "resolved", "K-1002"),
    # C. CV-01 출측 코일 정체 — 매번 '해결'로 기록되지만 3~4일마다 재발(원인 칸이 증상만 적힘)
    (2, "11:00", "EQ-0009", "AL-DSB-QUE", 15, 12, "출측 코일 걸림 제거", "코일 걸림", "resolved", None),
    (6, "16:30", "EQ-0009", "AL-DSB-QUE", 20, 10, "출측 코일 걸림 제거", "코일 걸림", "resolved", None),
    (9, "08:45", "EQ-0009", "AL-DSB-QUE", 18, 14, "출측 코일 걸림 제거", "코일 걸림", "resolved", None),
    (12, "19:20", "EQ-0009", "AL-DSB-QUE", 22, 11, "출측 코일 걸림 제거", "코일 걸림", "resolved", None),
    (15, "07:40", "EQ-0009", "AL-DSB-QUE", 7, 14, "출측 코일 걸림 제거", "코일 걸림", "resolved", "K-1206"),
    (19, "18:15", "EQ-0009", "AL-DSB-QUE", 5, 12, "출측 코일 걸림 제거", "코일 걸림", "resolved", "K-1206"),
    (23, "10:50", "EQ-0009", "AL-DSB-QUE", 6, 15, "출측 코일 걸림 제거", "코일 걸림", "resolved", "K-1206"),
    (26, "15:30", "EQ-0009", "AL-DSB-QUE", 7, 13, "출측 코일 걸림 제거", "코일 걸림", "resolved", "K-1206"),
    # D. PDP-01 차단기 트립 — 재투입하면 멀쩡해 '해결'로 닫았지만 5일 간격으로 다시 트립(간헐 고장),
    #    도입 뒤 K-1317로 접속부 과열을 찾아 단자 재체결 → 재발 없음
    (3, "07:50", "EQ-0002", "AL-PDP-TRIP", 30, 25, "차단기 리셋", "과부하 트립", "resolved", None),
    (8, "14:05", "EQ-0002", "AL-PDP-TRIP", 26, 12, "차단기 재투입", "과부하 트립", "resolved", None),
    (13, "05:40", "EQ-0002", "AL-PDP-TRIP", 33, 10, "차단기 재투입", "과부하 트립", "resolved", None),
    (18, "09:15", "EQ-0002", "AL-PDP-TRIP", 8, 52, "접속부 열화상 점검·단자 재체결", "접속부 과열", "resolved", "K-1317"),
    # E. RT-02 롤러 소음·진동 — 그리스 주입(임시)으로 버티다 도입 뒤 K-1017로 롤러 베어링 교체
    (6, "11:30", "EQ-0007", "AL-DRV-VIB", 22, 18, "롤러 그리스 주입", "롤러 베어링 마모", "temporary", None),
    (9, "23:10", "EQ-0007", "AL-DRV-VIB", 25, 15, "롤러 그리스 주입", "롤러 베어링 마모", "temporary", None),
    (13, "16:20", "EQ-0007", "AL-DRV-VIB", 19, 20, "롤러 그리스 주입", "롤러 베어링 마모", "temporary", None),
    (23, "02:40", "EQ-0007", "AL-DRV-VIB", 6, 45, "롤러 베어링 교체", "롤러 베어링 마모", "resolved", "K-1017"),
    # 그 밖의 설비 — 모든 설비가 4주 안에 한 번 이상 나오게
    (11, "02:30", "EQ-0005", "AL-GR-LEAK", 25, 60, "오일실 교체", "오일실 마모", "resolved", None),
    (20, "11:20", "EQ-0005", "AL-DRV-VIB", 9, 38, "커플링 볼트 재체결", "장착 볼트 풀림", "resolved", "K-1030"),
    (27, "01:50", "EQ-0005", "AL-GR-LEAK", 8, 25, "브리더 청소", "브리더 막힘", "resolved", "K-1027"),
    (12, "13:10", "EQ-0003", "AL-AIR-LOW", 21, 28, "드레인 밸브 점검", "드레인 막힘", "resolved", None),
    (25, "09:30", "EQ-0003", "AL-AIR-LOW", 7, 32, "드레인 밸브 점검", "드레인 막힘", "resolved", None),
    (14, "20:30", "EQ-0006", "AL-SENSOR-ANOMALY", 12, 9, "속도 센서 커넥터 재체결", "커넥터 접촉 불량", "resolved", None),
    (24, "15:45", "EQ-0008", "AL-DRV-VIB", 5, 18, "롤러 사이 이물 제거", "이물 끼임", "resolved", "K-1208"),
    (17, "08:20", "EQ-0010", "AL-DSB-QUE", 10, 15, "스크랩 코일 정체 제거", "스크랩 걸림", "resolved", None),
]


def build() -> dict:
    incidents = []
    for n, (day, hm, eq, code, detect, repair, action, cause, result, card) in enumerate(sorted(ROWS), 1):
        h, m = map(int, hm.split(":"))
        alarm = START + timedelta(days=day, hours=h - START.hour, minutes=m)
        act = alarm + timedelta(minutes=detect)
        incidents.append({
            "incident_id": f"IN-{n:04d}", "equipment_id": eq, "alarm_code": code,
            "alarm_at": alarm.isoformat(), "action_at": act.isoformat(),
            "recovered_at": (act + timedelta(minutes=repair)).isoformat(),
            "action": action, "cause": cause, "result": result,
            "handover_id": f"HO-H{n:04d}", "card_id": card,
        })
    return {"_meta": {"start": START.isoformat(), "end": END.isoformat(), "adopted_at": ADOPTED.isoformat(),
                      "is_synthetic": True}, "incidents": incidents}


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(OUT)
