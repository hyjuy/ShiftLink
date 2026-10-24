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

## Additional Pi checks

Candidate-bound display/lifecycle/reader/RMS regressions: 24 passed in 116.465s (regression3.log). The first two attempts only exposed absent isolated dependencies/test files and are preserved as setup errors. Portable repository fixture path: the same five assertions passed in 72.918s; original inputs remain intact. New synthetic regression fixtures contain no private fault ledger or operating logs.

Separate 2,000-frame ×69-channel replay benchmark, same in-memory SQLite inputs and five calls each: old median 2.385361s, cursor-bound median 0.002231s, last two frames identical and all 2,000 rows retained. Indexed plan uses run_id and sequence bounds. This is a storage benchmark, not UI/network end-to-end time. Updated snapshots/replay executable-line observation: 8/8 lines (100%), not whole-file or branch coverage; the initial instrument included a Python3.13 None line marker and was corrected without changing code/tests.

Rendered proposed RMS16 unit verified with systemd-analyze, no installation or service changes. Checkpoint migration rehearsal preserved cursor, confirmed event ID and stopped notices, rejected an old binding without explicit conversion, retained the source journal byte-for-byte and emitted no duplicate. Fresh development: 18/18 positives (four process and fourteen persistent freezes), zero false/duplicate notices, delay p95 24s, in-range freeze p95 15s, compute p95 0.0276265s over 13,281 frames. Four healthy 900-frame development runs had longest exact RMS plateaus 3/3/5/5/4/5/5 by the seven channels; these statistics were computed for documentation after the candidate was frozen, without altering it.

The held-out manifest has 54 new runs: 24 process, 14 freeze, 16 healthy runs. All input hashes and pairwise seed/nonce/run disjointness against development and previous evaluation verified (zero overlap). All generator/model/profile/protocol hashes were frozen before generation. Paired evaluation is still in progress; no deployment is implied by these intermediate checks.

## Real-time measurement harness preparation

The original v1 measurement helper remains byte-for-byte inside the sealed model source. Before executing any real-time test, static review found that aiInsightsFrom intentionally drops sequence; telemetry now obtains the event sequence from the raw reader item rather than the UI projection. The final helper also waits for the last source frame, checks worker errors, closes its isolated HTTP listener and distinguishes frame delay from measured wall time. These are measurement corrections; frozen detector/profile/data/scoring and gates are unchanged. A separately pinned mes_rms_realtime_v3.py executes the corrected public mes_rms_realtime.py bytes.

The planned real-time source/worker/browser all execute on Pi. Optional loopback-only SSH forwarding relays their HTTP traffic Pi→Jetson→Pi through the existing authenticated SSH service; no Jetson test program or operating MES/PDA control is used. The exact trusted Jetson public host key was verified using the existing connection and saved only in the validation directory. Report this as a relayed isolated path, excluding operating MES database and physical kiosk timing. Actual operating HTTP/poll status will be checked separately after conditional activation. This relay adds transport evidence beyond a Pi-only loopback test without claiming it is the full operating route.

## Real-time setup diagnosis (original failures retained)

v3 and v4 did not reach fault injection: the isolated Chromium never requested the HTTP page before the startup timeout. Worker requests/configuration worked through the authenticated Pi→Jetson→Pi relay, and the unchanged installed alarm-panel file regression still passed in 3.458s. Missing shared memory/process capacity, proxy bypass and HTTPS upgrades were investigated; proxy bypass did not help. Chrome NetLog showed a successful local TCP connection and COOKIE_PERSISTENT_STORE_KEY_LOAD_STARTED without completion; the HTTP request waited on key-store initialization. A separate empty-profile HTTP probe changed only --password-store=basic and then fetched /, /done and /favicon.ico, exit 0, no browser error. This flag applies only to an empty, temporary test profile, with no accounts or stored credentials. No operating browser flags, keyring, service or PDA bytes changed.

Original failed logs/probes and the v1/v3/v4 helpers remain preserved. The separately frozen v5 helper has SHA256 d8a9eda988c83c2797d6824c76be1d3fe4ca7183d35507ce19d91c68be95cca7 and repeats the full fixed five-case real-time protocol; no model/data/scoring/gate changes were made. websocket-client 1.8.0 was installed only in the existing isolated test-venv for CDP diagnosis, not in a runtime environment and not required by the final helper. Physical vibrator motion and the operating kiosk display timing are not measured by this isolated regression.
