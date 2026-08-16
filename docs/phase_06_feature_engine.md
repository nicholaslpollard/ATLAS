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
7. Missing/non-numeric OHLCV input is rejected rather than silently interpolated.
8. Historical batch math and incremental/live math must be equivalent bar-for-bar.
9. Full-market historical persistence is benchmark-driven; ATLAS will not blindly multiply the lake by every feature column.
10. Persisted recursive feature partitions depend on both their own source bars and the exact recursive state entering the partition.

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

RSI14 requires 14 price changes / 15 contiguous observed closes. Gains and losses are Wilder-smoothed.
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

The sorted registry is SHA-256 fingerprinted. State checkpoints and persisted feature
artifacts carry the calculation contract/fingerprint so stale derived data is detectable.

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

## Phase 6C exact incremental state and durable partitions

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

Feature Parquet partitions now use a state-dependent manifest contract. A partition's
dependency fingerprint includes:

```text
feature partition contract
feature calculation contract
feature registry fingerprint
source bar SHA-256
incoming recursive-state fingerprint
```

The manifest also records the outgoing state fingerprint and feature-file SHA-256. This is
critical for corrected historical data: a session can become stale even if its own bar file
never changed, because an earlier correction can alter the EMA/RSI/ATR/OBV state entering it.

`HistoricalFeatureMaterializer` processes source sessions chronologically through the same
incremental engine intended for live use. A first historical build requires an explicit
empty-state bootstrap at the chosen ATLAS history origin. Subsequent runs resume from the
current exact checkpoint. Month-end state snapshots are retained as replay anchors. A
corrected historical source replays from the latest valid month-end anchor strictly before
the correction (or genesis if none exists), replacing every downstream feature partition
through the requested end rather than patching one recursive day in isolation.

## Phase 6D measured persistence architecture

The first real target-machine benchmark ran on 2026-08-16 against the production ATLAS lake:

```text
timeframe:              4h
sample sessions:        20
sample range:           2026-07-20 -> 2026-08-14
rows:                   714,562
symbols:                13,110
registered features:    33
source Parquet:         16.1 MiB
wall/process CPU:       ~6.8 minutes
CPU one-core equiv:     99.6%
rows/second:            1,746
feature RAM frame:      221.3 MiB
feature Parquet:        100.2 MiB
compressed bytes/row:   147.1
output/source ratio:    6.23x
```

Linear projection across the 1,255-session provider-backed lake:

```text
projected rows:         44,838,766
projected Parquet:      6,289.8 MiB (~6.14 GiB)
projected compute:      427.9 minutes (~7.13 hours single-core)
```

The machine had approximately 206 GiB free after this benchmark. Therefore storage is not
the limiting factor for 4h persistence; rebuild/maintenance time is the more important cost.

### Active persistence policy

```text
1d   permanent full historical core features
4h   permanent full historical core features
1h   benchmark candidate — one target-machine benchmark still required
15m  on-demand / cache history
1m   live/current feature state only
```

The 1d dataset is materially smaller than 4h and is strategically important for regime,
trend, research, and walk-forward work, so it is accepted as permanent without requiring a
separate capacity gate. 15m is intentionally not promoted to a full 33-column historical
matrix because its row volume/rebuild cost is much larger. 1m remains state/current only.

One 1h benchmark is still required to decide whether 1h joins the permanent tier or remains
on-demand/cache. The persistence code is already tier-agnostic, so promoting 1h later does
not require redesign.

## Benchmark command

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_features.py `
  --timeframe 1h `
  --end 2026-08-14 `
  --sessions 20 `
  --project-sessions 1255
```

The Windows RSS probe was hardened after the initial 4h run returned `unknown`, so the 1h
benchmark should also report actual peak process working-set usage.

The benchmark writes only a JSON report under `data/derived/features/_benchmarks`; its
sample feature Parquet is temporary and removed automatically.

## Validation

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_phase6.py
```

The validator checks a classic Wilder RSI reference vector, a hand-calculated Wilder ATR recurrence,
provider-native ticker separation, feature contract metadata, the registry fingerprint, measured
persistence tiers, and state-dependent feature partition fingerprints.

At branch head `e3ae02d019fa8bfc88fce4f77b3430e21aa01b76`, GitHub Actions is green on both
Ubuntu and Windows Python 3.14. The Windows run reports **116 passed in 8.57s**.

The pytest suite covers exact EMA/Wilder initialization, RSI/ATR/MACD warm-up, Bollinger
population standard deviation, OBV, structure levels, session isolation, exact symbol case,
batch-vs-incremental equivalence, state checkpoint continuation, benchmark projections,
measured persistence tiers, state-dependent partition invalidation, exact historical resume,
and monthly-anchor corrected-history replay.

## Remaining Phase 06 acceptance

1. Run the 1h real historical benchmark and lock its tier.
2. Run a small real historical materialization pilot using the permanent 4h contract before the full feature backfill.
3. Validate selected real historical feature values against canonical/derived bars and independent calculations.
4. Prove the persisted current state can feed the Phase 5 live path without numerical discontinuity.
5. Only after those gates, backfill permanent feature timeframes across the provider-backed history.

Phase 05's market-hours WebSocket throughput/finalization gates remain separate and may be completed while Phase 06 proceeds.
