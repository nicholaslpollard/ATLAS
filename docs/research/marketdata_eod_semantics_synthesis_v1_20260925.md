# MarketData x Massive EOD Source Semantics — Evidence Synthesis V1 (2026-09-25)

## Scope and immutable inputs

This is a **read-only interpretation** of previously opened source experiments, not
a new experiment, a rerun, or new vendor acquisition. It does not change historical
gate verdicts. The source artifacts remain on the operator's workstation.

- Paid Starter historical entitlement/source/schema/OI qualification PASSED:
  `20260925T182731Z` /
  `f7a0c78e6812e59bf1b7efd243ce9c66c0325aa7241fd5a46868b3fc2224747a`.
- Disjoint EOD comparison V2 FAILED under its frozen whole-experiment gate:
  `20260924T023405Z` /
  `7461146a5c3f3f021384fea54cdfae1c4f62b509ed64f55f8a61b1b0d8d13dad`.
  Nevertheless, its **53 positive-volume matched sessions** on six anchors
  showed MarketData last = Massive close in 100% of comparisons; all MarketData
  last values were within independent Massive daily low/high; price and
  volume aggregate median differences were zero; maximum observed relative
  volume difference was ~0.30%. V2 failed its sparse-case requirement: zero
  zero-volume observations. It remains FAILED.
- First sparse confirmation V1 FAILED its preregistered positive-control
  minimum (18 vs 20), despite 105/105 observed activity matches:
  `20260924T033435Z` /
  `d7ce4d184d175b6f60233f2a4470e8e4e67a27691ac8a45a082b805b9e3cce6d`.
  It remains FAILED.
- Fresh sparse confirmation V2 PASSED every frozen check:
  `20260925T184421Z` /
  `398ca760a7e05126e18008c6e7c09fc2f9d03e8a07b5a9a95e0282891d4c2d69`.
  38 zero-volume and 68 positive-volume sessions across 12 fresh anchors,
  106/106 activity concordance with Massive bar absence/presence, zero
  mismatches, no invalid volume, no extra Massive dates.

## Permissible combined source interpretation

For **observed sampled sessions**, the independent results support two distinct
claims, neither a blanket provider price validation:

1. **Positive-volume EOD last/volume calibration**: the 53 positive-volume
   comparisons in failed disjoint V2 aligned closely with Massive trade-derived
   day aggregates. This is informative calibration evidence; V2's overall
   `VALIDATION_FAILED` verdict is unchanged.
2. **Activity-state support**: the fresh sparse V2 sample confirms that
   MarketData positive/zero-volume status matched Massive daily aggregate
   presence/absence, including low-activity contracts. This is accepted
   activity-concordance evidence only; no price checks were performed by
   sparse V2.

Do **not** add the 53 and 106 populations and call them a single joint price
validation. They were different selected instruments/dates and tested different
hypotheses.

## Simulator boundary derived from the evidence

The next engineering step may build a **quarantined candidate-first EOD cache**
with strict source fields and an explicit price-eligibility flag. However:

- A zero-volume `last` is not a validated same-session trade price; do not
  use it for trade execution, favorable fill claims, or realized P&L.
- Historical bid/ask presence and geometric sanity are not executable-fill
  validation. Use them as observed EOD quote context until separate bid/ask
  timestamp/spread/fill and transaction-cost semantics are accepted.
- EOD-D bid/ask/last/volume and provider `underlyingPrice` cannot inform an
  open/intraday-D decision or contract strike selection. OI is D-1-settled.
- A stock signal ending at D close must not use the same D-close option snapshot
  as an already executable D-close option fill without a separate timing model.
  A future EOD-only option experiment must freeze decision/entry/exit cutoffs.
- The selected test-contract moneyness used for provider qualification/validation
  is **not** a PIT-safe simulator selector. Candidate construction must derive
  strike bounds from the accepted stock opportunity-time price and request
  explicit strikes or a bounded interval.
- Preserve as-traded contract identity, expiration, deliverable/corporate-action
  quarantine, raw payload hashes and provider license state.
- No intraday option STOP/TARGET path can be inferred from EOD snapshots.
- Do not treat this synthesis as strategy evidence or historical option P&L.

## Product decision

**Close the source activity mini-campaign.** Prior failed results remain immutable;
the newly passed sparse V2 closes its own experiment. Proceed to bounded,
restart-safe **candidate-first acquisition/cache adapter** rather than further
routine repreregistration loops.

Batch same-ticker/date/expiry/strike windows into one *historical chain* request
where possible. True quote-history REST calls are single-contract; concurrency
alone does not reduce credits. Assess either per-contract quote series or
date-wise shared chains according to explicit credit/row estimates, avoiding
unbounded all-expiration requests. Cache by canonical request identity and
independently verify receipts before reuse. Keep provider calls gated to the
authorized single workstation/IP and enforce retention/licensing. The external
NVMe may hold these secondary datasets when bound; core ATLAS and the Alpaca SIP
V2 stock corpus stay on the internal drive.

Authority: infrastructure and source-observation only. No historical
execution price, P&L, predictor/strategy validation, PAPER, LIVE, broker,
order, promotion, or confluence authority is granted.
