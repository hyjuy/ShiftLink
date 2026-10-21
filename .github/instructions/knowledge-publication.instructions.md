---
applyTo: "shiftlink/mes/{candidate_review,publication,query,server,storage}.py,shiftlink/rag/embedding.py,shiftlink/rag2/{embed,s30h}.py,shiftlink/mes/web/*candidate*,tests/test*publication*.py"
---

# Knowledge publication boundaries

- Follow `docs/planning/knowledge-publication-20261021.plan.md` and `docs/failures/knowledge-publication-integrity.md`.
- Review approval, quality approval, embedding completion and search visibility are separate. Schema-valid placeholders and unstructured logs cannot pass quality review.
- Preserve source work logs, draft cards, query-time evidence and review audit history. Derive asset bindings from the original incident, never from the currently selected installation.
- Publish card, chunks, vectors and manifest in one SQLite transaction. Before committing network results, recheck review revision, content hash and attempt ID. A superseded result must not resurrect a card.
- Keep embedding network calls outside `MesService._lock`. Failed jobs must remain durable and retry after restart; never mark them searchable to hide a failure.
- `shiftlink/rag/embedding.py` owns document/query prefixes. The published model must match S30h's index model and dimension. A model change requires re-embedding; do not relabel old vectors.
- Create per-query index views. Do not mutate a running pipeline's shared rows/vectors/cards. Validate the publication ticket again under the final query-save lock.
- Field cards are scoped to their original assets and verified conditions. Judge rejection still means no answer. Retrieval availability does not prove equipment safety or factual correctness.
- Run `python scripts/check_knowledge_publication.py` before finishing. It also parses staged Python blobs, since passing tests on a dirty worktree does not prove the staged commit is valid. Do not stage filtered zero-context patches from a dirty file.
- Run publication unit/HTTP/S30h tests and the real-browser test; preserve evidence for failures and fixes. Live-model checks are opt-in and must be reported separately from deterministic model fixtures.
- Do not start/restart a Jetson service, edit the static KB/index, or download models as part of a local test.
