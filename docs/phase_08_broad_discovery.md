# Phase 08 - Broad Discovery Funnel

Phase 08 turns the accepted Phase 07 point-in-time universe into a fast, auditable discovery population. The cheap broad pass targets under 60 seconds on the target machine and is initially acceptable under two minutes. Candidate count is threshold-driven; there is no arbitrary 5K hard cap.

## Separation

```text
Phase 07 eligible universe
        -> data health / activity / cheap setup evidence
        -> NORMAL / WATCH / WARM / HOT
        -> deeper quant / regime / strategy analysis
        -> Instrument Engine
        -> shares / fractional shares / options
```

Discovery is instrument-agnostic by default. The legacy `has options` filter is preserved as a future selectable instrument capability. `Options Only` may intersect an optionability map early for efficiency, while Auto/Best Instrument can keep the broad universe. Full option chains are reserved for a much smaller finalist/HOT population.

## First real-data gate

`scripts/inventory_discovery_inputs.py` measures the accepted universe against the 1d, 4h, and 1h feature partitions before any Phase 08 liquidity thresholds are locked. It reports exact feature coverage, intraday segment coverage, daily data-quality/warmup counts, close/volume/dollar-volume/relative-volume/volatility distributions, population counts at several informational threshold bands, input SHA-256 values, and runtime.

The threshold bands in the inventory are measurements only, not filtering policy. The real 2026-08-14 output will be used to choose the deterministic activity/data-health policy.

Report path:

```text
data/derived/discovery/input_inventory/YYYY/YYYY-MM-DD.json
```

After this gate, Phase 08 will implement the measured data-health/activity filter, cheap vectorized bull/bear setup evidence, persistence states, guaranteed position/watchlist processing, idempotent discovery artifacts, and the full-universe performance benchmark.
