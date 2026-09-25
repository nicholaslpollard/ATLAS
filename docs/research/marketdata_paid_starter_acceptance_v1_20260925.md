# MarketData.app Paid Starter Five-Year Qualification V1 Acceptance — 2026-09-25

## Observed first-run result

**QUALIFIED_FOR_FIVE_YEAR_EOD_ECONOMICS_CHALLENGER**

The operator supplied the complete console output of the first paid-Starter workstation
qualification. It is retained as observed workstation evidence, not a new provider
query or a fresh GitHub-side reproduction.

- Frozen contract: `atlas-marketdata-five-year-historical-options-v1`
- Contract fingerprint: `7855b0cd49ad725841aa90d8b6cd78083402d22fe7a5b0cc4aae8050cec392b3`
- Run ID: `20260925T182731Z`
- Evidence fingerprint: `f7a0c78e6812e59bf1b7efd243ce9c66c0325aa7241fd5a46868b3fc2224747a`
- Plan mode: paid Starter; **not** the Starter Trial.
- Raw receipts and report retained on the operator workstation at
  `data/research/provider_qualification/marketdata_app/historical_options_v1/20260925T182731Z/report.json`.
- Observed credits consumed: **10**; last observed remaining: **9,990**.
- Terminal error: **none**.

| Underlying | Historical anchor | Selected qualification-only OCC contract | Chain rows | Quote rows | Non-null OI (chain / quote) |
| --- | --- | --- | ---: | ---: | ---: |
| SPY | 2021-10-01 | `SPY211101C00434000` | 16 | 7 | 16 / 7 |
| AAPL | 2022-10-03 | `AAPL221104C00142000` | 16 | 9 | 16 / 9 |
| MSFT | 2023-10-02 | `MSFT231103C00320000` | 16 | 9 | 16 / 9 |
| NVDA | 2024-10-01 | `NVDA241101C00117000` | 16 | 9 | 16 / 9 |
| QQQ | 2025-10-01 | `QQQ251031C00603000` | 16 | 8 | 16 / 8 |
| SPY | 2026-09-01 | `SPY260930C00762000` | 16 | 8 | 16 / 8 |

The six anchors total 96 returned chain rows and 50 returned selected-contract
quote rows. Every anchor returned usable bid/ask rows, non-null OI, required schema,
and present-but-null historical Greek fields. The oldest non-AAPL SPY anchor was
non-empty, establishing sampled paid-plan historical access that the trial-only
AAPL exception could not demonstrate.

All frozen paid-plan checks reported true:

- oldest 2021-10-01 anchor;
- broad five-year entitlement on the sampled six-anchor qualification;
- non-empty chains and quote series for every anchor;
- OI and usable bid/ask across all anchors;
- required schema and historical-Greeks-null behavior.

## What this acceptance does and does not establish

This closes the **bounded paid-Starter entitlement/schema/OI/endpoint qualification**
and supersedes the prior pending-paid-qualification status. It demonstrates sampled
access across the rolling five-year window, **not exhaustive coverage of every
underlying, option contract, or date**.

It does not validate EOD option bid/ask as executable fills, zero-volume last as an
independent trade price, historical option intraday paths, derived Greeks, a
PIT-safe contract selector, option P&L, strategy evidence or PAPER/LIVE authority.

For historical decision date D, settled open interest is the D-1 observation;
bid/ask/last/volume/underlyingPrice are EOD-D. A strategy decision before the close
cannot inspect EOD-D prices, volume, provider-side moneyness or strikeLimit selection.
As-traded option data must not silently combine with incompatible adjusted stock
prices or unqualified nonstandard deliverables.

Prior independent vendor evidence is preserved without changing its verdicts:
disjoint validation V1/V2 both failed their frozen gates, the sparse V1 run failed
its positive-control floor despite complete observed activity concordance, and
sparse-activity confirmation V2 remains preregistered but not yet observed.

## Next engineering package

The subscription should now support the **candidate-first five-year EOD acquisition
adapter**: exact PIT stock opportunity -> bounded, explicit-strike/expiry option
request -> frozen contract selection -> selected-contract EOD quote horizon -> raw
SHA-256 receipt -> deduplicated storage/cache -> conservative EOD-only simulator
integration. No whole-universe bulk download is authorized.

The external-secondary-storage architecture is merged, but its hardware activation
remains pending. This report and its raw receipts are existing local secondary data
and must be preserved/migrated under
`data/research/provider_qualification` when the external NVMe is bound. The core
stock database and ATLAS installation remain in their current internal location.

Provider reads remain workstation-only under the current account/IP and licensing
boundaries. No provider token is stored in this acceptance record.
