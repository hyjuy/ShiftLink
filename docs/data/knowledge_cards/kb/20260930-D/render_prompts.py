"""Render prompts/<EQ>.md from prompt_template.md + plan.json and record sha256 in prompts/index.json."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
REL = "docs/data/knowledge_cards/kb/20260930-D"
MES_ID = {"CAU": "EQ-0003", "PDP": "EQ-0002"}
SAFETY = "docs/sources/safety"
SOURCES = {
    "CAU": ["원문: `docs/data/sources/CAU/compressed-air-ref-eng.pdf` — CEATI *Compressed Air Energy Efficiency Reference Guide* (118쪽)",
            "원문: `docs/data/sources/CAU/Manual-on-Energy-Efficiency.pdf` — UNEP/TERI *Energy Efficient Technologies and Best Practices in Steel Rolling Industries* (116쪽, 압축공기 절)",
            "한계: 두 자료 모두 에너지 효율 중심이다. 고장 진단·안전 근거가 부족한 슬롯은 skip한다",
            f"T5 보조: `{SAFETY}/산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf` 중 압축공기·공기압축기 관련 조항이 있으면 쓴다"],
    "PDP": ["원문: `docs/data/sources/PDP/15001-20000_16339.pdf` — UNIDO 1987 *Electrical and Mechanical Maintenance in Rolling Mills* (스캔 OCR, 품질 낮음 — 쪽마다 직접 대조)",
            "원문: `docs/data/sources/PDP/d2e0a4ea3d7e62b24193679803b73e6.pdf` — ABB *Electrical System Service* 소개 (8쪽, 브로슈어라 절차 근거로 약함)",
            f"안전(KOSHA): `{SAFETY}/E-7-2012 전기작업에 관한 기술지침.pdf`, `{SAFETY}/E-105-2011 전기작업안전에 관한 기술지침.pdf`, "
            f"`{SAFETY}/E-154-2016 전기작업계획서의 작성에 관한 기술지침.pdf`, `{SAFETY}/E-14-2012 감전시 응급조치에 관한 기술지침.pdf`, "
            f"`{SAFETY}/E-92-2017+접지설비+계획+및+유지관리에+관한+기술지침.pdf`",
            f"법령: `{SAFETY}/산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf`의 전기 관련 조항(정전 작업·충전부 방호 등)",
            f"`{SAFETY}/KOSHA_Guide(기술지침)_길라잡이.pdf`·지침 목록 PDF는 참고용이며 카드 근거로 쓰지 않는다"],
}

# Round 2: new sources + K-1305 retry. Round-1 prompts are re-rendered byte-identically (slots without "round").
R2_OUT = ("**2차 출력 경로(우선)**: 아래 '출력'·'검증' 절의 `out/{eq}.json`·`out/{eq}_notes.md`는 1차 결과이므로 **읽기만 하고 덮어쓰지 않는다**. "
          "이번 카드는 `out/{eq}-r2.json`·`out/{eq}-r2_notes.md`에 쓰고, 검증 명령의 파일 경로도 `out/{eq}-r2.json`으로 바꿔 실행한다")
NO_DUP = "중복 금지: 배치 D 1차 카드(`docs/data/knowledge_cards/kb/20260930-D/cards.json`, K-1301~1310)와 같은 내용이면 다른 후보를 고른다"
SOURCES_R2 = {
    "CAU": [f"원문(신규): `docs/data/sources/CAU/Kaishan_KRSP_V_Instruction_Manual.pdf` — Kaishan KRSP 급유식 스크루 압축기 사용설명서 (Table 8-1 Troubleshooting Guide: 증상·원인·조치, 5장 정비, 1장 안전)",
            f"원문(신규): `docs/data/sources/CAU/DOE_Improving_Compressed_Air_Sourcebook_v3.pdf` — US DOE *Improving Compressed Air System Performance* v3 (Fact Sheet 3 누설, 4 압력 강하, 8 정비)",
            *SOURCES["CAU"], NO_DUP, R2_OUT.format(eq="CAU"),
            "재시도 슬롯: S05 · K-1305 · T2 · 압축공기 압력 + 압축기 전류 등 `mes-card-signals.md`의 CAU 신호 조합 (1차에서 근거 없음으로 skip — Kaishan 고장 진단 표 등 신규 원문으로 다시 찾는다. 조합은 CAU 신호 안에서 근거에 맞게 바꿔도 된다. 그래도 없으면 skip)"],
    "PDP": [f"원문(신규): `docs/data/sources/PDP/USBR_FIST_3-16_Maintenance_of_Power_Circuit_Breakers_2020.pdf` — US Bureau of Reclamation FIST 3-16 (1.5 정비 중 안전, 2장 정비·진단 시험, 3장 배선용 차단기 MCCB, 4장 600V 이하 기중차단기)",
            f"원문(신규): `docs/data/sources/PDP/ABB_MaxSG_LV_Switchgear_1SXU900082M0201.pdf` — ABB MaxSG 저압 배전반 설치·정비 매뉴얼",
            f"안전(신규, KOSHA): `{SAFETY}/B-E-13-2026 수변전설비에 관한 기술지원규정.pdf`, `{SAFETY}/E-57-2020 배선차단기 일반관리에 관한 기술지침.pdf`, `{SAFETY}/E-40-2013 차단기 시험에 관한 기술지침.pdf`",
            *SOURCES["PDP"], NO_DUP, R2_OUT.format(eq="PDP")],
}

R3_OUT = R2_OUT.replace("-r2", "-r3").replace("2차", "3차").replace("1차 결과이므로", "1차 결과이므로(2차 `-r2` 파일도 마찬가지)")
SOURCES_R3 = {
    "CAU": [f"안전(KOSHA, 이번 라운드의 주 근거): `{SAFETY}/M-103-2017 공기압 시스템의 안전에 관한 기술지침.pdf`, `{SAFETY}/G-17-2017 압축공기의 안전한 사용에 관한 기술지침.pdf`",
            f"법령 보조: `{SAFETY}/산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf`",
            "중복 금지: 배치 D 1·2차 CAU 카드(`out/CAU.json`, `out/CAU-r2.json` — 특히 K-1304 안전밸브, K-1315)와 같은 내용이면 다른 조항을 고른다",
            R3_OUT.format(eq="CAU")],
}

plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
tpl = (HERE / "prompt_template.md").read_text(encoding="utf-8")
index = {"batch_id": plan["batch_id"], "seed": plan["seed"],
         "template_sha256": hashlib.sha256(tpl.encode("utf-8")).hexdigest(), "prompts": {}}
RETRY = {"CAU": ["K-1305"]}
jobs = [(eq, eq, 1, SOURCES[eq]) for eq in SOURCES] + [(f"{eq}-r2", eq, 2, SOURCES_R2[eq]) for eq in SOURCES_R2] + [(f"{eq}-r3", eq, 3, SOURCES_R3[eq]) for eq in SOURCES_R3]
for key, eq, rnd, sources in jobs:
    slots = [s for s in plan["slots"] if s["equipment"] == eq and s.get("round", 1) == rnd]
    if rnd == 2:
        slots += [s for s in plan["slots"] if s["card_id"] in RETRY.get(eq, [])]
    path = f"{REL}/prompts/{key}.md"
    text = (tpl.replace("{PROMPT_ID}", f"{plan['batch_id']}/{key}")
               .replace("{EQ}", eq)
               .replace("{MES_ID}", MES_ID[eq])
               .replace("{PROMPT_PATH}", path)
               .replace("{SLOTS}", "\n".join(f"- {s['slot']} · {s['card_id']} · {s['tacit_type']} · {s['hint']}" for s in slots))
               .replace("{SOURCES}", "\n".join(f"- {x}" for x in sources)))
    (HERE / "prompts" / f"{key}.md").write_text(text, encoding="utf-8", newline="\n")  # hash == file bytes
    index["prompts"][key] = {"path": path, "equipment": eq, "round": rnd,
                             "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                             "card_ids": [s["card_id"] for s in slots]}
old = HERE / "prompts" / "index.json"
if old.exists():
    for k, v in json.loads(old.read_text(encoding="utf-8")).items():
        if k not in index:
            index[k] = v
(HERE / "prompts" / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v["sha256"][:12] for k, v in index["prompts"].items()}))
