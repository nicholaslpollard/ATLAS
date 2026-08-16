# Phase 06 — Feature Engine

Phase 06 converts trusted ATLAS bars into reproducible quantitative features while
keeping provider facts and derived calculations strictly separated.

## Core guarantees

1. Canonical/provider bars are never mutated by feature computation.
2. Provider-native ticker case is preserved; `TPC` and `TpC` are distinct symbols.
3. Feature calculations are grouped by exact symbol before any rolling/recursive math.
4. Warm-up is explicit. A feature is NaN until its mathematical initialization is valid.
5. Recursive indicators use documented ATLAS initialization rules rather than library defaults.
6. Feature definitions are versioned and fingerprinted for downstream invalidation/provenance.
7. Missing inputs reset recursive state rather than silently bridging a data gap.
8. Historical batch math and incremental/live math must be equivalent bar-for-bar.
9. Full-market historical persistence is benchmark-driven; ATLAS will not blindly multiply the lake by every feature column.

## Phase 6A mathematical contract

### EMA

ATLAS EMA is seeded with the arithmetic mean of the first complete `period` inputs,
then follows:

```text
alpha = 2 / (period + 1)
EMA_t = EMA_(t-1) + alpha * (x_t - EMA_(t-1))
```

This differs from pandas `ewm(adjust=False)` initialization and is intentional.

### Wilder smoothing

Wilder-recursive averages use an arithmetic-mean seed and then:

```text
W_t = (W_(t-1) * (period - 1) + x_t) / period
```

### RSI

RSI14 requires 14 price changes / 15 contiguous closes. Gains and losses are Wilder-smoothed.
Flat gain/loss windows are defined as RSI=50; gain-only windows are 100; loss-only windows are 0.

### True Range / ATR

```text
TR_t = max(
  high_t - low_t,
  abs(high_t - close_(t-1)),
  abs(low_t - close_(t-1))
)
```

The first true range uses high-low because no previous close exists. ATR is the Wilder average of TR.

### MACD

All MACD EMA legs use the same ATLAS SMA-seeded EMA convention. With 12/26/9 parameters,
the MACD line first becomes available at bar 26 and its signal/histogram at bar 34.

### Bollinger Bands

ATLAS uses a 20-bar SMA and population standard deviation (`ddof=0`) by contract.

## Core feature registry

The first production registry contains 33 features across:

- momentum / returns;
- trend averages, slopes, distance, efficiency;
- volatility / ATR / Bollinger / realized volatility;
- volume / OBV / relative volume / dollar volume;
- structure / prior levels / breakout/breakdown / drawdown.

Each definition records:

```text
name
family
version
minimum_history_bars
dependencies
recursive
```

The sorted registry is SHA-256 fingerprinted. State checkpoints and later persisted
feature artifacts carry the calculation contract/fingerprint so stale derived data is detectable.

## Phase 6B session and benchmark-relative context

Session-aware helpers are separate from continuous technical-series math. Regular-session
context currently includes:

- session bar index;
- session open;
- previous completed regular-session close;
- overnight gap;
- return from session open;
- session high/low to date;
- session range position to date.

Non-regular rows do not become regular-session state. Exact provider-native symbols own
independent state. Benchmark-relative primitives include aligned price ratio, relative
return, and relative-strength change; they require explicitly aligned asset/benchmark bars.

## Phase 6C exact incremental state

ATLAS does not approximate recursive indicators by loading an arbitrary recent window.
`IncrementalFeatureEngine` carries the exact state needed by EMA20/50/200, MACD 12/26/9,
Wilder RSI14, Wilder ATR14, OBV, and bounded rolling features.

A deterministic equivalence test feeds the same generated market sequence through:

```text
historical batch engine
        versus
one-bar-at-a-time incremental engine
```

and requires every registered core feature to match at each bar within floating-point
tolerance. This test caught and corrected a real semantic discrepancy: incremental
`drawdown_20` initially used rolling intrabar high while the batch contract correctly used
rolling close high.

Exact incremental state can be saved as portable deterministic gzip-JSON. Checkpoints carry:

- checkpoint schema version;
- feature calculation contract;
- registry fingerprint;
- timeframe;
- as-of date;
- exact per-symbol recursive state and bounded rolling buffers;
- a SHA-256 content fingerprint.

This gives later historical/live jobs resumability without pickles or hidden library state.

## Phase 6D persistence benchmark gate

ATLAS deliberately does **not** yet commit to materializing all 33 features for every 1m/15m
historical row. The historical lake is large enough that this decision must be empirical.

Run a real-data benchmark such as:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_features.py `
  --timeframe 4h `
  --end 2026-08-14 `
  --sessions 20 `
  --project-sessions 1255
```

The benchmark:

1. reads real canonical/derived ATLAS Parquet;
2. calculates all 33 core features across the full sample without cross-symbol leakage;
3. measures wall time, process CPU, peak RSS, and rows/second;
4. writes a temporary compact key+feature Parquet using the configured ATLAS compression;
5. measures actual compressed bytes/row and output/source ratio;
6. optionally projects sample compute/storage to the full 1,255-session lake;
7. removes the temporary feature file and saves only the benchmark JSON report.

One-minute benchmarking requires an explicit `--allow-1m` guard because even a modest
full-market sample can consume substantial RAM.

The results determine which feature/timeframe combinations are permanently materialized,
which are maintained only as current snapshots/state, and which are computed/cached on demand.
This avoids repeating the legacy Chart Monitor indicator-maintenance problem.

## Validation

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_phase6.py
```

The validator checks a classic Wilder RSI reference vector, a hand-calculated Wilder ATR recurrence,
provider-native ticker separation, feature contract metadata, and the registry fingerprint.

The pytest suite additionally covers exact EMA/Wilder initialization, RSI/ATR/MACD warm-up,
Bollinger population standard deviation, OBV, structure levels, session isolation, exact symbol
case, batch-vs-incremental equivalence, state checkpoint continuation, and benchmark projections.

## Remaining Phase 06 acceptance

1. Run the 4h real historical benchmark and use the measured footprint/throughput to lock the persistence profile.
2. Benchmark any additional timeframe needed to resolve the persistence decision (likely 1h and/or 15m samples).
3. Implement the selected persistence/current-state/cache policy with contract fingerprints and idempotent invalidation.
4. Validate real historical feature values for selected symbols/timeframes against the underlying canonical bars.
5. Prove current/live incremental feature state can resume from an exact checkpoint.

Phase 05's market-hours WebSocket throughput/finalization gates remain separate and may be completed while Phase 06 proceeds.
