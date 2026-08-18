# Phase 06 Status

**Status: ACCEPTED — 2026-08-17**

Phase 06 is developed as a stacked branch on `phase-05-live-market-state` while the remaining Phase 05 real-market acceptance checks are completed separately. The Phase 06 implementation and target-machine acceptance are complete; the PR remains open only to preserve clean stacked-branch history until Phase 05 is merged.

## Accepted feature contract

- 33 versioned core quantitative features with a deterministic SHA-256 registry fingerprint.
- Explicit SMA-seeded EMA and Wilder recursive smoothing.
- Wilder RSI14 and ATR14 reference-vector validation.
- MACD 12/26/9 with explicit warm-up semantics.
- Bollinger Bands with population standard deviation (`ddof=0`).
- Returns/log returns, realized volatility, OBV, relative volume, dollar-volume features.
- Rolling price structure, breakout/breakdown, drawdown, moving-average slope/distance, and directional efficiency.
- Exact provider-native ticker preservation and case-sensitive state isolation.
- Intraday recursive state isolated by exact symbol + session segment.
- One-bar incremental feature engine with exact batch equivalence.
- Portable gzip-JSON recursive-state checkpoints with monthly anchors.
- Atomic Parquet feature partitions with source/state dependency fingerprints and SHA-256 manifests.
- Corrected-history replay from the latest valid monthly exact-state anchor.

## Measured persistence policy

- `1d`: permanent historical core features.
- `4h`: permanent historical core features.
- `1h`: permanent historical core features.
- `15m`: on-demand/cache history.
- `1m`: live/current feature state only.

## Permanent feature lake acceptance

History origin: `2021-08-16`  
Finalized endpoint: `2026-08-14`  
Expected exchange sessions per permanent timeframe: `1,255`

### 1d

- 1,255/1,255 sessions.
- 13,856,199 persisted feature rows.
- Zero stale sessions.
- Current checkpoint exactly `2026-08-14`.
- Independent AAPL verification: 1,255 source rows, 33/33 feature columns matched.
- Maximum absolute difference: `2.183e-11` — PASS.

### 4h

- 1,255/1,255 sessions.
- 38,247,842 persisted feature rows.
- Zero stale sessions.
- Current checkpoint exactly `2026-08-14`.
- Independent AAPL verification: 6,265 source rows, 5 target rows, 33/33 feature columns matched.
- Maximum absolute difference: `1.364e-11` — PASS.

### 1h

- 1,255/1,255 sessions.
- 102,084,180 persisted feature rows.
- Zero stale sessions.
- Current checkpoint exactly `2026-08-14`.
- Independent AAPL verification: 21,285 source rows, 17 target rows, 33/33 feature columns matched.
- Maximum absolute difference: `1.062e-10` — PASS.

Total permanent persisted feature rows: **154,188,221**.

## Final combined feature-lake audit

The deep audit over `2021-08-16 -> 2026-08-14` verified:

- 1,255/1,255 manifests for each permanent timeframe.
- source/feature/manifest coverage.
- source SHA integrity.
- every persisted feature Parquet SHA (`--deep-feature-sha`).
- unbroken genesis → input state → output state → next input state lineage.
- final manifest output-state fingerprint equals the current checkpoint fingerprint.

Results:

- `1d`: PASS.
- `4h`: PASS.
- `1h`: PASS.
- combined lake: **PASS**.

## Historical → incremental continuation acceptance

Using the persisted `2026-07-31` month-end exact-state checkpoints, ATLAS hydrated the same `IncrementalFeatureEngine` intended for current/live processing and replayed unseen August source bars to `2026-08-14`.

AAPL results:

- `1d`: 10 replay sessions / 10 rows / 33 features / maximum abs diff `0.000e+00` — PASS.
- `4h`: 10 replay sessions / 50 rows / 33 features / maximum abs diff `0.000e+00` — PASS.
- `1h`: 10 replay sessions / 170 rows / 33 features / maximum abs diff `0.000e+00` — PASS.

This proves historical persisted state can continue through the incremental/live-compatible calculation path with no numerical discontinuity.

## Automated acceptance

Current accepted Phase 06 head before this status-only commit: `822e57526de9294c9dab0a22b12cd00f2094f220`.

- Foundation validator: PASS.
- Phase 3 validator: PASS.
- Phase 4 validator: PASS.
- Phase 5 validator: PASS.
- Phase 6 validator: PASS.
- Wilder RSI/ATR references: PASS.
- provider-native ticker separation: PASS.
- measured persistence tiers: PASS.
- state-dependent partition fingerprint: PASS.
- batch/incremental equivalence: PASS.
- combined state-lineage audit regression: PASS.
- checkpoint hydration/continuation regression: PASS.
- Ubuntu Python 3.14: **124 passed in 5.83s**.
- Windows Python 3.14: **124 passed in 9.16s**.
- Target machine after final-gate pull: **124 passed in 11.77s**.

## Acceptance decision

**Phase 06 Feature Engine is accepted.**

The remaining Phase 05 market-hours WebSocket throughput/finalization gates are independent of this acceptance and do not invalidate the completed Phase 06 feature lake or state-continuity contract.
