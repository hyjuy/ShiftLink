"""ShiftLink architecture diagrams D1-D10 (diagram-design layout grammar, white paper + pastel roles, Korean labels).

  python gen.py            # writes d1-*.html ... d10-*.html next to this file
D0 (d0-overview.html) is hand-written and is the style reference.
"""
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANS = "'Geist', 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"
MONO = "'Geist Mono', ui-monospace, monospace"
INK, MUTED, SUB = "#1e293b", "#475569", "#334155"
ROLES = {  # fill, stroke, legend label
    "person": ("#fde7ef", "#be185d", "사람"),
    "device": ("#e0f2fe", "#0369a1", "현장 장치"),
    "server": ("#ede9fe", "#6d28d9", "서버"),
    "model": ("#fef3c7", "#b45309", "모델"),
    "store": ("#dcfce7", "#15803d", "저장소"),
    "cloud": ("#f1f5f9", "#475569", "클라우드"),
    "step": ("#ffffff", "#94a3b8", "단계"),
    "exp": ("#ffffff", "#94a3b8", "실험 중"),
}
ARROW = {"default": "#475569", "link": "#2563eb", "accent": "#b45309", "exp": "#94a3b8"}


def width(text: str, size: int, mono: bool = False) -> float:
    w = 0.0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        w += 1.0 if unicodedata.east_asian_width(ch) in ("W", "F") else (0.62 if mono else 0.60)
    return w * size


def r4(v: float) -> int:
    return int(-(-v // 4) * 4)


def node(x, y, w, h, role, name, lines=(), strong=False, dashed=False, name_size=16):
    """lines: (text, kind) with kind ko | mono | model | ko-strong."""
    fill, stroke, _ = ROLES[role]
    sw = 2 if strong else 1
    dash = ' stroke-dasharray="5,4"' if dashed else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#ffffff"/>',
           f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}/>',
           f'<text x="{x + 16}" y="{y + 28}" font-family="{SANS}" font-size="{name_size}" font-weight="600" fill="{INK}">{name}</text>']
    ty = y + 50
    for text, kind in lines:
        if kind == "mono":
            out.append(f'<text x="{x + 16}" y="{ty}" font-family="{MONO}" font-size="12" fill="{MUTED}">{text}</text>')
        elif kind == "model":
            out.append(f'<text x="{x + 16}" y="{ty}" font-family="{SANS}" font-size="11" font-weight="600" fill="#b45309">{text}</text>')
        else:
            out.append(f'<text x="{x + 16}" y="{ty}" font-family="{SANS}" font-size="12" font-weight="500" fill="{MUTED}">{text}</text>')
        ty += 20
    for t, _ in lines:
        assert width(t, 12, False) <= w - 24 + 8, (name, t, width(t, 12), w)
    assert width(name, name_size) <= w - 24 + 4, (name, width(name, name_size), w)
    return "\n".join(out)


def chip(x, y, w, h, role, name, sub=None, sub_mono=False, dashed=False):
    """Small inner box (artifact chip / step) with 14px name and one 12px line."""
    fill, stroke, _ = ROLES[role]
    dash = ' stroke-dasharray="5,4"' if dashed else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="#ffffff"/>',
           f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1"{dash}/>',
           f'<text x="{x + 12}" y="{y + 20}" font-family="{SANS}" font-size="14" font-weight="600" fill="{INK}">{name}</text>']
    if sub:
        fam = MONO if sub_mono else SANS
        out.append(f'<text x="{x + 12}" y="{y + 38}" font-family="{fam}" font-size="12" font-weight="500" fill="{MUTED}">{sub}</text>')
        assert width(sub, 12, sub_mono) <= w - 16, (name, sub, w)
    assert width(name, 14) <= w - 16, (name, w)
    return "\n".join(out)


def zone(x, y, w, h, label, sub=None):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="none" stroke="#94a3b8" stroke-width="1" stroke-dasharray="6,4"/>',
           f'<text x="{x + 16}" y="{y + 24}" font-family="{SANS}" font-size="14" font-weight="600" fill="{MUTED}">{label}</text>']
    if sub:
        out.append(f'<text x="{x + 16 + width(label, 14) + 12}" y="{y + 24}" font-family="{SANS}" font-size="12" font-weight="500" fill="#64748b">{sub}</text>')
    return "\n".join(out)


def arrow(d, kind="default", dashed=False, sw=1.2, slug="dx", both=False):
    color = ARROW[kind]
    dash = ' stroke-dasharray="5,4"' if dashed else ""
    start = f' marker-start="url(#{slug}-{kind})"' if both else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{dash}{start} marker-end="url(#{slug}-{kind})"/>'


def label(cx, top, text, mono=False, color=SUB):
    """Masked arrow label, 16px tall mask starting at `top`; width from the per-character budget."""
    w = r4(width(text, 12, mono) + 8)
    fam = MONO if mono else SANS
    fill = "#2563eb" if mono and color == "link" else color
    return (f'<rect x="{cx - w // 2}" y="{top}" width="{w}" height="16" fill="#ffffff"/>'
            f'<text x="{cx}" y="{top + 12}" font-family="{fam}" font-size="12" font-weight="500" fill="{fill}" text-anchor="middle">{text}</text>')


def note(x, y, text, color="#64748b", size=12, anchor="start"):
    return f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="{size}" font-weight="500" fill="{color}" text-anchor="{anchor}">{text}</text>'


def legend(items, y=668):
    """items: role keys or ('line', kind, dashed, text)."""
    out = [f'<line x1="48" y1="{y - 20}" x2="1232" y2="{y - 20}" stroke="#e2e8f0" stroke-width="1"/>']
    x = 48
    for it in items:
        if isinstance(it, str) or it[0] == "box":
            role = it if isinstance(it, str) else it[1]
            fill, stroke, text = ROLES[role]
            text = text if isinstance(it, str) else it[2]
            it = role
            dash = ' stroke-dasharray="3,2"' if it == "exp" else ""
            out.append(f'<rect x="{x}" y="{y}" width="16" height="12" rx="2" fill="{fill}" stroke="{stroke}"{dash}/>')
            out.append(f'<text x="{x + 24}" y="{y + 11}" font-family="{SANS}" font-size="12" font-weight="500" fill="{SUB}">{text}</text>')
            x += 24 + r4(width(text, 12)) + 28
        else:
            _, kind, dashed, text = it
            dash = ' stroke-dasharray="5,4"' if dashed else ""
            out.append(f'<line x1="{x}" y1="{y + 6}" x2="{x + 32}" y2="{y + 6}" stroke="{ARROW[kind]}" stroke-width="1.2"{dash}/>')
            out.append(f'<text x="{x + 40}" y="{y + 11}" font-family="{SANS}" font-size="12" font-weight="500" fill="{SUB}">{text}</text>')
            x += 40 + r4(width(text, 12)) + 28
    return "\n".join(out)


def page(slug, eyebrow, title, desc, body):
    markers = "\n".join(
        f'<marker id="{slug}-{k}" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto-start-reverse"><polygon points="0 0, 8 3, 0 6" fill="{c}"/></marker>'
        for k, c in ARROW.items())
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&family=Noto+Serif:ital@0;1&family=Noto+Sans+KR:wght@400;500;600&family=Noto+Serif+KR:wght@400&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: {SANS}; background: #ffffff; color: {INK}; min-height: 100vh; display: flex; align-items: center;
           justify-content: center; padding: 3rem 2rem; }}
    .frame {{ max-width: 1320px; width: 100%; }}
    .diagram-container {{ width: 100%; overflow-x: auto; }}
    .eyebrow {{ font-size: 0.8rem; font-weight: 500; color: {MUTED}; margin-bottom: 0.5rem; }}
    svg {{ width: 100%; min-width: 1280px; display: block; }}
    @media print {{ .diagram-container {{ overflow-x: visible; }} svg {{ min-width: 0; }} }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{eyebrow}</p>
    <div class="diagram-container">
      <svg viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{slug}-title {slug}-desc">
        <title id="{slug}-title">{title}</title>
        <desc id="{slug}-desc">{desc}</desc>
        <defs>
{markers}
        </defs>
        <rect width="100%" height="100%" fill="#ffffff"/>
{body}
      </svg>
    </div>
  </div>
</body>
</html>
"""
    (HERE / f"{slug}.html").write_bytes(html.encode("utf-8"))
    return slug


# ---------------------------------------------------------------- D1 현장 배치도
def d1():
    s = "d1"
    A = lambda d, k="default", dashed=False: arrow(d, k, dashed, slug=s)
    b = []
    # zones (3): 현장, Jetson, 클라우드
    b.append(zone(40, 72, 552, 488, "현장"))
    b.append(zone(640, 72, 420, 488, "Jetson Orin Nano"))
    b.append(zone(1088, 352, 152, 160, "클라우드"))
    # host frames inside 현장
    b.append(f'<rect x="64" y="384" width="200" height="120" rx="6" fill="none" stroke="#0369a1" stroke-width="1"/>')
    b.append(note(80, 408, "Unity PC", "#0369a1", 14))
    b.append(f'<rect x="304" y="120" width="272" height="412" rx="6" fill="none" stroke="#0369a1" stroke-width="1"/>')
    b.append(note(320, 144, "라즈베리파이", "#0369a1", 14))
    b.append(note(320, 164, "카메라 · 터치스크린", "#64748b", 12))
    # arrows
    b.append(A("M248,456 H320"))                                              # Unity → 분류기
    b.append(A("M560,456 H600 Q608,456 608,448 V320 Q608,312 616,312 H664", "link"))   # 분류기 → MES
    b.append(A("M560,232 H616 Q624,232 624,240 V264 Q624,272 632,272 H664", "link"))   # PDA → MES
    b.append(A("M760,240 V172 Q760,164 768,164 H880", "accent"))              # MES → Ollama 답변
    b.append(A("M844,284 H880", "accent"))                                    # MES → Ollama 판정
    b.append(A("M754,344 V432"))                                              # MES → SQLite
    b.append(A("M844,472 H880"))                                              # SQLite → 업로더
    b.append(A("M1040,472 H1104"))                                            # 업로더 → Aiven
    # labels
    b.append(label(284, 432, "설비 사진"))
    b.append(label(648, 368, "설비 스캔"))
    b.append(label(588, 208, "/api/*", mono=True, color="#2563eb"))
    b.append(label(824, 140, "답변·임베딩"))
    b.append(label(792, 380, "적재"))
    b.append(label(1072, 448, "TLS", mono=True))
    # chips / nodes
    b.append(node(80, 420, 168, 72, "device", "가상 공장", [("2인 인수인계 시연", "ko")], name_size=14))
    b.append(node(320, 184, 240, 112, "device", "PDA 화면", [("Chromium 키오스크 · 프록시", "ko"), ("얼굴 로그인 YuNet·SFace", "ko"), (":8080", "mono")]))
    b.append(node(320, 404, 240, 104, "device", "설비 인식", [("MobileNetV3 INT8 · ONNX", "ko"), (":8090", "mono")]))
    b.append(node(664, 240, 180, 104, "server", "MES 서버", [("shiftlink-mes", "mono"), (":8000", "mono")]))
    b.append(node(880, 120, 160, 88, "model", "Ollama", [("답변 · 임베딩 모델", "ko"), (":11434", "mono")]))
    b.append(node(880, 240, 160, 88, "model", "Ollama 판정", [("판정 모델 전용", "ko"), (":11436", "mono")]))
    b.append(node(664, 432, 180, 80, "store", "SQLite", [("mock-mes.sqlite3", "mono")]))
    b.append(node(880, 432, 160, 80, "server", "업로더", [("30초 주기", "ko")]))
    b.append(node(1104, 392, 120, 104, "cloud", "Aiven", [("MySQL", "mono"), ("인계·질의 보관", "ko")]))
    b.append(legend(["device", "server", "model", "store", "cloud", ("line", "link", False, "HTTP · Tailscale"), ("line", "default", False, "내부 전달")]))
    return page(s, "배치도 · ShiftLink 아키텍처 D1", "ShiftLink 현장 배치도",
                "라즈베리파이의 PDA 화면과 설비 인식, Unity PC의 가상 공장이 Tailscale로 Jetson의 MES 서버에 연결되고, Jetson 안에서 Ollama 두 대와 SQLite, 업로더가 돌며 업로더가 Aiven MySQL로 기록을 올린다.",
                "\n".join(b))


# ---------------------------------------------------------------- D2 질의 한 건의 흐름 (sequence)
def d2():
    s = "d2"
    xs = {"pda": 136, "mes": 392, "eng": 648, "oll": 904, "db": 1144}
    heads = [("pda", "device", "PDA 화면", "라즈베리파이"), ("mes", "server", "MES 서버", ":8000"),
             ("eng", "model", "근거 기반 답변 엔진", "검색·판정·선별·답변"), ("oll", "model", "Ollama 모델", "임베딩·판정·답변"),
             ("db", "store", "SQLite", "질의 기록")]
    b = []
    top, bottom = 72, 628
    for k, role, name, sub in heads:     # lifelines first
        b.append(f'<line x1="{xs[k]}" y1="{top + 64}" x2="{xs[k]}" y2="{bottom}" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="4,4"/>')
    msgs = [  # (y, from, to, text, kind, dashed)
        (168, "pda", "mes", "① 질문 · 선택한 설비", "link", False),
        (264, "mes", "eng", "③ 질문 + MES 관측·경보", "accent", False),
        (312, "eng", "oll", "④ 검색어 임베딩", "default", False),
        (360, "eng", "oll", "⑤ 후보 카드별 판정 점수", "default", False),
        (456, "eng", "oll", "⑦ 남은 카드로 답변 생성", "default", False),
        (504, "eng", "mes", "⑧ 답변 · 인용 · 안전 카드", "accent", True),
        (552, "mes", "db", "⑨ 질의·근거 기록", "default", False),
        (600, "mes", "pda", "⑩ 답변 표시", "link", True),
    ]
    for y, f, t, text, kind, dashed in msgs:
        x1, x2 = xs[f], xs[t]
        x2e = x2 - 4 if x2 > x1 else x2 + 4
        b.append(arrow(f"M{x1},{y} H{x2e}", kind, dashed, slug=s))
        b.append(label((x1 + x2) // 2, y - 24, text))
    # self messages: ② on MES, ⑥ on engine
    b.append(arrow("M392,200 H440 Q448,200 448,208 V224 Q448,232 440,232 H396", "default", slug=s))
    b.append(note(460, 222, "② MES 관측·경보 붙이기", SUB))
    b.append(arrow("M648,384 H696 Q704,384 704,392 V400 Q704,408 696,408 H652", "default", slug=s))
    b.append(note(716, 404, "⑥ 기준 미달 제외 · 확신 시 바로 답변", SUB))
    for k, role, name, sub in heads:     # heads last
        w = 192 if k == "eng" else 168
        b.append(node(xs[k] - w // 2, top, w, 64, role, name, [(sub, "mono" if sub.startswith(":") else "ko")], strong=(k == "eng"), name_size=15 if k == "eng" else 16))
    b.append(legend(["device", "server", "model", "store", ("line", "default", False, "요청"), ("line", "default", True, "응답"), ("line", "link", False, "HTTP")]))
    return page(s, "시퀀스 · ShiftLink 아키텍처 D2", "질의 한 건의 흐름",
                "PDA에서 보낸 질문이 MES 서버에서 관측·경보를 붙여 답변 엔진으로 가고, 엔진이 Ollama로 임베딩·판정·답변을 거쳐 답과 인용을 돌려주면 MES가 기록하고 PDA에 표시한다.",
                "\n".join(b))


def diamond(cx, cy, hw, hh, title, sub, role="step"):
    fill, stroke, _ = ROLES[role]
    pts = f"{cx - hw},{cy} {cx},{cy - hh} {cx + hw},{cy} {cx},{cy + hh}"
    return (f'<polygon points="{pts}" fill="#ffffff"/>'
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
            f'<text x="{cx}" y="{cy - 2}" font-family="{SANS}" font-size="14" font-weight="600" fill="{INK}" text-anchor="middle">{title}</text>'
            f'<text x="{cx}" y="{cy + 16}" font-family="{SANS}" font-size="12" font-weight="500" fill="{MUTED}" text-anchor="middle">{sub}</text>')


# ---------------------------------------------------------------- D3 근거 기반 답변 엔진 판단 로직 (flowchart)
def d3():
    s = "d3"
    A = lambda d, k="default", dashed=False: arrow(d, k, dashed, slug=s)
    b = []
    # arrows first
    b.append(A("M224,200 H264"))                                   # 입력 → 검색
    b.append(A("M464,200 H504"))                                   # 검색 → 판정
    b.append(A("M704,200 H732"))                                   # 판정 → 남은 카드?
    b.append(A("M868,200 H952"))                                   # 남은 카드? 예 → 확신?
    b.append(A("M800,252 V368"))                                   # 아니오 → 보류
    b.append(A("M1020,252 V352"))                                  # 확신? 아니오 → 작성 (모델 판단)
    b.append(A("M1088,200 H1144 Q1152,200 1152,208 V372 Q1152,380 1144,380 H1100", "accent"))   # 예 → 작성 (반드시 답)
    b.append(A("M940,396 H864"))                                   # 작성 → 보류
    b.append(A("M1020,440 V520", "accent"))                        # 작성 → 검증
    b.append(A("M1100,560 H1136", "accent"))                       # 검증 → 출력
    b.append(A("M940,568 H792 Q784,568 784,560 V440"))             # 검증 실패 → 보류
    b.append(A("M664,404 H704", "exp", True))                      # 실험 주석 → 보류
    # labels
    b.append(label(910, 176, "예"))
    b.append(label(800, 300, "아니오"))
    b.append(label(1020, 296, "애매 · 모델 판단"))
    b.append(label(1152, 280, "확신 · 반드시 답"))
    b.append(label(902, 372, "보류 판단"))
    b.append(label(1040, 472, "답"))
    b.append(label(852, 576, "검증 실패"))
    # step captions above the selection diamonds (D0 numbering)
    b.append(note(910, 124, "③ 선별", "#92400e", 14, "middle"))
    # nodes
    b.append(node(48, 160, 176, 80, "server", "질문 + MES 관측", [("MES 서버에서", "ko")], name_size=15))
    b.append(node(264, 148, 200, 104, "model", "① 검색", [("후보 카드 최대 8개", "ko"), ("다른 설비 인계 기록 제외", "ko"), ("EmbeddingGemma 300M", "model")]))
    b.append(node(504, 148, 200, 104, "model", "② 판정", [("카드마다 관련도 점수", "ko"), ("", "ko"), ("EXAONE 3.5 판정 모델", "model")]))
    b.append(diamond(800, 200, 68, 52, "남은 카드?", "점수 ≥ 0.3"))
    b.append(diamond(1020, 200, 68, 52, "확신 높음?", "최고 ≥ 0.9"))
    b.append(node(940, 352, 160, 88, "model", "④ 답변 작성", [("남은 카드로 · 인용", "ko"), ("EXAONE 3.5 답변 모델", "model")], strong=True))
    b.append(node(704, 368, 160, 72, "step", "답 보류", [("해당 지식 없음 표시", "ko")]))
    b.append(node(940, 520, 160, 80, "server", "검증", [("인용·숫자 확인", "ko"), ("안전 조건 덧붙임", "ko")]))
    b.append(node(1136, 520, 104, 80, "device", "답변 출력", [("PDA 표시", "ko")], name_size=15))
    # experimental annotation (dashed): not part of the running route
    b.append(node(264, 360, 400, 88, "exp", "실험 중", [("[MES] 블록을 답변 모델 입력에 추가", "ko"), ("근거 0개여도 MES 관측만으로 답변", "ko")], dashed=True, name_size=14))
    b.append(legend(["server", "model", "step", "device", "exp", ("line", "accent", False, "답이 나가는 길"), ("line", "default", False, "흐름")]))
    return page(s, "순서도 · ShiftLink 아키텍처 D3", "근거 기반 답변 엔진의 판단",
                "질문과 MES 관측으로 후보 카드를 검색하고 판정 모델이 점수를 매긴 뒤, 남은 카드가 없으면 보류하고, 확신이 높으면 반드시 답하며, 애매하면 답변 모델이 보류 여부를 정하고, 검증을 통과한 답만 PDA에 나간다.",
                "\n".join(b))


# ---------------------------------------------------------------- D4 MES
def d4():
    s = "d4"
    A = lambda d, k="default", dashed=False: arrow(d, k, dashed, slug=s)
    b = []
    b.append(A("M320,340 H432"))                                                   # 엔진 → API
    b.append(A("M720,160 H488 Q480,160 480,168 V276", "link"))                    # PDA → API
    b.append(A("M624,288 H720"))                                                   # API → 연결
    b.append(A("M624,360 H676 Q684,360 684,368 V436 Q684,444 692,444 H720"))     # API → 분석
    b.append(A("M624,388 H656 Q664,388 664,396 V564 Q664,572 672,572 H720"))     # API → 카드 초안
    b.append(A("M528,404 V520"))                                                   # API → SQLite
    b.append(A("M944,288 H1008", "accent"))                                        # 연결 → 답변 엔진
    b.append(A("M944,572 H1008", "default", True))                                 # 카드 초안 → 지식카드
    b.append(label(376, 316, "스냅샷·이벤트"))
    b.append(label(592, 136, "/api/*", mono=True, color="#2563eb"))
    b.append(label(548, 448, "저장"))
    b.append(label(976, 264, "요청"))
    b.append(label(976, 548, "검수 후"))
    b.append(node(64, 276, 256, 128, "server", "설비 상태 엔진", [("센서 신호 · 고장 시나리오", "ko"), ("경보 판정 · 증상", "ko"), ("설비 10대 카탈로그", "ko")]))
    b.append(node(432, 276, 192, 128, "server", "MES API", [(":8000", "mono"), ("/api/state · events", "mono"), ("/api/query · handover", "mono")], strong=True))
    b.append(node(720, 124, 224, 72, "device", "PDA 화면", [("상태 · 질의 · 인계 · 근무일지", "ko")]))
    b.append(node(720, 252, 224, 72, "server", "답변 엔진 연결", [("관측·경보를 질의에 첨부", "ko")]))
    b.append(node(720, 408, 224, 72, "server", "분석 대시보드", [("정지 손실 · 반복 증상", "ko")]))
    b.append(node(720, 536, 224, 72, "server", "지식 후보 검토", [("현장 해결 기록 → 카드 초안", "ko")]))
    b.append(node(1008, 252, 232, 72, "model", "근거 기반 답변 엔진", [("검색 · 판정 · 선별 · 답변", "ko")]))
    b.append(node(1008, 536, 232, 72, "store", "지식카드", [("검수된 카드만 검색에 반영", "ko")]))
    b.append(node(432, 520, 192, 72, "store", "SQLite", [("기록 · 인계 outbox", "ko")]))
    b.append(legend(["server", "device", "model", "store", ("line", "link", False, "HTTP"), ("line", "default", False, "전달"), ("line", "default", True, "검수 후 반영")]))
    return page(s, "구성도 · ShiftLink 아키텍처 D4", "MES 구성",
                "설비 상태 엔진이 센서 신호와 경보를 만들어 MES API로 내보내고, MES API는 PDA 화면, 답변 엔진 연결, 분석 대시보드, 지식 후보 검토로 데이터를 나누며 기록은 SQLite에 저장하고 검수된 카드만 지식카드에 반영된다.",
                "\n".join(b))


# ---------------------------------------------------------------- D5 PDA 사용 흐름 (user journey, Unity 2인 시연)
def d5():
    s = "d5"
    A = lambda d, k="default", dashed=False: arrow(d, k, dashed, slug=s)
    b = []
    b.append(zone(40, 80, 1200, 168, "작업자 A", "이번 조"))
    b.append(zone(40, 352, 1200, 168, "작업자 B", "다음 조"))
    xs = [64, 256, 448, 640, 832, 1024]
    for x in xs[:-1]:
        b.append(A(f"M{x + 160},172 H{x + 188}", "accent" if x == 448 else "default"))
    b.append(A("M1104,216 V300 Q1104,308 1096,308 H728 Q720,308 720,316 V396", "link"))
    b.append(A("M608,444 H636"))
    b.append(A("M800,444 H828"))
    b.append(label(912, 300, "인계 전달"))
    steps = [("① 얼굴 로그인", [("안면 인식", "ko"), ("실패 시 사번 로그인", "ko")], "device", False),
             ("② 설비 선택", [("촬영 스캔", "ko"), ("또는 설비 목록", "ko")], "device", False),
             ("③ 설비 확인", [("MES 상태 · 센서값", "ko"), ("정비 이력 · 인계", "ko")], "device", False),
             ("④ 증상 질의", [("근거 카드로 답", "ko"), ("없으면 답 보류", "ko")], "model", True),
             ("⑤ 조치 기록", [("조치 입력", "ko"), ("결과 확인", "ko")], "device", False),
             ("⑥ 근무일지·인계", [("센서값 불러오기", "ko"), ("전송 대기 후 업로드", "ko")], "device", False)]
    for x, (name, lines, role, strong) in zip(xs, steps):
        b.append(node(x, 128, 160, 88, role, name, lines, strong=strong, name_size=15))
    for x, name, lines in [(448, "① 얼굴 로그인", [("같은 PDA 화면", "ko")]),
                           (640, "② 인계 사항 확인", [("받은 메모 · 센서값", "ko")]),
                           (832, "③ 설비 확인", [("인계 받은 설비부터", "ko")])]:
        b.append(node(x, 400, 160, 88, "device", name, lines, name_size=15))
    b.append(note(64, 584, "Unity 가상 공장에서 플레이어 2명이 캐릭터로 교대 · 인수인계를 시연한다. 가상 설비 화면은 ② 설비 선택의 촬영 입력이 된다."))
    b.append(legend([("box", "device", "PDA 화면"), ("box", "model", "답변 엔진을 쓰는 단계"), ("line", "default", False, "화면 이동"), ("line", "link", False, "다음 조로 전달")]))
    return page(s, "사용 흐름 · ShiftLink 아키텍처 D5", "PDA 사용 흐름",
                "작업자 A가 얼굴 로그인, 설비 선택, 설비 확인, 증상 질의, 조치 기록, 근무일지·인계 작성을 거치면 인계가 다음 조 작업자 B에게 전달되고, B는 로그인 뒤 인계 사항과 설비를 확인한다.",
                "\n".join(b))


# ---------------------------------------------------------------- D6 얼굴인식 (process)
def d6():
    s = "d6"
    A = lambda d, k="default", dashed=False: arrow(d, k, dashed, slug=s)
    b = []
    b.append(zone(40, 64, 1200, 464, "라즈베리파이", "얼굴 이미지와 임베딩은 기기 밖으로 나가지 않는다"))
    b.append(note(64, 124, "로그인", "#0369a1", 14))
    b.append(note(264, 388, "등록", "#0369a1", 14))
    xs = [64, 264, 464, 664, 864, 1064]
    for x in xs[:-1]:
        b.append(A(f"M{x + 160},184 H{x + 196}", "accent" if x in (664, 864) else "default"))
    b.append(A("M344,400 V232"))                                   # 등록 촬영 → 검출
    b.append(A("M544,228 V396"))                                   # 임베딩 → 저장 (등록 때)
    b.append(A("M624,444 H736 Q744,444 744,436 V232"))             # 저장 → 비교
    b.append(A("M944,228 V396", "default", True))                  # 판정 실패 → 사번 로그인
    b.append(label(544, 300, "등록 때"))
    b.append(label(744, 300, "등록 임베딩"))
    b.append(label(944, 300, "실패"))
    b.append(node(64, 140, 160, 88, "device", "카메라 프레임", [("PDA 화면 카메라", "ko"), (":8080 로컬 프록시", "ko")], name_size=15))
    b.append(node(264, 140, 160, 88, "model", "얼굴 검출·정렬", [("YuNet 2023mar", "model"), ("검출 점수 ≥ 0.8", "ko")], name_size=15))
    b.append(node(464, 140, 160, 88, "model", "얼굴 임베딩", [("SFace 2021dec", "model"), ("얼굴 특징 벡터", "ko")], name_size=15))
    b.append(node(664, 140, 160, 88, "server", "1:1 비교", [("코사인 ≥ 0.363", "ko"), ("본인 등록과만 비교", "ko")], strong=True, name_size=15))
    b.append(node(864, 140, 160, 88, "server", "프레임 판정", [("5장 중 3장 이상", "ko"), ("한 장 우연 통과 방지", "ko")], name_size=15))
    b.append(node(1064, 140, 152, 88, "device", "로그인 완료", [("홈 화면", "ko")], name_size=15))
    b.append(node(264, 400, 160, 88, "person", "얼굴 등록", [("사번 + 얼굴 8장", "ko"), ("동의 철회 시 삭제", "ko")], name_size=15))
    b.append(node(464, 400, 160, 88, "store", "임베딩 저장", [("사번.npz · 권한 600", "ko"), ("원본 이미지 저장 안 함", "ko")], name_size=15))
    b.append(node(864, 400, 160, 88, "device", "사번 로그인", [("사번 · 비밀번호", "ko")], name_size=15))
    b.append(legend(["device", "model", "server", "store", "person", ("line", "accent", False, "통과 판단"), ("line", "default", True, "실패 시")]))
    return page(s, "처리 과정 · ShiftLink 아키텍처 D6", "얼굴 로그인",
                "PDA 카메라 프레임에서 YuNet으로 얼굴을 찾고 SFace로 임베딩을 만든 뒤 본인 등록 임베딩과 코사인 0.363 이상인지 비교하고, 5장 중 3장 이상 통과하면 로그인한다. 등록 때는 임베딩만 저장하고 원본 이미지는 저장하지 않는다.",
                "\n".join(b))


# ---------------------------------------------------------------- D7 설비 인식 (process, PC 학습 → 파이 실시간)
def d7():
    s = "d7"
    A = lambda d, k="default", dashed=False: arrow(d, k, dashed, slug=s)
    b = []
    b.append(zone(40, 64, 928, 168, "PC", "학습"))
    b.append(zone(280, 352, 488, 168, "라즈베리파이", "실시간 분류"))
    b.append(zone(816, 352, 216, 168, "Jetson"))
    b.append(A("M264,156 H300"))
    b.append(A("M504,156 H540"))
    b.append(A("M744,156 H780"))
    b.append(A("M624,200 V396"))
    b.append(A("M504,444 H540"))
    b.append(A("M744,444 H836", "accent"))
    b.append(A("M1012,444 H1052", "link"))
    b.append(label(624, 296, "INT8 모델 배포"))
    b.append(label(792, 420, "클래스명"))
    b.append(node(64, 112, 200, 88, "step", "학습 사진", [("웹캠 촬영 · 숫자키 1~6", "ko"), ("Unity 가상 설비 사진", "ko")]))
    b.append(node(304, 112, 200, 88, "model", "전이학습", [("MobileNetV3-Small", "model"), ("6클래스 → ONNX", "ko")]))
    b.append(node(544, 112, 200, 88, "model", "양자화", [("INT8 정적 양자화", "ko"), ("보정은 학습 사진만", "ko")]))
    b.append(node(784, 112, 160, 88, "step", "평가", [("클래스별 정확도", "ko"), ("1장 추론 시간", "ko")]))
    b.append(node(304, 400, 200, 88, "device", "입력", [("카메라 프레임", "ko"), ("Unity 사진 수신 :8090", "ko")]))
    b.append(node(544, 400, 200, 88, "model", "실시간 분류", [("신뢰도 ≥ 0.8", "ko"), ("같은 결과 5프레임 연속", "ko")], strong=True))
    b.append(node(840, 400, 172, 88, "server", "MES 서버", [("/api/equipment/scan", "mono"), ("클래스명만 받음", "ko")], name_size=15))
    b.append(node(1056, 400, 168, 88, "device", "PDA 설비 선택", [("스캔한 설비로 이동", "ko")], name_size=15))
    b.append(note(64, 600, "클래스 6개: HPU · GR · RT · CV · CAU · PDP. 사진은 파이에서만 처리하고 Jetson에는 클래스명만 보낸다."))
    b.append(legend(["step", "model", "device", "server", ("line", "accent", False, "확정 결과 전송"), ("line", "link", False, "HTTP")]))
    return page(s, "처리 과정 · ShiftLink 아키텍처 D7", "설비 인식",
                "PC에서 웹캠·Unity 사진으로 MobileNetV3-Small을 전이학습해 INT8로 양자화하고, 라즈베리파이가 카메라나 Unity 사진을 실시간 분류해 신뢰도 0.8 이상이 5프레임 이어지면 클래스명만 Jetson MES 서버로 보내 PDA가 그 설비를 선택한다.",
                "\n".join(b))


# ---------------------------------------------------------------- D8 데이터 적재
def d8():
    s = "d8"
    A = lambda d, k="default", dashed=False: arrow(d, k, dashed, slug=s)
    b = []
    b.append(zone(40, 56, 544, 472, "SQLite", "Jetson · mock-mes.sqlite3"))
    b.append(zone(936, 56, 304, 472, "Aiven MySQL", "클라우드"))
    b.append(A("M560,148 H584 Q592,148 592,156 V200 Q592,208 600,208 H636"))
    b.append(A("M560,276 H584 Q592,276 592,268 V256 Q592,248 600,248 H636", "accent"))
    b.append(A("M880,208 H900 Q908,208 908,200 V156 Q908,148 916,148 H956"))
    b.append(A("M880,248 H900 Q908,248 908,256 V268 Q908,276 916,276 H956", "accent"))
    b.append(A("M1088,320 V412"))
    b.append(label(908, 172, "TLS", mono=True))
    b.append(label(1088, 360, "조회만"))
    b.append(node(64, 104, 232, 88, "store", "MES 실행", [("runs · snapshots", "mono"), ("runtime_events", "mono")]))
    b.append(node(64, 232, 232, 88, "store", "사건", [("incidents", "mono"), ("incident_records", "mono")]))
    b.append(node(64, 360, 232, 108, "store", "지식 후보", [("card_drafts", "mono"), ("card_draft_records", "mono"), ("card_draft_reviews", "mono")]))
    b.append(node(320, 104, 240, 88, "store", "질의 기록", [("query_log", "mono"), ("query_evidence", "mono")]))
    b.append(node(320, 232, 240, 108, "store", "인계 · 근무일지", [("handover_outbox", "mono"), ("work_report_*", "mono"), ("resolution_sessions", "mono")], strong=True))
    b.append(note(320, 392, "왼쪽 열은 Jetson에만 남는다.", "#64748b"))
    b.append(note(320, 412, "오른쪽 열의 미전송 행만 올린다.", "#64748b"))
    b.append(node(640, 168, 240, 128, "server", "업로더", [("30초 주기 · 미전송 행만", "ko"), ("연결 실패 → 다음 주기 재시도", "ko"), ("해시가 다르면 conflict 보류", "ko")], strong=True))
    b.append(note(640, 328, "현장 해결 기록이 실린 인계는", "#64748b"))
    b.append(note(640, 348, "기능 확정 전까지 로컬에 둔다 (10/13).", "#64748b"))
    b.append(node(960, 104, 256, 88, "cloud", "질의 업로드", [("query_upload", "mono"), ("설비 · 지연 · 지식 없음 여부", "ko")]))
    b.append(node(960, 232, 256, 88, "cloud", "인계 업로드", [("handover_upload", "mono"), ("인계 본문 · 근무일지", "ko")]))
    b.append(node(960, 416, 256, 88, "server", "인계 보드", [(":8810", "mono"), ("다음 조 인계 목록 · 읽기 전용", "ko")]))
    b.append(legend(["store", "server", "cloud", ("line", "accent", False, "인계가 올라가는 길"), ("line", "default", False, "전달")]))
    return page(s, "데이터 적재 · ShiftLink 아키텍처 D8", "데이터 적재",
                "Jetson SQLite의 질의 기록과 인계·근무일지 테이블에서 미전송 행만 업로더가 30초마다 Aiven MySQL의 query_upload와 handover_upload로 올리고, 연결이 끊기면 다음 주기에 다시 시도하며 해시가 다르면 보류한다. 인계 보드는 handover_upload를 읽기만 한다.",
                "\n".join(b))


# ---------------------------------------------------------------- D9 모듈 구성도 (dependency graph)
def d9():
    s = "d9"
    A = lambda d, k="default", both=False: arrow(d, k, slug=s, both=both)
    b = []
    b.append(zone(40, 48, 236, 536, "라즈베리파이에서 실행"))
    b.append(A("M620,184 V224 Q620,232 612,232 H428 Q420,232 420,240 V284", "accent", both=True))   # mes ↔ rag2
    b.append(A("M660,184 V476"))                                                                     # mes → agent
    b.append(A("M700,184 V224 Q700,232 708,232 H892 Q900,232 900,240 V284"))                         # mes → data
    b.append(A("M760,128 H1032 Q1040,128 1040,136 V516 Q1040,524 1032,524 H1004"))                   # mes → rag
    b.append(A("M560,128 H300 Q292,128 292,136 V516 Q292,524 300,524 H316"))                         # mes → edge
    b.append(A("M460,376 V416 Q460,424 468,424 H612 Q620,424 620,432 V476", "accent"))               # rag2 → agent
    b.append(A("M860,376 V416 Q860,424 852,424 H708 Q700,424 700,432 V476"))                         # data → agent
    b.append(A("M520,524 H556"))                                                                     # edge → agent
    b.append(A("M760,524 H796", both=True))                                                          # agent ↔ rag
    b.append(A("M142,184 V284"))                                                                     # pda → face
    b.append(A("M232,140 H244 Q252,140 252,148 V516 Q252,524 244,524 H236"))                         # pda → vision
    b.append(node(52, 96, 180, 88, "device", "PDA 키오스크", [("shiftlink.pda", "mono"), ("286줄", "ko")]))
    b.append(node(52, 288, 180, 88, "device", "얼굴 로그인", [("shiftlink.face", "mono"), ("397줄", "ko")]))
    b.append(node(52, 480, 180, 88, "device", "설비 인식", [("shiftlink.vision", "mono"), ("810줄", "ko")]))
    b.append(node(560, 96, 200, 88, "server", "MES 서버·화면", [("shiftlink.mes", "mono"), ("5,928줄", "ko")]))
    b.append(node(320, 288, 200, 88, "model", "근거 기반 답변 엔진", [("shiftlink.rag2", "mono"), ("985줄", "ko")], strong=True))
    b.append(node(800, 288, 200, 88, "step", "카드·학습 데이터 도구", [("shiftlink.data", "mono"), ("1,109줄", "ko")], name_size=15))
    b.append(node(320, 480, 200, 88, "model", "Ollama 연결", [("shiftlink.edge", "mono"), ("537줄", "ko")]))
    b.append(node(560, 480, 200, 88, "server", "질의 라우팅·검증", [("shiftlink.agent", "mono"), ("1,690줄", "ko")]))
    b.append(node(800, 480, 200, 88, "server", "카드 검색 v1", [("shiftlink.rag", "mono"), ("819줄", "ko")]))
    b.append(note(1064, 300, "A → B: A가 B를 import", SUB))
    b.append(note(1064, 324, "import 한 번뿐인 연결", "#64748b"))
    b.append(note(1064, 344, "data→rag, rag↔edge 생략", "#64748b"))
    b.append(note(1064, 368, "작은 모듈 communication,", "#64748b"))
    b.append(note(1064, 388, "unity_demo 생략", "#64748b"))
    b.append(legend([("box", "device", "파이 쪽"), ("box", "server", "서버·공통"), ("box", "model", "답변 엔진·모델 연결"), ("box", "step", "오프라인 도구"),
                     ("line", "accent", False, "답변 엔진 경로"), ("line", "default", False, "import")]))
    return page(s, "의존 관계 · ShiftLink 아키텍처 D9", "모듈 구성",
                "shiftlink 패키지에서 mes가 rag2, agent, rag, edge, data를 불러 쓰고 rag2와 mes는 서로를 import한다. 라즈베리파이 쪽 pda는 face와 vision만 불러 쓴다.",
                "\n".join(b))


# ---------------------------------------------------------------- D10 모델 개발·평가 (swimlane)
def d10():
    s = "d10"
    A = lambda d, k="default": arrow(d, k, slug=s)
    b = []
    lanes = [("사용자", 56), ("Claude", 160), ("Codex", 264), ("GPU 인스턴스", 368), ("Jetson", 472)]
    for i, (name, y) in enumerate(lanes):
        if i % 2 == 0:
            b.append(f'<rect x="40" y="{y}" width="1200" height="104" fill="#f8fafc"/>')
        b.append(note(56, y + 56, name, INK, 14))
    b.append('<line x1="40" y1="576" x2="1240" y2="576" stroke="#e2e8f0" stroke-width="1"/>')
    b.append('<line x1="168" y1="56" x2="168" y2="576" stroke="#e2e8f0" stroke-width="1"/>')
    b.append(A("M368,108 H776 Q784,108 784,116 V188 Q784,196 792,196 H812"))           # 평가 셋 → 평가
    b.append(A("M280,252 V412 Q280,420 288,420 H396"))                                  # 데이터 → LoRA
    b.append(A("M576,420 H604"))                                                         # LoRA → GGUF
    b.append(A("M784,420 H896 Q904,420 904,412 V256"))                                  # GGUF → 평가
    b.append(A("M696,276 V236 Q696,228 704,228 H812"))                                  # Codex 후보 → 평가
    b.append(A("M904,172 V116 Q904,108 912,108 H1020", "accent"))                       # 평가 → 블라인드 판정
    b.append(A("M1112,148 V480", "accent"))                                             # 판정 → Jetson
    b.append(label(1112, 304, "채택 시"))
    b.append(label(560, 100, "문항은 해시만 공유", color="#64748b"))
    b.append(node(192, 68, 176, 80, "person", "평가 셋 확정", [("60문항 동결", "ko"), ("Codex에 비공개", "ko")], name_size=15))
    b.append(node(192, 172, 176, 80, "step", "학습 데이터", [("카드에서 합성 질문", "ko"), ("판정 점수 0~3", "ko")], name_size=15))
    b.append(node(608, 276, 176, 80, "step", "후보 개선", [("프롬프트 · 코드", "ko"), ("평가 셋은 보지 않음", "ko")], name_size=15))
    b.append(node(400, 380, 176, 80, "model", "LoRA 학습", [("EXAONE 3.5 2.4B", "model"), ("r=16 · 3에폭", "ko")], name_size=15))
    b.append(node(608, 380, 176, 80, "model", "GGUF 변환", [("Q4_K_M · 1.5GB", "ko"), ("llama.cpp", "ko")], name_size=15))
    b.append(node(816, 172, 176, 80, "step", "평가 · 채점", [("사전 등록 규칙대로", "ko"), ("이름 가린 비교표", "ko")], name_size=15))
    b.append(node(1024, 68, 176, 80, "person", "블라인드 판정", [("X/Y 중 나은 쪽", "ko"), ("채택 여부 결정", "ko")], strong=True, name_size=15))
    b.append(node(1024, 484, 176, 80, "server", "등록 · 적용", [("ollama create", "mono"), ("시연 서버 설정", "ko")], name_size=15))
    b.append(note(192, 604, "수치는 판정 모델(10/6 채택) 기준이다. 답변 모델도 같은 과정을 거쳤다."))
    b.append(legend([("box", "person", "사람 판정"), ("box", "step", "에이전트 작업"), ("box", "model", "학습 산출물"), ("box", "server", "배포 장치"),
                     ("line", "accent", False, "채택까지 가는 길"), ("line", "default", False, "전달")]))
    return page(s, "스윔레인 · ShiftLink 아키텍처 D10", "모델 개발과 평가",
                "Claude가 카드로 학습 데이터를 만들면 GPU 인스턴스에서 EXAONE 3.5 2.4B를 LoRA로 학습해 GGUF로 바꾸고, Claude가 사용자가 동결한 평가 셋과 Codex의 후보 개선을 사전 등록 규칙대로 채점한 뒤, 사용자가 이름 가린 비교로 채택하면 Jetson에 등록한다.",
                "\n".join(b))


if __name__ == "__main__":
    import sys
    which = sys.argv[1:] or ["d1", "d2"]
    for w in which:
        print(globals()[w]())
