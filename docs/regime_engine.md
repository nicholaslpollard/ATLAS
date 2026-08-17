# Phase 09 - Market, Sector, and Ticker Regime Engine

Phase 09 adds deterministic context between broad discovery and later ML/strategy routing. It describes the environment in which an opportunity exists; it does not select the final trade instrument and it does not replace Phase 08 setup evidence.

## Intended hierarchy

```text
market regime
    -> sector / industry context
        -> ticker regime
            -> later strategy router / ML / analogue / simulation layers
```

The regime engine must remain point-in-time safe, deterministic for finalized/as-of data, and independently auditable. Position/watchlist/custom routes remain eligible for context even when outside normal broad discovery.

## Gate 1 - local evidence inventory: ACCEPTED

Contract: `regime-input-inventory-v1-local-breadth-benchmark-sector-proxy-audit`.

Accepted 2026-08-14 target-machine evidence:
- 8,034 Phase 08 discovery-state records
- 8,034 / 8,034 exact daily breadth joins
- 4 / 4 complete market proxies (`SPY`, `QQQ`, `IWM`, `DIA`) across 1d, regular 4h, and regular 1h
- 11 / 11 complete sector proxies across the same horizons
- no sector, industry, SIC, NAICS, or GICS mapping fields in accepted local universe/reference snapshots

## Gate 2 - point-in-time classification evidence: ACCEPTED

Contract: `regime-classification-probe-v1-massive-sic-point-in-time`.

Accepted deterministic 250-instrument Massive Ticker Overview probe:
- 250 / 250 provider responses and exact ticker matches
- 120 SIC codes/descriptions
- 130 missing SIC
- 0 provider errors
- common stock: 108 / 122 = 88.52% SIC coverage
- preferred: 7 / 7
- ETF: 4 / 100

Decision: SIC is point-in-time industry evidence when present, not a universal taxonomy. No SIC-to-GICS, SIC-to-Select-Sector-SPDR, or ticker-to-sector crosswalk is guessed.

## Gate 3 - historical calibration: ACCEPTED

Contract: `regime-calibration-v2-historical-continuous-proxy-distributions`.

Accepted target-machine run:
- 1,255 XNYS sessions / 1,255 daily feature manifests
- 1,056 fully warmed sessions from 2022-05-31 through 2026-08-14
- 199-session EMA200 warm-up gap
- complete 1,056-observation history for all 4 market proxies and all 11 sector proxies
- 7,411 end-date calibration participants at the accepted `$250,000` activity floor

Accepted 2026-08-14 interpretation:
- broad medium/long-term market structure was constructive
- same-day breadth was mixed at 47.83% positive return
- market-basket EMA20 distance and EMA20 slope were above historical p75
- market volatility remained a separate risk dimension
- sector participation was broadly constructive

Calibration preserves Phase 06 source/feature separation with exact `(symbol, timestamp_utc)` canonical-bar + derived-feature joins. The activity-floor population is calibration evidence, not a reconstructed survivorship-safe historical Phase 07 universe.

## Gate 4 - raw candidate regime policy: ACCEPTED AS CHATTER BASELINE

Contract: `regime-policy-probe-v1-quartile-dimensional-no-hysteresis`.

The retrospective p25/p75 diagnostic produced a usable, non-collapsed market distribution across BEAR/BULL/MIXED/STRONG_BEAR/STRONG_BULL. It also exposed material raw chatter:
- market transition rate: 31.18%
- market median run: 2.0 sessions
- market one-day-run share: 36.67%
- sector transition rates: 36.11%-42.09%
- sector median runs: 1-2 sessions

Decision: the dimensional state definitions are informative enough to retain, but raw states are not production-ready without temporal stabilization.

## Gate 5 - dimensional persistence comparison: ACCEPTED

Probe contract: `regime-persistence-probe-v1-dimension-confirmation-grid`.

Selected policy contract: `regime-persistence-policy-v1-two-session-dimensional-confirmation`.

The target-machine comparison evaluated 2-session and 3-session confirmation, applied independently to the underlying dimensions before recomputing the composite.

### Accepted persistence: 2 sessions

Market 2-session result:
- transition rate 15.07%, down 51.67% from raw
- median run 5.0 sessions
- one-day-run share 5.62%
- exact raw agreement 74.24%
- bull/bear family agreement 86.27%
- opposite-direction lag only 0.47%

Market 3-session result:
- transition rate 9.38%, down 69.91%
- median run 8.5 sessions
- family agreement fell to 76.52%
- opposite-direction lag increased to 1.33%

Sector 2-session result:
- mean transition rate 15.94%, down 58.34%
- median run 4.0 sessions
- family agreement 75.61%
- opposite-direction lag 2.16%

Sector 3-session result:
- mean transition rate 10.12%, down 73.56%
- family agreement fell to 62.78%
- opposite-direction lag increased to 5.17%

Decision: 2-session confirmation provides the better stability/lag trade-off. The extra smoothing from 3 sessions does not justify the larger divergence and directional lag. The selected persistence applies to dimensions, not only to the final composite.

## Gate 6 - point-in-time threshold memory policy: CURRENT

Contract: `regime-threshold-probe-v1-prior-only-252-policy-grid`.

The Gate 4/5 p25/p75 bands were retrospective full-window diagnostics. They cannot become production thresholds because they contain future distribution information. Gate 6 removes that leakage.

All candidates use the same first **252 fully warmed sessions** as seed/training history and begin evaluation on the next session. Thresholds for a current observation use **strictly earlier observations only**. The accepted 2-session dimensional confirmation is then applied.

Candidate grid:
- `frozen_252`: calculate p25/p75 from the first 252 warmed sessions and keep them fixed
- `expanding_252`: after the same seed, recalculate from all observations strictly before the current session
- `rolling_252`: after the same seed, recalculate from only the 252 observations strictly before the current session

Because all candidates use the same warm-up, the expected target-machine comparison window is:
- 804 market sessions (`1,056 - 252`)
- 8,844 sector observations (`804 × 11`)

The probe measures for each policy:
- market and sector state balance
- transition rate, run length, and one-day-run share
- agreement with the retrospective Gate 4/5 reference (diagnostic benchmark only, not truth)
- opposite-direction mismatch against that reference
- end-date market and sector states
- end-date market threshold bands for key breadth/trend/volatility metrics

The purpose is to decide whether production thresholds should be fixed after a training anchor, adapt slowly with expanding history, or adapt to a trailing one-year distribution. No candidate is locked until the target-machine evidence is reviewed.

Diagnostic:

```powershell
.\.venv\Scripts\python.exe scripts\probe_regime_thresholds.py --start 2021-08-16 --end 2026-08-14
```

## Classification boundary

Sector ETFs are measured directly as traded instruments. Mapping individual stocks to those sectors remains a separate taxonomy problem and will not be fabricated. Raw SIC remains optional point-in-time industry evidence where authoritative provider facts exist.

## Remaining Phase 09 work

1. Select and lock a point-in-time-safe market/sector threshold memory policy from Gate 6.
2. Materialize the accepted deterministic market and sector regime contracts.
3. Build ticker-regime evidence/state on the accepted market context, with optional authoritative industry context where available.
4. Validate the final market -> sector -> ticker hierarchy before Phase 09 acceptance.

Strategy-router semantics remain outside Phase 09 until the regime states themselves are accepted.
