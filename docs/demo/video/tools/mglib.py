"""시연 영상 모션그래픽(MG) 렌더링 공통 부품. 1920x1080 논리 좌표, 내부 2배 해상도로 그린 뒤 줄여 계단을 없앤다."""
from __future__ import annotations

import math
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, S, FPS = 1920, 1080, 2, 30
BG = (247, 244, 237)        # 따뜻한 오프화이트
TEAL = (22, 107, 104)       # PDA 앱 청록
TEAL_L = (200, 224, 221)
INK = (43, 47, 51)
GREY = (150, 154, 158)
GREY_L = (221, 223, 224)
AMBER = (214, 142, 40)
FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"
_fonts: dict = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_B if bold else FONT, int(size * S))
    return _fonts[key]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ramp(t, t0, t1):
    """t0~t1 사이를 0→1로, 가감속을 준다."""
    x = clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t0)
    return x * x * (3 - 2 * x)


def mix(c0, c1, a):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * a) for i in range(3))


def fade(color, a, bg=BG):
    return mix(bg, color, clamp(a))


class Canvas:
    def __init__(self, bg=BG):
        self.bg = bg
        self.img = Image.new("RGB", (W * S, H * S), bg)
        self.d = ImageDraw.Draw(self.img)

    def p(self, pt):
        return (pt[0] * S, pt[1] * S)

    def line(self, a, b, w=4, color=TEAL):
        self.d.line([self.p(a), self.p(b)], fill=color, width=int(w * S))
        r = w * S / 2   # 끝을 둥글게
        for q in (a, b):
            x, y = self.p(q)
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    def poly(self, pts, w=4, color=TEAL, closed=False):
        for i in range(len(pts) - 1):
            self.line(pts[i], pts[i + 1], w, color)
        if closed:
            self.line(pts[-1], pts[0], w, color)

    def dashed(self, a, b, w=3, color=GREY, dash=14, gap=10):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        if n == 0:
            return
        ux, uy = dx / n, dy / n
        pos = 0.0
        while pos < n:
            e = min(pos + dash, n)
            self.d.line([self.p((a[0] + ux * pos, a[1] + uy * pos)), self.p((a[0] + ux * e, a[1] + uy * e))],
                        fill=color, width=int(w * S))
            pos += dash + gap

    def rrect(self, box, r=16, fill=None, outline=None, w=3):
        x0, y0, x1, y1 = box
        self.d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], radius=r * S, fill=fill, outline=outline,
                                 width=int(w * S))

    def circle(self, c, r, fill=None, outline=None, w=3):
        x, y = self.p(c)
        self.d.ellipse([x - r * S, y - r * S, x + r * S, y + r * S], fill=fill, outline=outline, width=int(w * S))

    def arc(self, c, r, a0, a1, w=4, color=TEAL):
        x, y = self.p(c)
        self.d.arc([x - r * S, y - r * S, x + r * S, y + r * S], a0, a1, fill=color, width=int(w * S))

    def text(self, xy, s, size=32, color=INK, anchor="mm", bold=False):
        self.d.text(self.p(xy), s, font=font(size, bold), fill=color, anchor=anchor)

    def arrowhead(self, tip, angle, size=18, color=TEAL):
        a = math.radians(angle)
        l, r = a + math.radians(155), a - math.radians(155)
        pts = [tip, (tip[0] + size * math.cos(l), tip[1] + size * math.sin(l)),
               (tip[0] + size * math.cos(r), tip[1] + size * math.sin(r))]
        self.d.polygon([self.p(q) for q in pts], fill=color)

    def arrow(self, a, b, w=4, color=TEAL, head=20):
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        end = (b[0] - math.cos(math.radians(ang)) * head * 0.6, b[1] - math.sin(math.radians(ang)) * head * 0.6)
        self.line(a, end, w, color)
        self.arrowhead(b, ang, head, color)

    def out(self):
        return self.img.reduce(S)


# ---------- 아이콘 (선 두께 통일, 중심 cx,cy, 반크기 r) ----------
def icon(c: Canvas, name, cx, cy, r=46, color=TEAL, w=5):
    if name == "face":
        k = r * 0.38
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = cx + sx * r, cy + sy * r
                c.line((x, y), (x - sx * k, y), w, color)
                c.line((x, y), (x, y - sy * k), w, color)
        c.circle((cx, cy - r * 0.18), r * 0.3, outline=color, w=w)
        c.arc((cx, cy + r * 0.62), r * 0.46, 200, 340, w, color)
    elif name == "machine":
        c.rrect((cx - r, cy - r * 0.5, cx + r * 0.55, cy + r * 0.6), 8, outline=color, w=w)
        c.line((cx - r * 0.7, cy + r * 0.6), (cx - r * 0.7, cy + r * 0.85), w, color)
        c.line((cx + r * 0.25, cy + r * 0.6), (cx + r * 0.25, cy + r * 0.85), w, color)
        c.circle((cx + r * 0.55, cy - r * 0.45), r * 0.4, fill=BG, outline=color, w=w)
        c.line((cx + r * 0.55 - r * 0.58, cy - r * 0.45), (cx + r * 0.55 + r * 0.58, cy - r * 0.45), w - 1, color)
        c.line((cx + r * 0.55, cy - r * 0.45 - r * 0.58), (cx + r * 0.55, cy - r * 0.45 + r * 0.58), w - 1, color)
    elif name == "gauge":
        c.circle((cx, cy), r * 0.95, outline=color, w=w)
        c.arc((cx, cy), r * 0.7, 150, 390, w - 2, color)
        c.line((cx, cy), (cx + r * 0.5, cy - r * 0.45), w, color)
        c.circle((cx, cy), r * 0.1, fill=color)
    elif name == "chat":
        c.rrect((cx - r, cy - r * 0.75, cx + r, cy + r * 0.45), 18, outline=color, w=w)
        c.poly([(cx - r * 0.4, cy + r * 0.45), (cx - r * 0.55, cy + r * 0.95), (cx - r * 0.05, cy + r * 0.45)], w, color)
        c.text((cx, cy - r * 0.15), "[1]", int(r * 0.5), color, bold=True)
    elif name == "clipboard":
        c.rrect((cx - r * 0.75, cy - r * 0.9, cx + r * 0.75, cy + r), 10, outline=color, w=w)
        c.poly([(cx - r * 0.4, cy - r * 0.6), (cx - r * 0.4, cy - r * 1.1), (cx + r * 0.4, cy - r * 1.1), (cx + r * 0.4, cy - r * 0.6)], w, color)
        c.line((cx - r * 0.4, cy - r * 0.1), (cx + r * 0.4, cy - r * 0.1), w - 1, color)
        c.line((cx - r * 0.4, cy + r * 0.3), (cx + r * 0.1, cy + r * 0.3), w - 1, color)
    elif name == "card":
        c.rrect((cx - r * 0.8, cy - r * 0.95, cx + r * 0.8, cy + r * 0.95), 12, outline=color, w=w)
        c.line((cx - r * 0.45, cy - r * 0.45), (cx + r * 0.1, cy - r * 0.45), w - 1, color)
        c.line((cx - r * 0.45, cy - r * 0.1), (cx + r * 0.35, cy - r * 0.1), w - 1, color)
        c.circle((cx + r * 0.35, cy + r * 0.5), r * 0.36, fill=BG, outline=color, w=w)
        c.poly([(cx + r * 0.2, cy + r * 0.5), (cx + r * 0.32, cy + r * 0.63), (cx + r * 0.52, cy + r * 0.38)], w - 1, color)
    elif name == "cloud":
        c.arc((cx - r * 0.4, cy), r * 0.45, 90, 270, w, color)
        c.arc((cx, cy - r * 0.2), r * 0.6, 180, 360, w, color)
        c.arc((cx + r * 0.45, cy), r * 0.45, 270, 450, w, color)
        c.line((cx - r * 0.4, cy + r * 0.45), (cx + r * 0.45, cy + r * 0.45), w, color)
    elif name == "pda":
        c.rrect((cx - r * 0.55, cy - r * 0.95, cx + r * 0.55, cy + r * 0.95), 12, outline=color, w=w)
        c.rrect((cx - r * 0.38, cy - r * 0.7, cx + r * 0.38, cy + r * 0.45), 6, outline=color, w=w - 2)
        c.circle((cx, cy + r * 0.7), r * 0.1, fill=color)
    elif name == "chip":
        c.rrect((cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7), 10, outline=color, w=w)
        c.rrect((cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35), 4, outline=color, w=w - 2)
        for k in (-0.4, 0, 0.4):
            for s in (-1, 1):
                c.line((cx + k * r, cy + s * r * 0.7), (cx + k * r, cy + s * r * 1.0), w - 2, color)
                c.line((cx + s * r * 0.7, cy + k * r), (cx + s * r * 1.0, cy + k * r), w - 2, color)
    elif name == "monitor":
        c.rrect((cx - r, cy - r * 0.7, cx + r, cy + r * 0.45), 8, outline=color, w=w)
        c.line((cx, cy + r * 0.45), (cx, cy + r * 0.8), w, color)
        c.line((cx - r * 0.45, cy + r * 0.8), (cx + r * 0.45, cy + r * 0.8), w, color)
    elif name == "lock":
        c.rrect((cx - r * 0.6, cy - r * 0.1, cx + r * 0.6, cy + r * 0.8), 8, outline=color, w=w)
        c.arc((cx, cy - r * 0.15), r * 0.42, 180, 360, w, color)
        c.circle((cx, cy + r * 0.35), r * 0.1, fill=color)
    elif name == "brand":   # ⇄ 마크
        c.line((cx - r, cy - r * 0.35), (cx + r, cy - r * 0.35), w, color)
        c.poly([(cx + r * 0.55, cy - r * 0.8), (cx + r, cy - r * 0.35), (cx + r * 0.55, cy + r * 0.1)], w, color)
        c.line((cx + r, cy + r * 0.35), (cx - r, cy + r * 0.35), w, color)
        c.poly([(cx - r * 0.55, cy - r * 0.1), (cx - r, cy + r * 0.35), (cx - r * 0.55, cy + r * 0.8)], w, color)


# ---------- 렌더 드라이버 ----------
def _frame(args):
    fn, t = args
    return fn(t).tobytes()


def render(fn, duration, out_path, workers=6, fps=FPS):
    """fn(t)->PIL.Image(1920x1080). 프레임을 ffmpeg로 바로 흘려 보낸다."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(duration * fps)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "medium",
           str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(workers) as pool:
        for data in pool.imap(_frame, ((fn, i / fps) for i in range(n)), chunksize=4):
            proc.stdin.write(data)
    proc.stdin.close()
    proc.wait()
    return out_path
