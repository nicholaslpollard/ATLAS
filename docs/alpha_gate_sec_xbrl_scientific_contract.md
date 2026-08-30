# Pre-Phase33 SEC XBRL Fundamental Alpha — Frozen Scientific Contract

**Status: FROZEN BEFORE MARKET OUTCOMES.** The source/chronology/identity v1 `AUDIT_FAIL` is preserved. The targeted v2 source-semantics repair returned `AUDIT_PASS` with 171 unambiguous active common-stock mappings and 38 issuers with at least three mappings, while reading zero market outcomes and zero protected returns.

## Contract identity

Contract: `alpha-gate-xbrl-scientific-v1-six-yoy-quality-change-hypotheses`

Fingerprint: `239215aad3c151200c77d214d5723e446877fcb014fb2280b9cd909b3ea379ef`

Entry source-repair fingerprint: `e17cf5539fbd5d3d0c31514d5fbed97332f046eb98af05dfaa0039a8c127304f`

The performance population is the exact 200-CIK deterministic feasibility sample. It may not be replaced, expanded, or trimmed because of later returns. Predictor history may use SEC facts from `2016-01-01..2026-08-11`; governed market outcomes begin no earlier than `2021-08-16`.

## Point-in-time predictor semantics

Only original SEC `10-Q` and `10-K` accession versions are eligible. Facts remain attached to the exact accession that published them; later filings never overwrite earlier PIT state. The decision session is the first XNYS session whose open is strictly after SEC acceptance.

Instrument mapping is the accepted corrected rule: exact issuer CIK + exact historical date + `active=true` + `type=CS`, followed by unique STRONG/MEDIUM security-level resolution. No preferred, warrant, right, unit, inactive security, fallback identity, or arbitrary share-class choice is permitted.

`Assets` is an instant USD fact. Net income, operating cash flow, revenue, gross profit, and cost of revenue are USD duration facts. The quarter reconstruction rule is fixed before outcomes:

- prefer a direct 70–110 day standalone quarter duration;
- Q1 YTD is itself the quarter when no distinct direct row is available;
- Q2/Q3 may be reconstructed as current YTD minus the immediately preceding same-fiscal-year PIT YTD value already public by the current acceptance;
- Q4 may be reconstructed from a 300–380 day FY value minus the already public PIT Q1/Q2/Q3 quarter values;
- annual values are never treated directly as quarterly values;
- fiscal `fy`/`fp` controls quarter identity, so non-calendar issuers are not forced onto calendar quarters;
- lagged assets are the most recent prior fiscal-period-end Assets value accepted by the current decision, with a maximum 200-day gap;
- direct `GrossProfit` has precedence. Otherwise gross profit is revenue minus cost for the same accession and economic period. Revenue precedence is `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet`; cost precedence is `CostOfRevenue`, `CostOfGoodsAndServicesSold`.

The three frozen quarterly features are:

- gross profitability = quarterly gross profit / lagged assets;
- cash profitability = quarterly operating cash flow / lagged assets;
- accrual intensity = (quarterly net income − quarterly operating cash flow) / lagged assets.

Each current observation is compared only with the same issuer, same fiscal quarter, prior fiscal year feature produced from that prior observation's original PIT filing state. Current filings do not rewrite prior-year predictor values.

## Six finite hypotheses

Exactly six hypotheses exist. Zero-value year-over-year changes emit no signal.

1. `gross_profitability_improvement_long`: gross profitability YoY change > 0, LONG.
2. `gross_profitability_deterioration_short`: gross profitability YoY change < 0, SHORT.
3. `cash_profitability_improvement_long`: cash profitability YoY change > 0, LONG.
4. `cash_profitability_deterioration_short`: cash profitability YoY change < 0, SHORT.
5. `accrual_quality_improvement_long`: accrual intensity YoY change < 0, LONG.
6. `accrual_quality_deterioration_short`: accrual intensity YoY change > 0, SHORT.

No threshold, percentile, feature, direction, horizon, or candidate may be added or tuned after outcomes are observed.

## Outcome and friction contract

Entry is the decision-session open. Primary exit is the close 63 XNYS sessions after the decision. The primary outcome is directional stock return minus same-window SPY return minus direction-specific cost. Positive unhedged directional return is also mandatory.

Primary total costs are 10 bps LONG and 35 bps SHORT. The SHORT primary cost includes a conservative 100 bps annualized borrow assumption prorated over the 63-session horizon. Stress costs are 25 bps LONG and 100 bps SHORT; the SHORT stress assumption uses 300 bps annualized borrow plus execution friction. The 21- and 126-session outcomes are diagnostics only and cannot replace the primary 63-session test.

## Development and protected chronology

- governed signal start: `2021-08-16`;
- development last signal: `2024-12-31`;
- outer embargo: `2025-01-02..2025-04-03`;
- protected first signal: `2025-04-04`;
- protected last signal: `2026-05-11`;
- protected outcome end: `2026-08-11`.

The outer embargo is 63 XNYS sessions, preventing the last development primary outcome from overlapping the first protected signal. Development is chronologically split 70/30 with a 63-session internal purge. Selection uses four folds, internal validation three folds, and protected confirmation four folds.

Dependence from overlapping 63-session outcomes is handled with a 63-session block bootstrap, 2,000 replicates, seed `330033`. Confidence levels are 95% selection, 90% internal validation, and 80% protected confirmation.

## Frozen gates

Selection minimums: 250 event rows, 120 signal sessions, 50 unique instruments, and at least 3/4 positive folds.

Internal validation minimums: 60 event rows, 30 signal sessions, 20 unique instruments, and at least 2/3 positive folds.

Protected minimums: 75 event rows, 30 signal sessions, 25 unique instruments, and at least 2/4 positive folds.

At each applicable stage the primary after-cost mean and its required bootstrap lower confidence bound must be positive, stress-cost mean must be positive, and unhedged after-cost mean must be positive. At least 60% of years having at least 15 signal sessions must have positive primary mean. A single decision session may contribute no more than 10% of rows and a single instrument no more than 5%.

Selection multiplicity is global Holm–Bonferroni across all six hypotheses at alpha 0.05. At most one winner per direction proceeds, ranked by highest internal primary lower confidence bound and then candidate ID. At most one finalist per direction may reach protected returns. Runner-up substitution is forbidden.

A deflated-performance diagnostic is required but cannot rescue a failed hard gate.

## Protected evidence

Protected predictors may be counted after finalists are fixed, but protected returns may not be read before finalists exist. A source-only protected sufficiency check must first prove the frozen protected sample floors. If that check fails, the candidate closes without spending the holdout.

Any non-empty protected return read consumes this mechanism's protected holdout. A protected failure cannot be replaced by the runner-up. Zero finalists is valid.

## Authority boundary

This contract itself reads zero stock returns, zero SPY returns, and zero protected returns. Provider writes, broker reads/writes, orders, PAPER submissions, LIVE writes, automation writes, and automatic broker failover remain disabled. Phase33 Signal-to-Trade authority remains false until this mechanism independently earns accepted `SUPPORTED` alpha.
