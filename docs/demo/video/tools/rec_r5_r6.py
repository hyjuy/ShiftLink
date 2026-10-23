"""R5 질문1(근거 있는 답) · R6 질문2(해당 지식 없음) 녹화. Jetson에 실제로 질의한다(질의 기록이 남는다).
준비: Jetson MES가 hydraulic_fault 상태, 노트북 PDA 서버 :8082(--jetson Jetson --unity :8090 --cnn), Unity 작업자는 HPU-01 앞(F로 작업자 모드).
python -X utf8 rec_r5_r6.py [r5|r6]"""
import os
import sys
import time

os.environ.setdefault("REC_PDA", "http://127.0.0.1:8082")
os.environ.setdefault("REC_STUB_LOGIN", "1")
from rec_lib import Rec  # noqa: E402

Q1 = "펌프 소리가 평소보다 커졌고 탱크 점검창에 우유빛 거품이 보여. 뭐부터 봐야 해?"
Q2 = "예비 필터는 어디에 보관돼 있어?"


def open_chat(r):
    r.login()
    r.tap("#toScan", 3000)
    r.tap("#scanShoot", 6000)
    r.pg.mouse.move(900, 400)


def ask(r, q, done_selector):
    r.mark("질문 입력 시작")
    r.type("#question", q)
    r.wait(1200)
    r.mark("전송")
    r.tap("#doSearch", 300)
    t = time.time()
    r.pg.wait_for_selector(done_selector, timeout=120_000)
    print(f"  응답 {time.time() - t:.1f}초", flush=True)
    r.mark("답변 표시")


def r5():
    with Rec("R5_ask_answer") as r:
        open_chat(r)
        r.mark("상태 화면")
        r.wait(1500)
        ask(r, Q1, "text=참고 매뉴얼 보기")
        r.wait(9000)                                   # 답변 읽는 시간
        r.shot("r5_answer")
        r.mark("참고 매뉴얼 열기")
        r.tap("text=참고 매뉴얼 보기", 6500)
        r.shot("r5_ref")
        r.mark("안전 바 열기")
        r.tap("text=/HPU-01 · 안전 수칙/", 5500)
        r.shot("r5_safety")
        r.tap("text=/HPU-01 · 안전 수칙/", 1000)
        r.mark("관련 지식 연결 열기")
        r.tap("text=관련 지식 연결", 6000)
        r.shot("r5_related")
        r.mark("끝")
        r.wait(1500)


def r6():
    with Rec("R6_no_knowledge") as r:
        open_chat(r)
        r.mark("상태 화면")
        r.wait(1000)
        ask(r, Q2, "text=해당 지식 없음")
        r.wait(5000)
        r.shot("r6_noknow")
        r.mark("끝")


if __name__ == "__main__":
    for n in sys.argv[1:] or ["r5", "r6"]:
        globals()[n]()
        print("recorded", n)
