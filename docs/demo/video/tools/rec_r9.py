"""R9 새 카드 인용: R8에서 승인된 카드가 검색에 반영된 뒤, 다른 계정으로 같은 질문을 하면 새 카드를 근거로 답하는지 녹화한다.
Jetson에 질의가 실제로 기록된다. 계정 비밀번호는 환경 변수로만 받는다:
  REC_PASSWORD=... python -X utf8 rec_r9.py [사번]   (기본 M002)
준비: 노트북 PDA 서버 :8082 (--jetson Jetson). 설비는 목록에서 직접 고른다(Unity 스캔 불필요)."""
import os
import sys
import time

os.environ.setdefault("REC_PDA", "http://127.0.0.1:8082")
from rec_lib import Rec  # noqa: E402

Q2 = "예비 필터는 어디에 보관돼 있어?"


def run(emp):
    with Rec("R9_new_card") as r:
        r.login(emp)
        r.mark("로그인 완료")
        r.wait(1500)
        r.tap("#toManual", 1500)
        r.pg.evaluate("""()=>{const b=[...document.querySelectorAll('button')].find(e=>e.innerText.trim()==='01'&&e.parentElement.parentElement.innerText.startsWith('HPU'));b.click()}""")
        r.wait(2500)
        r.mark("HPU-01 선택")
        r.type("#question", Q2)
        r.wait(1000)
        r.mark("전송")
        r.tap("#doSearch", 300)
        t = time.time()
        r.pg.wait_for_function("document.body.innerText.includes('답변 기준')||document.body.innerText.includes('해당 지식 없음 —')", timeout=120_000)
        print(f"  응답 {time.time() - t:.1f}초", flush=True)
        r.mark("답변 표시")
        r.wait(6000)
        r.shot("r9_answer")
        txt = r.pg.inner_text("body")
        print("  본문:", txt[txt.find("현재 MES"):][:400].replace("\n", " | "))
        if r.pg.locator("text=참고 매뉴얼 보기").count():
            r.mark("참고 열기")
            r.tap("text=참고 매뉴얼 보기", 6000)
            r.shot("r9_ref")
        r.mark("끝")
        r.wait(1500)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "M002")
