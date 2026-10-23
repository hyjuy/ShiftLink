"""R7 근무일지 작성 → 저장 전 확인 → 저장 → 토스트(후보 N건 검토 대기). 녹화용 로컬 MES(:8011)에 저장한다.
python -X utf8 rec_r7.py [--rehearse]  (--rehearse: 녹화 없이 흐름만 점검하고 마지막 화면을 shots/r7_*.png로 남김)"""
import sys
from datetime import date, datetime

from rec_lib import Rec

WORK = "예비 필터: A동 자재실 2번 선반. HPU-01 필터 교체 완료"
SYMPTOM = "펌프 소음 증가, 점검창 우유빛 거품"
RESULT = "교체 후 펌프 소음 정상, 점검창 거품 사라짐. 다음 교대는 필터 차압을 확인."


def run(rehearse):
    with Rec("R7_worklog", video=not rehearse) as r:
        r.login()
        r.tap("#toScan", 3000)
        r.tap("#scanShoot", 5000)
        r.tap("#chatReport", 2500)
        r.tap("#reportAdd", 1200)
        r.type("textarea[data-key='symptom']", SYMPTOM)
        r.type("textarea[data-key='story']", WORK)
        r.tap("button[data-action='result']", 800)
        r.type("textarea[data-key='result']", RESULT)
        r.tap(".record input[type=date]", 300)
        r.pg.locator(".record input[type=date]").first.fill(date.today().isoformat())
        r.pg.locator(".record input[type=time]").first.fill(datetime.now().strftime("%H:%M"))
        r.wait(800)
        r.shot("r7_filled")
        r.tap("#reportSave", 2500)
        r.shot("r7_confirm")
        r.wait(2500)
        r.tap("dialog[open] button:has-text('저장')", 1200)
        r.shot("r7_toast")
        r.wait(2500)
        print(r.pg.inner_text("body")[-900:].replace("\n", " | "))
        return r


if __name__ == "__main__":
    run("--rehearse" in sys.argv)
