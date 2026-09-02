# LIT-01 Literature-Native Population and Predictor Source

**Branch:** `literature-anchored-alpha-exploration`  
**Scope:** exploratory source/population fidelity only  
**Target outcomes:** CLOSED  
**Protected outcomes:** CLOSED

## Accepted predecessor evidence

The accepted total-return source result is:

`TOTAL_RETURN_SOURCE_SEMANTICS_PASS_ALPACA_PRIMARY`

Alpaca historical daily bars with `adjustment=all` are therefore the accepted primary LIT-01 historical total-return source. Massive PIT references plus ATLAS stable identity remain identity authority. This acceptance does not imply alpha support or trading authority.

The first full adjusted lag-endpoint acquisition then completed on exact branch head `47cb4080eb129106c36203c77ab49dfe4ec618e4` with status:

`ADJUSTED_PREDICTOR_SOURCE_CAPACITY_READY_FOR_REVIEW`

Target-machine evidence:

- plan fingerprint: `fabc33802154ffae053cceca330917a85b86b1e6ec98b30b17dcd8b6c1497d0a`;
- 109 / 109 required endpoint sessions;
- 8,210 / 8,210 deterministic acquisition units complete;
- 815,442 unique endpoint/instrument rows;
- 784,477 `AVAILABLE`;
- 30,965 `ZERO_BAR`;
- zero provider rejections;
- `momseason_short_year1`: 516,084 adjusted-reconstructable rows out of 537,515 stable-identity rows (`0.960129`);
- `momseason_years2_5`: 303,835 adjusted-reconstructable rows out of 313,947 strict-all-four stable-identity rows (`0.967791`);
- zero target outcome reads;
- zero protected return reads;
- protected holdout unconsumed;
- zero broker/order/PAPER/LIVE activity.

This proves that the accepted Alpaca adjusted-price layer itself is not the dominant source bottleneck. The broad census is preserved as valid source-capacity evidence, but its **population interpretation is not the final literature-native population** for two reasons discovered before any outcome access.

## Literature-fidelity correction 1 — native formation universe

OpenSourceAP commit `8db892442c2c3a3779b0f1eac4370d3655be15a1` provides two relevant layers:

1. `Signals/pyCode/SignalMasterTable.py` globally retains CRSP share codes `10`, `11`, `12` and exchange codes `1`, `2`, `3` — common stocks on NYSE, AMEX/NYSE American, and Nasdaq.
2. `SignalDoc.csv` applies `exchcd%in%c(1,2)` to both `MomSeasonShort` and `MomSeason`, so the Heston-Sadka portfolio-formation cross-section is NYSE + AMEX, not Nasdaq.

The earlier ATLAS adjusted-endpoint census instead began from `discovery_eligible`. That route is broader and also embeds ATLAS-specific policy: NYSE, Nasdaq, ARCA, BATS and AMEX; common stocks, ADRs, ETFs, ETNs, funds and preferreds; ATLAS identity-quality/data-health/manual exclusions.

That is appropriate for ATLAS discovery, but it is not a neutral literature replication population.

The native source contract therefore starts from the complete PIT **reference snapshot**, not the discovery route, and uses the provider-native mapping:

- formation market: `stocks`;
- formation locale: `us`;
- formation security type: Massive `CS` (`Common Stock`);
- formation primary exchange: `XNYS` or `XASE`;
- one unambiguous active listing per stable instrument identity.

Massive `CS` is the closest provider-native analogue to OpenSourceAP's retained ordinary common-share codes. `ADRC`, ETFs, funds, preferreds, units and other ATLAS discovery types are not included in the native LIT-01 formation population.

## Literature-fidelity correction 2 — available annual history

The original strict ATLAS endpoint planner required all four annual lags for `momseason_years2_5`. That was deliberately conservative for source feasibility, but it is stricter than the external replication.

OpenSourceAP `MomSeason.py` constructs the years-2-to-5 signal from the four annual same-month lag columns and divides by the number of nonmissing annual lags. The replicated definition therefore uses the **available** annual history among years 2, 3, 4 and 5 rather than requiring all four observations.

The prospective source rule is now:

- `momseason_short_year1`: the year-1 same-calendar-month lag must be valid;
- `momseason_years2_5`: assess years 2, 3, 4 and 5 independently; at least one valid annual lag is required; the later frozen signal formula will average the available annual lag returns;
- lag-count `1/2/3/4` is retained explicitly for population and later robustness analysis;
- the strict-all-four population remains preserved as earlier source evidence and may later be used only as a predeclared robustness slice, not as the primary literature replication.

No LIT-01 target return was inspected to choose this rule.

## Historical lag membership and ticker changes

OpenSourceAP's signal master table contains common stocks on NYSE/AMEX/Nasdaq before the MomSeason formation filter is applied. Therefore the lag-month observation may come from `XNYS`, `XASE`, or `XNAS`, while the target formation cross-section remains `XNYS`/`XASE` only.

For each annual lag:

- the lag-month reference row must be a common stock on NYSE/AMEX/Nasdaq;
- the previous-month endpoint is a price anchor for that monthly return and requires stable identity/ticker metadata, but is not incorrectly subjected to a second portfolio-membership filter;
- a ticker change inside the lag month is **not** an economic discontinuity when the same ATLAS stable `instrument_id` is proven at both endpoints;
- prior code that rejected all within-lag ticker changes is preserved as earlier conservative evidence, but the native source contract permits them and requests each endpoint under its own PIT historical ticker.

## Reuse-first supplemental acquisition

The native population source does not discard the completed 815,442-row adjusted endpoint acquisition.

It builds the externally specified native endpoint plan and compares each `(endpoint_session, instrument_id)` key with the accepted adjusted endpoint Parquet:

- matching keys are reused with their existing source provenance;
- only endpoint keys absent because of the old strict-all-four or same-ticker planner enter a supplemental plan;
- a reused key with a conflicting PIT historical ticker is a hard integrity failure;
- supplemental acquisition remains single-session only with `adjustment=all`, `feed=sip`, `timeframe=1Day`, and `asof=endpoint_session`;
- dates remain restricted to `required_lag_reference_dates()` and cannot enter the protected window;
- completed supplemental units are resumable and retain raw Alpaca response provenance.

The native endpoint materialization records whether each row is reused accepted evidence or a native supplemental endpoint.

## Native population census

The source funnel is measured at one stable grain:

`formation_month_hypothesis_instrument`

Stages:

1. **literature-native formation population** — complete PIT NYSE/AMEX common-stock source scope;
2. **identity/formula-defined population** — sufficient stable PIT annual-lag identity under the externally replicated available-history rule;
3. **adjusted/formula-defined population** — sufficient accepted `adjustment=all` endpoint availability to define the predictor later.

For each hypothesis the report records:

- native formation rows;
- identity-defined rows;
- adjusted-defined rows;
- adjusted/native and adjusted/identity retention;
- monthly native/identity/adjusted cross-section counts;
- minimum, median and maximum adjusted monthly cross-section size;
- valid annual-lag count distribution;
- historical identity/source failure reasons;
- ticker-change lags retained under stable identity.

The generic `research_population_coverage` contract remains an audit layer, but its 5% severe-attrition flag is diagnostic only. Final LIT-01 research-power/sample requirements are not inferred from this source census.

## Safety boundary

This package may acquire missing **lag-predictor endpoints only**. It does not calculate a monthly predictor return, read a formation/target-month return, inspect the master protected window, or change production state.

Hard report fields remain:

- `target_outcome_rows_read = 0`;
- `protected_return_rows_read = 0`;
- `protected_holdout_consumed = False`;
- canonical market data mutation = `False`;
- global Alpaca adjustment mutation = `False`;
- broker/order/PAPER/LIVE activity = `0`.

## Next decision boundary

A completed native run may return:

`NATIVE_POPULATION_SOURCE_CAPACITY_READY_FOR_REVIEW`

That status means the externally specified population and predictor-input capacity are ready to be evaluated. It is not alpha support.

Only after the native source population is accepted may LIT-01 proceed to a literature-specific research-gate calibration and prospective scientific freeze. That downstream freeze must be based on **monthly independent portfolio observations**, not the hundreds of thousands of stock-level source rows, and must remain fully prospective before any development target outcomes are opened.
