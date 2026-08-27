# ATLAS Master Roadmap

**Last synchronized: 2026-08-26.**

## Architecture

`market/reference -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> deep research/news -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state. Massive is primary market/reference. Webull is primary PAPER/sandbox; Alpaca is manual secondary only. ML is probability evidence; AI is audit only; browser is monitoring/control only.

## Development contract

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> FOCUSED TEST -> INDEPENDENT VALIDATE -> FULL CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT`

Use the largest safe coherent batch. Preregister research search space, costs, dependence handling, multiplicity, temporal validation, and protected-evidence boundary before inspecting target performance. Zero-case/no-selection/no-finalist outcomes are valid.

## Current state

- **Phases 1–25 ACCEPTED / MERGED.**
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950`.
- Phase25 target code head `302bf6db5d807884f3b74cda049fc95864c5a194`, CI `32981080421` Ubuntu/Windows SUCCESS.
- Phase25 final docs head `f2d10465b71446b253b5d73a50845d2ea1e704d3`, CI `33025699177` Ubuntu/Windows SUCCESS.
- Phase25 decision: **NO SUPPORT REPLACEMENT**.
- **Phase26 is next: Materially Different Strategy Architecture Research.**

## Accepted strategy authority

Phase11 remains authoritative:

- SUPPORTED: 0;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Only accepted SUPPORTED strategies may promote under current production authority. Phase24 and Phase25 did not earn replacement.

## Phase24 result

Twenty-eight bounded threshold variants were preregistered under stronger robustness methodology. Result: 0 basic-pass, 0 selections/finalists, 0 protected reads. All variants failed key chronology/uncertainty/stress-cost robustness. **NO SUPPORT REPLACEMENT.**

## Phase25 result

Phase25 rebuilt historical production-path fidelity while holding the eight incumbent rules and accepted three-session outcome fixed.

Production-path evidence:

- exact PIT active-only reference lineage completed across the replay interval;
- 1,260 discovery replay sessions;
- 23,177 WARM/HOT directional rows;
- 15,283 fully route-eligible candidates;
- 61,132 eligible route decisions;
- 185,416 total route decisions.

Incumbent evidence:

- legacy research-source route join 43,456 / 57,160 = 76.0252%;
- 24,753 development rule-fired rows;
- every non-empty incumbent had a negative 10 bps production-path mean and worsened versus broad evidence;
- Gate9 selected 0 and produced 0 finalists;
- all eight failed positive folds, mean, median, positive-rate, bootstrap LCB, 25 bps stress, year robustness, and regime robustness;
- protected reads 0;
- Gate11: `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`.

Conclusion: historical population mismatch was not hiding robust incumbent edge. Do not relax Phase24/25 gates or continue threshold-tuning the same v1 families.

## Phase26 — next locked direction

Phase26 will investigate materially different architectures on an exact production-path-native research table.

Requirements:

1. research-only; zero provider/broker/order/PAPER/LIVE/support authority;
2. source observations directly from accepted Phase25 PIT identities/context + canonical 1d/4h/1h features and accepted outcome, not the incomplete legacy research table;
3. freeze candidate architecture/search space before target performance;
4. retain 10 bps primary and 25 bps stress economics unless separately replaced by evidence;
5. retain chronological selection/internal validation, purge, session-level aggregation, block bootstrap, year/regime robustness, concentration gates, and global multiplicity control;
6. candidate families must be materially different: cross-sectional relative strength, volatility/liquidity-conditioned mean reversion, gap continuation/reversal, volatility-normalized trend structures, multi-timeframe confirmation, and composite feature-block signals are initial directions;
7. short candidates must be independently designed, not mirrored long rules;
8. protected/future prospective evidence remains separate;
9. Phase11 support remains production authority unless a later separately accepted replacement decision occurs.

The initial Phase26 work should be implemented as one cumulative research batch with one cross-platform CI boundary and one target-machine evidence command.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; do not synthesize pre-2021 intraday history; unknown state fails closed; uncertain mutations require reconciliation; no automatic broker failover; PAPER does not imply LIVE; browser remains monitoring/control only; scheduler/PostgreSQL promotion and LIVE remain separate future authority decisions.