# FINRA Consolidated Short Interest — Frozen Scientific Contract

Status: **FROZEN BEFORE ANY MARKET OUTCOME READ**

Scientific contract:

`alpha-gate-finra-short-interest-scientific-v1-four-position-change-crowding-buckets`

Scientific fingerprint:

`0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`

## Accepted source/PIT entry evidence

This science is bound to the accepted target PIT audit at exact repository head:

`db1af342ba4481360bf429ad696b5c7870b20f73`

Accepted PIT fingerprint:

`ffdb7389ceae73f31a3781a79a8d825338102b9084cb30dd03bf21f6bf003846`

Accepted target PIT report SHA-256:

`4fb3abc3e561fd4187efbf60967127230f14d37204d21b5ccb910c40a4469845`

Accepted source-only evidence was `PIT_AUDIT_PASS`: 136,731 immutable exchange-listed rows, 63,761 PIT-eligible rows, 8,054 unique PIT instruments, and all 12 audited files with at least 2,500 eligible rows. Target outcome rows read = 0, protected return rows read = 0, protected holdout consumed = false.

FINRA data is treated as public only after the seventh XNYS session after settlement and after FINRA's stated 4:40 PM ET publication availability. The decision session is therefore the first XNYS regular-session open strictly after publication. Revision-flagged and stock-split-flagged source rows remain excluded. Security identity must be the exact FINRA symbol/primary exchange mapped to an active common stock at settlement and decision with the same strong/medium instrument identity.

## Predictor transformation

The predictor uses only source/reference facts available before market outcomes.

For each PIT-eligible row with a valid previous-cycle short position and finite positive days-to-cover:

- position change = `ln((current short + 1) / (previous short + 1))`;
- change percentile = within-settlement average-tie percentile rank;
- crowding percentile = within-settlement average-tie percentile rank of FINRA days-to-cover.

The average-tie percentile is `(average rank - 1) / (N - 1)`. It is calculated independently inside each settlement cross-section.

Frozen tails:

- rapid covering: change percentile `<= 0.10`;
- rapid buildup: change percentile `>= 0.90`;
- crowded: days-to-cover percentile `>= 0.80`;
- non-crowded: days-to-cover percentile `< 0.80`.

No alternate tail or crowding threshold may be introduced after outcomes.

## Exactly four hypotheses

1. `rapid_short_build_crowded_short` — rapid buildup + crowded, SHORT.
2. `rapid_short_build_non_crowded_short` — rapid buildup + non-crowded, SHORT.
3. `rapid_short_cover_crowded_long` — rapid covering + crowded, LONG.
4. `rapid_short_cover_non_crowded_long` — rapid covering + non-crowded, LONG.

These buckets are mutually exclusive inside the two frozen change tails. There is no squeeze-direction reversal, alternate absolute-share threshold, alternate days-to-cover threshold, float/market-cap threshold, or post-result subgroup rescue.

To bound compute and dependence without observing returns, each candidate/settlement is deterministically capped at 75 rows by ascending SHA-256 of candidate + stable instrument + settlement + scientific fingerprint. Sampling is market-outcome independent.

## Frozen chronology and performance

- source settlement start: `2021-06-30`;
- source settlement cutoff: `2026-04-15`;
- governed performance signal start: `2021-08-16`;
- development last signal: `2024-12-31`;
- outer embargo: `2025-01-02..2025-04-03`;
- protected signals: `2025-04-04..2026-05-11`;
- protected outcome end: `2026-08-11`;
- entry: decision-session open;
- primary exit: close 63 XNYS sessions after decision;
- diagnostic horizons: 21 and 126 sessions only;
- benchmark: SPY;
- primary metric: direction-adjusted stock minus same-window SPY minus direction-specific cost;
- independent positive after-cost unhedged return is also required.

Primary costs are LONG 10 bps and SHORT 35 bps. Stress costs are LONG 25 bps and SHORT 100 bps. The short schedule retains the established ATLAS assumption of 100 bps annualized borrow plus execution in primary cost and 300 bps annualized plus execution in stress cost. Exact entry open and exit close are required; any split-crossing market path is censored fail-closed.

## Frozen statistical governance

Development is chronological 70/30 by distinct decision sessions, with a 63-XNYS-session purge before internal confirmation. Selection uses four chronological folds; internal uses three; protected uses four. Dependence-aware inference uses 63-session block bootstrap, 2,000 replicates, fixed seed 456033.

Selection minimums per candidate: 900 rows, 30 signal sessions, 500 unique instruments, and at least 3/4 positive folds. Internal minimums: 250 rows, 12 sessions, 150 instruments, and at least 2/3 positive folds. Protected source-only minimums: 300 rows, 16 sessions, 200 instruments, and at least 3/4 positive folds once returns are authorized.

Additional frozen robustness rules include at least 60% positive eligible years, at least 8 signal sessions for a year to count, maximum 5% of rows from one signal session, maximum 2% from one instrument, positive primary mean, positive primary LCB, positive stress mean, positive unhedged primary mean, and a required deflated-performance diagnostic.

Multiplicity is global `HOLM_BONFERRONI_GLOBAL_4` at alpha 0.05. At most one selection winner per direction may proceed to internal confirmation and at most one finalist per direction may proceed to protected confirmation. Winner ordering is highest primary selection LCB then candidate id within direction. Runner-up substitution is forbidden.

## Protected and authority boundary

Protected predictor/source prechecks may be built before a finalist because they contain no market outcome. Protected returns are finalist-only. Any nonempty protected-return read consumes the holdout. No provider writes, broker reads/writes, orders, PAPER/LIVE submissions, automation writes, automatic broker failover, or Phase33 signal-to-trade authority are granted by this contract.

If development is negative, the family closes negative rather than changing thresholds, directions, horizons, costs, chronology, sampling, dependence, multiplicity, winner/finalist rules, or protected policy.
