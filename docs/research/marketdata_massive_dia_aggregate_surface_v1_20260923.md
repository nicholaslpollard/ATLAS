# MarketData x Massive DIA Aggregate-Surface Diagnostic V1 — 2026-09-23

## Status

**AGGREGATE_SURFACES_CONSISTENT / DIAGNOSTIC COMPLETE / FROZEN**

Contract:

`atlas-marketdata-massive-dia-aggregate-surface-diagnostic-v1`

This package follows the entitlement-blocked raw-trade diagnostic. It is a new
diagnostic and does not alter the frozen failed disjoint validation or the frozen
raw-trade diagnostic.

## Triggering evidence

The raw-trade diagnostic stopped under:

- run id: `20260923T222933Z`;
- evidence fingerprint:
  `48d58cecf4d084f241f8b6b008454427389be609c18d42ffcdcb318a12be4e6a`;
- status: `DIAGNOSTIC_INCOMPLETE`;
- condition metadata: 33 rows;
- first raw-trade date: 2026-08-06;
- terminal result: HTTP 403.

Current Massive documentation identifies that 403 as consistent with plan
entitlement: historical option trades are not included in Options Basic or Starter,
while custom option aggregate bars are included in Options Basic with end-of-day
recency and two years of history.

## Frozen hypothesis

If the missing daily bars are ordinary consequences of Massive's qualifying-trade
aggregate semantics, the same dates should also lack one-minute aggregate bars while
the dates that have daily bars should produce one-minute aggregate rows.

This is only an aggregate-surface consistency hypothesis. It does **not** prove
whether raw trades existed on a missing date and does not apply trade-condition
eligibility rules.

## Exact source evidence

The diagnostic reuses and verifies the accepted failed-validation evidence for:

- contract: `DIA260904C00531000`;
- window: 2026-08-03..2026-08-13;
- 9 MarketData EOD rows;
- 4 Massive daily aggregate rows;
- daily-bar dates: 2026-08-03, 2026-08-04, 2026-08-05 and 2026-08-11;
- missing daily-bar dates: 2026-08-06, 2026-08-07, 2026-08-10, 2026-08-12 and
  2026-08-13.

The failed validation remains `VALIDATION_FAILED` and immutable.

## Frozen procedure

ATLAS makes:

- **0 MarketData calls**;
- exactly **9 Massive reads**;
- one unadjusted 1-minute custom-aggregate request for each of the nine DIA dates;
- at most 50,000 base aggregates per date;
- 0 provider writes.

The existing Massive 5-requests/minute pacing remains authoritative.

For every date ATLAS preserves:

- whether the original Massive daily bar exists;
- MarketData EOD last, volume, bid and ask from the accepted raw evidence;
- original Massive daily volume when available;
- one-minute aggregate row count;
- summed one-minute aggregate volume;
- raw response and SHA-256 receipt;
- deterministic disposition.

Possible dispositions:

- `DAILY_AND_MINUTE_AGGREGATES_PRESENT`;
- `DAILY_AND_MINUTE_AGGREGATES_ABSENT`;
- `DAILY_PRESENT_MINUTE_ABSENT`;
- `DAILY_ABSENT_MINUTE_PRESENT`.

The aggregate surfaces are classified as consistent only when every daily-present
control has at least one minute bar and every daily-missing target date has no minute
bars.

## Workstation result — 2026-09-23

Accepted diagnostic evidence:

- run id: `20260923T225713Z`;
- evidence fingerprint:
  `dadc60d4eb1bf4f33d123cdd1b8b09d92222f8e53b4fdb3a9a28c48b1d5b1487`;
- status: `AGGREGATE_SURFACES_CONSISTENT`;
- terminal error: none;
- disposition counts:
  - `DAILY_AND_MINUTE_AGGREGATES_PRESENT`: 4;
  - `DAILY_AND_MINUTE_AGGREGATES_ABSENT`: 5.

Observed date-level relationship:

| Date | MarketData volume | Massive daily | Massive minute rows | Massive minute volume |
| --- | ---: | --- | ---: | ---: |
| 2026-08-03 | 3 | present | 2 | 3 |
| 2026-08-04 | 6 | present | 1 | 6 |
| 2026-08-05 | 41 | present | 2 | 41 |
| 2026-08-06 | 0 | absent | 0 | 0 |
| 2026-08-07 | 0 | absent | 0 | 0 |
| 2026-08-10 | 0 | absent | 0 | 0 |
| 2026-08-11 | 1 | present | 1 | 1 |
| 2026-08-12 | 0 | absent | 0 | 0 |
| 2026-08-13 | 0 | absent | 0 | 0 |

The control/target pattern is exact: every positive-volume MarketData date has both
Massive daily and minute aggregate evidence, every zero-volume MarketData date lacks
both Massive aggregate surfaces, and summed Massive minute volume equals MarketData
volume on every positive-volume date.

This does not prove whether the five empty aggregate dates had literally no raw
trades or only no aggregate-eligible raw trades, because the current Massive plan
does not expose historical option trades. It does show that the original 4/9 daily
coverage failure is not isolated to the daily endpoint and that zero MarketData
volume is the observed separator in this frozen case.

The result justifies a separately preregistered activity-aware V2 validation on a new
disjoint sample. It does not change V1.

V2 contract:
`docs/research/marketdata_massive_disjoint_validation_v2_20260923.md`.

## Interpretation boundary

`AGGREGATE_SURFACES_CONSISTENT` would support only this statement: Massive's daily
presence/absence pattern is reproduced on its finer aggregate surface for the frozen
DIA window.

It would **not** establish:

- that no raw trades occurred;
- that raw trades were ineligible under OPRA condition rules;
- that MarketData's EOD last or volume is independently validated;
- that the failed disjoint V1 should be reinterpreted; or
- historical option execution/simulator authority.

`AGGREGATE_SURFACE_INCONSISTENCY` would instead require investigation of Massive
aggregate construction or endpoint semantics before any coverage-aware V2 is designed.

Any validation V2 remains a new preregistered experiment on a new disjoint sample.

## Authority

Diagnostic only. No historical-price, bid/ask, intraday, execution, simulator,
strategy, PAPER, LIVE, broker/order, promotion or confluence authority.
