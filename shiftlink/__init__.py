"""ShiftLink — 현장의 경험을 다음 교대와 다음 세대로 연결하는 온디바이스 지식 에이전트.

Standing constraints every subpackage inherits (통합본 v1.1 §3.1, §4.10, §4.12):
- Read-only assistive layer. Nothing here changes official MES/CMMS state; the
  furthest any write goes is proposing a candidate for a human to accept.
- Answers cite knowledge card / equipment dictionary / handover ids. Without
  grounding the answer is "해당 지식 없음", not a generated guess.
- Synthetic knowledge is never presented as a veteran's confirmed knowledge.
  L1 (시뮬레이션 검증) is the highest grade an MVP answer may cite, and every
  response carries the "실제 작업지시 아님" notice.
- Inference, retrieval, handover storage and the audit log stay local; the
  cloud path is a separate daily batch of ids, hashes and metrics only.

Subpackages:
- `agent`  — rule router, fixed pipeline, contracts, response building.
- `rag`    — retrieval and extraction over knowledge cards.
- `data`   — synthetic data pipeline plan (P0~P6), planning only.
- `edge`   — Jetson runtime concerns (outbox, audit, daily batch), placeholder.
- `mes`    — synthetic local MES used for demonstration only.
"""
