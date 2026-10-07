"""Unity PC에서 실행: PDA 촬영 폴더에 새로 저장된 사진을 파이 분류 서버로 보낸다(표준 라이브러리만).

    python scripts/send_unity_captures.py --dir <Unity 촬영 폴더> --pi http://<파이>:8090

Unity는 PNG와 JSON을 모두 저장한 뒤에만 "저장 성공"을 표시하므로, 짝 JSON이 생긴 PNG만 보낸다.
시작할 때 이미 있던 사진은 보내지 않는다(--all이면 보낸다). 파이는 classify.py --listen 으로 받는다.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def ready(folder: Path) -> set[Path]:
    """짝 JSON까지 저장이 끝난 PNG."""
    return {p for p in folder.glob("*.png") if p.with_suffix(".json").exists()}


def send(pi: str, image: Path, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(pi.rstrip("/") + "/classify", data=image.read_bytes(),
                                 headers={"Content-Type": "application/octet-stream"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--pi", required=True)
    parser.add_argument("--all", action="store_true", help="이미 있던 사진도 보낸다")
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()
    done = set() if args.all else ready(args.dir)
    print(f"감시: {args.dir} → {args.pi}/classify (기존 {len(done)}장 건너뜀)", flush=True)
    while True:
        for image in sorted(ready(args.dir) - done):
            try:
                r = send(args.pi, image)
                print(f"{image.name}: {r['class']} conf={r['conf']} {r['ms']}ms 확정={r['confirmed']} Jetson전송={r['sent']}", flush=True)
                done.add(image)
            except OSError as error:  # 파이가 꺼졌으면 다음 주기에 다시 보낸다
                print(f"{image.name}: 전송 실패 {error}", flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
