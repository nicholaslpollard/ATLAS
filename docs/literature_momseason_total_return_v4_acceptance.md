# LIT-01 Total-Return Source Acceptance v4

**Branch:** `literature-anchored-alpha-exploration`  
**Scope:** source semantics only / exploratory / non-authoritative  
**Target outcomes:** CLOSED  
**Protected outcomes:** CLOSED

## Preserved v3 result

The exact-head target-machine v3 run on `5acc9b3a30fbeabd5ed5b28b7677203c5612e5e4` returned:

`TOTAL_RETURN_SOURCE_SEMANTICS_REVIEW_REQUIRED`

The result is preserved and is not reclassified as PASS. Three gates passed:

- minimum complete cases per kind;
- Alpaca adjustment alignment;
- split-ratio alignment.

The only failed gate was `same_currency_provider_value_alignment`. All 18 sampled dividend cases were classified `MISSING_CURRENCY_METADATA`, leaving zero direct same-currency provider-value comparisons.

The same run retained strong source-side price evidence:

- missing-factor dividends: 3 complete price cases;
- with-factor dividends: 5 complete price cases;
- splits: 5 complete price cases;
- currency-valid Massive scale evidence: 10 cases, median relative error `7.640007626402262e-05`, maximum `0.0004481352965559626`;
- split scale evidence: 5 cases, median `5.557051684867975e-05`, maximum `0.0004481352965559626`;
- zero provider calls in v3;
- zero target outcome reads;
- zero protected return reads;
- protected holdout unconsumed;
- zero broker/order/PAPER/LIVE activity.

## Root cause

The v3 code joins the immutable v2 cases back to the full retained Massive and Alpaca action caches. The normalization layer preserves complete provider action rows rather than selecting a reduced field list. Therefore the missing Alpaca dividend currency values are not a derived-cache projection bug.

Alpaca's current Market Data documentation states that `currency` is part of corporate-action schemas, but the historical dividend records retained by the actual source run do not populate usable currency metadata for the sampled cases. ATLAS must not infer or manufacture that missing metadata.

## V4 repair contract

V4 is additive, cached-only, and preserves v1/v2/v3 evidence. It does not lower the frozen 10-basis-point source tolerances.

The failed v3 direct same-currency amount gate is replaced only because it is **unevaluable**, not because its observed value was unfavorable. V4 substitutes dimensionally valid independent corroboration already present in the frozen source evidence:

1. **Minimum complete evidence:** at least 3 complete cases remain required for each source family: missing-factor dividends, with-factor dividends, and splits.
2. **Alpaca internal adjustment alignment:** for every complete v2 case, the Alpaca corporate-action value must explain the observed `raw` versus `adjustment=all` scale within `0.001` relative error.
3. **Massive USD-dividend corroboration:** at least 3 complete dividend cases explicitly denominated `USD` by Massive must independently explain the Alpaca price-scale change within `0.001` relative error.
4. **Split corroboration:** at least 3 complete split cases must independently explain the Alpaca price-scale change within `0.001` relative error.

No FX conversion is introduced. Non-USD or missing-currency dividend values are not directly compared with USD price bars.

## Accepted v4 target-machine result

The exact-head target-machine v4 run on `b80db8a33b60d9eb66ee0aba812e2353cd570b36` returned:

`TOTAL_RETURN_SOURCE_SEMANTICS_PASS_ALPACA_PRIMARY`

All four frozen source gates passed:

- `minimum_complete_cases_per_kind = True`;
- `alpaca_internal_adjustment_alignment = True`;
- `massive_usd_dividend_scale_corroboration = True`;
- `split_ratio_alignment = True`.

Accepted evidence:

- complete adjusted-price cases: 3 missing-factor dividends, 5 with-factor dividends, and 5 splits;
- Alpaca internal adjustment-scale relative error: 13 cases, median `0.000102937793342242`, maximum `0.0004853492895708397`;
- Massive USD-dividend independent scale corroboration: 5 cases, median `0.000102937793342242`, maximum `0.0003534828573442557`;
- split independent scale corroboration: 5 cases, median `5.557051684867975e-05`, maximum `0.0004481352965559626`;
- provider calls in v4: 0;
- canonical data mutation: none;
- target outcome rows read: 0;
- protected return rows read: 0;
- protected holdout consumed: False;
- broker/order/PAPER/LIVE activity: none.

## Meaning of the accepted v4 result

The accepted source conclusion is narrowly:

- Alpaca historical daily bars with `adjustment=all` are accepted as the primary LIT-01 historical total-return source;
- Massive PIT reference snapshots plus ATLAS `InstrumentIdentityResolver` remain identity authority;
- Massive USD dividends and split ratios remain independent source corroboration;
- missing Massive `historical_adjustment_factor` values are not filled, reconstructed, or used to compute LIT-01 returns.

This source-semantic acceptance does **not** mean LIT-01 alpha is supported. It grants no Phase33, PAPER, LIVE, broker, execution, or production authority.

## Next source-capacity stage

After the accepted v4 result, ATLAS may materialize only the lagged predictor endpoints required by the already-frozen LIT-01 formulas.

The next acquisition contract is deliberately narrower than a general historical backfill:

- endpoint dates come exclusively from `required_lag_reference_dates()`;
- each Alpaca request is one historical session only (`start == end == endpoint_session`);
- `adjustment=all`, SIP daily bars, USD price semantics, and `asof=endpoint_session` are fixed;
- only instruments that belong to the PIT eligible formation population and have stable historical identity for the required lag are planned;
- exact provider response bytes and rejection evidence are retained in the isolated LIT-01 Alpaca namespace;
- the derived endpoint artifact is provider-neutral and keyed by endpoint session + stable instrument id;
- the source-capacity report audits the complete eligible population -> stable-identity population -> adjusted-endpoint-reconstructable population using the retained `research_population_coverage` contract;
- no monthly predictor return is calculated in this stage;
- no formation-target return, development outcome, or protected return is read.

The first complete target-machine materialization ends at `ADJUSTED_PREDICTOR_SOURCE_CAPACITY_READY_FOR_REVIEW`, not a post-hoc coverage PASS. Any minimum source-coverage rule must be frozen after reviewing source missingness and still before target outcomes are opened.
