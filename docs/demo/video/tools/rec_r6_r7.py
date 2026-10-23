"""R6(해당 지식 없음) 직후 같은 화면에서 근무일지 작성 → 저장 전 확인 → 저장 → 토스트(후보 N건 검토 대기).
Jetson에 질의와 근무일지(지식 카드 후보)가 실제로 저장된다. --rehearse: 저장 전 확인 창까지만 가고 취소한다(저장 안 함).
REC_PASSWORD=... python -X utf8 rec_r6_r7.py [--rehearse]   (계정 M002, 비밀번호는 환경 변수로만)"""
import os
import sys
from datetime import date, datetime

os.environ.setdefault("REC_PDA", "http://127.0.0.1:8082")
from rec_lib import Rec  # noqa: E402
from rec_r5_r6 import Q2  # noqa: E402


def open_hpu(r, emp):
    """실제 계정으로 로그인하고 설비 목록에서 HPU-01을 고른다(Unity 스캔 없이)."""
    r.login(emp)
    r.tap("#toManual", 1500)
    r.pg.evaluate("""()=>{const b=[...document.querySelectorAll('button')].find(e=>e.innerText.trim()==='01'&&e.parentElement.parentElement.innerText.startsWith('HPU'));b.click()}""")
    r.wait(2500)


def ask(r, q):
    r.mark("질문 입력 시작")
    r.type("#question", q)
    r.wait(1200)
    r.mark("전송")
    r.tap("#doSearch", 300)
    r.pg.wait_for_function("document.body.innerText.includes('해당 지식 없음 —')||document.body.innerText.includes('답변 기준')", timeout=120_000)
    r.mark("답변 표시")

ACTION = "조장 무전으로 확인: 예비 필터는 A동 자재실 2번 선반에 보관. 그 필터로 HPU-01 필터 교체"
RESULT = "예비 필터 보관 위치는 A동 자재실 2번 선반. 교체 후 펌프 소음 정상, 점검창 거품 없음"
SYMPTOM = "펌프 소음 증가, 점검창 우유빛 거품"
STORY = "예비 필터 보관 위치를 몰라 질문했으나 해당 지식이 없어 조장에게 무전으로 확인함"
NOTE = "예비 필터 보관 위치가 시스템에 기록돼 있지 않아 질문에 답을 찾지 못했음."
EVIDENCE = "교체 후 30분간 펌프 소음 정상, 점검창 거품 없음"


def run(rehearse):
    with Rec("R6R7_session", video=not rehearse) as r:
        open_hpu(r, os.environ.get("REC_EMP", "M002"))
        r.pg.evaluate("localStorage.clear()")
        ask(r, Q2)
        r.wait(3000)
        r.mark("근무일지 작성 누름")
        r.tap("#chatReport", 3000)                     # 마지막 질문·답이 이상증상 기록으로 들어온다
        r.mark("입력 시작")
        # 기록 1: 마지막 질문·답이 들어온 이상증상 기록 — 발생 현상만 채운다
        r.type("textarea[data-key='symptom']", SYMPTOM)
        r.pg.locator(".record").nth(0).locator("input[type=date]").first.fill(date.today().isoformat())
        r.pg.locator(".record").nth(0).locator("input[type=time]").first.fill(datetime.now().strftime("%H:%M"))
        # 기록 2: 현장 조치 기록(조치 단계·결과) — 이 기록이 지식 카드 후보가 된다
        r.tap("#reportAdd", 1200)
        R = "[data-record='1']"
        r.pg.locator(f"select[data-key='type']{R}").first.select_option(label="고장 대응·수리")
        r.wait(900)
        r.pg.locator(".record").nth(1).locator("input[type=date]").first.fill(date.today().isoformat())
        r.pg.locator(".record").nth(1).locator("input[type=time]").first.fill(datetime.now().strftime("%H:%M"))
        r.type(f"textarea[data-key='story']{R}", STORY)
        r.type(f"textarea[data-key='note']{R}", NOTE)
        r.tap(f"button[data-action='step']{R}", 700)
        r.type(f"textarea[data-key='action'][data-step='0']{R}", ACTION)
        r.type(f"textarea[data-key='observed_result'][data-step='0']{R}", RESULT)
        r.pg.locator(f"select[data-key='outcome']{R}").first.select_option("resolved")
        r.wait(900)
        r.pg.locator(f"select[data-key='normal_run_status']{R}").first.select_option("no_recurrence")
        r.pg.locator(f"input[data-key='normal_run_minutes']{R}").first.fill("30")
        r.type(f"textarea[data-key='normal_run_evidence']{R}", EVIDENCE)
        r.wait(1200)
        print("  조치 결과 =", r.pg.locator("select[data-key='outcome'][data-record='1']").first.input_value())
        r.shot("r7_filled")
        r.mark("저장 누름")
        r.tap("#reportSave", 2500)
        r.mark("저장 전 확인")
        r.shot("r7_confirm")
        print(r.pg.locator("dialog[open]").first.inner_text()[:700].replace("\n", " | "))
        if rehearse:
            r.tap("dialog[open] button:has-text('취소')", 500)
            return
        r.wait(3500)
        r.mark("확인창 저장")
        r.tap("dialog[open] button:has-text('저장')", 1200)
        r.shot("r7_toast")
        r.mark("토스트")
        print(r.pg.inner_text("#toast")[:100])
        r.wait(3500)
        r.mark("끝")


if __name__ == "__main__":
    run("--rehearse" in sys.argv)
