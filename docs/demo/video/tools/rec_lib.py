"""REC 녹화 공통: 파이 키오스크와 같은 PDA 화면을 노트북에서 열어 녹화한다.
- 노트북 PDA 서버(python -m shiftlink.pda --port 8081 --jetson <녹화용 MES> --unity http://127.0.0.1:8090 --cnn ...)를 쓴다.
  Unity 카메라·설비 분류·/api 프록시는 이 서버가 하고, 데이터는 녹화용 로컬 MES로만 간다(Jetson·파이에 쓰지 않음).
- pda.html은 파이 키오스크 파일을 그대로 받아 쓴다(pda.js는 저장소와 같음을 md5로 확인).
- 로그인은 녹화용 MES의 녹화 전용 계정(E-101 김신입)으로 한다. 얼굴 로그인 R1은 사람이 따로 녹화. 커서 대신 터치 원을 그린다."""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

PDA = os.environ.get("REC_PDA", "http://127.0.0.1:8081")
PI = os.environ.get("REC_PI", "http://raspberrypi.tail0a6af3.ts.net:8080")
QUERY = os.environ.get("REC_QUERY")          # 질의만 다른 서버로 보낼 때(기본: PDA 서버의 프록시)
PASSWORD = os.environ.get("REC_PASSWORD", "rec-op-2026")   # 녹화용 복사본 DB에만 있는 계정
OUT = Path(__file__).resolve().parents[4] / "output" / "video" / "rec"
VIEW = {"width": 1280, "height": 800}

TOUCH_JS = """
(() => {
  const st = document.createElement('style');
  st.textContent = '*{cursor:none!important} .rec-touch{position:fixed;width:56px;height:56px;margin:-28px 0 0 -28px;border-radius:50%;'
    + 'border:4px solid rgba(22,107,104,.9);background:rgba(22,107,104,.18);pointer-events:none;z-index:2147483647;'
    + 'animation:rt .55s ease-out forwards} @keyframes rt{from{transform:scale(.6);opacity:1}to{transform:scale(1.25);opacity:0}}';
  document.documentElement.appendChild(st);
  addEventListener('pointerdown', (e) => {
    const d = document.createElement('div'); d.className = 'rec-touch';
    d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px';
    document.body.appendChild(d); setTimeout(() => d.remove(), 700);
  }, true);
})();
"""

_pi_html = None


def _page(route):
    global _pi_html
    if _pi_html is None:
        try:
            _pi_html = urllib.request.urlopen(PI + "/pda.html", timeout=10).read()
        except OSError:                     # 파이에 닿지 않으면 노트북 PDA 서버의 화면 파일(저장소 버전)을 쓴다
            return route.continue_()
    route.fulfill(status=200, content_type="text/html; charset=utf-8", body=_pi_html)


def _login(route):
    # Jetson의 실제 계정을 쓰지 않는 녹화(REC_STUB_LOGIN=1)에서만: 계정 확인을 대신한다
    body = json.loads(route.request.post_data or "{}")
    route.fulfill(status=200, content_type="application/json",
                  body=json.dumps({"operator": {"id": body.get("id") or "E-101", "name": "김신입"}}))


def _query(route):
    resp = route.fetch(url=QUERY + "/api/query", timeout=180_000)
    route.fulfill(response=resp)


class Rec:
    """with Rec('r2') as r: r.pg ... — 끝나면 output/video/rec/<name>.webm"""

    def __init__(self, name, video=True, scale=1):   # 영상 녹화는 배율 1일 때만 화면이 영상 틀에 꽉 찬다
        self.name, self.video, self.scale = name, video, scale

    def __enter__(self):
        self.p = sync_playwright().start()
        self.b = self.p.chromium.launch(channel="chrome")
        kw = dict(viewport=VIEW, device_scale_factor=self.scale, locale="ko-KR", timezone_id="Asia/Seoul")
        if self.video:
            kw.update(record_video_dir=str(OUT / "_raw"),
                      record_video_size={"width": int(VIEW["width"] * self.scale), "height": int(VIEW["height"] * self.scale)})
        self.ctx = self.b.new_context(**kw)
        self.ctx.add_init_script(TOUCH_JS)
        self.ctx.route("**/pda.html", _page)
        if os.environ.get("REC_STUB_LOGIN"):
            self.ctx.route("**/api/account/login", _login)
        if QUERY:
            self.ctx.route("**/api/query", _query)
        self.pg = self.ctx.new_page()
        self.t0 = time.time()
        return self

    def login(self, emp="E-101"):
        pg = self.pg
        pg.goto(PDA + "/pda.html")
        pg.wait_for_selector("#employeeId")
        pg.fill("#employeeId", emp)
        pg.fill("#employeePassword", PASSWORD)
        pg.click("#accountSubmit")
        pg.wait_for_timeout(2500)

    def tap(self, selector, wait=900):
        loc = self.pg.locator(selector).first
        loc.scroll_into_view_if_needed()
        box = loc.bounding_box()
        self.pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.pg.mouse.down()
        self.pg.mouse.up()
        self.pg.wait_for_timeout(wait)

    def type(self, selector, text, delay=55):
        self.tap(selector, 300)
        self.pg.keyboard.type(text, delay=delay)

    def wait(self, ms):
        self.pg.wait_for_timeout(ms)

    def mark(self, label):
        print(f"  [{time.time() - self.t0:5.1f}s] {label}", flush=True)

    def shot(self, name):
        (OUT / "shots").mkdir(parents=True, exist_ok=True)
        self.pg.screenshot(path=str(OUT / "shots" / f"{name}.png"))

    def __exit__(self, *exc):
        video = self.pg.video if self.video else None
        self.ctx.close()
        if video:
            src = Path(video.path())
            dst = OUT / f"{self.name}.webm"
            dst.unlink(missing_ok=True)
            src.rename(dst)
        self.b.close()
        self.p.stop()
