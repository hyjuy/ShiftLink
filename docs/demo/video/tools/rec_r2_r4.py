"""R2 인계 확인, R3 설비 스캔(Unity 가상 카메라→CNN), R4 MES 상태·안전 수칙 녹화.
준비: 녹화용 MES(:8011, hydraulic_fault), 노트북 PDA 서버(:8081), Unity 빌드 실행·작업자는 HPU-01 앞."""
import sys

from rec_lib import Rec


def smooth_scroll(r, dy, steps=40, ms=25):
    for _ in range(steps):
        r.pg.mouse.wheel(0, dy / steps)
        r.wait(ms)


def r2():
    with Rec("R2_handover") as r:
        r.login()
        r.wait(2500)                                     # 홈: 인계 사항 맨 위 HPU-01
        r.pg.mouse.move(640, 300)
        r.tap("button:has-text('HPU-01 필터 상태 점검')", 2000)
        smooth_scroll(r, 900, 60, 30)
        r.wait(1500)
        smooth_scroll(r, 900, 60, 30)
        r.wait(2500)


def r3_r4():
    with Rec("R3R4_scan_status") as r:
        r.login()
        r.wait(1200)
        r.tap("#toScan", 3500)                           # Unity 가상 카메라 영상
        r.tap("#scanShoot", 6000)                        # 분류 → HPU-01 확정 → 설비 화면
        r.pg.mouse.move(400, 470)
        r.wait(2500)                                     # R4: 범위 이탈 행
        r.tap("text=안전 수칙", 3500)                     # 상단 안전 바 펼침
        r.tap("text=안전 수칙", 1500)


if __name__ == "__main__":
    for name in sys.argv[1:] or ["r2", "r3_r4"]:
        globals()[name]()
        print("recorded", name)
