# Phase 06 Status

Phase 06 is developed as a stacked branch on `phase-05-live-market-state` while the remaining
Phase 05 real-market acceptance checks are deferred to market hours.

## Implemented

- 33-versioned core feature registry with SHA-256 contract fingerprint.
- Explicit SMA-seeded EMA and Wilder recursive smoothing.
- Wilder RSI14 and ATR14 reference-vector validation.
- MACD 12/26/9 with explicit warm-up semantics.
- Bollinger Bands with population standard deviation (`ddof=0`).
- Returns/log returns, realized volatility, OBV, relative volume, dollar-volume features.
- Rolling price structure, breakout/breakdown, drawdown, moving-average slope/distance, directional efficiency.
- Exact provider-native symbol isolation.
- Regular-session context and gap helpers.
- Benchmark-relative return/strength primitives.
- Incremental one-bar feature engine.
- Batch-vs-incremental equivalence test across every registered core feature.
- Portable gzip-JSON exact-state checkpoints with contract/timeframe/content fingerprints.
- Historical feature benchmark tooling that measures compute, memory, and actual compressed Parquet footprint before the permanent persistence profile is selected.

## Key acceptance already obtained in CI

- Classic Wilder RSI vector: PASS.
- Hand-calculated Wilder ATR recurrence: PASS.
- Provider-native `TPC` / `TpC` isolation: PASS.
- Session-state symbol isolation: PASS.
- Batch/incremental equivalence: PASS after the equivalence test caught and corrected the rolling-close-vs-intrabar-high drawdown discrepancy.

## Next decision gate

Run the real 4h historical benchmark on the target machine. Its measured rows/sec, peak RSS,
compressed bytes/row, and projected 1,255-session footprint determine whether the 33-column core
matrix should be permanently materialized at 4h and which larger timeframes require additional
benchmarking. Full-market 1m/15m feature persistence is not assumed.
