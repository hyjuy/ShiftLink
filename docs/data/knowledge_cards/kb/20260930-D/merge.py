"""Merge out/<EQ>.json -> cards.json, pin prompt_version to path@sha256, validate, write README trace table."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from shiftlink.agent.schemas import KnowledgeCard  # noqa: E402

index = json.loads((HERE / "prompts" / "index.json").read_text(encoding="utf-8"))
plan = {s["card_id"]: s for s in json.loads((HERE / "plan.json").read_text(encoding="utf-8"))["slots"] if not s.get("dropped")}

cards, rows, problems = [], [], []
for key, meta in index["prompts"].items():
    eq = meta.get("equipment", key)  # round-2 prompts are keyed "<EQ>-r2"
    prompt_file = ROOT / meta["path"]
    actual = hashlib.sha256(prompt_file.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    if actual != meta["sha256"]:
        problems.append(f"{eq}: prompt file changed after dispatch ({actual[:12]} != {meta['sha256'][:12]})")
    out = HERE / "out" / f"{key}.json"
    if not out.exists():
        problems.append(f"{key}: out/{key}.json missing")
        continue
    for c in json.loads(out.read_text(encoding="utf-8")):
        slot = plan.get(c.get("card_id"))
        if not slot or slot["equipment"] != eq or slot["tacit_type"] != c.get("tacit_type"):
            problems.append(f"{c.get('card_id')}: not matching plan slot")
        c["provenance"]["prompt_version"] = f"{meta['path']}@sha256:{meta['sha256']}"
        try:
            KnowledgeCard.model_validate(c)
        except Exception as e:  # keep going, report all
            problems.append(f"{c.get('card_id')}: schema {e.errors()[0]['msg'] if hasattr(e, 'errors') else e}")
            continue
        cards.append(c)
        src = "; ".join(f"{s['source_id']} {s.get('locator') or ''}".strip() for s in c["provenance"]["sources"])
        rows.append(f"| {c['card_id']} | {slot['slot']} | {eq} | {c['tacit_type']} | {c['title']} | "
                    f"[prompts/{key}.md](prompts/{key}.md) | `{meta['sha256'][:12]}` | {src} |")

cards.sort(key=lambda c: c["card_id"])
rows.sort()
(HERE / "cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
skipped = sorted(set(plan) - {c["card_id"] for c in cards})

readme = f"""# KB 카드 배치 {index['batch_id']}

- 시드: `{index['seed']}` — [`plan.py`](plan.py)가 이 시드로 슬롯(카드 ID·설비·유형)을 정한다. 같은 시드면 [`plan.json`](plan.json)이 바이트 단위로 같다.
- 생성: Claude Code 서브에이전트(general-purpose), 모델 `{index['dispatch']['model']}`, {index['dispatch']['dispatched_at']}.
- 프롬프트: [`prompt_template.md`](prompt_template.md) → [`render_prompts.py`](render_prompts.py) → `prompts/<설비>.md`. 해시는 [`prompts/index.json`](prompts/index.json).
- 서브에이전트에게 준 지시는 프롬프트 파일을 읽고 따르라는 한 줄뿐이다(`index.json`의 `dispatch.wrapper`). 실제 지시 내용은 프롬프트 파일과 같다.
- **재현성 한계**: 시드는 슬롯 계획만 고정한다. LLM이 쓴 카드 본문은 같은 프롬프트로 다시 돌려도 똑같이 나오지 않는다. 그래서 프롬프트 원문과 해시, 카드별 근거 페이지를 남긴다.
- 모든 카드는 `status=draft`, `grade=L0`, `split=kb`이다. accepted 여부는 사람이 검수해 정한다.

## 카드 → 프롬프트 추적표

각 카드의 `provenance.prompt_version` = `<프롬프트 경로>@sha256:<해시>`, `provenance.seed_ids` = `["{index['batch_id']}:seed={index['seed']}", "slot:<Sxx>"]`.

| 카드 | 슬롯 | 설비 | 유형 | 제목 | 생성 프롬프트 | 프롬프트 sha256 | 근거 |
|---|---|---|---|---|---|---|---|
""" + "\n".join(rows) + f"""

## 미작성 슬롯 ({len(skipped)})

{', '.join(skipped) if skipped else '없음'} — 사유는 `out/<설비>_notes.md`.
"""
(HERE / "README.md").write_text(readme, encoding="utf-8", newline="\n")

# review.md: one readable block per card for human accept/reject.
# Verdicts already typed into review.md survive regeneration.
import re  # noqa: E402
prev = (HERE / "review.md").read_text(encoding="utf-8") if (HERE / "review.md").exists() else ""
verdicts = dict(re.findall(r"^## (K-\d{4}).*?^- \*\*판정\*\*: ?([^\n]*)$", prev, re.M | re.S))
notes = {key: (HERE / "out" / f"{key}_notes.md").read_text(encoding="utf-8") if (HERE / "out" / f"{key}_notes.md").exists() else ""
         for key in index["prompts"]}
all_notes = "\n".join(notes.values()).splitlines()
blocks = [f"# {index['batch_id']} 검수표\n\n판정 칸에 `accepted` / `rejected` / `수정` 중 하나를 적는다. accepted면 grade를 L1로 올린다.\n"]
for c in cards:
    # match the card_id column only (notes mention other cards in 비고); round-2 note wins (K-1305 retry)
    note = next((ln for ln in reversed(all_notes) if ln.count("|") > 2 and ln.split("|")[2].strip() == c["card_id"]), "")
    lines = [f"## {c['card_id']} · {c['equipment']} · {c['tacit_type']}{' · ⚠ 안전' if c['safety_flag'] else ''} — {c['title']}", "",
             f"- **부품**: {c['component']}"]
    if c.get("symptom"):
        lines.append(f"- **증상**: {c['symptom']}")
    lines += [f"- **노하우**: {c['know_how']}", f"- **근거 설명**: {c['rationale']}"]
    if c.get("safety_basis"):
        lines.append(f"- **안전 근거**: {c['safety_basis']}")
    for cond in c.get("conditions", []):
        lines.append(f"- **조건**: `{cond['signal']} {cond['op']} {cond['value']}{' ' + cond['unit'] if cond.get('unit') else ''}`")
    for st in ((c.get("type_payload") or {}).get("steps") or []):
        pre = f"[전제: {'; '.join(st['preconditions'])}] " if st.get("preconditions") else ""  # reviewers must see step preconditions
        stop = f" / 중지: {'; '.join(st['stop_conditions'])}" if st.get("stop_conditions") else ""
        esc = f" / 넘김: {st['escalation_target']}" if st.get("escalation_target") else ""
        lines.append(f"  {st['order']}. {pre}{st['action']} → {st['expected_result']}{stop}{esc}")
    lines += [f"- **출처**: " + "; ".join(f"{s['source_id']} {s.get('locator') or ''}" for s in c["provenance"]["sources"]),
              f"- **작성 노트**: {note.strip() or '-'}", f"- **판정**: {verdicts.get(c['card_id'], '').strip()}", ""]
    blocks.append("\n".join(lines))
(HERE / "review.md").write_text("\n".join(blocks), encoding="utf-8", newline="\n")
print(f"cards: {len(cards)} / slots: {len(plan)} / skipped: {len(skipped)}")
for p in problems:
    print("PROBLEM:", p)
