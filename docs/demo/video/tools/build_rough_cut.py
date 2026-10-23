"""러프컷 조립. 사용: python -X utf8 build_rough_cut.py [--tts]
- 컷 목록(cuts.py)대로 컷마다 1920x1080·30fps 구간을 만들고 이어 붙여 output/video/final/rough_cut.mp4 를 낸다.
- 실제 클립이 있는 컷은 그 클립을, 없는 컷은 자리표시 화면을 쓴다. output/video/clips/<컷이름>.mp4 를 넣으면 자동으로 대체한다.
- 자막 카드(왼쪽 아래), 구석 표기, 가이드 내레이션(Windows 한국어 음성, 확정 녹음 전 임시)을 얹는다."""
from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw

from cuts import CORNER, CORNER_SPECIAL, CUTS, EXTRA, OVERLAY_VIDEO, name
from mglib import BG, INK, TEAL, font, S

ROOT = Path(__file__).resolve().parents[4]
VIDEO = ROOT / "output" / "video"
WORK = VIDEO / "final" / "work"
CLIPS = VIDEO / "clips"
W, H = 1920, 1080
TAG_COLOR = {"GEN": (120, 126, 134), "CAM": (30, 30, 30), "MG": (22, 107, 104), "REC": (190, 50, 45),
             "UNITY": (30, 90, 160)}


def ff(*args, quiet=True):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *map(str, args)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"ffmpeg 실패: {' '.join(cmd[:12])}...\n{r.stderr[-800:]}")


def wrap(text, size, maxw, bold=False):
    f = font(size, bold)
    lines, cur = [], ""
    for ch in text:
        if f.getlength(cur + ch) / S > maxw:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    return lines + ([cur] if cur else [])


def overlay_png(path, subtitle, corner, tag=None):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if subtitle:    # Apple 제품 영상 스타일: 화면 아래 가운데, 짧은 문장을 알약 모양 한 상자에
        size = 40
        lines = wrap(subtitle, size, 1380)
        f = ImageFont_scaled(font(size, False))
        lh = 58
        wmax = max(f.getlength(ln) for ln in lines)
        bw, bh = wmax + 90, lh * len(lines) + 30
        y1 = H - 64
        x0 = (W - bw) / 2
        d.rounded_rectangle([x0, y1 - bh, x0 + bw, y1], 34 if len(lines) == 1 else 28, fill=(18, 22, 26, 215))
        for i, ln in enumerate(lines):
            d.text((W / 2, y1 - bh + 15 + lh * i + lh / 2), ln, font=f, fill=(255, 255, 255, 255), anchor="mm")
    if corner:
        f = font(26, False)
        w = f.getlength(corner) / S
        d.rounded_rectangle([W - 70 - w - 36, 40, W - 70, 96], 16, fill=(20, 26, 30, 190))
        d.text((W - 70 - w - 18, 68), corner, font=ImageFont_scaled(f), fill=(255, 255, 255, 255), anchor="lm")
    im.save(path)


def extra_png(path, item):
    kind, xy, _ = item
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    teal = (22, 107, 104, 255)
    if kind == "circle":
        x, y, label = xy
        d.ellipse([x - 24, y - 24, x + 24, y + 24], fill=(22, 107, 104, 255), outline=(255, 255, 255, 255), width=3)
        d.text((x, y), label, font=ImageFont_scaled(font(30, True)), fill=(255, 255, 255, 255), anchor="mm")
    elif kind == "box":
        d.rounded_rectangle(list(xy), 18, outline=teal, width=7)
    elif kind == "underline":
        d.line(list(xy), fill=teal, width=7)
    im.save(path)


def ImageFont_scaled(f):
    # mglib의 글꼴은 2배 크기라 1배 캔버스에 그리려면 절반 크기 글꼴이 필요하다
    from PIL import ImageFont
    return ImageFont.truetype(f.path, f.size // S)


def placeholder_png(path, c):
    sheet, idx, dur, src, title, text, _ = c
    im = Image.new("RGB", (W, H), (22, 28, 38))
    d = ImageDraw.Draw(im)
    label = f"시트 {sheet} · 컷 {idx}" if sheet != "U" else f"보강 컷 {idx}"
    base = ImageFont_scaled(font(30))
    d.text((90, 90), label, font=base, fill=(150, 160, 172))
    tagcol = TAG_COLOR.get(src.split("+")[0], (90, 90, 90))
    x = 90
    for s_ in src.split("+"):
        col = TAG_COLOR.get(s_, (90, 90, 90))
        w = ImageFont_scaled(font(30, True)).getlength(s_) + 36
        d.rounded_rectangle([x, 150, x + w, 200], 25, fill=col)
        d.text((x + 18, 175), s_, font=ImageFont_scaled(font(30, True)), fill=(255, 255, 255), anchor="lm")
        x += w + 12
    f = ImageFont_scaled(font(52, True))
    y = 330
    for ln in wrap(title, 52, 1500, True):
        d.text((90, y), ln, font=f, fill=(255, 255, 255))
        y += 76
    d.text((90, H - 330), f"{dur}초 · 이 자리에 clips/{name(c)}.mp4 를 넣으면 자동으로 바뀝니다",
           font=ImageFont_scaled(font(28)), fill=(120, 190, 186))
    im.save(path)


def wav_len(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def build_segment(c, out):
    sheet, idx, dur, src, title, text, clip = c
    nm = name(c)
    WORK.mkdir(parents=True, exist_ok=True)
    corner = CORNER_SPECIAL.get((sheet, idx)) or CORNER.get(src)
    sub = WORK / f"{nm}_sub.png"
    overlay_png(sub, text, corner)
    user = CLIPS / f"{nm}.mp4"
    inputs, ss, speed = [], 0, 1.0
    if user.exists():
        vsrc, ss, kind = user, 0, "user"
    elif clip:
        vsrc, ss, kind = VIDEO / clip[0], clip[1], "made"
        speed = clip[2] if len(clip) > 2 else 1.0
    else:
        ph = WORK / f"{nm}_ph.png"
        placeholder_png(ph, c)
        vsrc, kind = ph, "placeholder"
    args = []
    if kind == "placeholder":
        args += ["-loop", "1", "-framerate", 30, "-t", dur, "-i", vsrc]
    else:
        args += ["-ss", ss, "-t", round(dur * speed + 0.5, 2), "-i", vsrc]
    args += ["-loop", "1", "-framerate", 30, "-t", dur, "-i", sub]
    extras = EXTRA.get((sheet, idx), []) if kind != "placeholder" else []
    for k, item in enumerate(extras):
        ep = WORK / f"{nm}_ex{k}.png"
        extra_png(ep, item)
        args += ["-loop", "1", "-framerate", 30, "-t", dur, "-i", ep]
    ovp = VIDEO / OVERLAY_VIDEO[(sheet, idx)] if (sheet, idx) in OVERLAY_VIDEO and (VIDEO / OVERLAY_VIDEO[(sheet, idx)]).exists() else None
    if ovp:
        args += ["-t", dur, "-i", ovp]
    wavp = WORK / f"{nm}.wav"
    has_a = wavp.exists() and text
    if has_a:
        args += ["-i", wavp]
    scale = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0xF7F4ED,"
             "setsar=1,setpts=(PTS-STARTPTS)/%s,fps=30,format=yuv420p,tpad=stop_mode=clone:stop_duration=60,trim=duration=%s,setpts=PTS-STARTPTS" % (speed, dur))
    fc = f"[0:v]{scale}[v];[v][1:v]overlay=0:0:format=auto[o0]"
    prev = "o0"
    if ovp:
        oi = 2 + len(extras)
        fc += (f";[{oi}:v]scale={W}:{H},fps=30,format=gbrp,setpts=PTS-STARTPTS[ov];"
               f"[o0]format=gbrp[b0];[b0][ov]blend=all_mode=screen[o0s]")
        prev = "o0s"
    for k, item in enumerate(extras):
        fc += f";[{prev}][{2 + k}:v]overlay=0:0:format=auto:enable='gte(t,{item[2]})'[x{k}]"
        prev = f"x{k}"
    fc += f";[{prev}]format=yuv420p[o]"
    aidx = 2 + len(extras) + (1 if ovp else 0)
    if has_a:
        L = wav_len(wavp)
        tempo = max(1.0, L / max(dur - 0.6, 1.0))
        tempo = min(tempo, 1.6)
        fc += f";[{aidx}:a]atempo={tempo:.3f},adelay=300|300,aresample=48000,apad,atrim=0:{dur}[a]"
        amap = ["-map", "[a]"]
        if L / tempo > dur - 0.3:
            print(f"  ! {nm}: 내레이션 {L:.1f}s > 컷 {dur}s (배속 {tempo:.2f}) — 자막/내레이션 줄이기 권장")
    else:
        fc += f";anullsrc=r=48000:cl=stereo,atrim=0:{dur}[a]"
        amap = ["-map", "[a]"]
    ff(*args, "-filter_complex", fc, "-map", "[o]", *amap, "-t", dur, "-c:v", "libx264", "-crf", 18, "-preset", "fast",
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", 48000, "-ac", 2, out)
    return kind


def make_tts():
    WORK.mkdir(parents=True, exist_ok=True)
    items = [{"file": str(WORK / f"{name(c)}.wav"), "text": c[5].removeprefix("(무전)").strip()} for c in CUTS if c[5]]
    (WORK / "tts.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    ps = WORK / "tts.ps1"
    ps.write_text(
        "Add-Type -AssemblyName System.Speech\n$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$s.SelectVoice('Microsoft Heami Desktop'); $s.Rate = 1\n"
        f"$items = Get-Content -Raw -Encoding UTF8 '{WORK / 'tts.json'}' | ConvertFrom-Json\n"
        "foreach ($i in $items) { $s.SetOutputToWaveFile($i.file); $s.Speak($i.text); $s.SetOutputToNull() }\n",
        encoding="utf-8-sig")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)], check=True)
    # 조장 무전 대사(AI 합성 음성): 무전기처럼 대역을 좁히고 살짝 눌러 준다
    for c in CUTS:
        if c[5].startswith("(무전)"):
            w = WORK / f"{name(c)}.wav"
            tmp = WORK / f"{name(c)}_radio.wav"
            ff("-i", w, "-af", "highpass=f=350,lowpass=f=2800,acompressor=threshold=-24dB:ratio=6,volume=1.4", tmp)
            tmp.replace(w)


def main():
    if "--tts" in sys.argv or not (WORK / "tts.json").exists():
        make_tts()
    segs, report = [], []
    for c in CUTS:
        out = WORK / f"{name(c)}.mp4"
        kind = build_segment(c, out)
        segs.append(out)
        report.append((name(c), c[2], kind))
        print(f"{name(c):<16}{c[2]:>3}s  {kind}", flush=True)
    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    final = VIDEO / "final" / "rough_cut.mp4"
    ff("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", final)
    total = sum(r[1] for r in report)
    made = sum(r[1] for r in report if r[2] != "placeholder")
    print(f"\n{final}\n총 {total}초 · 실제 클립 {made}초 · 자리표시 {total - made}초")
    (VIDEO / "final" / "cut_status.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
