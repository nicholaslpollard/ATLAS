# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-29. Phase31 remains closed `ACCEPTED_NEGATIVE`. Phase32 source qualification, full-history predictor/source acquisition, and independent local source/predictor acceptance are PASS. The next gate is the first development-only market-outcome evaluation under the unchanged frozen scientific policy. Protected stock/SPY returns remain unread.**

Read `docs/roadmap.md`, this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_scientific_contract.md`, `docs/phase32_predictor_independent_acceptance.md`, `docs/phase32_development_evaluation.md`, retained Phase32 incident docs, and `docs/phase31_closeout.md` before continuing.

## Authority state

- Accepted foundation: through **Phase31**.
- Phase26–31: all `ACCEPTED_NEGATIVE`.
- Accepted historical alpha support: **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Active gate: **Phase32 — SEC 8-K Material Corporate-Event Alpha**.
- Active internal step: **development-only performance evaluation**.
- Phase33 signal-to-trade remains blocked.
- LIVE and automatic broker failover remain disabled.

Root cause before workaround remains mandatory. Local `.env.example` modifications on the target machine are operator state and must not be overwritten casually.

## Retained Phase31 provenance — historical only

Phase31 Form-4 alpha closed `ACCEPTED_NEGATIVE` under scientific fingerprint:

`e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`

Its accepted source-quality repair retained 45,915 authoritative rows under repair fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

The original `FEASIBILITY_FAIL` remains preserved. Phase31 produced zero survivors/winners/finalists/support and zero protected reads. Historical rebaseline markers remain provenance only and do not supersede current Phase32/Phase33 numbering.

## Protected holdout

Master protected outcome window:

`2026-05-12..2026-08-11`

**Protected stock/SPY returns remain unread and the holdout remains unconsumed.** Phase32 has so far opened zero protected return rows. Protected predictor metadata is source-only and was allowed by the frozen contract before finalist selection.

The upcoming development gate may open **development** stock/SPY outcomes only. It must keep protected stock/SPY return reads at zero.

## Phase32 accepted source gates

Retained feasibility v2 contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Core V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Accepted core source = Massive original-8-K discovery plus official `data.sec.gov/submissions` metadata with exact accession/CIK/form/date/acceptance reconciliation.

Rejected semantic V1 fingerprint remains immutable:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Accepted semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic V2 passed with taxonomy version 1.0 / 119 rows, source-scope-aware ticker/text semantics, official SEC reconciliation, and zero target/protected outcomes.

Source/taxonomy census PASS:

- taxonomy rows **119**;
- observed taxonomy rows **112**;
- disclosure rows **7,468**;
- unique accessions **4,427**;
- unique CIKs **3,097**;
- mapped/unmapped ticker rows **6,231 / 1,237**;
- target/protected outcome rows **0 / 0**.

Accepted filing identity = exact accession + zero-padded issuer CIK + filing date + official SEC reconciliation. Ticker fields are mapping metadata only.

## Phase32 source incidents retained before outcomes

### Joint/multi-filer filing identity

Accession-level original-8-K and semantic rows can legitimately contain multiple filer CIKs. The accepted filing-entity source key is:

`EXACT_ACCESSION_PLUS_ZERO_PADDED_ISSUER_CIK_PLUS_ACCESSION_WIDE_FILING_DATE`

All rows under an accession must retain one filing date/original 8-K. Candidate evaluation is partitioned by issuer CIK. Co-filer CIKs remain provenance, and only issuer-CIK-matching index/Text/disclosure mappings may feed PIT instrument resolution. Missing issuer-specific evidence remains a hard failure.

### Massive Text ticker multiplicity

Accession `0001140361-26-029471` / CIK `0002017526` proved one filing entity can have multiple Text rows during ticker transition (`FRNM` / `PCSC`). The accepted rule allows one or more rows only when every non-ticker field is identical, preserves all ticker variants, hashes the complete deterministic row set plus shared non-ticker record, and fails closed on any non-ticker difference.

### Crash-cache corruption

An abrupt Windows crash left exactly two reconstructible JSON caches with original nonzero lengths but all bytes `0x00`. The exact bytes/hashes were diagnosed first, quarantined under `phase32-crash-corrupted-cache-targeted-quarantine-v1`, and only those two source paths were reacquired. The subsequent full cache parse reported zero malformed JSON/JSONL caches.

### SEC historical-shard rollover boundary

News Corp accession `0001564708-23-000471` / filing date `2023-10-05` exposed a one-day mismatch between SEC root `filingFrom`/`filingTo` summary metadata and actual SEC-declared shard contents. The accepted correction permits a one-calendar-day adjacent **SEC-declared** shard only when no date-covering shard exists, never guesses URLs, retains the two-shard cap, and still requires exact accession/date/original `8-K` after the read.

All source corrections above occurred before Phase32 market outcomes and changed no frozen hypothesis, direction, timing, outcome, cost, sample gate, multiplicity rule, identity-v4 rule, or protected boundary.

Retained evidence:

- `docs/phase32_massive_text_multiplicity_incident.md`
- `docs/phase32_crash_cache_corruption_incident.md`
- `docs/phase32_sec_submissions_shard_boundary_incident.md`
- `docs/phase32_sec_edgar_access_incident.md`

## Phase32 scientific contract — FROZEN

Policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Exactly five hypotheses:

1. `equity_issuance_short`;
2. `share_repurchase_long`;
3. `financial_integrity_adverse_short`;
4. `listing_distress_short`;
5. `solvency_distress_short`.

Frozen core methodology:

- first XNYS regular open strictly after official SEC acceptance time;
- decision-session open entry;
- close five XNYS sessions later;
- 10-bps after-cost SPY-relative primary plus required positive unhedged performance;
- mandatory 25-bps stress mean;
- identity-v4 strong/medium unique CIK-bound instrument only;
- no ticker+snapshot fallback, current-universe backprojection, or alias backfill;
- 75% chronological selection, five-session purge, remaining internal validation;
- 6/3/3 folds and five-session block bootstrap, 2,000 reps, seed 320832;
- selection/internal/protected sample gates = 500/150/50 event rows, 200/60/20 sessions, 200/60/20 unique instruments;
- global `HOLM_BONFERRONI_GLOBAL_5`;
- mandatory economic/year/prior-regime/concentration gates;
- one winner/finalist per direction;
- no runner-up substitution;
- protected returns only after finalists and a separate blindness/lineage audit.

Full details: `docs/phase32_scientific_contract.md`.

## Full-history predictor/source acquisition — ACCEPTED PASS

Target-machine completion:

- index rows **345,800**;
- disclosures **387,770**;
- candidate accessions **36,277**;
- filing entities **36,309**;
- multi-filer accessions **32**;
- eligible predictor rows **19,792**;
- development predictors **18,819**;
- protected-predictor-only rows **973**;
- contradictory instrument sessions **37**;
- stock / SPY / options / protected return rows **0 / 0 / 0 / 0**;
- provider writes / broker reads / broker writes / orders / PAPER / LIVE **0 / 0 / 0 / 0 / 0 / 0**.

Candidate predictor counts:

- `equity_issuance_short`: **9,302**;
- `financial_integrity_adverse_short`: **1,153**;
- `listing_distress_short`: **4,665**;
- `share_repurchase_long`: **3,410**;
- `solvency_distress_short`: **1,262**.

Filing-entity evidence SHA-256:

`18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`

Predictor SHA-256:

`c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`

## Independent predictor/source acceptance — ACCEPTED PASS

Contract:

`phase32-predictor-independent-acceptance-v1-local-immutable-source-only`

The independent local audit reprocessed all **36,309** filing entities, used zero network reads, read zero stock/SPY/options/protected returns, reproduced the filing-entity and predictor hashes exactly, rebuilt predictor output byte-for-byte, and froze:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

The first audit stop was a validator-only byte-preservation defect: generic nonblank normalization stripped the canonical SEC source-record trailing LF before hashing. Read-only diagnosis proved source/evidence hashes were correct; `_exact_nonblank_text()` now preserves exact whitespace for byte-level lineage. No source artifact or scientific rule changed.

Accepted artifact:

`data/derived/strategy_evaluation/phase32/predictor_v1/phase32_predictor_independent_acceptance.json`

## Exact next target — development-only performance evaluation

The source/predictor gate is complete. The next action is:

`scripts/run_phase32_development.py`

only after:

- `tests/unit/test_phase32_development.py` passes; and
- `scripts/validate_phase32_development.py` passes.

This is the **first Phase32 step authorized to read development stock/SPY outcomes**.

Before outcome reads it must verify:

1. independent acceptance fingerprint `531d91c...bebde`;
2. acquisition source-report hash lineage;
3. frozen predictor SHA `c5b171...1f3f9`;
4. frozen filing-entity SHA `18fd03...ff31`;
5. exact development/protected predictor partition;
6. one exact source-derived execution ticker for every development predictor;
7. accepted split/corporate-action evidence.

Any missing/ambiguous execution-ticker lineage fails before outcomes. ATLAS may not choose a ticker based on available price history.

The authorized development read then uses exact decision-session open / t+5 close stock and SPY bars, accepted split/missing-path censoring, previous-session accepted market/ticker regimes, frozen selection/internal folds/gates, Holm-5, winner/finalist limits, and no runner-up substitution.

Detailed contract: `docs/phase32_development_evaluation.md`.

### Outcome-dependent next branch

- **Zero finalists:** independent negative closeout; protected returns remain unread and the holdout unconsumed.
- **One or more finalists:** independent blindness/lineage audit, then an immutable finalist-only protected-return plan; protected returns remain unread until that audit/plan passes.

Phase33 remains blocked unless Phase32 closes with genuine historical `SUPPORTED` authority.
