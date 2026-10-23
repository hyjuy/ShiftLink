"""AI 생성 영상의 초록 화면(카메라 고정)에 실제 화면 녹화를 합성한다. 추적이 필요 없고, 모서리 4점을 한 번만 준다.
사용: python -X utf8 composite_screen.py <생성영상.mp4> <녹화.webm|mp4> <출력.mp4> x0,y0 x1,y1 x2,y2 x3,y3 [--ss 시작초] [--key 0x00FF00]
 - 모서리 순서: 화면의 왼쪽 위, 오른쪽 위, 왼쪽 아래, 오른쪽 아래 (생성 영상 1920x1080 기준 픽셀)
 - 화면을 가린 물체(손·사람)가 있으면 초록 키로 같이 살려 준다: 녹화는 초록 영역에만 보이고, 그 위에 손이 올라가면 가려진다.
시트 1·8, 시트 2·7, 시트 4·9 세 컷에만 쓴다."""
import subprocess
import sys


def main():
    a = sys.argv[1:]
    src, rec, out = a[0], a[1], a[2]
    pts = [tuple(map(float, p.split(","))) for p in a[3:7]]
    ss = float(a[a.index("--ss") + 1]) if "--ss" in a else 0.0
    key = a[a.index("--key") + 1] if "--key" in a else "0x00FF00"
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
    # 녹화를 네 모서리에 맞춰 원근 변환한 뒤, 초록이 있던 곳에만 보이게 합성한다
    fc = (f"[1:v]scale=1920:1080,format=rgba,perspective=x0={x0}:y0={y0}:x1={x1}:y1={y1}:x2={x2}:y2={y2}:x3={x3}:y3={y3}"
          f":interpolation=cubic:sense=destination[scr];"
          f"[0:v]split[g1][g2];[g1]chromakey={key}:0.18:0.08[keyed];"
          f"[g2][scr]overlay=0:0[plate];[plate][keyed]overlay=0:0:format=auto[o]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ss", str(ss), "-i", rec, "-filter_complex", fc,
           "-map", "[o]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-shortest", out]
    subprocess.run(cmd, check=True)
    print("완료:", out)


if __name__ == "__main__":
    if len(sys.argv) < 8:
        sys.exit(__doc__)
    main()
