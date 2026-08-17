# Phase 09 - Market, Sector, and Ticker Regime Engine

Phase 09 adds context between broad discovery and later ML/strategy routing. Its job is to describe the environment in which an opportunity exists; it does not select the final trade instrument and it does not replace the Phase 08 setup evidence.

## Intended hierarchy

```text
market regime
    -> sector / industry context
        -> ticker regime
            -> later strategy router / ML / analogue / simulation layers
```

The regime engine must remain point-in-time safe, deterministic for finalized/as-of data, and independently auditable. Position/watchlist/custom routes remain eligible for context even when they are outside normal broad discovery.

## Phase 09 first gate: evidence inventory

No regime labels or thresholds are locked from assumptions. `scripts/inventory_regime_inputs.py` first measures what ATLAS already has locally for the requested session:

- accepted Phase 08 discovery state and evidence population
- broad-market breadth from exact 1d canonical bars + Phase 06 features
- coverage and daily evidence for market proxies `SPY`, `QQQ`, `IWM`, `DIA`
- coverage and daily evidence for the eleven Select Sector SPDR proxies: `XLB`, `XLC`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLRE`, `XLU`, `XLV`, `XLY`
- regular-session 4h/1h feature availability for those proxies
- whether the current point-in-time universe/reference snapshots already contain sector, industry, SIC, NAICS, or GICS classification fields
- exact source hashes for the diagnostic inputs

Contract:

`regime-input-inventory-v1-local-breadth-benchmark-sector-proxy-audit`

Report path:

```text
data/derived/regimes/input_inventory/YYYY/YYYY-MM-DD.json
```

## Why classification is audited first

The current Phase 04/07 reference and universe contracts intentionally preserve provider facts needed for identity/routing; they do not claim a sector mapping. Phase 09 therefore refuses to infer a security's sector from its ticker/name. If local classification is absent, the next implementation step will add an explicit point-in-time classification source/contract before ticker-to-sector relative context is locked.

Sector proxy ETFs may still be used to measure sector-level market regimes because they are directly traded instruments with their own canonical bars/features. Mapping individual stocks to those sectors is a separate evidence problem and will not be fabricated.

## Planned regime outputs after inventory acceptance

The next contracts will separate three levels:

1. **Market regime** — trend, breadth, volatility, participation, and directional/risk state from broad breadth plus multiple market proxies rather than a single-index oracle.
2. **Sector regime** — sector-proxy trend/momentum/volatility/relative behavior, with point-in-time stock-to-sector mapping only after an authoritative classification source is established.
3. **Ticker regime** — per-security trend/volatility/participation/structure state, later augmented by market/sector-relative context.

Labels, scoring weights, persistence/hysteresis, and strategy-routing semantics remain intentionally unlocked until the real 2026-08-14 evidence inventory is reviewed.
