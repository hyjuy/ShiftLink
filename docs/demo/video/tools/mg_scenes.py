"""시연 영상 MG 컷. 사용: python mg_scenes.py [컷이름 ...]  (없으면 전부)  /  python mg_scenes.py --still 컷이름 초
수치는 스토리보드 문서의 실측값만 쓴다. 출력은 output/video/mg/<이름>.mp4"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image

from mglib import (AMBER, BG, GREY, GREY_L, INK, TEAL, TEAL_L, W, H, Canvas, clamp, fade, icon, mix, ramp, render)

OUT = Path(__file__).resolve().parents[4] / "output" / "video" / "mg"
CX, CY, R, NR = 960, 565, 300, 78
STEPS = [("로그인", "face"), ("설비 선택", "machine"), ("상태 확인", "gauge"),
         ("질문", "chat"), ("기록", "clipboard"), ("지식 승인", "card")]


def ang(i):
    return -90 + 60 * i


def ring_pt(deg, r=R):
    a = math.radians(deg)
    return (CX + r * math.cos(a), CY + r * math.sin(a))


def draw_arrow_seg(c, i, color, w=5, a=1.0):
    a0, a1 = ang(i) + 19, ang(i + 1) - 19
    col = fade(color, a)
    c.arc((CX, CY), R, a0, a1, w, col)
    tip = ring_pt(a1)
    c.arrowhead(tip, a1 + 90, 20, col)


def draw_node(c, i, a=1.0, filled=False, hot=False):
    x, y = ring_pt(ang(i))
    col = fade(TEAL, a)
    c.circle((x, y), NR, fill=fade(TEAL_L, a * 0.9) if filled else BG, outline=col, w=5)
    icon(c, STEPS[i][1], x, y, 42, col, 5)
    d = ang(i) % 360
    ox, oy = {270: (0, -(NR + 48)), 330: (NR + 20, 0), 30: (NR + 20, 0), 90: (0, NR + 48), 150: (-(NR + 20), 0), 210: (-(NR + 20), 0)}[d]
    lx, ly = x + ox, y + oy
    label = STEPS[i][0]
    from mglib import font
    f = font(38, True)
    wnum = f.getlength(f"{i + 1}  ") / 2
    wlab = f.getlength(label) / 2
    left = {270: -(wnum + wlab) / 2, 90: -(wnum + wlab) / 2, 330: 0, 30: 0, 150: -(wnum + wlab), 210: -(wnum + wlab)}[d]
    c.text((lx + left, ly), f"{i + 1}  ", 38, fade(TEAL, a), anchor="lm", bold=True)
    c.text((lx + left + wnum, ly), label, 38, fade(INK, a), anchor="lm", bold=True)


def kicker(c, s):
    c.text((90, 70), s, 30, GREY, anchor="lm")


def loop_scene(t, mode):
    c = Canvas()
    kicker(c, "ShiftLink · 한 번의 근무")
    show = [ramp(t, 0.3 + 0.45 * i, 0.9 + 0.45 * i) if mode == "intro" else 1.0 for i in range(6)]
    for i in range(6):
        if mode == "close" and i == 5:
            continue
        if show[i] > 0 and show[(i + 1) % 6] > 0.05 or mode != "intro":
            draw_arrow_seg(c, i, TEAL, 4 if mode != "final" else 6, ramp(t, 0.6 + 0.45 * i, 1.1 + 0.45 * i) if mode == "intro" else 1.0)
    if mode == "close":   # 마지막 화살표: 회색 → 청록
        p = ramp(t, 1.0, 2.6)
        draw_arrow_seg(c, 5, mix(GREY_L, TEAL, p), 4 + 3 * p)
    for i in range(6):
        draw_node(c, i, show[i], filled=(mode == "final" and t > 1.8))
    # 가운데 문구
    if mode == "intro":
        c.text((CX, CY - 24), "한 번의 근무", 46, fade(INK, ramp(t, 0.2, 0.8)), bold=True)
        c.text((CX, CY + 36), "여섯 단계, 하나의 고리", 34, fade(GREY, ramp(t, 0.4, 1.0)))
    elif mode == "close":
        a = ramp(t, 3.0, 3.8)
        c.text((CX, CY - 24), "오늘의 기록은", 44, fade(INK, a), bold=True)
        c.text((CX, CY + 36), "내일의 지식", 44, fade(TEAL, a), bold=True)
    # 점
    if mode == "intro" and t > 3.3:
        p = clamp((t - 3.3) / 2.5)
        x, y = ring_pt(ang(0) + 360 * p)
        c.circle((x, y), 15, fill=TEAL)
    if mode == "close":
        p = ramp(t, 1.0, 2.6)
        if 1.0 <= t <= 2.7:
            x, y = ring_pt(ang(5) + 60 * p)
            c.circle((x, y), 15, fill=TEAL)
        if 2.7 < t < 4.2:      # 닫힘 펄스
            q = (t - 2.7) / 1.5
            c.circle((CX, CY), R + 40 + 160 * q, outline=fade(TEAL, 1 - q), w=6)
    if mode == "final":
        p = clamp(t / 1.8)
        if t <= 1.8:
            x, y = ring_pt(ang(0) + 360 * p)
            c.circle((x, y), 15, fill=TEAL)
        if t > 1.8:
            q = clamp((t - 1.8) / 1.0)
            c.circle((CX, CY), R + 40 + 120 * q, outline=fade(TEAL, 1 - q), w=6)
    img = c.out()
    if mode == "close" and t > 5.4:   # 공장 장면으로 디졸브: 흰색으로
        img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), ramp(t, 5.4, 7.0))
    return img


def s2_1(t): return loop_scene(t, "intro")
def s2_4(t): return loop_scene(t, "close")
def s5_7(t): return loop_scene(t, "final")


def box(c, cx, cy, w, h, title, sub, ic, a, dashed=False):
    col = fade(TEAL if not dashed else GREY, a)
    c.rrect((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 22, fill=fade((255, 255, 255), a), outline=col, w=4)
    icon(c, ic, cx, cy - h * 0.2, 40, col, 5)
    c.text((cx, cy + h * 0.14), title, 34, fade(INK, a), bold=True)
    c.text((cx, cy + h * 0.33), sub, 26, fade(GREY, a))


def s2_2(t):
    c = Canvas()
    kicker(c, "현장 구성")
    ua, pa, ja, ca = ramp(t, 0.2, 0.8), ramp(t, 0.8, 1.4), ramp(t, 1.4, 2.0), ramp(t, 3.0, 3.6)
    U, P, J, CL = (330, 760), (860, 560), (1400, 560), (1560, 230)
    box(c, *U, 380, 220, "Unity PC", "시연용 가상 공장", "monitor", ua)
    box(c, *P, 380, 240, "Raspberry Pi · PDA", "얼굴 로그인 · 설비 인식", "pda", pa)
    box(c, *J, 380, 240, "Jetson Orin Nano", "MES · 지식 · AI 모델", "chip", ja)
    box(c, *CL, 360, 190, "클라우드 DB", "기록 보관에만 사용", "cloud", ca, dashed=True)
    if pa > 0.3:   # Unity → PDA : 점선
        c.dashed((U[0] + 190, U[1] - 60), (P[0] - 190, P[1] + 60), 4, fade(TEAL, ramp(t, 1.0, 1.6)))
        c.text((650, 745), "가상 카메라 영상", 24, fade(GREY, ramp(t, 1.2, 1.8)), anchor="mm")
    if ja > 0.3:   # PDA ↔ Jetson
        a = ramp(t, 1.6, 2.2)
        c.line((P[0] + 190, P[1]), (J[0] - 190, J[1]), 5, fade(TEAL, a))
        c.text((1130, 520), "질의 · 상태", 24, fade(GREY, a))
        if t > 2.3:
            q = ((t - 2.3) * 0.7) % 1
            x = (P[0] + 190) + q * (J[0] - P[0] - 380)
            c.circle((x, P[1]), 12, fill=TEAL)
    if ca > 0.3:
        c.dashed((J[0] + 60, J[1] - 120), (CL[0] - 40, CL[1] + 95), 4, fade(GREY, ca))
    c.text((CX, 960), "현장에는 PDA와 Jetson 두 대뿐입니다", 40, fade(INK, ramp(t, 3.8, 4.6)), bold=True)
    return c.out()


def s2_3(t):
    c = Canvas()
    kicker(c, "Jetson 안")
    c.rrect((470, 150, 1450, 900), 30, fill=(255, 255, 255), outline=TEAL, w=5)
    c.text((CX, 215), "Jetson Orin Nano 8GB", 40, INK, bold=True)
    rows = [("MES 설비 데이터", "실시간 센서 · 경보 · 상태", "gauge"),
            ("지식", "매뉴얼 58권 · 노하우 카드 · 인계 기록", "card"),
            ("작은 AI 모델", "판정 모델 · 답변 모델", "chip")]
    for i, (a_, b_, ic) in enumerate(rows):
        a = ramp(t, 0.5 + 1.0 * i, 1.2 + 1.0 * i)
        y = 360 + 170 * i
        c.rrect((540, y - 70, 1380, y + 70), 18, fill=fade(TEAL_L, a * 0.55), outline=fade(TEAL, a), w=3)
        icon(c, ic, 640, y, 34, fade(TEAL, a), 4)
        c.text((730, y - 18), a_, 36, fade(INK, a), anchor="lm", bold=True)
        c.text((730, y + 24), b_, 26, fade(GREY, a), anchor="lm")
    a = ramp(t, 3.8, 4.6)
    c.rrect((620, 800, 1300, 862), 31, fill=fade(TEAL, a), outline=None)
    c.text((CX, 831), "8GB · 외부 서버 없음", 32, fade((255, 255, 255), a), bold=True)
    return c.out()


def s3_12(t):
    c = Canvas()
    a = ramp(t, 0.3, 1.0) * (1 - ramp(t, 3.3, 4.0))
    c.text((CX, 470), "근거가 없다면?", 100, fade(INK, a), bold=True)
    x0, y0, x1, y1 = 800, 590, 1120, 800
    col = fade(GREY, a)
    for (p, q) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        c.dashed(p, q, 4, col)
    return c.out()


def s3_15(t):
    c = Canvas()
    kicker(c, "답은 이렇게 갈립니다")
    la, ra = ramp(t, 0.3, 1.0), ramp(t, 1.8, 2.5)
    # 왼쪽
    c.text((520, 230), "근거 있음", 54, fade(TEAL, la), bold=True)
    c.rrect((280, 330, 760, 480), 20, fill=fade((255, 255, 255), la), outline=fade(TEAL, la), w=4)
    icon(c, "card", 360, 405, 36, fade(TEAL, la), 4)
    c.text((560, 405), "지식 카드 찾음", 32, fade(INK, la))
    c.arrow((520, 490), (520, 590), 5, fade(TEAL, la))
    c.rrect((250, 600, 790, 800), 20, fill=fade(TEAL_L, la * 0.6), outline=fade(TEAL, la), w=4)
    c.text((520, 660), "답 + 출처 + 안전 수칙", 38, fade(INK, la), bold=True)
    c.text((520, 725), "근거 번호가 붙은 답", 28, fade(GREY, la))
    # 오른쪽
    c.text((1400, 230), "근거 없음", 54, fade(GREY, ra), bold=True)
    c.rrect((1160, 330, 1640, 480), 20, fill=fade((255, 255, 255), ra), outline=fade(GREY, ra), w=4)
    c.text((1400, 405), "맞는 카드 없음", 32, fade(INK, ra))
    c.arrow((1400, 490), (1400, 590), 5, fade(GREY, ra))
    c.rrect((1130, 600, 1670, 800), 20, fill=fade(GREY_L, ra * 0.6), outline=fade(GREY, ra), w=4)
    c.text((1400, 660), "해당 지식 없음 + 확인 안내", 36, fade(INK, ra), bold=True)
    c.text((1400, 725), "지어내지 않고 숙련자에게", 28, fade(GREY, ra))
    # 청록 선이 PDA로
    b = ramp(t, 3.4, 4.6)
    if b > 0:
        ex = 960
        c.line((520, 810), (520 + (ex - 520) * b, 810 + 60 * b), 5, fade(TEAL, b))
        c.line((1400, 810), (1400 + (ex - 1400) * b, 810 + 60 * b), 5, fade(TEAL, b))
        icon(c, "pda", 960, 960, 60, fade(TEAL, b), 5)
        c.line((960, 870), (960, 895), 5, fade(TEAL, b))
    return c.out()


def cloud_dots(n=560, seed=7):
    rnd = random.Random(seed)
    pts = []
    while len(pts) < n:
        x, y = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
        if x * x + y * y <= 1:
            pts.append((960 + x * 720, 600 + y * 250, rnd.uniform(5, 9)))
    return pts


DOTS = cloud_dots()
FILTER = (680, 520, 1480, 740)    # 이 설비 + 공통
NEAR = [i for i, (x, y, r) in enumerate(DOTS) if FILTER[0] < x < FILTER[2] and FILTER[1] < y < FILTER[3]][:9]


def s4_1(t):
    c = Canvas()
    kicker(c, "① 검색")
    fa = ramp(t, 0.2, 1.0)
    inside = lambda x, y: FILTER[0] < x < FILTER[2] and FILTER[1] < y < FILTER[3]
    dim = ramp(t, 3.0, 3.8)
    hot = ramp(t, 4.2, 5.0)
    for i, (x, y, r) in enumerate(DOTS):
        col = GREY
        a = fa * 0.9
        if t > 3.0 and not inside(x, y):
            a = fa * (0.9 - 0.7 * dim)
        if i in NEAR and hot > 0:
            col = mix(GREY, TEAL, hot)
            r = r * (1 + 0.6 * hot)
        c.circle((x, y), r, fill=fade(col, a))
    c.text((CX, 935), "3,950개 지식 조각", 46, fade(INK, fa), bold=True)
    c.text((CX, 992), "매뉴얼 58권 2,459쪽 · 카드 · 인계 기록", 26, fade(GREY, fa))
    # 질문 + 상태 → 검색어
    m = ramp(t, 0.8, 1.8)
    ya = 170
    xq = 560 + (800 - 560) * m          # 질문 → 가운데로
    xs = 1360 + (1130 - 1360) * m       # 상태 → 가운데로
    c.rrect((xq - 120, ya - 38, xq + 120, ya + 38), 20, fill=(255, 255, 255), outline=TEAL, w=3)
    c.text((xq, ya), "질문", 30, INK)
    c.rrect((xs - 190, ya - 38, xs + 190, ya + 38), 20, fill=(255, 255, 255), outline=TEAL, w=3)
    c.text((xs, ya), "MES 이상 상태", 30, INK)
    s = ramp(t, 1.8, 2.8)
    if s > 0.05:
        c.arrow((CX, 230), (CX, 230 + 270 * s), 6, TEAL)
    # 필터 윤곽
    if t > 2.6:
        a = ramp(t, 2.6, 3.4)
        c.rrect(FILTER, 28, outline=fade(TEAL, a), w=4)
        c.text((FILTER[0] + 20, FILTER[1] - 28), "이 설비 + 공통만", 28, fade(TEAL, a), anchor="lm", bold=True)
    return c.out()


def s4_2(t):
    c = Canvas()
    kicker(c, "② 판정")
    x0, wbar = 600, 960
    rows = [("K-1004 카드", 0.9998, True), ("인계 기록", 0.9988, True), ("조각 3", 0.18, False),
            ("조각 4", 0.11, False), ("조각 5", 0.22, False)]
    for v, lab in ((0.3, "0.3"), (0.9, "0.9")):
        xx = x0 + wbar * v
        c.dashed((xx, 250), (xx, 800), 3, GREY)
        c.text((xx, 225), lab, 28, GREY)
    c.text((x0 - 20, 225), "점수", 26, GREY, anchor="rm")
    for i, (name, v, ok) in enumerate(rows):
        y = 320 + 105 * i
        g = ramp(t, 0.8, 2.8)
        a = 1.0
        shift = 0
        if not ok and t > 3.4:
            a = 1 - ramp(t, 3.4, 4.4)
            shift = 140 * ramp(t, 3.4, 4.4)
        c.rrect((x0, y - 22, x0 + wbar, y + 22), 22, fill=fade(GREY_L, a * 0.5 + 0.2))
        w_ = max(30, wbar * v * g)
        col = TEAL if ok else GREY
        c.rrect((x0, y - 22, x0 + w_, y + 22), 22, fill=fade(col, a))
        c.text((x0 - 30, y), name, 32, fade(INK, a), anchor="rm")
        if ok and g > 0.95:
            c.text((x0 + wbar + 30, y), f"{v:.4f}", 30, TEAL, anchor="lm", bold=True)
        if ok and t > 3.8:
            c.text((x0 + wbar + 160, y), "통과", 30, TEAL, anchor="lm", bold=True)
        if not ok and t > 2.9:
            c.text((x0 + wbar * v + 40 + shift, y), "탈락", 28, fade(GREY, a), anchor="lm")
    c.text((CX, 900), "판정 모델이 조각마다 이 질문의 근거인지 점수를 매깁니다", 36, fade(INK, ramp(t, 1.0, 1.8)))
    c.text((CX, 975), "점수: 10/23 HPU 질문 실측 · 탈락 조각의 막대 길이는 개념 표시", 24, GREY)
    return c.out()


def s4_3(t):
    c = Canvas()
    kicker(c, "③ 답변 · ④ 규칙")
    c.rrect((330, 190, 1130, 830), 26, fill=(255, 255, 255), outline=TEAL, w=4)
    c.text((380, 240), "답변", 34, TEAL, anchor="lm", bold=True)
    lines = [(0.9, "S1"), (0.7, None), (0.85, "S2"), (0.6, None), (0.8, "S1")]
    for i, (frac, tag) in enumerate(lines):
        a = ramp(t, 0.6 + 0.55 * i, 1.1 + 0.55 * i)
        y = 330 + 95 * i
        wbar = 640 * frac * a
        c.rrect((380, y - 14, 380 + max(wbar, 8), y + 14), 14, fill=fade(GREY_L, a + 0.001))
        if tag and a > 0.95:
            c.rrect((380 + wbar + 12, y - 22, 380 + wbar + 82, y + 22), 10, outline=TEAL, w=3)
            c.text((380 + wbar + 47, y), f"[{tag}]", 26, TEAL, bold=True)
    stamps = [("MES 현재값을 첫 줄에", 3.2), ("다른 설비 문장 제거", 4.0), ("측정값 없으면 답하지 않음", 4.8)]
    for i, (s, t0) in enumerate(stamps):
        a = ramp(t, t0, t0 + 0.4)
        y = 300 + 190 * i
        slide = (1 - a) * 80
        c.rrect((1230 + slide, y - 55, 1780 + slide, y + 55), 20, fill=fade(TEAL_L, a), outline=fade(TEAL, a), w=4)
        c.text((1505 + slide, y), s, 32, fade(TEAL, a), bold=True)
        c.arrow((1225 + slide, y), (1140, y), 4, fade(TEAL, a), 16)
    c.text((CX, 950), "답은 남은 근거로만 쓰고, 틀리기 쉬운 부분은 코드가 처리합니다", 36, fade(INK, ramp(t, 1.0, 1.8)))
    return c.out()


def s4_8(t):
    c = Canvas()
    kicker(c, "현장 기록 → 지식 카드 후보")
    # 이동: 근무일지 카드 → 오른쪽 카드 윤곽
    m = ramp(t, 3.6, 5.2)
    lx0, lx1 = 340, 1060
    x0 = lx0 + (lx1 - lx0) * m
    bw = 560 - 60 * m
    # 수첩 쪽 (뒤)
    na = ramp(t, 1.8, 2.8) * (1 - 0.0)
    nx = x0 - 25
    c.rrect((nx, 210 + 22, nx + bw + 30, 790 + 22), 16, fill=fade((240, 228, 200), na), outline=fade((170, 150, 110), na), w=3)
    for k in range(9):
        yy = 290 + 60 * k
        c.line((nx + 30, yy), (nx + bw, yy), 2, fade((205, 190, 160), na))
    rnd = random.Random(3)
    for k in range(5):
        pts = [(nx + 60 + rnd.uniform(0, bw - 120), 300 + 100 * k + rnd.uniform(-20, 20)) for _ in range(4)]
        c.poly(pts, 3, fade((120, 100, 70), na))
    # 근무일지 카드 (앞)
    c.rrect((x0, 210, x0 + bw, 790), 22, fill=(255, 255, 255), outline=TEAL, w=4)
    c.text((x0 + 36, 262), "근무일지" if m < 0.6 else "지식 카드 후보", 36, TEAL, anchor="lm", bold=True)
    for k in range(5):
        c.rrect((x0 + 36, 330 + 85 * k, x0 + 36 + (bw - 72) * (0.9 - 0.12 * (k % 3)), 354 + 85 * k), 12, fill=GREY_L)
    if m > 0.9:
        c.circle((x0 + bw - 50, 262), 24, fill=TEAL_L, outline=TEAL, w=3)
        c.poly([(x0 + bw - 62, 262), (x0 + bw - 52, 273), (x0 + bw - 36, 250)], 4, TEAL)
    a = ramp(t, 0.3, 1.0)
    c.text((CX, 930), "수첩에만 남던 것을, 모두가 볼 수 있게", 40, fade(INK, a), bold=True)
    return c.out()


def s4_10(t):
    c = Canvas()
    kicker(c, "승인된 지식은 검색에 더해집니다")
    fly = ramp(t, 1.4, 3.4)
    for (x, y, r) in DOTS:
        c.circle((x, y + 40), r, fill=fade(GREY, 0.75))
    # 승인 카드 → 점
    if t < 1.4:
        a = ramp(t, 0.2, 0.8)
        c.rrect((220, 190, 500, 450), 20, fill=fade((255, 255, 255), a), outline=fade(TEAL, a), w=4)
        c.text((360, 250), "승인된 카드", 28, fade(TEAL, a), bold=True)
        icon(c, "card", 360, 345, 44, fade(TEAL, a), 5)
    else:
        sh = 1 - ramp(t, 1.4, 1.9)
        sx, sy, ex, ey = 360, 420, 1030, 640
        x, y = sx + (ex - sx) * fly, sy + (ey - sy) * fly - 160 * math.sin(math.pi * fly)
        if sh > 0:
            c.rrect((x - 140 * sh, y - 130 * sh, x + 140 * sh, y + 130 * sh), 20, fill=(255, 255, 255), outline=TEAL, w=4)
        c.circle((x, y), 11 + 4 * (1 - sh), fill=TEAL)
        if fly >= 1:
            q = clamp((t - 3.4) / 1.0)
            c.circle((ex, ey + 40), 11 + 40 * q, outline=fade(TEAL, 1 - q), w=4)
    n = 3951 if t > 3.4 else 3950
    c.text((CX, 225), f"{n:,}", 130, TEAL if t > 3.4 else INK, bold=True)
    c.text((CX, 325), "지식 조각", 36, GREY)
    if t > 3.4:
        a = ramp(t, 3.4, 4.0)
        c.text((CX + 280, 225), "+1", 70, fade(TEAL, a), bold=True)
    return c.out()


def result_card(t, kicker_s, big, line, foot, big_size=300):
    c = Canvas()
    kicker(c, kicker_s)
    a = ramp(t, 0.2, 0.9)
    off = (1 - a) * 40
    c.text((CX, 440 + off), big, big_size, fade(TEAL, a), bold=True)
    b = ramp(t, 0.7, 1.3)
    c.text((CX, 690), line, 46, fade(INK, b))
    c.text((CX, 985), foot, 28, fade(GREY, ramp(t, 1.0, 1.6)))
    return c.out()


def s5_2(t): return result_card(t, "성과 1/3", "4×", "처음 보는 질문 35개 중 답할 수 있는 범위: 6개 → 25개",
                                "보류 셋 · 사전 등록 후 1회 측정 · 2026-10-16")


def s5_3(t): return result_card(t, "성과 2/3", "42 / 42", "작업자 화면의 MES 현재값 · 상태 모순 0건",
                                "MES 충돌 평가 · 2026-10-22", 260)


def s5_4(t):
    c = result_card(t, "성과 3/3", "0", "다른 설비 값 섞기 18 → 0 · 없는 값 지어내기 4 → 0 · 추적한 안전 오류 0건",
                    "321문항 · Jetson 측정 · 2026-10-22")
    return c


def s5_5(t):
    c = Canvas()
    a = ramp(t, 0.2, 0.8)
    c.text((CX, 500), "외부 서버 없이 · 8GB 장비 한 대에서 · 응답 약 10초", 58, fade(INK, a), bold=True)
    c.text((CX, 985), "응답 시간 p95 10.5초 (321문항)", 28, fade(GREY, ramp(t, 0.6, 1.2)))
    return c.out()


def s5_8(t):
    c = Canvas()
    a = ramp(t, 0.1, 0.7)
    icon(c, "brand", 640, 480, 64, fade(TEAL, a), 9)
    c.text((1000, 470), "ShiftLink", 150, fade(TEAL, a), bold=True)
    c.text((CX, 680), "경험은 이어진다", 62, fade(INK, ramp(t, 0.5, 1.1)))
    return c.out()


def s5_9(t):
    c = Canvas()
    a = ramp(t, 0.1, 0.6)
    c.text((CX, 330), "ShiftLink", 96, fade(TEAL, a), bold=True)
    c.text((CX, 440), "경험은 이어진다", 40, fade(GREY, a))
    c.text((CX, 600), "허재원", 60, fade(INK, ramp(t, 0.35, 0.9)), bold=True)
    c.text((CX, 930), "모의 시연 · MES 데이터는 시뮬레이션 · 시연 설비 Unity 가상 공장 · 일부 장면 AI 생성", 26,
           fade(GREY, ramp(t, 0.4, 1.0)))
    return c.out()


SCENES = {
    "s2-1_MG": (s2_1, 6), "s2-2_MG": (s2_2, 6), "s2-3_MG": (s2_3, 6), "s2-4_MG": (s2_4, 7),
    "s3-12_MG": (s3_12, 4), "s3-15_MG": (s3_15, 6),
    "s4-1_MG": (s4_1, 6), "s4-2_MG": (s4_2, 7), "s4-3_MG": (s4_3, 6), "s4-8_MG": (s4_8, 6), "s4-10_MG": (s4_10, 6),
    "s5-2_MG": (s5_2, 4), "s5-3_MG": (s5_3, 4), "s5-4_MG": (s5_4, 4), "s5-5_MG": (s5_5, 3),
    "s5-7_MG": (s5_7, 3), "s5-8_MG": (s5_8, 2), "s5-9_MG": (s5_9, 2),
}

# ---- AI 생성 영상 위에 얹는 오버레이 (검은 배경 → ffmpeg screen 합성으로 투명해진다) ----
K = (0, 0, 0)
LT = (120, 220, 212)      # 어두운 장면 위에서 읽히는 밝은 청록
WH = (245, 245, 245)


def ov_network(t):
    """S1-8: 클라우드·AI 채팅 아이콘이 자물쇠·방화벽 선에 막힌다. 생성 화면(초록 단말) 위 중앙에 얹는다."""
    c = Canvas(bg=K)
    a = ramp(t, 0.2, 0.9)
    for cx, name_ in ((660, "cloud"), (960, "chat")):
        icon(c, name_, cx, 470, 78, mix(K, WH, a), 8)
    b = ramp(t, 1.6, 2.6)                   # 방화벽 선
    if b > 0:
        c.dashed((540, 600 - 220 * b), (540 + 840 * b, 600 - 220 * b), 7, mix(K, LT, b), 26, 14)
        c.line((540, 600), (540, 600 - 220 * b), 7, mix(K, LT, b))
        c.line((1380, 600), (1380, 600 - 220 * b), 7, mix(K, LT, b))
    d = ramp(t, 2.6, 3.4)
    icon(c, "lock", 1230, 470, 70, mix(K, LT, d), 8)
    e = ramp(t, 3.4, 4.2)                   # 빨간 사선 대신 얇은 가위표
    if e > 0:
        for cx in (660, 960):
            c.line((cx - 60, 410), (cx + 60, 530), 7, mix(K, (230, 120, 110), e))
            c.line((cx + 60, 410), (cx - 60, 530), 7, mix(K, (230, 120, 110), e))
    c.text((960, 700), "공장망 · 외부 접근 차단", 52, mix(K, WH, ramp(t, 3.0, 3.8)), bold=True)
    return c.out()


def ov_logo(t):
    """S1-9: 청록 선이 HPU 쪽에서 그려져 로고로 이어진다."""
    c = Canvas(bg=K)
    p = ramp(t, 0.3, 2.4)
    pts = [(260, 900), (700, 820), (1100, 640), (1380, 520)]
    n = len(pts) - 1
    for i in range(n):
        seg = clamp(p * n - i)
        if seg > 0:
            a, b = pts[i], pts[i + 1]
            c.line(a, (a[0] + (b[0] - a[0]) * seg, a[1] + (b[1] - a[1]) * seg), 7, mix(K, LT, 1))
    q = ramp(t, 2.6, 3.6)
    icon(c, "brand", 700, 330, 56, mix(K, LT, q), 8)
    c.text((1010, 322), "ShiftLink", 118, mix(K, WH, q), bold=True)
    c.text((960, 455), "경험을 잇다", 52, mix(K, WH, ramp(t, 3.2, 4.2)))
    return c.out()


def ov_logo_card(t):          # 사용 안 함(자리 보존): 단독 로고 카드는 s5-8
    return ov_logo(t)


SCENES["s1-8_overlay"] = (ov_network, 6)
SCENES["s1-9_overlay"] = (ov_logo, 5)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--still":
        OUT.mkdir(parents=True, exist_ok=True)
        fn, _ = SCENES[args[1]]
        fn(float(args[2])).save(OUT / f"{args[1]}_still.png")
        sys.exit()
    for name in (args or SCENES):
        fn, dur = SCENES[name]
        print("render", name, flush=True)
        render(fn, dur, OUT / f"{name}.mp4")

