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

Accepted 2026-08-14 target-machine evidence:

- 8,034 Phase 08 discovery-state records
- 8,034 / 8,034 exact daily breadth joins
- 4 / 4 complete market proxies (`SPY`, `QQQ`, `IWM`, `DIA`) across 1d, regular 4h, and regular 1h evidence
- 11 / 11 complete Select Sector SPDR proxies across the same horizons
- no local sector, industry, SIC, NAICS, or GICS classification fields

Report path: `data/derived/regimes/input_inventory/YYYY/YYYY-MM-DD.json`.

## Gate 2 - point-in-time classification probe: ACCEPTED

Contract: `regime-classification-probe-v1-massive-sic-point-in-time`.

Accepted deterministic 250-instrument Massive Ticker Overview probe:

- 250 / 250 provider responses and exact provider-native ticker matches
- 120 SIC codes/descriptions
- 130 missing SIC observations
- 0 provider errors
- common stock (`CS`): 108 / 122 = 88.52% SIC-covered
- preferred (`PFD`): 7 / 7
- ETF: 4 / 100

Decision: raw SIC is valid point-in-time **industry** evidence when present, especially for company-like securities. It is not a universal ATLAS taxonomy. ETF/fund/ETN context remains on its own security-type/proxy path. Phase 09 does **not** invent a SIC-to-GICS, SIC-to-Select-Sector-SPDR, or ticker-to-sector crosswalk.

Report path: `data/derived/regimes/classification_probe/YYYY/YYYY-MM-DD.json`.

## Gate 3 - historical regime calibration: ACCEPTED

Contract: `regime-calibration-v2-historical-continuous-proxy-distributions`.

Accepted target-machine calibration:

- 1,255 XNYS sessions and 1,255 1d feature manifests
- 1,056 fully warmed sessions from 2022-05-31 through 2026-08-14
- 199-session warm-up gap, exactly matching EMA200 initialization
- complete 1,056-observation history for all 4 market proxies and all 11 sector proxies
- historical broad participation at the accepted Phase 08 `$250,000` daily-dollar-volume floor
- continuous trend evidence from existing Phase 06 `price_distance_ema_20` and `ema_20_slope_1`
- p10/p25/p50/p75/p90 distributions and explicit end-date basket snapshots

Calibration preserves Phase 06 source/feature separation through exact `(symbol, timestamp_utc)` joins between canonical 1d close and derived 1d features.

### Accepted 2026-08-14 interpretation

The 7,411-instrument calibration population was structurally constructive:

- 68.60% above EMA20
- 65.74% above EMA50
- 62.77% above EMA200
- 58.67% EMA20 above EMA50
- 60.55% EMA50 above EMA200
- 67.59% RSI above 50
- 69.90% positive MACD histogram
- only 47.83% positive one-day return

The market proxy basket had strong trend structure but mixed same-day participation:

- 100% above EMA50 and EMA200
- 25% positive on the day
- median EMA20 distance `0.020810`, above historical p75 `0.019084`
- median EMA20 slope `0.002195`, above historical p75 `0.002013`
- median NATR14 `0.011141`, below historical p25 `0.011529`

The sector basket was broadly constructive:

- 90.91% above EMA50
- 72.73% above EMA200
- 63.64% positive on the day
- 90.91% RSI above 50
- 72.73% positive MACD histogram
- median EMA20 distance and slope both above historical p75

Decision: trend/structure, momentum, immediate participation, volatility, and directional efficiency must remain separate dimensions. A single bullish/bearish threshold would discard useful information.

The historical activity-floor population is calibration evidence, not a reconstructed survivorship-safe Phase 07 universe.

Report path: `data/derived/regimes/calibration/YYYY/YYYY-MM-DD.json`.

## Gate 4 - raw candidate regime policy: ACCEPTED AS A CHATTER BASELINE

Contract: `regime-policy-probe-v1-quartile-dimensional-no-hysteresis`.

The retrospective p25/p75 policy probe is diagnostic only. Its full-window bands are not point-in-time trading-performance evidence and are not production thresholds.

Accepted target-machine raw-state evidence across 1,056 sessions:

### Market state balance

- `BEAR`: 146 / 13.83%
- `BULL`: 257 / 24.34%
- `MIXED`: 404 / 38.26%
- `STRONG_BEAR`: 137 / 12.97%
- `STRONG_BULL`: 112 / 10.61%

The class distribution is usable: `MIXED` is the largest bucket while bullish and bearish families both remain meaningfully represented. No threshold/class-collapse problem was found that would justify changing the raw labels before persistence is tested.

### Raw market chatter

- 329 transitions
- 31.18% transition rate
- median run length 2.0 sessions
- 121 one-day runs
- 36.67% of runs lasted only one session

### Raw sector chatter

All eleven sector ETFs showed materially higher transition rates than desirable for a stable context layer:

- rates ranged from 36.11% (`XLF`) to 42.09% (`XLP`)
- median run lengths were only 1-2 sessions
- several sectors ended with a one-session median raw run

Decision: the raw dimensional definitions are retained for persistence testing, but **no raw Gate 4 state is production-ready without temporal stabilization**.

### Accepted 2026-08-14 raw state

Market:

- composite `BULL`
- structure `UP`, score 2
- momentum `POSITIVE`, score 1
- participation `MIXED`
- volatility `NORMAL`
- efficiency `NORMAL`

Sector proxies included `STRONG_BULL` for XLE, XLK, and XLV; `BULL` for XLC, XLF, XLI, and XLP; `BEAR` for XLU; and `MIXED` for XLB, XLRE, and XLY.

Report path: `data/derived/regimes/policy_probe/YYYY/YYYY-MM-DD.json`.

## Gate 5 - persistence confirmation comparison: CURRENT

Contract: `regime-persistence-probe-v1-dimension-confirmation-grid`.

Diagnostic:

```powershell
.\.venv\Scripts\python.exe scripts\probe_regime_persistence.py --start 2021-08-16 --end 2026-08-14
```

The probe compares **2-session** and **3-session** confirmation without changing the raw Gate 4 thresholds or labels.

Persistence is applied to dimensions independently:

### Market

- structure
- momentum
- participation
- volatility
- directional efficiency

The market composite is recomputed from the persisted directional dimensions after confirmation.

### Sector proxies

- structure
- momentum
- volatility
- directional efficiency

Each sector composite is recomputed from its persisted structure and momentum. SIC is not involved and no stock-to-sector mapping is assumed.

### Confirmation semantics

- the first observation initializes immediately
- a different state becomes a pending candidate
- the candidate must appear for `N` consecutive sessions before the persisted state switches
- returning to the persisted state clears the pending candidate
- a different pending candidate restarts the confirmation streak

The grid evaluates `N=2` and `N=3`. Their deterministic maximum confirmation lags are one and two sessions respectively.

### Evidence used to choose persistence

For both market and sectors, the probe measures:

- transition rate and reduction versus raw Gate 4
- median run length
- one-day run share
- exact agreement with raw states
- bullish/bearish family agreement with raw states
- opposite-direction mismatch rate, specifically measuring persistence lag that leaves a bull-family persisted state opposite a raw bear-family state or vice versa
- end-date state under each confirmation candidate

This prevents ATLAS from solving chatter merely by creating an excessively slow regime model.

Report path: `data/derived/regimes/persistence_probe/YYYY/YYYY-MM-DD.json`.

## Point-in-time threshold requirement after Gate 5

Even after a persistence candidate is selected, the current p25/p75 policy bands remain retrospective full-window diagnostics. Production Phase 09 still requires a **point-in-time-safe threshold policy** and validation before market/sector regime semantics can be locked. Persistence selection is therefore not the final production gate.

## Why classification remains separate

Sector proxy ETFs can be measured directly because they are traded instruments with their own canonical bars/features. Mapping individual stocks to those sectors is a separate taxonomy problem and will not be fabricated. Raw SIC remains optional industry evidence where authoritative provider facts exist.

## Remaining Phase 09 work

1. Compare 2-session versus 3-session persistence using Gate 5 stability/lag evidence.
2. Select or refine persistence only from measured trade-offs.
3. Replace retrospective diagnostic bands with a point-in-time-safe threshold policy and validate it historically.
4. Lock accepted market and direct sector-proxy state semantics.
5. Build ticker-regime evidence/state on accepted market context, with optional authoritative industry context where available.
6. Validate the final market -> sector -> ticker context hierarchy before Phase 09 acceptance.

Strategy-router semantics remain outside the regime evidence contract until the regime states themselves are accepted.
