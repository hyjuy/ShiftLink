---
applyTo: "shiftlink/rag/graph_explain.py,shiftlink/mes/web/pda.js,tests/*graph_explain*"
---

# KG explain boundaries

- Keep `SHIFTLINK_KG_MODE=off` and depth 1 as defaults. Only depth `2` enables expansion; unsupported depth values fall back to the unchanged depth-1 contract.
- Read graphs only after final citation selection. Do not add related cards to answer text, cited_card_ids, evidence, prompts, retrieval/ranking, actions or sensor state.
- Allow exactly card → component → equipment, card → symptom ← card, card → document version ← card. No generic BFS, third hop, shared-equipment peers or synthetic asset traversal.
- Bind roots and related cards to the request's unique current card view: accepted/L1/kb, equipment/COMMON and asset scope, exact normalized version/content match. Never fill a missing current card from graph contents. Keep final-root S30h chunk binding and MES publication ticket validation.
- Preserve original edge direction and both cards' separate locators. Shared symptoms remain needs_review; held/unversioned sources stay held. Related cards are references, not equivalent advice or causal evidence.
- Exclude every final cited root, deduplicate related card IDs response-wide, sort deterministically. Caps: 10 related cards per root, 20 per response, 3 paths per related card; disclose truncation. These are display limits, not relevance rankings.
- Extend only graphContextElement for PDA metadata; use textContent and collapsed references. Preserve sensor/request/response handlers under the PDA AGENTS rules.
- Do not edit graph.json, validation.json, source cards, schema, models or indexes for this explain-only change.
- Run graph Python/DOM/browser tests and `python scripts/check_knowledge_publication.py`. Keep temporary outputs under docs/demo/kg; no device calls or service actions in local fixtures.
- Failure memory: `docs/failures/kg-explain-boundary.md`. Revalidate depth 1/2 response equality and current-view exclusion whenever expansion rules change.
