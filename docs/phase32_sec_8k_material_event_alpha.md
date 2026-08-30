# Phase 32 — SEC 8-K Material Corporate-Event Alpha

**Status:** ACTIVE — source qualification, full-history predictor/source acquisition, and independent local predictor/source acceptance are PASS. The next gate is the first development-only market-outcome evaluation under the unchanged frozen policy. Protected stock/SPY returns remain unread and Phase33 remains blocked.

Frozen scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Independent predictor/source acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

## Accepted source foundation

Retained core feasibility v2 contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Retained Massive original-8-K discovery endpoint:

`/stocks/filings/vX/index`

Retained public-availability rule:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

Core v2 source qualification used official `data.sec.gov/submissions` metadata and read **zero market outcomes**.

Core V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Core V2 established Massive original-8-K discovery plus official `data.sec.gov/submissions` metadata with exact accession/CIK/form/date/acceptance reconciliation and zero market-outcome reads.

Rejected semantic V1 fingerprint remains immutable:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Accepted semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic V2 established taxonomy version 1.0 / 119 rows, source-scope-aware ticker/text semantics, official SEC reconciliation, and zero target/protected outcomes. The local source census passed with 119 taxonomy rows, 112 observed taxonomy rows, 7,468 disclosures, 4,427 unique accessions, 3,097 unique CIKs, 6,231 mapped ticker rows, 1,237 unmapped rows, and zero target/protected outcomes.

Accepted filing identity is exact accession + zero-padded issuer CIK + filing date + official SEC reconciliation. Ticker fields are mapping metadata, not filing identity.

## Frozen five-hypothesis family

Exactly five hypotheses were frozen before performance:

1. `equity_issuance_short` — public offering / private placement / PIPE — SHORT;
2. `share_repurchase_long` — share repurchase program — LONG;
3. `financial_integrity_adverse_short` — accounting error / audit-opinion withdrawal / restatement / internal-control weakness — SHORT;
4. `listing_distress_short` — listing deficiency / delisting determination — SHORT;
5. `solvency_distress_short` — frozen debt-distress and bankruptcy/going-concern tags — SHORT.

No sixth hypothesis, taxonomy regrouping, narrative sign, alternate horizon, alternate entry, issuer-size filter, or post-result threshold is authorized.

## Frozen execution/statistical contract

- decision session = first XNYS regular-session open strictly after official SEC `acceptanceDateTime`;
- entry = decision-session open;
- exit = close five XNYS sessions later;
- primary = direction × (stock open-to-t+5-close return − SPY open-to-t+5-close return) − cost;
- required unhedged = direction × stock return − cost;
- cost grid 0/5/10/25/50 bps; primary 10; mandatory stress 25;
- development signals `2021-08-16..2026-05-04`; outer embargo `2026-05-05..2026-05-11`;
- protected signals `2026-05-12..2026-08-04`; protected outcome end `2026-08-11`;
- development = chronological first 75% selection, five-XNYS-session purge, remaining internal validation;
- folds selection/internal/protected = 6/3/3;
- five-session block bootstrap, 2,000 replicates, seed 320832;
- selection sample gates = 500 event rows / 200 sessions / 200 unique instruments / >=5 of 6 positive folds;
- internal gates = 150 / 60 / 60 / >=2 of 3;
- protected gates = 50 / 20 / 20 / >=2 of 3;
- global `HOLM_BONFERRONI_GLOBAL_5`, alpha 0.05;
- positive 10-bps mean, applicable LCB, 25-bps stress mean, and 10-bps unhedged mean are mandatory;
- year, prior-market-state, prior-ticker-state, session-concentration, and instrument-concentration gates are mandatory;
- at most one winner/finalist per direction;
- winner = highest primary selection LCB, tie `candidate_id` ascending;
- no runner-up substitution;
- protected returns are finalist-only after a separate blindness/lineage audit.

Full normative contract: `docs/phase32_scientific_contract.md` and `packages/backtesting/phase32_policy.py`.

## PIT instrument identity

Phase32 is bound to:

`instrument-identity-v4-no-issuer-level-medium-collapse`

Strong identity = Composite FIGI / Share Class FIGI. Medium identity = CIK + exact provider-native ticker + primary exchange + security type. Only strong/medium is eligible. Exactly one filing-CIK-matching instrument must resolve across the entry/exit interval. Ticker+snapshot fallback, current-universe backprojection, alias backfill, and guessing among multiple instruments are forbidden.

## Retained source corrections before outcomes

The full-history source path was corrected only where read-only evidence proved source/identity assumptions wrong, never by weakening scientific rules:

- joint/multi-filer original-8-K index accessions retain co-filer provenance while only issuer-CIK-matching index rows contribute ticker mappings;
- semantic disclosures are partitioned under filing-entity key `EXACT_ACCESSION_PLUS_ZERO_PADDED_ISSUER_CIK_PLUS_ACCESSION_WIDE_FILING_DATE`;
- Massive Text permits ticker-only multiplicity only when every non-ticker field is identical; every ticker variant and deterministic row-set/non-ticker hash is preserved;
- two all-null JSON caches caused by an abrupt Windows crash were byte-pinned, quarantined, and reacquired through the normal authoritative source path;
- SEC-declared historical-shard rollover fallback is limited to a one-calendar-day adjacent official shard only when no date-covering shard exists, with exact accession/date/original-8-K validation and the two-shard cap retained.

Retained incident evidence:

- `docs/phase32_sec_edgar_access_incident.md`
- `docs/phase32_massive_text_multiplicity_incident.md`
- `docs/phase32_crash_cache_corruption_incident.md`
- `docs/phase32_sec_submissions_shard_boundary_incident.md`

None of those corrections changed a hypothesis, direction, chronology, cost, outcome definition, sample gate, multiplicity control, identity-v4 rule, or protected boundary.

## Full-history predictor/source acquisition — ACCEPTED PASS

The target machine completed all **36,309** filing entities.

Accepted result:

- original-8-K index rows **345,800**;
- semantic disclosure rows **387,770**;
- candidate accessions **36,277**;
- filing entities **36,309**;
- multi-filer accessions **32**;
- eligible predictor rows **19,792**;
- development predictors **18,819**;
- protected-predictor-only rows **973**;
- contradictory instrument sessions **37**;
- stock / SPY / options / protected return rows read **0 / 0 / 0 / 0**;
- provider writes / broker reads / broker writes / orders / PAPER / LIVE **0 / 0 / 0 / 0 / 0 / 0**.

Filing-entity evidence SHA-256:

`18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`

Predictor SHA-256:

`c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`

## Independent local source/predictor acceptance — ACCEPTED PASS

Contract:

`phase32-predictor-independent-acceptance-v1-local-immutable-source-only`

The corrected independent audit reprocessed all **36,309** filing entities with zero network reads and zero stock/SPY/options/protected returns, reproduced both target hashes exactly, regenerated predictor output byte-for-byte, and froze acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

The first audit had stopped on an SEC source-record hash because a generic helper stripped the canonical trailing LF before hashing. Read-only diagnosis proved the source data was internally consistent; the validator was corrected to preserve exact byte-level lineage. No source evidence or scientific rule was changed. See `docs/phase32_predictor_independent_acceptance.md`.

## Exact current action — development-only performance evaluation

The next permitted operation is `scripts/run_phase32_development.py`, after its focused unit tests and contract validator pass.

This is the **first Phase32 step authorized to read development stock/SPY outcomes**. Before that one-way boundary, the runner revalidates the independent acceptance fingerprint, source-report hash, predictor SHA, filing-entity SHA, stage partition, exact source-derived execution-ticker lineage, and accepted split/corporate-action evidence.

The runner must fail before outcomes if any development predictor lacks exactly one frozen execution ticker. It may not choose a ticker based on market-data availability.

Development outcomes then use exact daily decision-open / t+5-close stock and SPY bars, censor accepted split crossings and missing exact stock paths, reconstruct previous-session accepted market/ticker regimes, apply the frozen selection/internal gates and Holm-5 family, freeze at most one winner/finalist per direction, and keep protected stock/SPY returns at zero reads.

Implementation and detailed boundary: `docs/phase32_development_evaluation.md`.

## Authority boundary

Allowed now: the accepted source/predictor artifacts, frozen policy, development-only market-outcome evaluation, local derived development artifacts, validators/tests, and documentation.

Forbidden: protected stock/SPY returns before finalists and a separate blindness/lineage audit, provider mutations, broker/account reads or writes, orders, PAPER, LIVE, automation writes, frontend trading authority, automatic broker failover, and Phase33 signal-to-trade authority.

A development study PASS only means the governed evaluation executed correctly. Alpha is supported only if the frozen scientific gates survive all required stages. Phase33 remains blocked until Phase32 or another alpha gate closes with genuine `SUPPORTED` authority.
