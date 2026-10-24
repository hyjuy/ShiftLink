# RMS quantization correction — preregistration and TDD

Original r6, profile, generator, consumed evaluation data and all old results remain intact. A separate normal-profile-rms16.json changes only seven vib_rms flat_windows from 8 to 16. No Timestral, generator jitter, channel suppression, or in-range exemption is introduced. Sixteen contiguous good measurements are required: a real RMS freeze can take up to 15 seconds from its first frozen frame, versus seven with r6. A genuine healthy plateau lasting sixteen frames remains an ambiguity; this change does not prove field accuracy.

## Development and frozen holdout

All generation, detector executions and tests run on Raspberry Pi. Development: four process mechanisms once each, four healthy runs of 900 frames, seven RMS channels each frozen inside and outside their normal range (14 episodes). Fresh seed/nonce/run per case; reject stratification by generator label only. The consumed two false notices are regression cases, never new holdout evidence.

After development passes, freeze source/profile/protocol hashes BEFORE generating holdout. Holdout: six naturally selected episodes per process mechanism (24), sixteen healthy runs of 900 frames, fourteen RMS freezes across all seven channels. Exclude all seeds from the previous evaluation and development. Seal all sensor input hashes before analysis. Run unchanged r6 and candidate on identical holdout inputs; no adjustment after looking at holdout. Separate private truth never enters model input.

First notice means unique event_id published through the actual PDA reader. Match same equipment inside [fault start, repair]; any other notice is false, any subsequent event for the same episode is duplicate. A repeated display of the same ID is not another notice. Outside frozen-window raw values resume naturally; process cases retain pause/repair/resume behavior. Bad/stale data cannot complete the flat window; checkpoint rebuild must preserve the confirmation decision.

Gates: every process and freeze episode detected; zero normal/unmatched notices; zero duplicates; overall latent p95 <=120 seconds; in-range freeze p95 <=15 seconds; Pi compute p95 <1 second. Also report original/candidate per-kind delays, including any added freeze confirmation time. Do not claim zero delay or improved sensitivity from artificial freezes.

Only after these gates pass: a separate real 1 Hz worker/HTTP/checkpoint/PDA DOM run measures source timestamp to rendered alarm with actual three-second polling. Report sample count, source location, network coverage, p95 and worst delay. Require no missing sequences, no model_error, processing p95<1 second, confirmed alarm retained until recovery, same-equipment single row and zero AI-induced repeat vibration. Existing service processes must stay healthy. Check actual Pi→Jetson access separately; loopback timing is not Jetson end-to-end timing.

Operational application is conditional on all gates and preserving active alarms and confirmed advisories. Never clear a real alarm to activate the new mode. Back up original files/unit/DB state; use separate candidate release/profile/state and an explicit rollback. PR #354 is merged, so use a follow-up PR rather than claiming to update its merged source.

## RED

Pi source initially lacked research imports; red.log contains an environment import error and is NOT RED evidence. After supplying exact installed r6 dependencies in the isolated source, red2.log ran five tests in 40.686s: three assertion failures (profile assertion and both reproduced false notices), other three behaviors passed. All originals and running services stayed unchanged.

## GREEN

Pi green.log: five tests passed in 63.233s. Both consumed false notices disappeared; a persistent in-range freeze was still detected once within fifteen seconds; bad/stale measurements broke confirmation; checkpoint restoration preserved decisions. Only the seven RMS windows changed. Profile SHA256 a87bef7e719b8f4b26b8eb8d840fb962fe58ac6c5599915e2c4e67cda01874af. Separate fresh development and holdout qualification remain required; this is not operational approval.

## Incremental replay RED (separate transport candidate)

Read-only Pi→Jetson state reads showed intermittent ~5s waits; operating poll_seconds was 5.390s. Inspection found MesStorage.replay deserializes the entire run before applying after_sequence while MesService holds its lock. This is a confirmed unnecessary workload; its exact share of live network jitter is not yet established. Pi isolated test with 1,000 frames reproduced 1,000 deserializations for a two-frame request and also for an empty tail. transport-red3.log: 3 tests, two assertion failures, 0.858s; as_of/run/sequence semantics passed. Earlier environment-only errors (upload ordering and missing system pydantic) are preserved and not counted as RED. Use the existing isolated test-venv, no global dependency changes. A separate transport-source keeps frozen model/data evaluation source unchanged.

## Incremental replay GREEN

Pi transport-green.log: all 20 incremental/storage/progressive HTTP tests passed in 25.053s. Tail and empty requests now decode only the requested frames (2 and 0), while existing full replay, time/run/sequence boundaries, storage atomicity and legacy/progressive controls remain valid. The snapshots method adds an optional after_sequence bound in the indexed SQL query; callers omitting it retain the original full-history behavior. The frozen analysis/source tree remains unchanged.
