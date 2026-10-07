# PDA merge integration — 2026-10-07

The integration branch includes main at `21805d0` and local MES/Unity work.
Git merged these changes cleanly, but runtime checks found incompatible PDA behavior.

## RED

- `node tests/pda_handover_copy.cjs`: `TypeError: unityLocation is not a function`.
  Main itself lost the PDA UI changes from `6af1e47` while retaining their tests and server API.
- `node tests/pda_network_boot.cjs`: `'login' !== 'home'`.
  The test predates the intentional login entry screen.
- `node tests/unity_pda_link.cjs`: null `equipment_id` access.
  The test selects the equipment before login; current behavior defers selection until work entry.

## Required behavior

Preserve login and face verification, retry an offline MES boot, retain a Unity equipment
link through login, restore handover context/evidence, and keep current sensor readings
separate from fixed query-time evidence. Existing sensor checks must remain intact.

## PDA GREEN and remaining integration RED

- `node --check shiftlink/mes/web/pda.js` and all eight `tests/*.cjs` scripts pass.
- Focused Python PDA, random MES, scrap, and dataset checks: 37 passed.
- Full Python suite: 931 passed, 1 skipped, 1 failed. The remaining failure is
  `MesSignalMapRuntimeTests.test_scenario_measurements_and_alarms_match_map`:
  the new `scrap_discharge` scenario is missing from the unlinked scenario inventory.
- Route score: dev 21/30 and sanity 29/30 meet CI floors (21 and 28).

No real camera or device deployment is implied.
