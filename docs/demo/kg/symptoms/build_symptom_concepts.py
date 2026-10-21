"""KB 카드에서 symptom_concepts.json과 review.md를 만든다 (표준 라이브러리, 모델 호출 없음).

매핑 판단은 아래 손으로 작성한 표(CONCEPTS, LINKS, HOLD, SAFETY_NOTES)에 있다.
안전·null 카드의 보류 규칙은 KB 플래그에서 코드가 강제한다.
실행: python docs/demo/kg/symptoms/build_symptom_concepts.py
"""
import json
from pathlib import Path

import check_symptoms as chk

HERE = Path(__file__).resolve().parent

# (id 접미, label, definition)
CONCEPTS = [
    ("hpu-outlet-pressure-absent", "펌프 출구 압력 없음",
     "펌프가 운전 중인데 출구 압력계에 압력이 읽히지 않는 상태. 압력이 읽히지만 작업에 부족한 상태와 구별한다."),
    ("hpu-outlet-pressure-low-present", "펌프 출구 압력은 읽히나 작업 압력·유량 부족",
     "펌프 출구 압력은 읽히지만 작업에 필요한 압력 또는 유량이 부족한 상태. 압력이 전혀 읽히지 않는 상태와 구별한다."),
    ("hpu-cooler-outlet-oil-temp-over-limit", "냉각기 출구 유온 상한 초과",
     "냉각기 출구 포트의 오일 온도 측정값이 카드가 밝힌 프로젝트 설정 상한 58 degC를 초과하는 관측. 이 수치는 원문 제조사 임계값이 아니며 '냉각 성능 확인 필요'는 포함하지 않는다."),
    ("hpu-pump-noise-low-output-milky-foam", "펌프 소음 증가·유량 또는 압력 저하·탱크 우유빛 거품",
     "펌프 운전 중 정상 기록 대비 소음이 증가하고, 유량 38 L_min 미만 또는 압력 145 bar 미만이며 탱크 유면에 우유빛 거품이 함께 관찰되는 상태. 소음 증가는 정성 관측이다. 작동유 변색·젤라틴 덩어리와는 구별한다."),
    ("hpu-fluid-cream-color-gel-rust", "작동유 크림색 변색·젤라틴 덩어리·녹",
     "작동유 색이 투명에서 크림색(우유빛)으로 바뀌고, 탱크나 부품에 젤라틴 같은 덩어리가 보이거나 금속면에 녹이 생기는 외관 변화. 펌프 소음·유량 저하와 유면 거품이 함께 나타나는 상태와 구별하며, 수분 오염이라는 원인 판단은 포함하지 않는다."),
    ("cv-idler-roll-slow-or-stopped-squeal", "부착물 없는 아이들러 롤 회전 지연·정지와 끽끽 소리",
     "운전 중 부착물 없는 아이들러 롤의 회전수가 동일 조건 정상 기록의 80% 미만이거나 0 rpm이고, 정상 주행 때 없던 고음의 끽끽 소리가 관찰되는 상태. 80%는 프로젝트 기준이며 원문 임계값이 아니다."),
    ("cv-belt-section-drift-at-all-points", "벨트 특정 구간만 모든 지점에서 한쪽으로 이탈",
     "벨트의 같은 구간이 지나갈 때마다 컨베이어 모든 지점에서 한쪽으로 벗어나고 나머지 구간은 똑바로 도는 상태. 벨트 전체가 중앙을 벗어나 치우치는 상태와 구별한다."),
    ("cv-belt-cover-spot-stripe-swelling", "벨트 커버 점·줄무늬 부풂",
     "벨트 커버 표면이 군데군데 점이나 줄무늬 모양으로 부풀어 있는 외관 상태. 기름·그리스 오염은 원인 후보이며 정의에 포함하지 않는다."),
    ("gr-reducer-regular-abnormal-noise", "감속기 규칙적 이상음",
     "감속기에서 평소와 다른 규칙적인 운전음이 나는 상태. 불규칙한 운전음이나 장착부 주변의 소리와 구별한다."),
    ("common-signal-out-of-range-without-alarm", "알람 없이 계측값이 정상 범위 이탈",
     "알람은 표시되지 않았지만 순회 중 읽은 계측값이 정상 범위를 벗어난 관측. 알람 부재와 계측 신호 부재는 다르며, 정상 범위 경계는 실제 알람 설정값이 아니다."),
    ("hpu-filter-dp-above-1-2-bar", "HPU 필터 차압 1.2 bar 초과",
     "hpu_filter_dp 측정값이 1.2 bar를 초과하는 관측(MES 정상 범위 0–1.2 bar, 1.2 bar는 정상에 포함). 이 경계는 제조사 고장 기준이 아니며 막힘·교체 필요 판정은 포함하지 않는다."),
    ("cau-air-pressure-drop", "압축공기 계통 압력 저하",
     "압축공기 계통 압력이 떨어진 관측. 압력 상승, 공급량 부족, 누설음과 구별하며 누설은 원인 후보로서 정의에 포함하지 않는다."),
    ("pdp-bus-voltage-dip-at-motor-start", "대형 모터 기동·부하 피크 시점 버스 전압 순간 강하",
     "대형 모터 기동이나 부하 피크와 시각이 겹쳐 배전 버스 전압이 잠깐 떨어지는 상태. 기동·피크와 겹치지 않는 강하나 차단기 트립이 동반된 전압 저하와 구별한다."),
    ("cau-compressor-stop-during-load-run", "압축기 부하 운전 중 정지",
     "압축기가 부하 운전 중 정지하며 과열 정지, 과부하 트립, 토출 고온 경보가 동반될 수 있는 상태. 정전·복전 후 기동 불가와 구별한다."),
    ("cau-compressor-no-start-after-power-restore", "복전 후 압축기 기동 불가",
     "정전 뒤 전원이 복구되었는데 압축기가 기동하지 않는 상태. 재기동 확인 순서 자체와 자동 재기동 설정은 포함하지 않는다."),
    ("cau-compressor-discharge-temp-high", "압축기 토출 고온",
     "압축기 토출 온도가 높은 상태. 부하 운전 중 정지가 동반되는 상태와 구별하며, 지정 외 윤활유 사용은 원인 후보로서 포함하지 않는다."),
    ("cau-compressor-oil-consumption-increase", "압축기 윤활유 소비 증가",
     "압축기 윤활유 소비량이 늘어난 관측. 지정 외 윤활유 사용은 원인 후보로서 포함하지 않는다."),
    ("cau-compressor-oil-foaming", "압축기 윤활유 거품",
     "압축기 윤활유에 거품이 생긴 관측. 작동유 탱크의 우유빛 거품과는 설비·매체가 달라 구별한다."),
]

# 비안전·증상 문자열 카드 → (개념 접미 목록, 검수 메모)
LINKS = {
    "K-1001": (["hpu-outlet-pressure-absent"], "압력 '없음'. K-1203의 '읽히나 부족'과 병합하지 않음."),
    "K-1002": (["hpu-cooler-outlet-oil-temp-over-limit"], "원문 증상의 '냉각 성능 확인이 필요하다'는 확인 요구라서 증상 개념에 넣지 않음. 58 degC는 프로젝트 설정값."),
    "K-1004": (["hpu-pump-noise-low-output-milky-foam"], "소음·유량/압력 미달·거품이 한 증상으로 함께 서술되어 복합 개념으로 둠. K-1008과 병합하지 않음."),
    "K-1008": (["hpu-fluid-cream-color-gel-rust"], "작동유 외관 변화. 원문이 에어레이션 거품과 혼동 가능하다고 명시하여 K-1004와 분리."),
    "K-1011": (["cv-idler-roll-slow-or-stopped-squeal"], "회전수(정지/지연)와 소리가 함께 서술됨. 80%는 프로젝트 기준."),
    "K-1013": (["cv-belt-section-drift-at-all-points"], "특정 구간·모든 지점이라는 조건이 증상의 일부. 일반적 벨트 사행과 분리."),
    "K-1016": (["cv-belt-cover-spot-stripe-swelling"], "외관 증상만 연결. 기름·그리스 오염은 원인 후보."),
    "K-1026": (["gr-reducer-regular-abnormal-noise"], "원문 증상은 '규칙적인 운전음'. 갈리는/두드리는 구분은 know_how의 원인 후보 분기라 개념으로 나누지 않음."),
    "K-1105": (["common-signal-out-of-range-without-alarm"], "인계 카드지만 증상 문장에 '알람 없이 정상 범위 이탈'이 관측으로 서술됨. 인계 방법 자체는 증상이 아니므로 제외."),
    "K-1201": (["hpu-filter-dp-above-1-2-bar"], "관측 부분만 연결. '실제 막힘 표시 확인이 필요하다'는 확인 요구라 제외."),
    "K-1202": (["hpu-filter-dp-above-1-2-bar"], "K-1201과 같은 관측(1.2 bar 초과)으로 병합. '교체 필요 여부 확인'은 조치 판단이라 제외."),
    "K-1203": (["hpu-outlet-pressure-low-present"], "압력은 읽히고 압력 또는 유량이 부족. K-1001(압력 없음)과 병합하지 않음."),
    "K-1301": (["cau-air-pressure-drop"], "압력 저하만 연결. '공압 설비 출력 저하'는 결과 서술이며 별도 개념으로 만들지 않음(검수 시 필요 여부 확인)."),
    "K-1303": (["cau-air-pressure-drop"], "'누설 의심'은 원인 후보라 제외. 압력 저하 관측만 연결."),
    "K-1307": (["pdp-bus-voltage-dip-at-motor-start"], "기동·부하 피크와 시각이 겹친다는 조건을 정의에 포함. 차단기 트립 동반 전압 저하(K-1310)와 구별."),
    "K-1311": (["cau-compressor-stop-during-load-run"], "정지가 중심. 경보 종류(고온/과부하) 분기는 확인 순서라 개념으로 나누지 않음."),
    "K-1322": (["cau-compressor-no-start-after-power-restore"], "'복전 후 기동 불가'만 연결. '정전 후 재기동' 상황·확인 순서는 증상이 아니라 제외."),
    "K-1323": (["cau-compressor-discharge-temp-high", "cau-compressor-oil-consumption-increase", "cau-compressor-oil-foaming"],
               "증상 문장에서 '다른 회사·상표 오일 사용'은 원인 후보라 제외하고 관측 3건만 연결. K-1311의 '정지 동반 토출 고온 경보'와 병합하지 않음."),
}

# 비안전·문자열 카드 중 연결하지 않는 카드 → 보류 이유
HOLD = {
    "K-1101": "증상이 아니라 인계 상황(확인 완료 범위·정상 결과의 다음 조 인계)을 서술. 증상 개념으로 만들지 않음.",
    "K-1102": "조치 후 계측값 회복 부족을 다음 조에 넘기는 인계 기록 절차. 특정 설비 증상이 없음.",
    "K-1104": "감각 관측을 기록하는 방법에 관한 카드. 소리·외관은 예시이며 특정 증상 개념으로 확정할 수 없음.",
    "K-1106": "조치 절차가 없는 상태의 인계 방법. 증상이 특정되지 않음.",
    "K-1107": "공급받는 설비의 유지압·장력 저하가 언급되나 설비와 신호가 여러 종류이고 핵심은 공급원 상태 인계. 개념 단위 확정 불가로 보류.",
    "K-1108": "추정과 관측을 구분해 적는 방법. 증상이 아님.",
    "K-1109": "요청만 접수된 상태의 인계 방법. 증상이 아님.",
    "K-1111": "수치 없이 눈대중으로 본 관측을 인계하는 방법. 증상이 특정되지 않음.",
    "K-1324": "전원 투입 순서(절차)를 서술. 증상이 아님.",
    "K-1401": "정비 작업 완료 증거 대조와 인계 절차. 증상이 아님.",
}

# 안전 카드(증상 문자열 있음) 연결 후보 — review.md 전용. 접두 '후보:'는 새 개념 가능성, '기존:'은 위 개념과의 관계.
SAFETY_NOTES = {
    "K-1005": "후보 없음. 축압기 점검 필요성 서술이며 관측 증상이 아님.",
    "K-1010": "후보: 벨트가 아이들러 중앙을 벗어나 한쪽으로 치우쳐 돎(벨트 사행). K-1012와 병합 후보. K-1013(특정 구간만)과는 병합하지 않음.",
    "K-1012": "후보: 벨트 중앙 이탈·한쪽 쏠림. K-1010과 병합 후보(소형 직접구동형 교체 후라는 설비 조건 차이 확인).",
    "K-1015": "후보 없음. '오작동·고장 발생'은 너무 일반적이라 개념 단위가 없음.",
    "K-1017": "후보: 롤러 컨베이어 소음·끽끽·휘파람 소리(RT). K-1011(CV 아이들러, 회전수 조건 포함)과 설비·조건이 달라 병합하지 않음.",
    "K-1020": "후보: 상승 버튼을 누를 때 파워유닛 밸브의 날카로운 소리와 플랫폼 미상승. K-1022(웅웅거림·퓨즈)와 병합하지 않음.",
    "K-1021": "후보: 하강 버튼을 눌러도 리프트가 내려가지 않음. 속도 퓨즈 잠김은 원인 후보라 제외.",
    "K-1022": "후보: 상승 버튼에도 리프트가 오르지 않음 + 모터 웅웅거림 또는 퓨즈 끊김. K-1020과 병합하지 않음.",
    "K-1023": "후보: 버튼 조작 없이 올린 리프트가 서서히 내려앉음. K-1021(내려가지 않음)과 반대 방향이라 병합하지 않음.",
    "K-1025": "후보: 감속기 베어링부 온도가 62 degC 초과. K-1210과 병합 후보(프로젝트 관측 기준이며 제조사 임계값 아님).",
    "K-1027": "후보: 감속기 지점별 오일 누유(gr_oil_leak == 1). 누유 위치·양은 별도 확인이라 개념에 포함하지 않음.",
    "K-1028": "후보: 감속기 불규칙한 운전음. K-1026(규칙적)과 병합하지 않음. 오일 내 이물은 원인 후보.",
    "K-1030": "후보: 감속기 장착부 주변의 평소와 다른 소리. 감속기 내부 운전음(K-1026/K-1028)과 위치가 달라 병합하지 않음.",
    "K-1103": "후보 없음. 정지·재기동 방지 상태를 넘기는 인계 상황이며 증상이 아님.",
    "K-1110": "후보 없음. 차단·감압 기록 부재를 넘기는 인계 상황이며 증상이 아님.",
    "K-1204": "후보: 운전 지시 중 벨트 미끄럼·정지. 장력 380 kPa 미만은 카드 조건이며 개념 정의 시 포함 여부 확인.",
    "K-1205": "후보: 장력이 정상 범위(380–460 kPa)인데 이송 능력 저하. K-1204와 장력 조건이 달라 병합하지 않음.",
    "K-1206": "후보: 벨트 저속(10 m_min 미만)과 이송물 적체(대기열 70 pct 초과). K-1205와 병합하지 않음.",
    "K-1207": "후보: 반송 지시가 있는데 물품이 이동하지 않음(RT). 반송 속도 20 m_min 미만 조건은 카드 조건.",
    "K-1208": "후보: 반송 중 모터 전류가 16 A 초과(가상 정상 범위 8–16 A). 프로젝트 관측 기준.",
    "K-1209": "후보: 정상 운전 대비 감속기 진동 상승(RMS 2.8 mm_s 초과). 베어링 온도 동반 여부는 확인 분기.",
    "K-1210": "후보: 베어링 온도 62 degC 초과(gr_brg_temp). K-1025와 병합 후보.",
    "K-1211": "후보: 정비 후 압력 회복에도 펌프 소음·기포. K-1004와 유사하나 정비 후 재가동 조건이 달라 병합하지 않음. 증상 일부만 해당.",
    "K-1212": "후보 없음. 오일 교환 후 확인 항목 서술이며 증상이 아님.",
    "K-1213": "후보: 장력 정상인데 벨트 한쪽 쏠림(편주) 확인. 정비 후 시험운전 맥락. K-1010/K-1012와의 관계는 검수 때 결정.",
    "K-1214": "후보 없음. 정비 완료와 재가동 승인 구분 서술이며 증상이 아님.",
    "K-1215": "후보 없음. 비상정지 후 복귀 조건 서술이며 증상이 아님.",
    "K-1216": "후보 없음. 과열 정지 후 재가동 관측 서술이며 증상이 아님.",
    "K-1217": "후보 없음. 인터록 정지 후 복귀 조건 서술이며 증상이 아님.",
    "K-1218": "후보: 저온 기동 후 압력·유량 부족과 펌프 소음. 저온 기동 조건이 증상 해석에 필요하여 K-1004/K-1203과 병합하지 않음.",
    "K-1219": "후보 없음. 장기 정지 후 재가동 확인 서술이며 증상이 아님.",
    "K-1302": "후보: 압축공기 배관·이음부 누설음. K-1301의 압력 저하(관측 대상이 다름)와 병합하지 않음.",
    "K-1305": "후보: 압축공기 압력 상승 + 압축기 전류 상승. K-1301(저하)과 방향이 반대라 병합하지 않음.",
    "K-1306": "후보: 차단기 트립 후 재투입하니 정상 복귀, 원인 흔적 없음. K-1308/K-1317과 병합하지 않음(재투입 후 정상 복귀가 증상의 일부).",
    "K-1308": "후보: 배전반 차단기 트립 + 급전 설비 정지. K-1317(배선차단기 트립, 원인 미확인)과 병합 여부는 검수 때 결정.",
    "K-1309": "후보 없음. 트립 표시를 보고 충전부 작업 전 안전 조건 서술이며 증상이 아님.",
    "K-1310": "후보: 버스 전압 저하 + 차단기 트립 동시 발생. K-1307(기동·피크 시 순간 강하)과 병합하지 않음.",
    "K-1312": "후보: 압축공기 공급량 부족·압축기 토출량 저하. K-1301(압력 저하)과 병합하지 않음.",
    "K-1313": "후보 없음. 정기 정비 시점이며 증상이 아님.",
    "K-1315": "후보: 차단기 외함·접속 도체 변색, 열화상 상간 온도차, 핫스폿. K-1325(차단기 동작 없는 접속부 발열)와 병합 여부는 검수 때 결정.",
    "K-1316": "후보: 장기 미조작 차단기의 핸들 뻑뻑함과 첫 개폐 지연.",
    "K-1317": "후보: 배선차단기 트립, 원인 미확인. K-1308과 병합 여부는 검수 때 결정.",
    "K-1318": "후보 없음. 정기 시험 절차이며 증상이 아님.",
    "K-1319": "후보 없음. 점검 전 안전 조건 서술이며 증상이 아님.",
    "K-1325": "후보: 차단기 동작 없이 접속부·단자 발열, 단자 볼트 풀림. 볼트 풀림은 원인 후보 성격이라 개념에서 제외 여부 확인.",
}

SAFE_REASON = "safety_flag=true. 증상 연결 보류(안전 카드 검수 대상)."
NULL_REASON = "symptom=null. 제목·조치에서 증상을 만들지 않고 연결 보류."


def build(cards):
    by_id = {c["card_id"]: c for c in cards}
    sid = lambda s: "sym:" + s
    concepts = [{"id": sid(i), "label": l, "definition": d} for i, l, d in CONCEPTS]
    card_map, needs = {}, []
    for c in cards:
        k = c["card_id"]
        held = c["safety_flag"] or c["symptom"] is None
        if held:
            card_map[k] = []
            parts = ([SAFE_REASON] if c["safety_flag"] else []) + ([NULL_REASON] if c["symptom"] is None else [])
            if not c["safety_flag"]:
                parts.append("안전 카드 아님.")
            needs.append({"card_id": k, "reason": " ".join(parts)})
        elif k in LINKS:
            card_map[k] = [sid(s) for s in LINKS[k][0]]
            needs.append({"card_id": k, "reason": "비안전 후보 연결, 사람 검수 전. " + LINKS[k][1]})
        else:
            card_map[k] = []
            needs.append({"card_id": k, "reason": "연결 보류. " + HOLD[k]})
    assert set(LINKS) | set(HOLD) == {k for k, c in by_id.items() if not (c["safety_flag"] or c["symptom"] is None)}
    assert not set(LINKS) & set(HOLD)
    return {"concepts": concepts, "card_map": card_map, "needs_review": needs}


def review_md(cards, data):
    by_id = {c["card_id"]: c for c in cards}
    lab = {c["id"]: c["label"] for c in data["concepts"]}
    q = lambda c: "없음(null)" if c["symptom"] is None else c["symptom"].replace("\n", " ")
    L = ["# 증상 매핑 검수 문서 (kg-demo-v1)", "",
         "모든 연결은 **사람 검수 전 후보**이며 `status: accepted` 같은 원본 상태와 무관하다. 안전성이 확인되었다는 뜻이 아니다.", ""]
    n_safe = sum(c["safety_flag"] for c in cards)
    n_null = sum(c["symptom"] is None for c in cards)
    nlink = sum(1 for c in cards if data["card_map"][c["card_id"]])
    L += ["## 1. 집계", "",
          f"- 카드 {len(cards)}장 모두 card_map·needs_review에 1회씩 기록",
          f"- safety_flag=true {n_safe}장 → 연결 0 (후보는 4절에만)",
          f"- symptom=null {n_null}장 → 연결 0 (안전 11장 + 비안전 2장)",
          "- 두 집합의 합집합 58장 → 연결 0",
          f"- 나머지 28장 → 연결 후보 {nlink}장, 보류 {28 - nlink}장",
          f"- 증상 개념 {len(data['concepts'])}개 (모두 연결된 카드가 있는 개념만)", ""]
    L += ["## 2. 증상 개념과 연결 카드", ""]
    for c in data["concepts"]:
        cs = [k for k, v in data["card_map"].items() if c["id"] in v]
        L += [f"- `{c['id']}` {c['label']} — {', '.join(cs)}", f"  - {c['definition']}"]
    L += ["", "## 3. 비안전·증상 있는 28장", ""]
    for c in cards:
        k = c["card_id"]
        if c["safety_flag"] or c["symptom"] is None:
            continue
        refs = data["card_map"][k]
        L += [f"### {k} {c['equipment']}/{c['component']}", f"- 원문 증상: {q(c)}"]
        if refs:
            L += [f"- 후보: {', '.join(f'`{r}`' for r in refs)}", f"- 메모: {LINKS[k][1]}"]
        else:
            L += ["- 보류", f"- 사유: {HOLD[k]}"]
        L += [""]
    L += ["## 4. 안전 카드 56장 (연결 보류, 후보는 이 절에만)", "",
          "자동 그래프에 이 카드들의 `DESCRIBES_SYMPTOM`은 만들지 않는다. 아래 후보는 사람 검수에서 채택해도 안전 카드 보류 규칙이 먼저 해제되어야 한다.", ""]
    for c in cards:
        k = c["card_id"]
        if not c["safety_flag"]:
            continue
        note = "후보 없음. symptom=null이라 증상을 만들지 않음." if c["symptom"] is None else SAFETY_NOTES[k]
        L += [f"- **{k}** {c['equipment']}/{c['component']}", f"  - 원문 증상: {q(c)}", f"  - {note}"]
    L += ["", "## 5. 비안전·symptom=null 2장", ""]
    for c in cards:
        if not c["safety_flag"] and c["symptom"] is None:
            L += [f"- **{c['card_id']}** {c['equipment']}/{c['component']}: {c['title']} — 증상을 만들지 않고 보류."]
    L += ["", "## 6. 병합·비병합 판단", "",
          "- 병합: K-1201+K-1202(같은 관측 1.2 bar 초과), K-1301+K-1303(압력 저하, '누설 의심'은 제외).",
          "- 비병합: K-1001(압력 없음) / K-1203(읽히나 부족) — 없음/낮음 구별.",
          "- 비병합: K-1004(펌프 소음·유량/압력 저하·유면 거품) / K-1008(작동유 외관 변화) — 원문이 거품과 변색을 혼동하지 말라고 함.",
          "- 비병합: K-1311(부하 운전 중 정지) / K-1322(복전 후 기동 불가) / K-1323(토출 고온·소비 증가·거품) — 운전·재가동, 정지 동반 여부 구별.",
          "- 비병합: K-1011(CV 아이들러, 회전 지연·정지) / 안전 카드 K-1017(RT 롤러 소음) — 설비와 회전수 조건 차이.",
          "- 비병합: K-1026(규칙적) / K-1028(불규칙) / K-1030(장착부 주변) — 소리 성질과 위치 차이.",
          "- 비병합: K-1301(압력 저하) / K-1305(압력 상승) / K-1312(공급량 부족) / K-1302(누설음).",
          "- 비병합: K-1307(기동·피크 시 순간 강하) / K-1310(전압 저하+차단기 트립).",
          "- 병합 후보(안전 카드라 보류): K-1010+K-1012, K-1025+K-1210.", ""]
    L += ["## 7. 사람이 확인할 사항", "",
          "1. 18개 개념의 정의 단위(복합 개념 K-1004, K-1011, K-1323 포함)가 현장 표현과 맞는지.",
          "2. K-1301의 '공압 설비 출력 저하'를 별도 증상 개념으로 둘지.",
          "3. K-1201/K-1202 병합, K-1301/K-1303 병합의 적절성.",
          "4. 보류 10장(인계·절차 카드) 중 K-1105처럼 증상 문장이 있는 카드를 더 연결할지, K-1107의 보류 유지 여부.",
          "5. 안전 카드 45장의 후보를 안전 검수 뒤에 연결할지(자동 연결 금지).",
          "6. 프로젝트 설정 임계값(58 degC, 80%, 1.2 bar 등)이 개념 정의에 들어간 것이 적절한지. 정의 문장은 제조사 기준이 아님.", ""]
    return "\n".join(L)


def _selfcheck(cards, data):
    assert chk.validate(cards, data) == []
    assert all(v == [] for k, v in data["card_map"].items() if next(c for c in cards if c["card_id"] == k)["safety_flag"])
    assert len(data["needs_review"]) == len(cards) == 86


def main():
    cards = json.loads(chk.KB.read_text(encoding="utf-8"))["cards"]
    data = build(cards)
    _selfcheck(cards, data)
    (HERE / "symptom_concepts.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (HERE / "review.md").write_text(review_md(cards, data), encoding="utf-8", newline="\n")
    print("written")


if __name__ == "__main__":
    main()
