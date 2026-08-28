# Phase 31 Scientific Contract — SEC Form-4 Insider-Transaction Alpha

**Status:** FROZEN BEFORE ANY PHASE31 MARKET-OUTCOME READ.

Policy fingerprint:

`e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`

This contract was frozen only after the Phase31 source-quality repair passed from immutable non-performance evidence. No Phase31 future stock return, SPY benchmark return, protected candidate return, or protected outcome was read in choosing these rules.

## 1. Source-quality prerequisite — exact target evidence

The original Massive raw-feed feasibility remains permanently recorded as `FEASIBILITY_FAIL`; it is not rewritten.

The fail-closed source-quality replay at head `03dcd371e79554cc9e52a1bb4ed3b642a067ca4b` passed with:

- raw rows preserved: **45,921**
- chronology-violation seed rows: **1**
- contaminated accessions: **1**
- whole-accession rows quarantined: **6**
- authoritative rows: **45,915**
- quarantine SHA256: `586df9eb91fb8a9a949a0dc44e0765f7c4b7db54c2b383037012d0fb17aaf1eb`
- target outcomes read: **0**
- protected candidate rows read: **0**
- protected returns read: **0**
- provider/broker/order/PAPER/LIVE authority: **0**.

Authoritative probe-window SHAs:

- `research_boundary`: `0378adc4364b0b49812f95f700ff47eb52d55b2cf2c17bbecad77a48d6f8a4d5`
- `mid_history`: `d8acaf8834ce166901388b437d5df1adf097d798fefb2e86449d92683acd7afd`
- `development_boundary`: `76c250af73a5694751eeb5974dbc55410c3ec63335d57632ab39d4a80d4edd8c`
- `protected_boundary`: `a3b1b23c00ffbc7372f779d48171fa0a7aac04a5b3bf028c7b2e9bf74d0bb6e0`.

All future Phase31 Form-4 research must use raw-preserved evidence behind the frozen whole-accession chronology quarantine. The anomalous WISH accession is not a ticker-specific exclusion; every accession is subject to the same generic rule.

## 2. Economic mechanism

Phase31 tests whether **publicly reported discretionary open-market/private insider purchases and sales** contain future stock-specific information after the filing becomes public.

SEC Form-4 transaction codes distinguish open-market/private purchases (`P`) and sales (`S`) from grants (`A`), exercises/conversions (`M` and other derivative codes), tax/exercise-price withholding (`F`), gifts (`G`), and other ownership mechanics. Massive exposes those structured fields directly.

Research motivation, not authority:

- Lakonishok and Lee, *The Review of Financial Studies* 14(1), 2001, found insider purchases more informative than insider sales and evidence of cross-sectional return predictability.
- Cohen, Malloy, and Pomorski, *The Journal of Finance* 67(3), 2012, found that insider trades have heterogeneous motives and that non-routine/opportunistic activity contains materially more information than routine activity.

These papers motivate separating purchase and sale hypotheses and testing clustering. They do not grant ATLAS support and none of their reported performance is an ATLAS threshold.

## 3. Public availability and execution timing

Frozen public-availability rule:

`NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE`

A filing may first influence a signal on the first XNYS session whose session date is strictly later than Massive `filing_date`.

Historical entry:

`DECISION_SESSION_OPEN`

The decision-session open is used because the filing is already public by the prior calendar date under the conservative rule. ATLAS receives no benefit from entering at a pre-filing or filing-day price.

Historical exit:

`CLOSE_20_XNYS_SESSIONS_AFTER_DECISION`

Primary horizon: **20 XNYS sessions**. This is frozen as an approximately one-trading-month horizon appropriate to a slower ownership-information mechanism rather than inheriting Phase30's short news horizon.

## 4. Full source scope

Historical Form-4 source acquisition:

- warmup/source start: `2021-07-16`
- research signal start: `2021-08-16`
- source/protected evidence end: `2026-08-11`
- monthly immutable raw shards: **62**
- `form_type=4` only
- provider sort `filing_date.asc`
- provider-native ticker strings/case preserved
- no current-universe projection backward
- no aliases/remapping
- no provider writes.

The warmup month supports a complete rolling 20-session cluster state when research signals begin.

A full-history acquisition must reproduce the four already-accepted probe windows exactly. Because the endpoint is beta, any historical revision in those overlap windows fails closed; it is not silently accepted after scientific freeze.

## 5. Alpha-authoritative accession eligibility

An accession can contribute to a purchase or sale event only when every applicable rule below is satisfied before looking at returns:

1. source row survived the general source-quality quarantine;
2. original `form_type == "4"`; amendments (`4/A`) are outside this Phase31 family;
3. transaction records only;
4. **transaction-code purity at accession level**:
   - purchase accession: every transaction row is code `P`;
   - sale accession: every transaction row is code `S`;
   - mixed accessions such as exercise-plus-sale sequences are excluded;
5. every transaction row is non-derivative; accepted Massive category spellings are exactly `non-derivative` and the provider's documented historical example spelling `non_derivative`;
6. purchase rows are acquired (`A`); sale rows are disposed (`D`);
7. reported transaction shares and transaction price per share are finite and strictly positive;
8. transaction timeliness is `O`; late (`L`) rows are excluded;
9. `aff_10b5_one == true` is excluded;
10. `aff_10b5_one == false` or null is allowed. Null is treated only as **unknown/not affirmatively flagged**, not proof that no 10b5-1 plan existed; the SEC checkbox requirement was introduced during the historical sample;
11. `equity_swap_involved == true` is excluded;
12. `not_subject_to_section_16 == true` is excluded;
13. at least one of officer, director, or 10% owner flags is true;
14. exactly one provider-native ticker association is required. Multi-ticker/share-class arrays are retained as provenance but excluded from alpha authority because Phase31 does not use filing text to infer which listed class was transacted;
15. exact ticker must resolve uniquely to accepted PIT instrument identity on the decision session;
16. safe PIT identity interval must support the full decision-to-exit path;
17. split/corporate-action crossings that invalidate an uncompensated open-to-close return are censored fail-closed.

No minimum dollar-value threshold, percentile tail, market-cap cutoff, insider-title ranking, or trade-size search is used. `transaction_value` is diagnostic only; gross value may be recomputed as shares × price for provenance but never determines candidate membership in this phase.

## 6. Event aggregation and contradictory evidence

The statistical event unit is:

`ONE_EXACT_TICKER_DECISION_SESSION_DIRECTION`

All qualifying accessions/owners for the same exact provider-native ticker, decision session, and purchase/sale direction are aggregated into one event row. Accession IDs and owner CIKs remain lineage fields.

If the same ticker/session contains both qualifying purchase and qualifying sale events, that ticker/session is excluded from both directions as contradictory/ambiguous.

This prevents multiple filings or multiple reporting owners from being treated as independent same-session market observations.

## 7. Frozen cluster definition

A clustered event is determined without returns.

For the current event direction and exact ticker, inspect the **current plus previous 19 XNYS decision sessions**. The cluster condition requires:

- at least **2 distinct owner CIKs**, and
- at least **2 distinct qualifying accessions**.

Cluster lookback: **20 XNYS sessions**.

No alternate 5/10/30/60-session window or owner threshold may be substituted after performance is observed.

## 8. Exactly four hypotheses

The complete global Phase31 hypothesis family is:

1. `open_market_purchase_long` — all qualifying purchase events, LONG;
2. `clustered_open_market_purchase_long` — qualifying clustered purchase events, LONG;
3. `open_market_sale_short` — all qualifying sale events, SHORT;
4. `clustered_open_market_sale_short` — qualifying clustered sale events, SHORT.

There is no fifth hypothesis, role-specific runner-up, trade-size version, alternate horizon, text/footnote model, current-market-cap filter, or post-result search.

The broad and clustered hypotheses deliberately overlap. The overlap is handled by dependence-aware inference plus the global four-hypothesis multiplicity family, not by post-result deduplication.

## 9. Market outcome and benchmark

For a decision session `t` and exit session `t+20`:

`stock_return = stock_close[t+20] / stock_open[t] - 1`

`spy_return = SPY_close[t+20] / SPY_open[t] - 1`

Direction multiplier:

- LONG = `+1`
- SHORT = `-1`.

Primary after-cost alpha:

`direction * (stock_return - spy_return) - cost`

Required unhedged economic robustness:

`direction * stock_return - cost`

SPY is an **evaluation benchmark**, not a historical hedge order. Transaction cost is charged to the focal stock trade only.

The SPY-relative primary prevents a generic bull or bear market from masquerading as insider-information alpha. A candidate must also have positive unhedged directional mean at the primary cost so a benchmark-relative result cannot pass while losing money directionally.

## 10. Cost model

Frozen round-trip cost grid:

`0 / 5 / 10 / 25 / 50 bps`

- primary gate: **10 bps**
- stress gate: **25 bps**
- other costs: diagnostics.

No candidate-specific cost assumption is allowed.

## 11. Chronology, purge, and holdout

Master protected outcome window remains:

`2026-05-12` through `2026-08-11`

Because Phase31 uses a 20-session outcome horizon, development signals must end early enough that no development label enters the master protected window.

Frozen outer boundary:

- last development signal: `2026-04-13`
- its `t+20` exit: `2026-05-11`
- outer embargo: `2026-04-14` through `2026-05-11` = 20 XNYS sessions
- protected signal start: `2026-05-12`
- last protected signal eligible for complete 20-session confirmation: `2026-07-14`
- its `t+20` exit: `2026-08-11`.

Development chronology:

- start `2021-08-16`
- end `2026-04-13`
- chronological first 75% of available decision sessions = selection region;
- then **20 XNYS sessions purge/embargo**;
- remaining development sessions = internal validation.

The actual selection cutoff/internal start are derived deterministically from the eligible XNYS session calendar, not selected using returns.

## 12. Dependence-aware statistics

Frozen inference:

- selection folds: **6**
- internal folds: **3**
- protected folds: **3**
- moving/block bootstrap length: **20 sessions**
- bootstrap replicates: **2,000**
- deterministic seed: **310231**
- selection confidence: **95%**
- internal confidence: **90%**
- protected confidence: **80%**.

The 20-session bootstrap block matches the overlapping event-return horizon and is not candidate-specific.

## 13. Mandatory sample gates

Selection candidate must have at least:

- **750** event rows
- **250** signal sessions
- **250** unique tickers
- positive primary-cost fold mean in **>=5/6** folds.

Internal validation must have at least:

- **250** event rows
- **80** signal sessions
- **80** unique tickers
- positive primary-cost fold mean in **>=2/3** folds.

Protected confirmation, only for frozen finalists, must have at least:

- **75** event rows
- **24** signal sessions
- **24** unique tickers
- positive primary-cost fold mean in **>=2/3** folds.

Zero qualifying candidates/finalists is valid and does not justify lowering these gates.

## 14. Mandatory profitability and robustness gates

At each applicable stage, a candidate must satisfy all frozen gates:

- primary 10-bps SPY-relative mean > 0;
- applicable one-sided bootstrap lower confidence bound > 0;
- 25-bps SPY-relative stress mean > 0;
- unhedged directional 10-bps mean > 0;
- fold requirement for that stage;
- positive calendar-year fraction >= **60%**, considering years with at least **20** signal sessions;
- positive prior-session market-state fraction >= **50%**, considering states with at least **20** signal sessions;
- positive prior-session ticker-state fraction >= **50%**, considering states with at least **20** signal sessions;
- max one signal session <= **10%** of rows;
- max one exact ticker <= **5%** of rows.

Market/ticker regimes used for robustness must be the **previous XNYS session's** accepted state. Decision-session close-derived state is forbidden because the trade enters at the decision-session open.

Win rate and median return are diagnostics only and cannot rescue or kill a candidate. A deflated-performance diagnostic is required but does not replace the frozen inferential gates.

## 15. Global multiplicity and winner freeze

Global family: exactly the four candidate IDs in Section 8.

Method:

`HOLM_BONFERRONI_GLOBAL_4`, family-wise alpha **0.05**.

A selection survivor must pass its raw one-sided inference and Holm correction plus every non-p-value gate.

At most one selection winner per direction is frozen:

1. among fully passing selection survivors for that direction, choose highest primary selection LCB;
2. deterministic tie-break: `candidate_id` ascending.

If the frozen winner fails internal validation, **no runner-up substitution** is allowed. At most one finalist per direction can reach the protected blindness gate.

## 16. Protected blindness

Protected Form-4 **metadata/predictors** may be built before finalist selection because they contain no market outcomes.

Protected stock/SPY returns are forbidden until:

1. development selection is complete;
2. selection winners are frozen;
3. internal validation is complete;
4. finalists are frozen;
5. an independent blindness/lineage audit proves the protected artifact contains no outcome leakage and the exact policy fingerprint is bound.

If there are zero finalists, protected returns remain unread and the master holdout remains unconsumed.

Once any nonempty protected Phase31 return is read, the master holdout is consumed for later alpha selection.

## 17. Explicitly unauthorized

Phase31 does not authorize:

- filing-footnote NLP or remarks sentiment;
- inferred text-based transaction purpose;
- provider-generated narrative scoring;
- transaction-value optimization/tails;
- alternate cluster windows;
- alternate outcome horizons;
- post-result role filters;
- ticker aliases/current-universe backprojection;
- same-day filing-date entry;
- current-session regime state at decision-session open;
- protected-return browsing before finalists;
- broker reads/writes;
- order writes;
- PAPER submissions;
- LIVE writes;
- automation writes;
- automatic broker failover;
- frontend trading authority.

## 18. Next internal action

With this contract frozen, the next target work is full historical Form-4 acquisition from `2021-07-16` through `2026-08-11` into immutable monthly raw shards plus separate source-quality authoritative/quarantine shards.

The acquisition must reconcile the four accepted probe windows exactly and read zero market outcomes. Only after an acquisition PASS may predictor-only event construction begin.
