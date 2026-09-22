"""Jetson runtime concerns. Package placeholder — nothing is implemented yet.

개발계획 §2 records this package as "패키지 자리만 확인". What belongs here once
it is built (N-3 9/21 승인, 통합본 §4.11·§4.12):
- Handover items preserved across shifts with their item id (F-05).
- Local append-only outbox plus a separate once-a-day upload batch. Uploads
  carry ids, hashes, metrics and metadata only — never record text or judge
  comments. Same id + same hash is ignored; same key + different hash is held
  as a conflict. A failed upload must not stop local analysis or storage.
- Local audit log for every tool call (actor, time, device, input, evidence,
  model version, tool arguments, result, approver).

Until then, an empty `shiftlink.edge` must not be read as "MES 저장 완료".
"""
