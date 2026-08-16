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

## Phase 6A core registry

The registry currently covers the first production feature set across:

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

The sorted registry is SHA-256 fingerprinted. Persistence in Phase 6C will include this fingerprint
so changes to the mathematical contract automatically make older derived partitions identifiable as stale.

## Validation

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_phase6.py
```

The validator checks a classic Wilder RSI reference vector, a hand-calculated Wilder ATR recurrence,
provider-native ticker separation, feature contract metadata, and the registry fingerprint.

The full pytest suite includes exact warm-up positions and deterministic reference values for EMA,
Wilder smoothing, RSI, ATR, MACD, Bollinger Bands, OBV, prior-window structure, registry behavior,
and cross-symbol isolation in the core engine.

## Next slices

### 6B — engine/session/multi-timeframe semantics

Extend the core engine with session-aware features, multi-timeframe feature plans, feature selection,
and calculation benchmarking.

### 6C — incremental materialization

Add bounded/stateful warm-up handling, partitioned Parquet feature storage, manifests/fingerprints,
corrected-session invalidation, and idempotent recomputation.

### 6D — real historical acceptance

Run the engine against the ATLAS historical lake, validate selected symbols against independent/reference
calculations, profile throughput and memory, and decide which feature families should be permanently
materialized versus computed on demand.
