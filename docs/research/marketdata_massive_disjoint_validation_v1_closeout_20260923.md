# MarketData x Massive Disjoint EOD Validation V1 Closeout — 2026-09-23

## Final status

**FAILED / FROZEN / NOT TO BE RERUN AS V1**

Preregistered contract:

`atlas-marketdata-massive-disjoint-validation-v1`

Accepted workstation evidence:

- run id: `20260923T211759Z`;
- evidence fingerprint:
  `2ab5dc3012bdbda388e6d2648403814999c54aa9ac0d4184295c595072eea145`;
- result: `VALIDATION_FAILED`;
- anchor pass count: 3/4;
- terminal error: none;
- observed MarketData credits consumed: 8;
- last observed MarketData credits remaining: 9,984.

The frozen thresholds are unchanged after observing this result.

## Anchor outcomes

### IWM — PASS

- selected contract: `IWM260306C00262000`;
- MarketData rows: 9;
- Massive rows: 9;
- overlap: 9/9 = 100%;
- MarketData last inside Massive daily range: 100%;
- median relative last/close difference: 0%;
- median relative volume difference: 0%;
- all preregistered anchor checks passed.

### AMZN — PASS

- selected contract: `AMZN260501C00210000`;
- MarketData rows: 7;
- Massive rows: 7;
- overlap: 7/7 = 100%;
- MarketData last inside Massive daily range: 100%;
- median relative last/close difference: 0%;
- median relative volume difference: 0%;
- all preregistered anchor checks passed.

### META — PASS

- selected contract: `META260702C00600000`;
- MarketData rows: 9;
- Massive rows: 9;
- overlap: 9/9 = 100%;
- MarketData last inside Massive daily range: 100%;
- median relative last/close difference: 0%;
- median relative volume difference: 0%;
- all preregistered anchor checks passed.

### DIA — FAIL

- selected contract: `DIA260904C00531000`;
- MarketData rows: 9;
- Massive daily aggregate rows: 4;
- overlap: 4/9 = 44.444444%;
- MarketData last inside Massive daily range on overlapping sessions: 100%;
- median relative last/close difference on overlapping sessions: 0%;
- median relative volume difference on overlapping sessions: 0%;
- failed checks:
  - minimum 5 overlapping sessions;
  - 100% overlap coverage.

DIA did **not** fail the price, range-containment or volume thresholds on the sessions
where both providers had a row. It failed the frozen coverage requirement.

## Aggregate outcome

Across the 29 overlapping validation sessions:

- exact MarketData-last / Massive-close match rate: 96.551724% — descriptive only;
- aggregate median relative last-close difference: 0%;
- maximum relative last-close difference: 11.557789%;
- aggregate MarketData-last-inside-Massive-range rate: 100%;
- aggregate median relative volume difference: 0%;
- maximum relative volume difference: 6.849315%.

The aggregate price and volume median checks passed. The overall gate failed because
the preregistration required **all four anchors** to pass.

## Interpretation boundary

The V1 result is a real failed validation and is preserved as such.

ATLAS will not:

- relax the 100% overlap threshold after seeing DIA;
- drop DIA from the sample;
- replace DIA with a new anchor inside V1;
- rerun V1 and select a more favorable result; or
- promote the three passing anchors into historical-price authority.

Current Massive documentation states that daily aggregates are derived only from
qualifying trades and that no aggregate bar is emitted when no eligible trade exists
for an interval. That mechanism is a plausible explanation for DIA's 4/9 aggregate
coverage, but it is **not assumed**. The next package is a separately versioned
diagnostic that inspects the exact missing DIA dates and Massive raw trades/condition
rules.

## Authority

V1 creates no MarketData EOD last/volume validation authority because its all-anchor
gate failed.

Still closed:

- historical bid/ask authority;
- intraday option-price authority;
- execution/slippage authority;
- simulator option-P&L authority;
- PIT option-selection authority;
- strategy evidence;
- PAPER/LIVE authority;
- broker/order authority; and
- promotion/confluence authority.

The Strategy Evidence Register remains unchanged.
