# Phase 09 - Market, Sector, and Ticker Regime Engine

Phase 09 adds deterministic context between broad discovery and later ML/strategy routing. It describes the environment in which an opportunity exists; it does not select the final trade instrument and it does not replace Phase 08 setup evidence.

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
- 4 / 4 complete market proxies (`SPY`, `QQQ`, `IWM`, `DIA`)
- 11 / 11 complete Select Sector SPDR proxies
- no sector, industry, SIC, NAICS, or GICS mapping fields in the accepted local universe/reference snapshots

The absence of classification is evidence, not permission to fabricate a mapping.

## Gate 2 - point-in-time classification probe: ACCEPTED

Contract: `regime-classification-probe-v1-massive-sic-point-in-time`.

Accepted deterministic 250-instrument Massive Ticker Overview probe:

- 250 / 250 provider responses
- 250 / 250 exact provider-native ticker matches
- 120 SIC codes/descriptions
- 130 missing SIC observations
- 0 provider errors
- common stock (`CS`) SIC coverage: 108 / 122 = 88.52%
- preferred (`PFD`) SIC coverage: 7 / 7
- ETF SIC coverage: 4 / 100

Decision: raw SIC is valid point-in-time **industry** evidence when present, especially for company-like securities. It is not a universal ATLAS taxonomy. ETF/fund/ETN context remains on its own security-type/proxy path. Phase 09 does **not** invent a SIC-to-GICS, SIC-to-Select-Sector-SPDR, or ticker-to-sector crosswalk.

## Gate 3 - historical regime calibration: ACCEPTED

Contract: `regime-calibration-v2-historical-continuous-proxy-distributions`.

Accepted target-machine calibration:

- 1,255 XNYS sessions and 1,255 1d feature manifests
- 1,056 fully warmed sessions from 2022-05-31 through 2026-08-14
- 199-session warm-up gap matching EMA200
- complete 1,056-observation histories for all 4 market proxies and 11 sector proxies
- 7,411 end-date calibration participants at the accepted `$250,000` daily-dollar-volume floor

2026-08-14 breadth was structurally constructive while immediate one-day participation was mixed. Continuous market EMA20 distance and slope were above historical p75. This established separate structure/trend, momentum, participation, volatility, and efficiency dimensions.

The broad regime population is intentionally defined by complete 1d feature evidence at/above the accepted `$250,000` activity floor plus exact canonical closes. This same population is used historically and for current market breadth so production thresholds and current observations are comparable. It is not presented as a reconstructed historical Phase 07 universe.

## Gate 4 - raw candidate regime policy: ACCEPTED AS CHATTER BASELINE

Contract: `regime-policy-probe-v1-quartile-dimensional-no-hysteresis`.

Raw market distribution over 1,056 sessions was usable/non-collapsed:

- BEAR 13.83%
- BULL 24.34%
- MIXED 38.26%
- STRONG_BEAR 12.97%
- STRONG_BULL 10.61%

But temporal stability was not production-ready:

- market transition rate 31.18%
- market median run 2.0 sessions
- market one-day-run share 36.67%
- sector transition rates about 36%-42%, often with 1-session median runs

Decision: retain the dimensional state definitions; solve chatter through explicit persistence rather than changing thresholds to force smoothness.

## Gate 5 - persistence policy: ACCEPTED

Probe contract: `regime-persistence-probe-v1-dimension-confirmation-grid`.

Accepted production persistence contract:

`regime-persistence-policy-v1-two-session-dimensional-confirmation`

Two-session confirmation was selected over three-session confirmation.

Two-session evidence:

- market transition rate 15.07% = 51.67% reduction
- market median run 5.0 sessions
- market directional-family agreement 86.27%
- market opposite-direction lag 0.47%
- sector mean transition rate 15.94% = 58.34% reduction
- sector median run 4.0 sessions
- sector directional-family agreement 75.61%
- sector opposite-direction lag 2.16%

Three-session confirmation reduced transitions further but sector family agreement fell to 62.78% and sector opposite-direction lag rose to 5.17%. The extra smoothing was not worth the additional state delay.

Persistence is applied to underlying dimensions independently; composite direction is recomputed from the persisted dimensions.

## Gate 6 - point-in-time threshold memory: ACCEPTED

Probe contract: `regime-threshold-probe-v1-prior-only-252-policy-grid`.

Accepted production threshold contract:

`regime-threshold-policy-v1-expanding-252-prior-only`

All candidates used the same first 252 fully warmed observations as seed history and strictly excluded the current observation from its own threshold calculation. The comparison covered 804 market evaluation sessions from 2023-06-01 through 2026-08-14 and 8,844 sector observations.

### Frozen 252

Market:
- transition rate 12.95%
- retrospective exact agreement 31.59%
- family agreement 52.61%
- opposite-direction mismatch 2.49%

Its end-date EMA200 p75 remained only 38.49%, demonstrating structural staleness relative to the later distribution.

### Expanding 252 - SELECTED

Market:
- transition rate 15.94%
- median run 5.0 sessions
- retrospective exact agreement 78.23%
- family agreement 86.69%
- opposite-direction mismatch **0.00%**
- 2026-08-14 effective state `BULL`

Sectors:
- mean transition rate 16.03%
- median run 5.0 sessions
- retrospective exact agreement 92.66%
- family agreement 95.62%
- opposite-direction mismatch 0.09%

Expanding thresholds adapt gradually using every prior observation and preserve the long-memory purpose of market regime without the staleness of frozen thresholds.

### Rolling 252

Market:
- transition rate 16.69%
- median run 4.0 sessions
- retrospective exact agreement 69.78%
- family agreement 81.34%
- opposite-direction mismatch 0.12%
- 2026-08-14 effective state `MIXED`

Rolling thresholds adapted more aggressively and materially changed end-date classification. They remain useful diagnostic evidence but were not selected.

### Locked threshold semantics

- policy: `expanding_252`
- seed: 252 fully warmed observations
- p25 / p75 state bands
- p90 stress bands for volatility
- current observation is always excluded
- history origin: `2021-08-16`
- changing the historical origin requires a versioned policy change; older-data backfills do not silently rewrite accepted semantics

## Gate 7 - production market/sector state materialization: CURRENT

State policy contract:

`regime-state-policy-v1-expanding252-confirm2-dimensional`

Snapshot contract:

`regime-state-snapshot-v1-market-sector-proxies`

Breadth population contract:

`regime-breadth-population-v1-250k-dollar-volume-complete-1d`

The materializer replays from the fixed history origin and writes one deterministic JSON snapshot for the requested trading session plus a source/policy-lineage manifest.

Snapshot path:

```text
data/derived/regimes/states/YYYY/YYYY-MM-DD.json
```

Manifest path:

```text
data/manifests/regimes/YYYY/YYYY-MM-DD.json
```

The snapshot contains:

- raw and effective market dimensions/composite
- current market breadth and market-proxy-basket evidence
- all current threshold bands used by the accepted policy
- raw and effective states for all eleven sector proxies
- current direct sector-proxy evidence and threshold bands
- fixed history origin, selected threshold policy, persistence, and source-lineage fingerprint

The JSON snapshot excludes generation time so unchanged inputs/policies produce an identical SHA-256. The manifest carries generation metadata and dependency lineage. Re-running an unchanged as-of state should return `CURRENT` without rewriting the snapshot.

Target-machine acceptance command:

```powershell
.\.venv\Scripts\python.exe scripts\build_regime_state.py --as-of 2026-08-14
```

For the accepted historical lake, expected structural counts are:

- 1,255 source 1d manifests
- 1,056 usable breadth sessions
- 804 point-in-time evaluation sessions
- first evaluation session 2023-06-01
- 8,844 sector evaluation observations

The expected effective 2026-08-14 market state from Gate 6 is `BULL`, with `UP` structure, `MIXED` persisted momentum, `MIXED` participation, `NORMAL` volatility, and `NORMAL` efficiency.

The command must be run twice: first `MATERIALIZED`, second `CURRENT`, with the exact same snapshot SHA-256.

## Remaining Phase 09 work

1. Accept Gate 7 target-machine materialization/replay evidence.
2. Build ticker-regime state on the accepted market context and direct security evidence.
3. Augment ticker context with authoritative SIC industry facts only where available; no guessed stock-to-sector mapping.
4. Validate the final market -> sector/industry -> ticker hierarchy and archive/operational contracts.
5. Keep strategy-router semantics outside Phase 09 until regime context itself is accepted.
