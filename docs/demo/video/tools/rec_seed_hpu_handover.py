"""R2용: 전 교대가 남긴 'HPU-01 필터 상태 점검 · 미해결' 인계 1건을 녹화용 로컬 MES에 저장한다.
python -X utf8 rec_seed_hpu_handover.py http://127.0.0.1:8011   (이미 있으면 건너뜀)"""
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import seed_demo_handovers as sd  # noqa: E402
from shiftlink.mes import configuration  # noqa: E402

base = sys.argv[1].rstrip("/")
config = configuration.from_catalog(json.loads(sd.CATALOG.read_text(encoding="utf-8")))
today = date.today()
d = today.isoformat()
HID = "HO-VIDEO-R2"
rec = sd.fault(d, "06:40", [sd.HPU],
               "HPU-01 유압 저하 확인. 펌프 소음이 평소보다 크고 탱크 점검창에 거품이 보인다.",
               symptom="HPU-01 유압 저하, 펌프 소음 증가",
               causes=[sd.cause(sd.HPU, "추정", "리턴 필터 상태가 의심된다. 확인하지 못했다.")],
               steps=[sd.step(f"{d}T06:50", "필터 상태 점검", "육안 점검만 했고 교체 여부는 판단하지 못함", "전혜민")],
               outcome="open", result="필터 상태 미확인",
               remaining_issue="HPU-01 필터 상태 점검 미해결",
               next_check="다음 교대에서 필터 재확인", next_check_at="다음 근무 시작 즉시",
               fault_sensors=[sd.sensor(sd.HPU, "hpu_pressure", "bar", "공급 압력이 정상 하한 미만",
                                        sd.sample(120, f"{d}T06:45"))])
row = dict(id=HID, day=0, shift="C", author="전혜민", targets=[sd.HPU], records=[rec],
           mes="HPU-01 유압 공급 압력 120 bar(정상 145~165).", follows=None, work_type="고장·이상 대응")
body = sd.payload(row, today, config)
body.pop("_saved_at")
sd.work_reports.validate(body, {e.equipment_id for e in config.equipment}, config)
got = json.load(urllib.request.urlopen(base + "/api/work-reports"))["reports"]
if any(r.get("handover_id") == HID for r in got):
    sys.exit("already exists")
req = urllib.request.Request(base + "/api/handover", json.dumps(body).encode(), {"Content-Type": "application/json"})
print(urllib.request.urlopen(req).read()[:300])
