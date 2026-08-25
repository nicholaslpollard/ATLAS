# Phase 25 Gate 6 — Provider-Free Phase7 + Discovery Reconstruction

**Status: ACTIVE / GATE5 TARGET EVIDENCE ACCEPTED / GATE6 IMPLEMENTATION**

## Accepted Gate5 boundary

Exact Gate5 implementation head: `151a1fea495d8c2d2c91fd68ec69e619d7e17025`.

Frozen Gate5 policy fingerprint:

`0e2060d91838c506d8b7c720fd38c06186dac8e4b4587385079b49cae519b8a0`

Exact-head cross-platform CI run `32854381515`: Ubuntu and Windows success through Gate5 plus the full repository regression suite.

Accepted target-machine Gate5 acquisition evidence through 2026-08-21:

- frozen acquisition sessions including the accepted probe: **1,253**;
- frozen bulk sessions after the probe: **1,252**;
- newly acquired bulk sessions: **1,252 / 1,252**;
- validated bulk sessions after the run: **1,252 / 1,252**;
- remaining frozen bulk sessions: **0**;
- successful provider page reads during bulk acquisition: **15,430**;
- accepted 2021-08-17 probe page reads: **12**;
- accepted probe persisted rows/instruments: **11,027 / 11,027**;
- probe re-fetch sessions: **0**;
- provider writes: **0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- Phase11 support writes: **0**;
- independent validation: **PASS**;
- Gate5 Pass: **true**.

Interpretation: exact PIT reference lineage is now locally complete for every Phase25 replay session. Gate5 must not be rerun merely to reconfirm accepted evidence.

## Gate6 purpose

Gate6 reconstructs the production discovery funnel from the accepted exact PIT reference lineage while remaining entirely provider-free. It deliberately stops before market/ticker regime routing, strategy-rule evaluation, strategy returns, or support analysis.

Replay scope:

`2021-08-16 -> 2026-08-21`, exact XNYS sessions only.

Gate6 reconstructs:

`exact PIT reference -> Phase7 universe -> discovery foundation -> 1d/4h/1h discovery score -> chronological discovery hysteresis -> WARM/HOT directional research population`

## Stateless historical materialization

For each replay session Gate6 may materialize only missing deterministic production artifacts using the accepted implementations:

1. `UniverseManager.build(session, force=False)` with no overrides;
2. `DiscoveryFoundationScanner.build(session)`;
3. `DiscoverySetupScanner.build(session)`.

Existing complete artifact sets must validate and be returned as skipped. If an existing set would need recomputation, Gate6 blocks rather than overwriting it. Any partial snapshot/manifest/exclusion set fails closed.

Gate6 performs **zero provider reads**. The reference snapshots produced by accepted Gates4/5 are local immutable inputs.

## Discovery hysteresis isolation

Gate6 does not call `DiscoveryStateManager.build()` and does not rewrite operational discovery-state snapshots.

Instead it reads each accepted discovery-score snapshot in chronological session order and applies the already accepted `ACTIVE_DISCOVERY_PERSISTENCE_POLICY` bootstrap/transition semantics in memory. Prior state is carried only from the immediately preceding replay session population. The result is written exclusively under:

`data/derived/strategy_evaluation/phase25/v1/gate6/through=2026-08-21/`

Research artifacts:

- `session_summary.parquet` — one row per exact replay session with Phase7/discovery funnel and state counts;
- `warm_hot_directional_population.parquet` — only effective WARM/HOT rows whose discovery direction is bullish or bearish;
- `reconstruction_report.json` — exact Gate5 binding, artifact counts, lineage hashes, and authority counters;
- `independent_validation.json` — separate provider-free validation of the completed lineage and research population.

This isolation is required because a full 2021–2026 chronological replay can legitimately have a different prior-state dependency chain than sparse current operational snapshots that were built before historical reconstruction existed. Gate6 studies route fidelity without rewriting accepted operational state.

## Gate6 authority lock

Gate6 has no authority to:

- call Massive or any other provider;
- overwrite existing historical universe/foundation/score artifacts;
- write operational discovery-state snapshots;
- use watchlist, position, custom, ticker, or manual exclusion overrides;
- run market, sector, or ticker regime routing;
- read strategy forward returns or protected strategy evidence;
- evaluate incumbent or challenger strategy rules;
- change Phase11 support or Phase24 statistical thresholds;
- read or mutate brokers;
- submit orders or PAPER trades;
- write LIVE state;
- invoke browser execution, scheduler authority, or PostgreSQL runtime promotion.

## Gate6 acceptance rule

Gate6 passes only if:

- all exact replay sessions have complete reference, Phase7 universe, discovery-foundation, and discovery-score artifact sets;
- existing artifact sets are preserved rather than force-replaced;
- the session summary contains exactly one row for every replay session from 2021-08-16 through 2026-08-21;
- the WARM/HOT research population contains only effective `warm`/`hot` rows with `bullish`/`bearish` direction;
- session+instrument keys in the research population are unique;
- population row totals reconcile exactly to session-summary directional totals;
- the report binds the exact accepted Gate5 report and independent-validation SHAs;
- provider reads/writes are zero;
- operational discovery-state writes are zero;
- regime routing, strategy-return reads, and strategy-rule evaluation are false;
- broker/order/PAPER/LIVE/support/protected-evidence counters remain zero;
- independent validation passes.

## Next boundary

Only after Gate6 target evidence is accepted may Gate7 reconstruct market/ticker route context on the accepted WARM/HOT directional population.

Gate7 must resolve ticker identity using exact same-session PIT evidence or another explicitly proven authoritative mapping. It may not silently reuse a stale authoritative-ticker-interval artifact derived from the former seven-snapshot reference state. Strategy returns and support replacement remain out of scope until the production-path population and routing context are independently accepted.
