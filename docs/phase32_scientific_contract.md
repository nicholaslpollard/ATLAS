# Phase 32 Scientific Contract — SEC 8-K Material Corporate-Event Alpha

**Status:** FROZEN BEFORE ANY PHASE32 MARKET-OUTCOME READ.

Policy fingerprint:

`0cac8c9cc05afd031c10d29ef83d3f49eb5de8bad864f18027d2a8a9585a2b88`

This contract was frozen only after core SEC provenance V2, semantic-source V2, and the immutable source/taxonomy census passed. No Phase32 future stock return, SPY benchmark return, protected candidate return, or protected outcome was read when choosing these rules.

## 1. Accepted source prerequisites

Core source V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Semantic source V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Retained semantic V1 failure remains immutable under fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

The source-only census passed with 119 taxonomy rows, 112 observed taxonomy rows, 7,468 disclosure rows, 4,427 unique accessions, 3,097 unique CIKs, 6,231 ticker-mapped rows, 1,237 unmapped rows, and zero target/protected outcome reads.

Accepted filing identity remains exact accession + zero-padded CIK + filing date + official SEC reconciliation. Massive ticker fields are mapping metadata, not filing identity.

## 2. Economic mechanism and finite search principle

Phase32 tests only taxonomy events whose source semantics support a direction **without reading returns or inventing a good/bad interpretation from narrative text**.

The five candidate mechanisms are:

1. new equity issuance can create dilution/new-share supply pressure — SHORT;
2. issuer share repurchases create issuer demand/capital return and can signal confidence — LONG;
3. adverse financial-integrity disclosures reduce reporting reliability — SHORT;
4. listing deficiency/delisting determinations impair exchange access/compliance — SHORT;
5. debt/solvency distress impairs funding capacity and enterprise viability — SHORT.

The census is feasibility evidence only. Its observed row counts for these families were 433, 106, 53, 126, and 64 respectively across the five accepted probe windows. They are not alpha rankings or performance thresholds.

## 3. Exactly five hypotheses

The complete global Phase32 family is:

1. `equity_issuance_short` — SHORT — exact tags:
   - `capital_and_financing/equity_activity/public_offering`
   - `capital_and_financing/equity_activity/private_placement`
   - `capital_and_financing/equity_activity/pipe_transaction`
2. `share_repurchase_long` — LONG — exact tag:
   - `capital_and_financing/shareholder_returns/share_repurchase_program`
3. `financial_integrity_adverse_short` — SHORT — exact tags:
   - `financial_results/financial_integrity/accounting_error_correction`
   - `financial_results/financial_integrity/audit_opinion_withdrawal`
   - `financial_results/financial_integrity/financial_restatement`
   - `financial_results/financial_integrity/internal_control_weakness`
4. `listing_distress_short` — SHORT — exact tags:
   - `regulatory_and_compliance/exchange_listing/listing_deficiency_notice`
   - `regulatory_and_compliance/exchange_listing/delisting_determination`
5. `solvency_distress_short` — SHORT — exact tags:
   - `capital_and_financing/debt_distress/covenant_violation`
   - `capital_and_financing/debt_distress/debt_acceleration`
   - `capital_and_financing/debt_distress/payment_default`
   - `capital_and_financing/debt_distress/rating_downgrade_trigger`
   - `risk_events/bankruptcy_and_insolvency/going_concern`
   - `risk_events/bankruptcy_and_insolvency/involuntary_bankruptcy`
   - `risk_events/bankruptcy_and_insolvency/receivership_appointment`
   - `risk_events/bankruptcy_and_insolvency/voluntary_bankruptcy`

No sixth hypothesis, alternate taxonomy grouping, text-derived sign, magnitude threshold, issuer-size filter, or alternate horizon may be introduced after performance is opened.

## 4. Explicitly excluded semantic families

Phase32 does not assign universal direction to source tags whose sign is not encoded by the taxonomy itself. Excluded from this research family are, among others:

- earnings, preliminary results, guidance updates/withdrawals;
- clinical-trial results and regulatory decisions;
- merger/acquisition agreements or completions where issuer transaction role does not establish a universal stock direction;
- executive/director appointments, departures, and compensation changes;
- general litigation updates and settlements;
- investor presentations/business updates;
- restructurings, strategic initiatives, contracts, launches, and partnerships;
- routine debt issuance/facilities;
- dividend declarations/policy changes;
- listing compliance regained, listing transfers, and bankruptcy emergence.

These exclusions prevent post-result semantic reinterpretation.

## 5. Public availability and execution timing

Frozen public-availability rule:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

Official SEC `acceptanceDateTime` is authoritative. Operationally, the decision session is the first XNYS session whose **regular-session open timestamp is strictly after** the SEC acceptance timestamp. A pre-open filing may therefore act at that same calendar day's regular open; a filing accepted at or after that open cannot act until a later session. Equality is not allowed.

Historical entry:

`DECISION_SESSION_OPEN`

Historical exit:

`CLOSE_5_XNYS_SESSIONS_AFTER_DECISION`

Primary horizon: **5 XNYS sessions**. This tests tradable short post-event drift after the public event; the announcement gap before the decision-session open is intentionally not credited to ATLAS.

## 6. Full source scope and taxonomy authority

- research signal start: `2021-08-16`
- source/protected evidence end: `2026-08-11`
- original `8-K` only; `8-K/A` amendments are outside this family;
- taxonomy version: exactly `1.0` for the frozen study;
- exact taxonomy triples only;
- nonblank disclosure `supporting_text` remains required for provenance;
- `items_text` lexical matching is diagnostic only;
- no `supporting_text` sentiment, LLM interpretation, narrative score, or keyword sign has alpha authority;
- any source/taxonomy revision that breaks accepted overlap or fingerprint invariants fails closed before outcomes.

## 7. Point-in-time instrument resolution

A filing cannot become an alpha event merely because it contains a ticker string.

For each exact accession/CIK, ATLAS forms the union of nonblank provider-native ticker mapping metadata from the accepted disclosure, text, and index sources. It then resolves those exact case-sensitive mappings on the decision session against the accepted point-in-time instrument registry.

Alpha authority requires:

1. exactly one unique `instrument_id` after point-in-time resolution;
2. reference issuer CIK exactly equals the filing CIK;
3. identity derives from Composite FIGI, Share Class FIGI, or CIK + primary exchange + security type; ticker+snapshot fallback alone is insufficient;
4. the safe identity interval covers decision-session entry through the five-session exit;
5. no current-universe backprojection or ticker-alias backfill;
6. if no instrument resolves, multiple instruments resolve, issuer CIK conflicts, or the safe interval is incomplete, the event is excluded;
7. split/corporate-action crossings that invalidate an uncompensated open-to-close return are censored fail-closed.

This rule can resolve historical mapping differences when they converge to one CIK-bound point-in-time instrument, but it never guesses among multiple share classes or unmapped securities.

## 8. Event aggregation and contradictory evidence

Statistical unit:

`ONE_PIT_INSTRUMENT_DECISION_SESSION_CANDIDATE`

For the same instrument, decision session, and candidate, all qualifying exact tags/accessions are aggregated into one event row while accession/category lineage is preserved.

An instrument/session may appear in more than one candidate with the same direction; that dependence is retained and handled by the global multiplicity family and dependence-aware inference.

If any frozen LONG and SHORT candidate qualify for the same instrument/session, that instrument/session is excluded from **all** Phase32 candidates as contradictory source evidence.

## 9. Market outcome and benchmark

For decision session `t` and exit `t+5`:

`stock_return = stock_close[t+5] / stock_open[t] - 1`

`spy_return = SPY_close[t+5] / SPY_open[t] - 1`

Direction multiplier:

- LONG = `+1`
- SHORT = `-1`

Primary after-cost alpha:

`direction * (stock_return - spy_return) - cost`

Required unhedged robustness:

`direction * stock_return - cost`

SPY is an evaluation benchmark, not a historical hedge order. Phase32 support would establish information alpha only; short borrow/locate and implementation feasibility remain Phase33 responsibilities.

## 10. Cost model

Frozen round-trip cost grid:

`0 / 5 / 10 / 25 / 50 bps`

- primary gate: **10 bps**
- mandatory stress gate: **25 bps**
- 0, 5, and 50 bps remain diagnostics.

No candidate-specific cost assumption is allowed.

## 11. Chronology, purge, and protected holdout

Master protected outcome window remains:

`2026-05-12` through `2026-08-11`

With the five-session horizon:

- last development signal: `2026-05-04`
- its `t+5` exit: `2026-05-11`
- outer embargo: `2026-05-05..2026-05-11` = 5 XNYS sessions
- protected signal start: `2026-05-12`
- last protected signal eligible for complete confirmation: `2026-08-04`
- its `t+5` exit: `2026-08-11`.

Development chronology:

- start `2021-08-16`
- end `2026-05-04`
- chronological first 75% of eligible decision sessions = selection region;
- then a 5-XNYS-session purge/embargo;
- remaining development sessions = internal validation.

The actual selection cutoff/internal start are derived deterministically from the eligible XNYS calendar, never from returns.

## 12. Dependence-aware inference

Frozen inference:

- selection folds: **6**
- internal folds: **3**
- protected folds: **3**
- moving/block bootstrap length: **5 sessions**
- bootstrap replicates: **2,000**
- deterministic seed: **320832**
- selection confidence: **95%**
- internal confidence: **90%**
- protected confidence: **80%**.

The five-session block matches the overlapping outcome horizon.

## 13. Mandatory sample gates

Selection requires at least:

- **500** event rows
- **200** signal sessions
- **200** unique PIT instruments
- positive primary-cost fold mean in **>=5/6** folds.

Internal validation requires at least:

- **150** event rows
- **60** signal sessions
- **60** unique PIT instruments
- positive primary-cost fold mean in **>=2/3** folds.

Protected confirmation, only for frozen finalists, requires at least:

- **50** event rows
- **20** signal sessions
- **20** unique PIT instruments
- positive primary-cost fold mean in **>=2/3** folds.

Zero survivors/finalists is valid and never permits lowering these gates.

## 14. Profitability, robustness, and concentration gates

At each applicable stage a candidate must satisfy all frozen gates:

- primary 10-bps SPY-relative mean > 0;
- applicable one-sided bootstrap lower confidence bound > 0;
- 25-bps SPY-relative stress mean > 0;
- unhedged directional 10-bps mean > 0;
- fold requirement for that stage;
- positive calendar-year fraction >= **60%** among years with >=20 signal sessions;
- positive prior-session market-state fraction >= **50%** among states with >=20 signal sessions;
- positive prior-session ticker-state fraction >= **50%** among states with >=20 signal sessions;
- max one signal session <= **10%** of rows;
- max one exact PIT instrument <= **5%** of rows.

Market/ticker regime state must come from the **previous XNYS session** because entry is at the current session open.

Win rate and median return are diagnostics only. A deflated-performance diagnostic is required but cannot replace the frozen gates.

## 15. Multiplicity and winner freeze

Global family: exactly the five IDs in Section 3.

Method:

`HOLM_BONFERRONI_GLOBAL_5`, family-wise alpha **0.05**.

A selection survivor must pass its raw one-sided inference, Holm correction, and every non-p-value gate.

At most one selection winner per direction is frozen:

1. among fully passing selection survivors for that direction, choose highest primary selection LCB;
2. deterministic tie-break: `candidate_id` ascending.

If the frozen winner fails internal validation, **no runner-up substitution** is allowed. At most one finalist per direction can reach protected confirmation.

## 16. Protected blindness

Protected 8-K metadata/predictors may be constructed before finalist selection because they contain no stock/SPY outcomes.

Protected stock/SPY returns are forbidden until:

1. development selection is complete;
2. selection winners are frozen;
3. internal validation is complete;
4. finalists are frozen;
5. an independent blindness/lineage audit proves protected artifacts contain no outcome leakage and binds this exact policy fingerprint.

If there are zero finalists, protected returns remain unread and the master holdout remains unconsumed.

Any nonempty protected Phase32 return read consumes the master protected holdout for later alpha selection.

## 17. Explicitly unauthorized

Phase32 does not authorize:

- taxonomy regrouping after performance;
- text sentiment, LLM scoring, keyword sign, or narrative magnitude thresholds;
- alternate event horizons;
- alternate entry timing;
- current-market-cap or liquidity filters chosen after returns;
- ticker aliases or current-universe backprojection;
- fallback ticker+snapshot identity as sufficient alpha authority;
- entry at an exchange open timestamp that is not strictly after SEC acceptance;
- current-session regime state at decision open;
- protected-return browsing before finalists;
- broker/account reads or writes;
- order writes;
- PAPER submissions;
- LIVE writes;
- automation writes;
- automatic broker failover;
- frontend trading authority;
- Phase33 signal-to-trade authority.

## 18. Next internal action

With this contract frozen, the next target is full-history Phase32 source/predictor acquisition from `2021-08-16` through `2026-08-11`, including original 8-K discovery, accepted semantic disclosures, official SEC acceptance metadata, and point-in-time instrument resolution.

That acquisition must preserve accepted source identities and read **zero market outcomes**. Only after the full-history predictor/source gate passes may development stock/SPY outcomes be opened under this exact fingerprint.
