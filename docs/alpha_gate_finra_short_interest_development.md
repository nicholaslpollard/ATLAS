# FINRA Consolidated Short Interest — Predictor and Development Implementation

Status: **IMPLEMENTED UNDER FROZEN SCIENCE; TARGET OUTCOMES NOT YET READ ON THIS IMPLEMENTATION**

Scientific fingerprint:

`0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`

Predictor contract:

`alpha-gate-finra-short-interest-predictor-v1-source-only-change-crowding-ranked`

Development contract:

`alpha-gate-finra-short-interest-development-v1-63-session-spy-relative-protected-blind`

Development implementation fingerprint:

`f5b99a52bf0e9d101b53493e0012a7a60d24b301f904d4b9958dc03638432a5f`

## Two-stage target runner

The target runner is intentionally ordered so market performance cannot open until source-only reconstruction has completed and passed.

### Stage 1 — source-only predictor reconstruction

The builder regenerates the full frozen twice-monthly FINRA settlement schedule from `2021-06-30` through `2026-04-15`: 116 settlement dates. For each date it reacquires the official FINRA historical file and the Massive active-common-stock snapshots at settlement and leakage-safe decision date.

It re-applies the accepted PIT rules, then requires previous short position and finite positive days-to-cover, calculates the frozen log position-change feature, ranks change and crowding within settlement, assigns exactly one of the four frozen candidate buckets when a row lies in a frozen tail, and applies the frozen deterministic cap of 75 rows per candidate per settlement.

Before any return can be opened, every candidate must independently satisfy the frozen source-count requirements in both development and protected stages. The predictor artifacts contain no price, return, benchmark, future-close, broker, execution, or order dependency. They explicitly record target outcome rows read = 0 and protected return rows read = 0.

If source-only reconstruction does not pass, the runner stops. Development outcomes remain unopened.

### Stage 2 — development-only outcome evaluation

Only after a persisted `SOURCE_ONLY_PREDICTOR_PASS` artifact with a matching SHA is present does the development study read market paths. It uses the accepted canonical daily Parquet path and exact entry-session open / 63-session exit close for the stock and SPY. Missing stock paths are censored. Missing SPY benchmark paths fail closed. Any path crossing accepted Phase26 split evidence is censored.

Selection and internal evaluation then apply the already-frozen costs, session-level aggregation, dependence-aware block bootstrap, global four-hypothesis Holm-Bonferroni correction, chronological folds, 63-session purge, robustness/concentration rules, one-winner-per-direction cap, and internal-only confirmation.

Protected predictor rows may be counted for source-only finalist prechecks. **Protected returns are never read by this implementation.** If an internal finalist passes its frozen protected source-only precheck, a later one-time finalist-only protected runner is required. If no finalist survives, or source-only protected evidence is insufficient, the family closes negative without changing science.

## Artifacts

Source-only predictor artifacts:

- `data/derived/strategy_evaluation/pre_phase33/finra_short_interest_predictor_v1/predictor_rows.jsonl`
- `data/derived/strategy_evaluation/pre_phase33/finra_short_interest_predictor_v1/predictor_report.json`

Development artifacts:

- `data/derived/strategy_evaluation/pre_phase33/finra_short_interest_development_v1/development_outcomes.jsonl`
- `data/derived/strategy_evaluation/pre_phase33/finra_short_interest_development_v1/finalists.json`
- `data/derived/strategy_evaluation/pre_phase33/finra_short_interest_development_v1/development_study.json`

No artifact or result from this gate grants provider writes, broker access, orders, PAPER/LIVE authority, automatic broker failover, or Phase33 signal-to-trade authority.
