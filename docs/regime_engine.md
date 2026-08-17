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

## Gate 1 - local evidence inventory

No regime labels or thresholds are locked from assumptions. `scripts/inventory_regime_inputs.py` measures what ATLAS already has locally for the requested session:

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

### Accepted 2026-08-14 inventory evidence

The target-machine run completed successfully with:

- 8,034 Phase 08 discovery-state records
- 8,034 / 8,034 exact daily breadth joins
- 4 / 4 complete market proxies across 1d, regular-session 4h, and regular-session 1h evidence
- 11 / 11 complete sector proxies across the same horizons
- no sector, industry, SIC, NAICS, or GICS classification fields in the current universe/reference snapshots

The absence of classification is an evidence result, not a reason to fabricate a mapping.

## Gate 2 - point-in-time classification probe

Because the local Phase 04/07 artifacts do not contain classification, Phase 09 next measures an explicit provider classification source before designing a permanent ticker-to-sector contract.

`scripts/probe_regime_classification.py` takes a deterministic sample from the exact Phase 08 discovery population and queries the Massive point-in-time Ticker Overview endpoint for raw SIC facts. The probe records:

- exact `instrument_id`, provider-native ticker, and Phase 07 security type
- provider-returned ticker and exact-case ticker match
- raw `sic_code` and `sic_description`
- missing-SIC observations
- provider errors
- coverage by security type
- exact Phase 08 discovery-state and Phase 07 universe source hashes
- every sampled observation for audit/review

Contract:

`regime-classification-probe-v1-massive-sic-point-in-time`

Report path:

```text
data/derived/regimes/classification_probe/YYYY/YYYY-MM-DD.json
```

This probe deliberately does **not** create a SIC-to-GICS, SIC-to-Select-Sector-SPDR, or ticker-to-sector crosswalk. SIC is being measured first as a raw point-in-time classification fact. Any permanent sector mapping will require its own explicit versioned policy and acceptance evidence.

## Why classification remains separate

The current Phase 04/07 reference and universe contracts intentionally preserve provider facts needed for identity/routing; they do not claim a sector mapping. Phase 09 therefore refuses to infer a security's sector from its ticker/name.

Sector proxy ETFs may still be used to measure sector-level market regimes because they are directly traded instruments with their own canonical bars/features. Mapping individual stocks to those sectors is a separate evidence problem and will not be fabricated.

## Planned regime outputs after classification evidence is accepted

The next contracts will separate three levels:

1. **Market regime** — trend, breadth, volatility, participation, and directional/risk state from broad breadth plus multiple market proxies rather than a single-index oracle.
2. **Sector regime** — sector-proxy trend/momentum/volatility/relative behavior, with point-in-time stock-to-sector mapping only after an authoritative classification source and crosswalk policy are established.
3. **Ticker regime** — per-security trend/volatility/participation/structure state, later augmented by market/sector-relative context.

Labels, scoring weights, persistence/hysteresis, strategy-routing semantics, and sector crosswalk policy remain intentionally unlocked until the real classification probe is reviewed.
