# Phase 31 — SEC Form-4 Insider-Transaction Alpha

**Status:** ACTIVE — SOURCE QUALITY PASS / SCIENTIFIC POLICY FROZEN / FULL-HISTORY ACQUISITION NEXT. No Phase31 market outcomes have been read. Phase31 is not accepted and Phase32 remains blocked.

**Source foundation:** Phase30 merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e` (`ACCEPTED_NEGATIVE`) with zero protected-return reads.

**Normative supporting records:**

- `docs/phase31_form4_feasibility_incident.md`
- `docs/phase31_form4_source_quality_repair.md`
- `docs/phase31_scientific_contract.md`.

## Plain-English phase start

ATLAS has tested five materially different modern alpha mechanisms and none earned support. Phase31 changes the information mechanism again: legally reported SEC Form-4 insider ownership changes.

The phase tests whether structured, publicly filed insider purchases and sales contain robust future stock-specific information after the filing becomes public. It is allowed to fail. Nothing may be tuned into a positive result after performance is observed.

## Entry condition

Phase30 accepted negative with zero survivors/winners/finalists/support, zero protected candidate/return reads, and independent negative reconstruction PASS. Entry satisfied by Phase30 PR #34 / merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e`.

## Provider / entitlement

Lead source:

`MassiveRESTClient -> GET /stocks/filings/vX/form-4`

Current Massive subscription: **Stocks Starter**.

The endpoint is early-access/beta. Do not assume Financials & Ratios Expansion, a Massive Options plan, paid partner data, or unavailable stock trade/quote entitlements.

Provider-native ticker strings/case and full raw row provenance are preserved.

## Conservative PIT rule

Until authoritative exact historical SEC acceptance timestamps are proven before performance, a filing may first influence ATLAS on the **first XNYS session strictly later than `filing_date`**.

Frozen constant:

`NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE`

Never use `transaction_date`, `period_of_report`, or `deemed_execution_date` as public-availability time.

## Original feasibility — failed and preserved

Target head:

`b59a64938eb84c0c1e7df3aaea390cc437326f94`

Feasibility fingerprint:

`edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`

Result:

`FEASIBILITY_FAIL`

Sole failed check:

`transaction_dates_do_not_postdate_filings`

This failure is permanent provenance and is not rewritten to PASS.

## Chronology diagnostic — complete

Diagnostic implementation head:

`80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`

The provider-free target diagnostic found:

- 36,854 transaction rows with filing + transaction dates
- 33,510 transaction before filing
- 3,343 same day
- 1 transaction after filing
- one WISH accession with filing `2023-08-17` and returned transaction `2023-09-15`
- violation artifact SHA `3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`
- provider calls = 0
- market/protected outcome reads = 0
- broker/order/PAPER/LIVE = 0.

The root cause is classified as a **Massive beta source-association/data-quality defect**. The chronology rule remains unchanged and ATLAS does not fabricate a corrected accession.

## Source-quality repair — TARGET PASS

Policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Source-quality fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Repair implementation head:

`03dcd371e79554cc9e52a1bb4ed3b642a067ca4b`

Target result:

`SOURCE_QUALITY_REPAIR_PASS`

- raw rows preserved: **45,921**
- chronology violation seeds: **1**
- contaminated accessions: **1**
- whole-accession rows quarantined: **6**
- authoritative rows: **45,915**
- quarantine SHA: `586df9eb91fb8a9a949a0dc44e0765f7c4b7db54c2b383037012d0fb17aaf1eb`
- target outcomes: 0
- protected candidates/returns: 0 / 0
- trading authority: 0.

Authoritative probe SHAs:

- `research_boundary` `0378adc4364b0b49812f95f700ff47eb52d55b2cf2c17bbecad77a48d6f8a4d5`
- `mid_history` `d8acaf8834ce166901388b437d5df1adf097d798fefb2e86449d92683acd7afd`
- `development_boundary` `76c250af73a5694751eeb5974dbc55410c3ec63335d57632ab39d4a80d4edd8c`
- `protected_boundary` `a3b1b23c00ffbc7372f779d48171fa0a7aac04a5b3bf028c7b2e9bf74d0bb6e0`.

The generic source-quality rule quarantines an entire accession whenever any transaction row has `transaction_date > filing_date`. It contains no WISH, code-M, security-type, role, or performance exception and no bad-row tolerance.

## Frozen scientific policy

Policy fingerprint:

`e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`

The complete normative policy is `docs/phase31_scientific_contract.md`.

### Exactly four hypotheses

1. `open_market_purchase_long`
2. `clustered_open_market_purchase_long`
3. `open_market_sale_short`
4. `clustered_open_market_sale_short`.

No fifth hypothesis, alternate horizon, role/value variant, filing-text model, runner-up search, or post-result replacement is allowed.

### Eligible events

Only pure original Form-4 open-market/private purchase (`P`) or sale (`S`) accessions can contribute. Eligible accessions are non-derivative, timely `O`, have positive shares and price, match acquired/disposed direction, are not affirmatively 10b5-1, are not equity swaps, are subject to Section 16 through an officer/director/10% role, have exactly one provider-native ticker, resolve uniquely to PIT identity, and survive source-quality/corporate-action checks.

Mixed-code grant/exercise/withholding/gift sequences are excluded. `transaction_value` is diagnostic only; no value threshold is used. `aff_10b5_one=null` is treated as unknown/not affirmatively flagged, not proof of no plan.

### Event unit / cluster

One exact ticker × decision session × direction is one event row regardless of how many qualifying accessions/owners contributed. Same-ticker/session qualifying purchase + sale is excluded as contradictory.

Cluster = current + previous 19 XNYS decision sessions, >=2 distinct owner CIKs and >=2 distinct qualifying accessions.

### Outcome

Entry:

`DECISION_SESSION_OPEN`

Exit:

`CLOSE_20_XNYS_SESSIONS_AFTER_DECISION`

Primary after-cost alpha:

`direction * (stock_return - SPY_return) - cost`

Unhedged directional mean after primary cost must also be positive.

Costs: 0/5/10/25/50 bps; primary 10; stress 25.

### Chronology / holdout

- source warmup `2021-07-16`
- research signal start `2021-08-16`
- last development signal `2026-04-13`
- t+20 development exit `2026-05-11`
- outer 20-session embargo `2026-04-14..2026-05-11`
- protected start `2026-05-12`
- last complete protected signal `2026-07-14`
- protected t+20 end `2026-08-11`.

Development uses chronological 75% selection, 20-session purge, then internal validation.

### Statistics / anti-overfit

- folds 6 / 3 / 3
- block bootstrap 20 sessions
- 2,000 reps, seed 310231
- confidence 95% / 90% / 80%
- selection minima 750 event rows / 250 sessions / 250 tickers / >=5-of-6 positive folds
- internal minima 250 / 80 / 80 / >=2-of-3
- protected minima 75 / 24 / 24 / >=2-of-3
- positive-year fraction >=60%
- positive previous-session market/ticker state fractions >=50%
- single-session concentration <=10%
- single-ticker concentration <=5%
- global `HOLM_BONFERRONI_GLOBAL_4`, alpha .05
- maximum one winner/finalist per direction
- winner = highest selection LCB then candidate ID
- no runner-up substitution
- win rate/median diagnostics only
- deflated-performance diagnostic required
- protected returns finalist-only.

## Full historical Form-4 acquisition — next

The next target is **full historical Form-4 acquisition** under the frozen contract:

`scripts/run_phase31_form4_acquisition.py`

Required scope:

- `2021-07-16` through `2026-08-11`
- 62 monthly immutable raw shards
- separate authoritative/quarantine shards
- resumable raw evidence
- exact reproduction of all four accepted probe windows
- zero target/protected market-outcome reads
- zero provider writes/broker/order/PAPER/LIVE/automation authority.

Because Massive Form 4 is beta, any disagreement with the frozen probe-window source hashes is a source-history drift incident and must fail closed.

A full-history acquisition PASS authorizes predictor-only construction. It does not accept Phase31, grant support, consume the holdout, or unlock Phase32.

## Protected evidence boundary

Master protected outcome window remains `2026-05-12..2026-08-11` and remains outcome-unopened.

Protected Form-4 metadata may be acquired and later transformed into predictor-only artifacts without outcomes. Protected stock/SPY returns may be read only for frozen finalists after independent blindness validation. Any nonempty protected return read consumes the holdout for later alpha selection.

## Current authority

Allowed:

- Massive read-only historical Form-4 acquisition under the frozen policy
- immutable raw/derived source artifacts
- source-quality quarantine/reconciliation
- metadata-only predictor engineering after acquisition PASS
- tests/validators/docs.

Forbidden:

- development/target market returns before predictor/source gates
- protected returns before finalists/blindness gate
- performance-driven filtering or hypothesis changes
- broker reads/writes
- order writes
- PAPER/LIVE submits
- automatic broker failover
- frontend trading authority.
