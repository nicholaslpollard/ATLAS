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

Contract: `regime-input-inventory-v1-local-breadth-benchmark-sector-proxy-audit`.

The accepted 2026-08-14 target-machine run established:

- 8,034 Phase 08 discovery-state records
- 8,034 / 8,034 exact daily breadth joins
- 4 / 4 complete market proxies (`SPY`, `QQQ`, `IWM`, `DIA`) across 1d, regular 4h, and regular 1h evidence
- 11 / 11 complete Select Sector SPDR proxies across the same horizons
- no sector, industry, SIC, NAICS, or GICS classification fields in the accepted local universe/reference snapshots

Report path: `data/derived/regimes/input_inventory/YYYY/YYYY-MM-DD.json`.

## Gate 2 - point-in-time classification probe: ACCEPTED

Contract: `regime-classification-probe-v1-massive-sic-point-in-time`.

The accepted deterministic 250-instrument Massive Ticker Overview probe returned:

- 250 / 250 provider responses
- 250 / 250 exact provider-native ticker matches
- 120 SIC codes/descriptions
- 130 missing SIC observations
- 0 provider errors
- common stock (`CS`) SIC coverage: 108 / 122 = 88.52%
- preferred (`PFD`) SIC coverage: 7 / 7
- ETF SIC coverage: 4 / 100

Decision: raw SIC is valid point-in-time **industry** evidence when present, especially for company-like securities. It is not a universal ATLAS security taxonomy. ETF/fund/ETN context remains on its own security-type/proxy path. Phase 09 does **not** invent a SIC-to-GICS, SIC-to-Select-Sector-SPDR, or ticker-to-sector crosswalk.

Report path: `data/derived/regimes/classification_probe/YYYY/YYYY-MM-DD.json`.

## Gate 3 - historical regime calibration: ACCEPTED

Current contract: `regime-calibration-v2-historical-continuous-proxy-distributions`.

Diagnostic:

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_regimes.py --start 2021-08-16 --end 2026-08-14
```

The accepted target-machine calibration produced:

- 1,255 XNYS sessions
- 1,255 1d feature manifests
- 1,056 fully warmed sessions from 2022-05-31 through 2026-08-14
- the 199-session warm-up gap expected from EMA200
- complete 1,056-observation history for all 4 market proxies and all 11 sector proxies
- historical broad participation at the accepted Phase 08 `$250,000` daily-dollar-volume floor
- normalized continuous proxy trend evidence from existing Phase 06 `price_distance_ema_20` and `ema_20_slope_1`
- market- and sector-basket p10/p25/p50/p75/p90 distributions
- explicit end-date market and sector basket snapshots

The calibration preserves Phase 06 source/feature separation by exact `(symbol, timestamp_utc)` joins between canonical 1d close and derived 1d features.

### Accepted 2026-08-14 interpretation

The calibration population contained 7,411 instruments. Breadth was structurally constructive:

- 68.60% above EMA20
- 65.74% above EMA50
- 62.77% above EMA200
- 58.67% EMA20 above EMA50
- 60.55% EMA50 above EMA200
- 67.59% RSI above 50
- 69.90% positive MACD histogram

Immediate one-day participation was mixed at 47.83% positive return.

The market proxy basket was also constructive but not a uniformly positive day:

- 100% above EMA50 and EMA200
- 25% positive on the day
- 100% RSI above 50
- 100% positive MACD histogram
- median EMA20 distance `0.020810`, above the historical p75 `0.019084`
- median EMA20 slope `0.002195`, above the historical p75 `0.002013`
- median NATR14 `0.011141`, below the historical p25 `0.011529`

The sector basket showed broad constructive participation:

- 90.91% above EMA50
- 72.73% above EMA200
- 63.64% positive on the day
- 90.91% RSI above 50
- 72.73% positive MACD histogram
- median EMA20 distance `0.015898`, above historical p75 `0.015327`
- median EMA20 slope `0.001676`, above historical p75 `0.001616`

Interpretation: market structure/trend, momentum, immediate participation, volatility, and directional efficiency must remain separate dimensions. A single bullish/bearish threshold would discard useful information.

The historical activity-floor population is calibration evidence, not a reconstructed historical Phase 07 universe. No survivorship-safe historical universe is claimed.

Report path: `data/derived/regimes/calibration/YYYY/YYYY-MM-DD.json`.

## Gate 4 - candidate regime policy stability probe: CURRENT

Contract: `regime-policy-probe-v1-quartile-dimensional-no-hysteresis`.

Diagnostic:

```powershell
.\.venv\Scripts\python.exe scripts\probe_regime_policy.py --start 2021-08-16 --end 2026-08-14
```

This is deliberately a **candidate-only** diagnostic. It uses retrospective full-window p25/p75 bands to evaluate state balance and raw transition behavior; it is not a point-in-time trading-performance backtest and its thresholds are not production thresholds.

### Candidate market dimensions

- **structure**: broad EMA50/EMA200 participation, EMA20>EMA50, EMA50>EMA200, plus continuous market-basket EMA20 distance and EMA20 slope
- **momentum**: broad RSI>50 and MACD-positive participation plus market-basket median RSI
- **participation**: broad one-day positive-return participation
- **volatility**: market-basket median NATR14 and realized volatility
- **efficiency**: market-basket median directional efficiency

The composite directional state is conservative: trend and momentum must agree before stronger bullish/bearish labels are emitted. Volatility remains an independent risk dimension rather than being forced into direction.

### Candidate sector-proxy dimensions

Each of the eleven sector ETFs is classified from its own historical distributions using direct price/EMA structure, normalized EMA20 distance/slope, return/RSI/MACD momentum evidence, NATR/realized-volatility risk, and directional efficiency. SIC is not used and no stock-to-sector mapping is assumed.

### Stability evidence to review

The raw policy intentionally has **no hysteresis**. The probe reports:

- state counts and percentages
- market dimensional state counts
- transition count/rate
- run count and median run length
- one-day run count/share
- end-date market state
- aggregate sector state distribution
- per-sector end state and transition behavior

Only after this raw stability evidence is reviewed will Phase 09 decide whether thresholds, state definitions, or persistence/hysteresis need adjustment.

Report path: `data/derived/regimes/policy_probe/YYYY/YYYY-MM-DD.json`.

## Why classification remains separate

Sector proxy ETFs can be measured directly because they are traded instruments with their own canonical bars/features. Mapping individual stocks to those sectors is a separate taxonomy problem and will not be fabricated. Raw SIC remains optional industry evidence where authoritative provider facts exist.

## Remaining Phase 09 work

1. Evaluate the Gate 4 candidate market/sector policy distribution and raw transition stability.
2. Refine or accept raw market and sector-proxy state definitions.
3. Design persistence/hysteresis only if the evidence demonstrates chatter.
4. Build ticker-regime evidence/state on the accepted market context, with optional authoritative industry context where available.
5. Validate the final market -> sector -> ticker context hierarchy before Phase 09 acceptance.

Strategy-router semantics remain outside the regime evidence contract until the regime states themselves are accepted.
