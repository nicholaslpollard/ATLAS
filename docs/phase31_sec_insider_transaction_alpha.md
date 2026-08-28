# Phase 31 — SEC Form-4 Insider-Transaction Alpha

**Status:** ACTIVE — SOURCE QUALITY PASS / SCIENTIFIC POLICY FROZEN / FULL-HISTORY ACQUISITION PASS / PREDICTOR-ONLY PASS / DEVELOPMENT-ONLY PERFORMANCE NEXT. Phase31 is not accepted, protected returns remain unopened, and Phase32 remains blocked.

**Source foundation:** Phase30 merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e` (`ACCEPTED_NEGATIVE`) with zero protected-return reads.

**Normative supporting records:**

- `docs/phase31_form4_feasibility_incident.md`
- `docs/phase31_form4_source_quality_repair.md`
- `docs/phase31_full_historical_acquisition.md`
- `docs/phase31_predictor_evidence.md`
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

The endpoint is early-access/beta. Provider-native ticker strings/case and full raw row provenance are preserved. No unavailable entitlement is assumed.

## Conservative PIT rule

A filing may first influence ATLAS on the **first XNYS session strictly later than `filing_date`**.

Frozen constant:

`NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE`

Never use `transaction_date`, `period_of_report`, or `deemed_execution_date` as public-availability time.

## Original feasibility — failed and preserved

Target head `b59a64938eb84c0c1e7df3aaea390cc437326f94` produced `FEASIBILITY_FAIL` on `transaction_dates_do_not_postdate_filings`. This failure is permanent provenance and is not rewritten.

Failed feasibility fingerprint:

`edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`

## Chronology diagnostic — complete

Diagnostic implementation head:

`80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`

The provider-free diagnostic found one impossible target row: WISH accession `0000950170-23-043337`, filing `2023-08-17`, returned transaction `2023-09-15`. The diagnostic evidence SHA is:

`3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`

Root cause was classified as a **Massive beta source-association/data-quality defect**, not an ATLAS parser bug. The chronology rule remains unchanged. Diagnostic provider calls = 0; target/protected market outcomes read = 0.

## Source-quality repair — TARGET PASS

Historical target result label:

`SOURCE_QUALITY_REPAIR_PASS`

Frozen source-quality policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Source-quality fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Target result:

- raw rows preserved **45,921**
- chronology violation seeds **1**
- contaminated accessions **1**
- whole-accession rows quarantined **6**
- authoritative rows **45,915**
- quarantine SHA `586df9eb91fb8a9a949a0dc44e0765f7c4b7db54c2b383037012d0fb17aaf1eb`
- target/protected outcomes **0**.

Authoritative probe SHAs remain frozen exactly as recorded in `docs/phase31_form4_source_quality_repair.md` and `packages/backtesting/phase31_policy.py`.

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

Entry: `DECISION_SESSION_OPEN`.

Exit: `CLOSE_20_XNYS_SESSIONS_AFTER_DECISION`.

Primary after-cost alpha:

`direction * (stock_return - SPY_return) - cost`

Unhedged directional mean after primary cost must also be positive. Costs: 0/5/10/25/50 bps; primary 10; stress 25.

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

## full historical Form-4 acquisition — PASS

Accepted target-machine run date: 2026-08-28.

Accepted acquisition implementation head:

`069cca8a76446cc33b5fcf4931612e56a315f5b8`

Accepted acquisition runner retained for provenance:

`scripts/run_phase31_form4_acquisition.py`

Evidence:

- 62 monthly immutable shards covering `2021-07-16..2026-08-11`
- 42 reused SHA-bound raw shards / 20 fresh shards
- 105 successful provider pages in the accepted resume run
- **2,993,648** raw rows
- **2,992,608** authoritative rows
- **1,040** quarantined rows
- **187** contaminated accessions
- **233** chronology violation seed rows
- **15** missing-`transaction_code` seed rows
- exact reproduction of all four accepted probe windows
- target outcome rows read 0
- protected candidate/return rows read 0 / 0
- provider/broker/order/PAPER/LIVE/automation authority 0.

The full-history historical-admissibility rule is generic: an entire accession is quarantined if any transaction row has impossible chronology or lacks the transaction classification required by the frozen P/S hypotheses. Raw evidence is retained unchanged; no code or field is inferred.

A full-history acquisition PASS authorized predictor-only construction only. It did not accept Phase31, grant support, consume protected returns, or unlock Phase32.

## Predictor-only Form-4 event construction — PASS

Accepted target-machine run date: 2026-08-28.

Accepted predictor implementation head:

`dbde716b79ae882bcfec412e1a13e1bb3c274f6a`

Runner:

`scripts/run_phase31_form4_predictors.py`

Target evidence:

- authoritative rows scanned **2,992,608**
- qualified accessions before session/identity **103,773**
- resolved noncontradictory events **5,870**
- development predictor rows **5,400**
- protected predictor rows **343**
- `open_market_purchase_long` membership **2,482**
- `clustered_open_market_purchase_long` membership **1,009**
- `open_market_sale_short` membership **3,261**
- `clustered_open_market_sale_short` membership **1,724**
- authoritative lineage SHA `a9a385828b436fde7bf2297d1f8b987c4899eaff7500d79fd0b6c4abf6de7918`
- identity interval SHA `beabae4416f8444a5a062d3c3d49cdab46dec7919a545850ac0808ed94cfe3de`
- development predictor SHA `a82ff3114febc0c6f7c13d5f045549b714edbf0fd66157ef93853be9ae90c49f`
- protected predictor SHA `d3bcd2696463ec1e384919007a36570475f8cb0bf1e393f109f0accd24224e27`
- target outcome rows read **0**
- protected return rows read **0**
- provider/broker/order/PAPER/LIVE/automation writes **0**.

Complete evidence: `docs/phase31_predictor_evidence.md`.

The predictor PASS freezes deterministic event and candidate membership before performance. It does not establish alpha. The broad and clustered hypotheses overlap by design and remain in the same four-hypothesis global multiplicity family.

## Development-only performance evaluation — active next step

Runner:

`scripts/run_phase31_development.py`

This is the first Phase31 stage allowed to read development stock/SPY outcomes. The dedicated path binds the frozen predictor evidence first, reads only development predictor rows, uses exact decision-session-open to t+20-close stock/SPY geometry, censors focal-stock split/corporate-action crossings using already accepted read-only evidence, and reconstructs accepted market/ticker robustness state from the **previous XNYS session**.

The stage then applies the frozen chronology, folds, bootstrap, profitability/stress/unhedged gates, year/regime robustness, concentration limits, global four-hypothesis Holm, deterministic winner rule, and internal validation. At most one winner/finalist per direction can survive. If a winner fails internal validation, no runner-up substitution is permitted.

The protected predictor artifact is hash-bound only in this stage. Protected candidate rows and protected stock/SPY returns remain unread. A development `Pass: True` means the study executed under its frozen integrity contract; it does not by itself mean Phase31 found supported alpha.

If there are zero finalists, the next internal action is independent negative closeout with the protected holdout still unconsumed. If there are finalists, the next action is an independent blindness/lineage audit and immutable finalist-only protected-return plan before any protected return is opened.

## Protected evidence boundary

Master protected outcome window remains `2026-05-12..2026-08-11` and protected returns remain outcome-unopened.

Protected Form-4 metadata may exist in frozen predictor-only artifacts without outcomes. Protected stock/SPY returns may be read only for frozen finalists after independent blindness validation. Any nonempty protected return read consumes the holdout for later alpha selection.

## Current authority

Allowed:

- immutable accepted Form-4 source artifacts
- source-quality quarantine/reconciliation
- frozen deterministic predictor evidence
- PIT identity resolution using accepted Composite-FIGI-authoritative intervals
- development-only market outcome reads through `scripts/run_phase31_development.py`
- accepted read-only corporate-action evidence for path censoring
- previous-session accepted market/ticker regime reconstruction
- tests/validators/docs.

Forbidden:

- protected predictor-row parsing during development performance
- protected stock/SPY returns before frozen finalists and blindness audit
- performance-driven filtering or hypothesis changes
- runner-up substitution
- provider writes
- broker reads/writes
- order writes
- PAPER/LIVE submits
- automatic broker failover
- frontend trading authority.
