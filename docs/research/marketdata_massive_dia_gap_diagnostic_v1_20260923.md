# MarketData x Massive DIA Aggregate-Gap Diagnostic V1 — 2026-09-23

## Status

**PREREGISTERED / WORKSTATION EVIDENCE PENDING**

Contract:

`atlas-marketdata-massive-dia-gap-diagnostic-v1`

This diagnostic follows the frozen failed disjoint validation in
`docs/research/marketdata_massive_disjoint_validation_v1_closeout_20260923.md`.

It does **not** reopen, rerun, reinterpret or weaken that V1 gate.

## Exact source evidence

The diagnostic is bound to:

- failed validation run: `20260923T211759Z`;
- evidence fingerprint:
  `2ab5dc3012bdbda388e6d2648403814999c54aa9ac0d4184295c595072eea145`;
- target contract: `DIA260904C00531000`;
- MarketData EOD rows: 9;
- Massive daily aggregate rows: 4;
- overlapping sessions: 4;
- validation result: `VALIDATION_FAILED`.

Before any provider call, ATLAS recomputes the failed report fingerprint and verifies
the MarketData and Massive raw files against their original SHA-256 receipts.

## Provider hypothesis being tested

Massive's current options aggregate documentation states that bars are constructed
from qualifying trades and that an interval with no eligible trades produces no
aggregate bar. Massive's own missing-aggregate guidance recommends checking the raw
Trades endpoint for the same window.

Therefore the five missing DIA aggregate dates can have materially different
meanings:

1. **No raw trades** — a MarketData EOD quote row can exist even though Massive has
   no trade from which to construct an OHLC bar.
2. **Raw trades exist but no price-eligible trades** — Massive may correctly omit a
   daily OHLC bar under its trade-condition rules.
3. **Price-eligible raw trades exist but no daily bar** — this is a stronger
   provider/reference inconsistency requiring separate investigation.
4. **Condition metadata is insufficient** — preserve the date as unresolved rather
   than guessing eligibility.

This diagnostic distinguishes those cases.

## Frozen procedure

ATLAS will reuse the accepted local MarketData and Massive raw evidence and first
derive the exact dates present in MarketData but absent from Massive daily aggregates.

It then makes:

- **0 MarketData calls**;
- one Massive options trade-condition metadata query;
- one bounded Massive raw-trades query for each missing DIA aggregate date;
- up to three pages per missing date, with `limit=50000` per page;
- 0 provider writes.

For every missing date, the report records:

- MarketData EOD last, volume, bid and ask;
- Massive raw trade count and summed size;
- trade condition IDs;
- provider condition names and consolidated update rules;
- count of trades eligible to update an OHLC price field;
- count eligible to update volume;
- count fully ineligible for aggregate fields;
- unresolved eligibility count;
- raw-response SHA-256 receipts; and
- a deterministic date disposition.

## Trade-condition interpretation

For each aggregate statistic, a condition-level `false` takes precedence over a
`true` when multiple conditions are attached to the same trade. Trades with no
condition code are treated as ordinary price/volume-eligible trades.

The diagnostic distinguishes **price eligibility** from **volume eligibility**.
A volume-only condition is not treated as proof that a missing daily OHLC bar should
exist.

Possible date dispositions:

- `NO_RAW_TRADES`;
- `NO_PRICE_ELIGIBLE_RAW_TRADES`;
- `RAW_TRADES_PRESENT_ELIGIBILITY_UNRESOLVED`;
- `PRICE_ELIGIBLE_RAW_TRADES_WITHOUT_DAILY_BAR`.

## Decision boundary

This package is diagnostic only.

Even if all five missing dates are explained by no raw trades or no price-eligible
trades:

- the original disjoint V1 remains `VALIDATION_FAILED`;
- its thresholds remain frozen;
- MarketData EOD last/volume does not become validated retroactively.

A coherent explanation may justify a **new V2 hypothesis** whose coverage criterion
is designed around the semantics of a trade-derived independent reference source.
Any V2 must use another disjoint sample and be preregistered before those provider
reads.

If price-eligible raw trades are found on missing-bar dates, ATLAS will investigate
Massive corrections/timestamp/aggregate construction before designing V2.

## Authority

No historical-price, bid/ask, intraday, execution, simulator, strategy, PAPER, LIVE,
broker/order, promotion or confluence authority.
