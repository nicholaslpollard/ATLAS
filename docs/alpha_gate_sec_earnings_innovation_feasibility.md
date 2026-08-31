# Pre-Phase33 SEC Diluted-EPS Earnings-Innovation Source Feasibility

## Purpose

This gate tests whether ATLAS has enough **source-only, point-in-time-compatible SEC XBRL diluted-EPS history** to justify a later earnings-innovation study. It does not read stock prices, SPY prices, market returns, protected returns, broker state, orders, PAPER, or LIVE trading state.

Frozen feasibility contract:

`alpha-gate-sec-earnings-innovation-feasibility-v1-diluted-eps-source-only-no-market-outcomes`

Frozen feasibility fingerprint:

`c32e4aa83b25cdc23476098ffc30bd48908123d047d75f18f0d45b2acaffcd0d`

Mechanism under source review:

`PIT_SEC_XBRL_DILUTED_EPS_SEASONAL_EARNINGS_INNOVATION_POST_PERIODIC_FILING_DRIFT`

Parent accepted `main` merge:

`715d8df8c07a58f10deeade14877757a6dea36a6`

## Scientific boundary

This is **not an earnings-announcement PEAD gate**. A 10-Q or 10-K can be filed after an issuer has already released earnings through another channel. Therefore this feasibility package makes no claim that a periodic filing acceptance timestamp is the market's first earnings-announcement timestamp.

If source feasibility passes, the next gate must be a separately frozen **source-only PIT original-accession and SEC-acceptance chronology audit**. Only after that audit may ATLAS decide whether a scientifically valid periodic-filing earnings-innovation hypothesis can be frozen. No market return may be used to decide that source/timing question.

## Frozen source representation

- official SEC Company Facts endpoint through `SECXBRLCompanyFactsClient`
- source window: `2016-01-01` through `2026-08-11`
- deterministic sample: exactly `300` CIKs drawn from the accepted Phase32 source-only issuer inventory
- sample ranking: SHA-256 of `CIK + feasibility contract`, ascending
- concept: `us-gaap:EarningsPerShareDiluted`
- unit: exact `USD/shares`
- forms: original-source candidates limited here to `10-Q` and `10-K`
- direct-quarter diagnostic duration: `70..110` days inclusive
- no fallback to basic EPS, net income, analyst estimates, market prices, or prior XBRL performance results

The gate deliberately measures source capacity only. Exact accession versioning, first-public acceptance ordering, amended filing treatment, fiscal-quarter identity, and unique PIT instrument identity remain work for the next source-only gate.

## Frozen numeric feasibility gates

All must pass:

- exact sample size: `300`
- successful Company Facts documents: at least `270`
- EPS-bearing documents: at least `210`
- issuers with at least `12` distinct direct-quarter EPS period ends: at least `180`
- issuers with at least `16` distinct direct-quarter EPS period ends: at least `120`
- total issuer/direct-quarter observations: at least `2,500`
- distinct calendar years represented by direct-quarter observations: at least `8`
- same-accession / same-semantic-context conflicting diluted-EPS values: `0`

The `16`-quarter depth threshold is a source-capacity proxy for a later standardized seasonal earnings-innovation baseline. It is **not** itself an SUE formula and does not freeze a trading hypothesis.

## Governance

At this gate:

- alpha hypotheses are not frozen;
- target market outcomes are forbidden;
- protected market outcomes are forbidden;
- the protected holdout remains unconsumed;
- provider writes are zero;
- broker reads/writes are zero;
- order writes are zero;
- PAPER submits are zero;
- LIVE writes are zero;
- automation writes are zero;
- automatic broker failover is disabled;
- Phase33 Signal-to-Trade authority remains false.

A `FEASIBILITY_FAIL` is preserved as a valid source negative. Thresholds may not be lowered after seeing the target result. A genuine mechanical/provider/schema defect may only be repaired under a separately fingerprinted source-repair contract without changing these frozen source gates.
