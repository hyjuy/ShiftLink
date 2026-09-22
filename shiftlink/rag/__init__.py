"""Retrieval and extraction over knowledge cards.

- Only `status=accepted AND split=kb AND grade=L1` cards are searchable; dev and
  sealed events never enter the runtime KB (통합본 §4.7.6, §4.10).
- Safety cards are retrieved independently of top-k and condition matching
  follows 계약 §4.2 — a missing signal stays unknown, never a mismatch.
- The embedding model and vector store choice is still open (N-5, 9/21 "추후
  결정"); `InMemoryToolProvider` is the deterministic stand-in used until then.

Import from the modules directly (`shiftlink.rag.retrieval`,
`shiftlink.rag.extraction`) — this package keeps no re-export surface.
"""
