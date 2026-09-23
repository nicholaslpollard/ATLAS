# MarketData.app Starter Trial Capability Acceptance — 2026-09-23

## Status

**ACCEPTED / STARTER-TRIAL CAPABILITY QUALIFIED / BROAD FIVE-YEAR ENTITLEMENT NOT PROVEN**

Source contract:

`atlas-marketdata-five-year-historical-options-v1`

Accepted workstation run:

- run id: `20260923T203419Z`;
- evidence fingerprint:
  `facd9289fc56279a14294c442f8a1f256388cfd152662be1bc06f600d1bf914a`;
- qualification status: `QUALIFIED_FOR_STARTER_TRIAL_CAPABILITY`;
- terminal error: none;
- observed API credits consumed: 8;
- last observed API credits remaining: 9,992.

## Accepted anchors

| Underlying | PIT date | Selected qualification-only contract | Chain rows | Quote rows |
| --- | --- | --- | ---: | ---: |
| AAPL | 2021-10-01 | AAPL211029C00143000 | 16 | 7 |
| SPY | 2026-03-02 | SPY260331C00686000 | 16 | 9 |
| MSFT | 2026-05-01 | MSFT260529C00415000 | 16 | 7 |
| NVDA | 2026-07-01 | NVDA260731C00200000 | 16 | 7 |
| QQQ | 2026-09-01 | QQQ260930C00708000 | 16 | 8 |

Every anchor had:

- non-empty historical option-chain data;
- non-empty selected-contract historical EOD quote series;
- non-null historical open interest in every returned chain and quote row;
- at least one usable finite, non-crossed bid/ask observation in both chain and
  quote-series evidence;
- all required schema fields;
- historical IV/delta/gamma/theta/vega present and null as documented.

The deep AAPL 2021-10-01 trial exception succeeded and therefore proves deep-history
endpoint mechanics for AAPL under the trial. It does **not** prove that the Starter
Trial or unpaid account can retrieve five years for arbitrary non-AAPL tickers.

## What this accepts

The run establishes that MarketData.app is technically capable, under the current
Starter Trial, of supplying the candidate-first data mechanics ATLAS needs:

`historical chain -> exact OCC contract -> short historical EOD quote path`

It also validates the provider's historical OI field availability and the expected
absence of stored historical Greeks.

This is sufficient to advance MarketData from **unproven trial candidate** to
**qualified Starter-Trial capability source**.

## What this does not accept

This result does not establish:

- broad five-year entitlement across arbitrary underlyings;
- historical price authority for the simulator;
- a PIT contract-selection rule;
- independent bid/ask validation;
- an execution/slippage model;
- intraday option replay;
- strategy evidence;
- PAPER/LIVE authority;
- broker/order authority; or
- promotion/confluence authority.

The qualification contract's selected contracts are endpoint-linkage probes only.
They must not become a simulator contract-selection rule because their selection used
provider EOD-D moneyness information.

## Next gate — independent recent overlap

Before any paid Starter purchase, ATLAS will use the accepted local MarketData raw
evidence and the existing Massive Options Basic entitlement for a **read-only,
four-contract semantic calibration**:

- SPY260331C00686000;
- MSFT260529C00415000;
- NVDA260731C00200000;
- QQQ260930C00708000.

For each contract, ATLAS will request one unadjusted Massive 1Day aggregate series
over the exact MarketData quote window and compare MarketData historical
`last`/volume with Massive daily close/volume on overlapping sessions.

The 2021 AAPL anchor is excluded from this Massive REST diagnostic because the current
Massive Options Basic plan exposes only two years of REST aggregate history.

This next package is intentionally **exploratory semantic calibration** with no
post-hoc price-authority threshold. If overlap is coherent, a separately preregistered
validation package must use a disjoint contract/date sample before any MarketData
historical-price authority is considered.

Massive Basic does not expose historical option quotes, so this overlap cannot
independently validate MarketData bid/ask. Bid/ask authority remains unresolved until
a separately qualified source (for example, recovered Czar28 if its historical EOD
schema supports the needed field semantics) can provide independent overlap.

## Authority

This acceptance changes provider-source qualification state only. The Strategy
Evidence Register remains unchanged.
