"""얼굴 로그인 점검·등록 도구 (웹캠 사용). 이미지는 저장하지 않는다.

    python -m shiftlink.face fetch                         # 모델 내려받기(해시 확인)
    python -m shiftlink.face enroll --id E-001 [--shots 8] [--headless]  # 등록. 미리보기는 화면만, 파일 저장 없음
    python -m shiftlink.face verify --id E-001 [--threshold 0.363] [--headless] [--log <저장소 밖>/attempts.csv --who 팀원A]
        (시도 기록은 저장소 밖에 둔다: 익명 라벨이어도 날짜·시각·점수가 모이면 누가 시도했는지 추정된다.
         예: ../ShiftLink-records/experiments/face_login/attempts.csv)
    python -m shiftlink.face delete --id E-001             # 삭제(동의 철회)
    python -m shiftlink.face bench [--frames 50]           # 한 프레임 지연 p50/p95, 메모리
"""
from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import numpy as np

from . import DEFAULT_THRESHOLD, FACE_FRAMES, FACE_NEED
from .engine import FaceEngine
from .models import fetch_models
from .store import FaceStore
from .verify import append_attempt, decide


def _open(camera: int):
    import cv2
    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        raise SystemExit(f"카메라 {camera}를 열 수 없음")
    return cap


def _grab(cap, engine: FaceEngine, count: int, gap: float, title: str, headless: bool) -> list[np.ndarray | None]:
    """얼굴이 잡힌 프레임만 count장 모은다. 미리보기는 화면에만 그리고 파일로 저장하지 않는다. q는 중단."""
    import cv2
    out: list[np.ndarray | None] = []
    missed = 0
    while len(out) < count and missed < count * 12:
        ok, frame = cap.read()
        embedding = engine.embed(frame) if ok else None
        if ok and not headless:
            text = f"얼굴 {len(out)}/{count}" if embedding is None else f"잡힘 {len(out) + 1}/{count}"
            cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            cv2.imshow(title, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        if embedding is None:
            missed += 1
            continue
        out.append(embedding)
        if headless:
            time.sleep(gap)
        else:
            cv2.waitKey(int(gap * 1000))
    if not headless:
        cv2.destroyAllWindows()
    return out


def _rss_mb() -> float | None:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except ImportError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--headless", action="store_true", help="미리보기 창을 띄우지 않는다(파이 키오스크)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch")
    enroll = sub.add_parser("enroll")
    enroll.add_argument("--id", required=True)
    enroll.add_argument("--shots", type=int, default=8)
    verify = sub.add_parser("verify")
    verify.add_argument("--id", required=True)
    verify.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    verify.add_argument("--frames", type=int, default=FACE_FRAMES)
    verify.add_argument("--min-pass", type=int, default=FACE_NEED)
    verify.add_argument("--log", type=Path, help="시도 기록 CSV(점수·통과 여부만, 이미지·임베딩 없음)")
    verify.add_argument("--who", default="본인", help="시도한 사람 라벨. 사칭 시험에는 익명 라벨(예: 팀원A)")
    delete = sub.add_parser("delete")
    delete.add_argument("--id", required=True)
    bench = sub.add_parser("bench")
    bench.add_argument("--frames", type=int, default=50)
    args = parser.parse_args(argv)

    store = FaceStore()
    if args.command == "fetch":
        for name, path in fetch_models().items():
            print(f"{name} OK {path}")
        return 0
    if args.command == "delete":
        print("삭제함" if store.delete(args.id) else "등록 없음")
        return 0

    engine = FaceEngine.load()
    cap = _open(args.camera)
    try:
        if args.command == "enroll":
            print(f"등록 시작: {args.id}. 'face' 창을 보고 고개를 조금씩 돌려 주세요. q는 중단.", flush=True)
            shots = [e for e in _grab(cap, engine, args.shots, 0.5, "face enroll (q quit)", args.headless) if e is not None]
            print(f"  잡은 얼굴 {len(shots)}/{args.shots}", flush=True)
            if len(shots) < args.shots:
                print(f"얼굴을 {args.shots}번 잡지 못함({len(shots)}번). 등록하지 않음")
                return 1
            print(f"저장: {store.save(args.id, np.stack(shots))}  (임베딩만 저장, 이미지는 저장하지 않음)")
            return 0
        if args.command == "verify":
            template = store.load(args.id)
            if template is None:
                print("등록 없음 또는 모델 버전 불일치: 다시 등록하세요")
                return 2
            verdict = decide(_grab(cap, engine, args.frames, 0.2, "face verify (q quit)", args.headless), template, args.threshold, args.min_pass)
            if args.log:
                append_attempt(args.log, args.id, args.who, args.threshold, verdict)
            print(f"{'통과' if verdict.passed else '실패'} 최고 유사도={verdict.best_score} "
                  f"얼굴 프레임={verdict.frames_seen} 통과 프레임={verdict.frames_passed} (임계값 {args.threshold})")
            return 0 if verdict.passed else 1
        # bench
        times: list[float] = []
        for _ in range(args.frames):
            ok, frame = cap.read()
            if not ok:
                continue
            t0 = time.perf_counter()
            engine.embed(frame)
            times.append((time.perf_counter() - t0) * 1000)
        if not times:
            print("프레임을 읽지 못함")
            return 1
        times.sort()
        p95 = times[min(len(times) - 1, int(len(times) * 0.95))]
        rss = _rss_mb()
        print(f"프레임 {len(times)}장: p50={statistics.median(times):.0f}ms p95={p95:.0f}ms "
              f"메모리={'n/a(psutil 없음)' if rss is None else f'{rss:.0f}MB'} (얼굴 없는 프레임은 검출만 해서 더 빠름)")
        return 0
    finally:
        cap.release()


if __name__ == "__main__":
    raise SystemExit(main())
