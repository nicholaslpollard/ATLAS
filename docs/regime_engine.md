# Phase 09 - Market, Sector, and Ticker Regime Engine

Phase 09 adds deterministic context between broad discovery and later ML/strategy routing. It describes the environment in which an opportunity exists; it does not select the final trade instrument and it does not replace Phase 08 setup evidence.

## Intended hierarchy

```text
market regime
    -> sector / industry context
        -> ticker regime
            -> later strategy router / ML / analogue / simulation layers
```

The regime engine is point-in-time safe, deterministic for finalized/as-of data, and independently auditable. Position/watchlist/custom routes remain eligible for context even when they are outside normal broad discovery.

## Gates 1-7 - market/sector foundation: ACCEPTED

Accepted contracts:

- `regime-input-inventory-v1-local-breadth-benchmark-sector-proxy-audit`
- `regime-classification-probe-v1-massive-sic-point-in-time`
- `regime-calibration-v2-historical-continuous-proxy-distributions`
- `regime-policy-probe-v1-quartile-dimensional-no-hysteresis`
- `regime-persistence-policy-v1-two-session-dimensional-confirmation`
- `regime-threshold-policy-v1-expanding-252-prior-only`
- `regime-state-policy-v1-expanding252-confirm2-dimensional`
- `regime-state-snapshot-v1-market-sector-proxies`
- `regime-breadth-population-v1-250k-dollar-volume-complete-1d`

Key accepted semantics:

- broad market regime uses point-in-time breadth plus SPY/QQQ/IWM/DIA proxy evidence
- 11 Select Sector SPDR proxies form the sector-context layer
- raw SIC from Massive Ticker Overview is valid optional point-in-time **industry** evidence when present
- Phase 09 does **not** invent a SIC-to-GICS, SIC-to-Select-Sector-SPDR, or ticker-to-sector crosswalk
- market/sector persistence uses 2-session dimensional confirmation
- thresholds use expanding prior-only history after a 252-session seed
- history origin is 2021-08-16
- current observations are excluded from their own threshold calculation

Accepted 2026-08-14 market/sector materialization:

- 1,255 source 1d manifests
- 1,056 usable breadth sessions
- 804 point-in-time evaluation sessions
- first evaluation session 2023-06-01
- 8,844 sector evaluation observations
- effective market state `BULL`
- sector state counts `BEAR=1, BULL=5, MIXED=3, STRONG_BULL=2`
- deterministic replay produced identical dependency fingerprint and snapshot SHA on the immediate second run

## Gate 8 - ticker regime semantics/history-safety evidence: ACCEPTED

Contract:

`ticker-regime-probe-v1-routed-multitimeframe-identity-history-audit`

Ticker regime population is Phase 08 discovery-state instruments plus Phase 07 POSITION/WATCHLIST/CUSTOM routed overrides.

Accepted ticker dimensions:

- 1d structure
- regular-session 4h direction
- regular-session 1h direction
- 4h/1h short-horizon alignment
- 1d momentum
- self-relative risk/efficiency evidence handled separately

Accepted descriptive ticker states:

- `STRONG_UPTREND`
- `UPTREND`
- `PULLBACK_UP`
- `RANGE_MIXED`
- `TRANSITION_UP`
- `TRANSITION_DOWN`
- `BOUNCE_DOWN`
- `DOWNTREND`
- `STRONG_DOWNTREND`

These labels are context, not strategy selection.

## Gate 9 - authoritative ticker history/depth: ACCEPTED

Accepted contract:

`ticker-history-probe-v2-operational-current-alias-authoritative-interval-depth`

2026-08-14 accepted evidence:

- routed population: 8,034
- authoritative current interval: 1,090
- current alias no conflict: 6,830
- unresolved multi-alias: 17
- unresolved ticker reuse: 97
- unresolved/history-blocked residual: 114 / 8,034 = 1.42%
- operational depth >=2/5/20/60/126/252: 7,231 / 7,215 / 7,172 / 7,010 / 6,786 / 6,415
- authoritative interval depth >=2/5/20/60/126/252: 926 / 925 / 907 / 852 / 783 / 673

Locked safety rules:

- sparse reference observation dates are not ownership bounds
- exact stable-ID authority wins over ticker-text reuse
- unresolved histories receive zero operational depth
- no ticker-text history splice
- 252 sessions are not a universal ticker prerequisite

## Gate 10 - ticker-state persistence/stability: ACCEPTED

Evidence contract:

`ticker-persistence-probe-v1-safe-history-composite-vs-dimensional-confirmation`

Selected policy:

`ticker-persistence-policy-v1-two-session-dimensional-confirmation`

2026-08-14 evidence across 1,713,049 state observations:

- raw transition rate: 48.10%
- raw one-session run share: 53.84%
- raw A->B->A flipbacks: 268,095
- selected dimensional-confirm-2 transition rate: 21.40% (55.50% reduction)
- one-session run share: 15.75%
- A->B->A flipbacks: 2,714 (~98.99% reduction)
- directional-family agreement: 90.38%
- opposite-direction mismatch: 7.71%

Three-session candidates were rejected because directional lag increased materially. Confirmation resets across missing XNYS sessions.

## Gate 11 - self-relative ticker risk/volatility: ACCEPTED

Evidence contract:

`ticker-risk-probe-v1-safe-self-relative-prior-only-lookback-grid`

Fallback audit:

`ticker-risk-fallback-audit-v1-current-severity-and-history-cohorts`

Selected production policy:

`ticker-risk-policy-v1-126-primary-60-provisional-prior-only`

Production semantics:

- >=126 prior sessions: `FULL_126`
- 60-125 prior sessions: `PROVISIONAL_60`
- <60 prior sessions: insufficient history; no self-relative risk/efficiency state
- missing exact current metrics: no current self-relative state
- identity-blocked history: no historical self-relative state
- 252 sessions remain an audit/reference horizon, not a production prerequisite
- all thresholds are prior-only; current observation excluded

Safety evidence:

- 126 vs 252: 99.70% within one risk level, 0.00% 2+ level understatements, 0/1,066 `STRESSED -> CALM/NORMAL`
- 60 vs selected 126 target: 0.00% 2+ level understatements, 0/914 `STRESSED -> CALM/NORMAL`; remaining larger errors were conservative overstatements

## Gate 12 - production ticker-regime materialization: ACCEPTED

Contracts:

- `ticker-state-policy-v1-confirm2-dimensional-risk126-60`
- `ticker-state-snapshot-v1-routed-identity-persistence-risk`
- `ticker-state-manifest-v1-policy-lineage`

Accepted 2026-08-14 target-machine materialization:

- records: 8,034
- raw/effective current state available: 7,338
- confirmed 2-session persistence: 7,231
- current-only identity-blocked: 104
- current-only shallow-history: 3
- no current state: 696
- history status: 1,090 authoritative / 6,830 current-alias-no-conflict / 17 unresolved multi-alias / 97 unresolved ticker reuse
- risk modes: 7,340 `FULL_126` / 212 `PROVISIONAL_60` / 304 insufficient / 64 no-current-metrics / 114 identity-blocked
- effective state counts sum exactly to 7,338
- dependency fingerprint: `a4fa34175df4e3949e8972e1033651fea64e8f708c09c764f6bd19be2c396a95`
- snapshot SHA-256: `b516165225847e583c9073b5333232765f69fd332aa8208a79c93b2b9e1049d9`
- first build: `MATERIALIZED`, 146.956s
- immediate second build: `CURRENT / SKIPPED`, 3.361s
- second run preserved identical record counts, state/risk distributions, dependency fingerprint, and snapshot SHA

The materializer persists exactly one row per routed stable identity. Identity-blocked and shallow histories may retain current-only regime context, but historical claims remain explicitly limited. No provider history is spliced by ticker text.

## Gate 13 - final hierarchy/integrity validation: CURRENT

Audit contract:

`regime-hierarchy-integrity-v1-market-sector-proxy-optional-sic-ticker`

The final audit validates:

- accepted market snapshot contract, exact as-of date, and snapshot SHA
- exact 11-member sector-proxy set with an effective state for every proxy
- one ticker-state row per expected routed stable identity
- exact current ticker match between universe routing and ticker-state snapshot
- no missing or extra routed identities
- market context can be attached to every routed ticker record
- Gate 9 history status, Gate 10 persistence status, and Gate 11 risk mode accounting remain intact
- industry policy remains `OPTIONAL_AUTHORITATIVE_SIC_ONLY`
- sector assignment policy remains `NO_GUESSED_CROSSWALK`
- the accepted 250-name Massive classification probe remains evidence that provider-native SIC can be attached when available; missing SIC is allowed and never fabricated

Audit command:

```powershell
.\.venv\Scripts\python.exe scripts\audit_regime_hierarchy.py --as-of 2026-08-14
```

Phase 09 remains open until Gate 13 passes on the target machine and the full suite remains green.
