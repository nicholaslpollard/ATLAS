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

## Gate 1 - local evidence inventory: ACCEPTED

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

## Gate 2 - point-in-time classification probe: ACCEPTED

Because the local Phase 04/07 artifacts do not contain classification, Phase 09 measured an explicit provider classification source before designing any permanent ticker-to-sector contract.

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

### Accepted 2026-08-14 classification evidence

The target-machine 250-instrument deterministic probe returned:

- 250 / 250 provider responses
- 250 / 250 exact provider-native ticker matches
- 120 SIC codes and descriptions
- 130 missing SIC observations
- 0 provider errors
- 48.00% overall SIC coverage

The security-type split is the important evidence:

- common stock (`CS`): 108 / 122 SIC-covered = 88.52%
- preferred (`PFD`): 7 / 7 SIC-covered
- ETF: 4 / 100 SIC-covered
- ADR common (`ADRC`): 0 / 8 SIC-covered
- fund (`FUND`): 0 / 11 SIC-covered
- ETN: 0 / 1 SIC-covered
- ETV: 1 / 1 SIC-covered, too small to generalize

Decision: raw SIC remains valid point-in-time **industry** evidence when present, especially for company-like securities, but SIC is not a universal ATLAS security classification. ETF/fund/ETN context remains on a separate security-type/proxy path. Phase 09 does **not** invent a SIC-to-GICS, SIC-to-Select-Sector-SPDR, or ticker-to-sector crosswalk.

## Gate 3 - historical regime calibration: CURRENT

A single accepted session is not enough evidence for regime cutoffs. Before market, sector-proxy, or ticker regime labels are locked, Phase 09 measures the historical distributions already present in the permanent Phase 06 1d feature lake.

Diagnostic:

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_regimes.py --start 2021-08-16 --end 2026-08-14
```

Contract:

`regime-calibration-v1-historical-activity-floor-proxy-distributions`

The calibration pass measures:

- historical broad participation using complete 1d feature rows at the accepted Phase 08 `$250,000` daily-dollar-volume floor
- distributions for close above EMA20/50/200, EMA20 above EMA50, EMA50 above EMA200, positive one-day return, RSI above 50, and positive MACD histogram
- exact historical evidence for `SPY`, `QQQ`, `IWM`, `DIA`
- exact historical evidence for all eleven sector proxy ETFs
- market-basket and sector-basket participation/trend/momentum/volatility distributions
- exact 1d feature-manifest coverage and an aggregate lineage fingerprint

The historical activity-floor population is calibration evidence, not a claim that ATLAS has reconstructed a Phase 07 reference universe for every old session. This distinction prevents hidden survivorship/reference assumptions.

Report path:

```text
data/derived/regimes/calibration/YYYY/YYYY-MM-DD.json
```

Regime thresholds remain **unlocked** until this historical distribution evidence is reviewed.

## Why classification remains separate

The current Phase 04/07 reference and universe contracts intentionally preserve provider facts needed for identity/routing; they do not claim a sector mapping. Phase 09 therefore refuses to infer a security's sector from its ticker/name.

Sector proxy ETFs may still be used to measure sector-level market regimes because they are directly traded instruments with their own canonical bars/features. Mapping individual stocks to those sectors is a separate taxonomy problem and will not be fabricated.

## Planned regime outputs after calibration acceptance

The next contracts will separate three levels:

1. **Market regime** — trend, breadth, volatility, participation, and directional/risk state from broad breadth plus multiple market proxies rather than a single-index oracle.
2. **Sector regime** — direct sector-proxy trend/momentum/volatility/relative behavior. Any stock-to-sector mapping remains optional and separately versioned rather than being required to measure sector ETF regimes.
3. **Ticker regime** — per-security trend/volatility/participation/structure state, augmented by market context and by authoritative industry/sector context only where that context actually exists.

Labels, scoring weights, persistence/hysteresis, and strategy-routing semantics remain intentionally unlocked until Gate 3 historical calibration is reviewed.
