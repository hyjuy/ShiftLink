"""R8 관리자 승인: Jetson MES /knowledge-candidates.html 에서 R7 후보를 검토 승인 → 검수 통과 → 검색 반영까지 녹화한다.
Jetson의 지식 검색에 실제로 반영된다. 관리자 계정은 환경 변수로만 받는다(파일에 남기지 않음):
  REC_ADMIN_ID=... REC_ADMIN_PW=... python -X utf8 rec_r8.py [--rehearse]
--rehearse: 로그인하고 후보 상세까지만 보고 끝낸다(승인하지 않음)."""
import os
import sys
import time

from rec_lib import Rec

JETSON = os.environ.get("REC_JETSON", "http://jetson-06.tail0a6af3.ts.net:8000")
CARD_HINT = "예비 필터 보관 위치를 몰라 질문"          # R7 후보 제목의 일부
REASON1 = "원인·조치·정상 운전 확인(30분)을 검토함. 적용 조건과 안전 조건에 문제 없음."
REASON2 = "원문과 안전 조건을 확인했고 검수 통과 처리함."


def smooth_scroll(r, selector, dy, steps=30, ms=40):
    for _ in range(steps):
        r.pg.evaluate("([s,d])=>{const e=document.querySelector(s);(e||document.scrollingElement).scrollBy(0,d)}",
                      [selector, dy / steps])
        r.wait(ms)


def run(rehearse):
    with Rec("R8_admin_approve", video=not rehearse) as r:
        pg = r.pg
        pg.goto(JETSON + "/knowledge-candidates.html")
        pg.wait_for_selector("#review-admin-id")
        r.wait(1200)
        r.mark("로그인")
        pg.fill("#review-admin-id", os.environ["REC_ADMIN_ID"])
        pg.fill("#review-admin-password", os.environ["REC_ADMIN_PW"])
        r.wait(600)
        r.tap("#review-login-form button[type=submit]", 3000)
        pg.wait_for_selector("#review-workspace:not([hidden])", timeout=20000)
        r.mark("후보 목록")
        r.wait(1500)
        r.tap(f".candidate-list :text('{CARD_HINT}')", 2500)
        r.shot("r8_detail")
        if rehearse:
            print(pg.inner_text("#candidate-detail")[:600].replace("\n", " | "))
            return
        r.mark("후보 상세 훑기")
        smooth_scroll(r, "#candidate-detail", 700)
        r.wait(1500)
        smooth_scroll(r, "#candidate-detail", 700)
        r.wait(1500)
        r.mark("검토 승인")
        r.type("#review-reason", REASON1)
        r.wait(800)
        r.tap("button[data-action='approve']", 3000)
        r.shot("r8_approved")
        r.mark("검수 통과")
        r.pg.fill("#review-reason", "")
        r.type("#review-reason", REASON2)
        r.wait(800)
        r.tap("button[data-action='quality_pass']", 2500)
        r.shot("r8_quality")
        r.mark("임베딩 대기")
        t = time.time()
        while time.time() - t < 240:
            st = pg.inner_text("#publication-state") if pg.locator("#publication-state").count() else ""
            if "검색 반영 완료" in st or "실패" in st:
                break
            r.wait(3000)
            pg.locator("#review-refresh").click() if pg.locator("#review-refresh").is_enabled() else None
        r.mark("상태: " + (pg.inner_text("#publication-state") if pg.locator("#publication-state").count() else "?"))
        r.shot("r8_published")
        r.wait(3000)


if __name__ == "__main__":
    run("--rehearse" in sys.argv)
