# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-30. Phase31 is closed `ACCEPTED_NEGATIVE`. Phase32 source qualification, predictor/source acquisition, independent source acceptance, and development-only performance evaluation are PASS. One frozen finalist, `solvency_distress_short`, now enters the independent blindness/lineage audit and source-only protected-plan freeze. Protected returns remain unread.**

Read `docs/roadmap.md`, this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_scientific_contract.md`, `docs/phase32_predictor_independent_acceptance.md`, `docs/phase32_development_evaluation.md`, `docs/phase32_finalist_blindness_audit.md`, retained Phase32 incident docs, and `docs/phase31_closeout.md` before continuing.

## Authority state

- Accepted foundation: through **Phase31**.
- Phase26–31: all `ACCEPTED_NEGATIVE`.
- Accepted historical alpha support: **0**. The Phase32 development finalist is not yet supported alpha.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Active gate: **Phase32 — SEC 8-K Material Corporate-Event Alpha**.
- Active internal step: **independent finalist blindness/lineage audit + immutable source-only protected plan**.
- Phase33 signal-to-trade remains blocked.
- LIVE and automatic broker failover remain disabled.

Root cause before workaround remains mandatory.

## Protected boundary

Master protected outcome window remains `2026-05-12..2026-08-11`.

Development stock/SPY outcomes have now been opened under the frozen Phase32 contract. **Protected stock/SPY returns remain unread and the holdout remains unconsumed.**

Protected predictor metadata is source-only and was allowed by the frozen contract. The exact next gate may use it only to independently freeze finalist identity, exact execution-ticker lineage, protected rows, three-fold assignments, and source-only sample counts. No protected return may be read until that audit passes and its exact fingerprint/plan hashes are frozen into a separate protected evaluator.

Retained pre-performance freeze marker: before the authorized development gate, **Phase32 market outcomes remain unread** was the governing state after the accepted full-history source/predictor acquisition and independent source audit. That historical marker is preserved for contract continuity; it does not override the current statement above that development outcomes are now opened while protected returns remain unread.

## Retained Phase31 provenance

Phase31 Form-4 alpha closed `ACCEPTED_NEGATIVE` under scientific fingerprint `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`. Its accepted source-quality repair retained 45,915 authoritative rows under repair fingerprint `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`. The original `FEASIBILITY_FAIL` remains preserved. Phase31 produced zero survivors/winners/finalists/support and zero protected reads.

Retained historical Phase31 markers are provenance only: Massive plan `Stocks Starter`; original result `FEASIBILITY_FAIL`; repair policy `RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`; diagnosed root cause `Massive beta source-association/data-quality defect`; historical acquisition runner `scripts/run_phase31_form4_acquisition.py`.

## Phase32 accepted source gates

Retained core feasibility v2 contract: `phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`.

Core V2 source fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Accepted official SEC metadata source: `data.sec.gov/submissions`. Accepted discovery: Massive original-8-K index. Accepted timing: `FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`.

Rejected semantic V1 fingerprint remains immutable:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Accepted semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic V2/source census retained 119 taxonomy rows, 112 observed taxonomy rows, 7,468 disclosures, 4,427 unique accessions, 3,097 unique CIKs, 6,231 mapped ticker rows, 1,237 unmapped rows, and zero target/protected outcomes.

Accepted filing identity = exact accession + zero-padded issuer CIK + filing date + official SEC reconciliation. Ticker fields are mapping metadata only.

## Retained Phase32 source corrections before outcomes

- Joint/multi-filer accessions are partitioned under filing-entity key `EXACT_ACCESSION_PLUS_ZERO_PADDED_ISSUER_CIK_PLUS_ACCESSION_WIDE_FILING_DATE`; co-filer provenance is retained but cannot contaminate issuer ticker mapping.
- Massive Text permits ticker-only multiplicity only when all non-ticker fields are identical; all ticker variants and deterministic hashes are preserved; any non-ticker conflict fails closed.
- Two all-null JSON caches caused by an abrupt Windows crash were byte-pinned, quarantined, and only those paths reacquired; the complete post-repair cache parse passed.
- SEC historical-shard rollover fallback is limited to one calendar day and official SEC-declared shard names only when no date-covering shard exists; exact accession/date/original `8-K` remains mandatory.

These corrections changed no frozen hypothesis, direction, timing, outcome, cost, sample gate, multiplicity rule, identity-v4 rule, or protected boundary.

Retained evidence: `docs/phase32_massive_text_multiplicity_incident.md`, `docs/phase32_crash_cache_corruption_incident.md`, `docs/phase32_sec_submissions_shard_boundary_incident.md`, and `docs/phase32_sec_edgar_access_incident.md`.

## Phase32 scientific contract — FROZEN

Policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Exactly five hypotheses are frozen:

1. `equity_issuance_short`;
2. `share_repurchase_long`;
3. `financial_integrity_adverse_short`;
4. `listing_distress_short`;
5. `solvency_distress_short`.

Frozen methodology uses SEC acceptance-time public availability, decision-session open entry, close five XNYS sessions later, 10-bps SPY-relative primary plus required positive unhedged performance, 25-bps stress, identity-v4 strong/medium unique CIK-bound instrument, 75% chronological selection + five-session purge + internal validation, 6/3/3 folds, five-session block bootstrap, frozen sample/robustness/concentration gates, global `HOLM_BONFERRONI_GLOBAL_5`, at most one winner/finalist per direction, no runner-up substitution, and finalist-only protected returns.

## Full-history predictor/source acquisition — ACCEPTED PASS

- index rows **345,800**;
- disclosures **387,770**;
- candidate accessions **36,277**;
- filing entities **36,309**;
- multi-filer accessions **32**;
- eligible predictors **19,792**;
- development predictors **18,819**;
- protected-predictor-only rows **973**;
- contradictory instrument sessions **37**;
- stock / SPY / options / protected return rows at acquisition **0 / 0 / 0 / 0**.

Filing-entity evidence SHA-256:

`18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`

Predictor SHA-256:

`c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`

## Independent predictor/source acceptance — ACCEPTED PASS

Contract: `phase32-predictor-independent-acceptance-v1-local-immutable-source-only`.

The corrected local audit reprocessed all **36,309** filing entities, used zero network reads, read zero stock/SPY/options/protected returns, reproduced both accepted hashes, regenerated predictor output byte-for-byte, and froze independent acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

## Development-only performance evaluation — ACCEPTED PASS

Target-machine branch head at the accepted run:

`777015507c6f01c2b175ac3103b62cee557bb603`

The focused unit tests passed `7/7`; the development contract validator passed all checks; then the governed performance run completed successfully.

Development result:

- predictor rows read **18,819**;
- usable outcome rows **18,448**;
- missing exact stock paths **294**;
- split crossings **79**;
- protected return rows **0**;
- protected holdout consumed **false**.

All five frozen candidates passed selection and Holm-5. Frozen selection winners were:

- LONG: `share_repurchase_long`;
- SHORT: `solvency_distress_short`.

Internal validation:

- `share_repurchase_long`: FAIL on `primary_lcb_positive`; 90% LCB `-0.00078597`; no runner-up substitution.
- `solvency_distress_short`: PASS; 303 rows, 186 sessions, 219 instruments, mean10 `0.03760873`, unhedged10 `0.03134181`, LCB `0.01713014`.

Frozen finalist:

`solvency_distress_short`

This is a development finalist only. Historical support remains zero until the protected gate passes.

## Exact next target — independent finalist blindness / lineage audit

Run `scripts/run_phase32_finalist_audit.py` only after `tests/unit/test_phase32_finalist_audit.py` and `scripts/validate_phase32_finalist_audit.py` pass.

The audit is independent of the development implementation. It must independently reproduce the accepted development geometry, chronology, bootstrap, Holm-5 family, selection winners, internal result, and exact finalist set.

Then it freezes a source-only protected plan for `solvency_distress_short` with exact execution-ticker lineage and three protected folds. Before any protected return read it also checks whether the frozen protected predictor population can possibly satisfy the **50 rows / 20 sessions / 20 instruments** source-only sample gates.

- If those source-only counts fail: do **not** open protected returns; proceed to negative closeout with the holdout unconsumed.
- If they pass: freeze the exact audit fingerprint and protected-plan hashes into a separate finalist-only protected evaluator. Protected returns remain unread until that later evaluator is implemented and validated.

Phase33 remains blocked unless Phase32 closes with genuine historical `SUPPORTED` authority.
