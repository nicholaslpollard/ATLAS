# Phase 32 — SEC 8-K Material Corporate-Event Alpha

**Status:** `ACCEPTED_NEGATIVE` — source qualification, full-history predictor/source acquisition, independent predictor/source acceptance, development-only performance evaluation, and the independent finalist blindness/lineage audit all executed validly. The only frozen finalist, `solvency_distress_short`, has 46 protected event rows versus the preregistered 50-row minimum. Protected stock/SPY returns remain unread, the holdout remains unconsumed, and Phase33 remains blocked.

Frozen scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Independent predictor/source acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

## Purpose

Phase32 tested whether structured, timestamped SEC 8-K material corporate-event disclosures contain robust after-cost post-disclosure return information distinct from Phases26–31.

## Accepted source foundation

Retained core feasibility v2 contract: `phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`.

Retained Massive original-8-K discovery endpoint: `/stocks/filings/vX/index`.

Retained official SEC submissions source: `data.sec.gov/submissions`.

Retained public-availability rule: `FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`.

Core V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Rejected semantic V1 fingerprint remains immutable:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Accepted semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic V2 established taxonomy version 1.0 / 119 rows, source-scope-aware ticker/text semantics, official SEC reconciliation, 7,468 disclosures, 4,427 unique accessions, 3,097 unique CIKs, 6,231 mapped ticker rows, 1,237 unmapped rows, and zero target/protected outcomes during source qualification.

Accepted filing identity remained exact accession + zero-padded issuer CIK + filing date + official SEC reconciliation. Ticker fields were mapping metadata, not filing identity.

## Frozen five hypotheses

Exactly five hypotheses were frozen before performance:

1. `equity_issuance_short` — SHORT;
2. `share_repurchase_long` — LONG;
3. `financial_integrity_adverse_short` — SHORT;
4. `listing_distress_short` — SHORT;
5. `solvency_distress_short` — SHORT.

No sixth hypothesis, taxonomy regrouping, narrative sign, alternate horizon, alternate entry, issuer-size filter, or post-result threshold was authorized.

## Frozen execution/statistical contract

- decision session = first XNYS regular-session open strictly after official SEC `acceptanceDateTime`;
- entry = decision-session open;
- exit = close five XNYS sessions later;
- primary = direction × (stock return − SPY return) − cost;
- required unhedged = direction × stock return − cost;
- primary cost 10 bps; mandatory stress 25 bps;
- development signals `2021-08-16..2026-05-04`;
- protected signals `2026-05-12..2026-08-04`; protected outcome end `2026-08-11`;
- 75% chronological selection, five-session purge, internal validation;
- folds selection/internal/protected = 6/3/3;
- five-session block bootstrap, 2,000 replicates, seed 320832;
- selection sample gates = 500 event rows / 200 sessions / 200 unique instruments / >=5 of 6 positive folds;
- internal gates = 150 / 60 / 60 / >=2 of 3;
- protected gates = **50 / 20 / 20** / >=2 of 3;
- global `HOLM_BONFERRONI_GLOBAL_5`, alpha 0.05;
- positive 10-bps mean, applicable LCB, 25-bps stress mean, and 10-bps unhedged mean required;
- frozen robustness/concentration gates required;
- at most one winner/finalist per direction;
- no runner-up substitution;
- protected returns finalist-only after independent blindness/lineage audit and immutable plan freeze.

Full normative contract remains `docs/phase32_scientific_contract.md` and `packages/backtesting/phase32_policy.py`.

## PIT instrument identity

Phase32 remained bound to `instrument-identity-v4-no-issuer-level-medium-collapse`.

Strong identity = Composite FIGI / Share Class FIGI. Medium identity = CIK + exact provider-native ticker + primary exchange + security type. Only strong/medium was eligible. Exactly one filing-CIK-matching instrument had to resolve across the entry/exit interval. Ticker+snapshot fallback, current-universe backprojection, alias backfill, and guessing among multiple instruments remained forbidden.

## Full-history predictor/source acquisition — ACCEPTED PASS

The target machine completed all **36,309** filing entities.

- original-8-K index rows: **345,800**;
- semantic disclosure rows: **387,770**;
- candidate accessions: **36,277**;
- filing entities: **36,309**;
- multi-filer accessions: **32**;
- eligible predictor rows: **19,792**;
- development predictors: **18,819**;
- protected-predictor-only rows: **973**;
- contradictory instrument sessions: **37**;
- stock / SPY / options / protected return rows at acquisition: **0 / 0 / 0 / 0**.

Filing-entity evidence SHA-256:

`18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`

Predictor SHA-256:

`c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`

## Independent source/predictor acceptance — ACCEPTED PASS

The independent local audit reprocessed all 36,309 filing entities with zero network reads and zero stock/SPY/options/protected returns, reproduced both target hashes exactly, regenerated predictor output byte-for-byte, and froze acceptance fingerprint `531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`.

## Development-only performance evaluation — ACCEPTED PASS

Observed evidence:

- development predictor rows read: **18,819**;
- usable outcome rows: **18,448**;
- missing exact stock paths: **294**;
- split crossings: **79**;
- protected return rows: **0**;
- protected holdout consumed: **false**.

All five hypotheses passed selection and Holm-5. Frozen selection winners were `share_repurchase_long` and `solvency_distress_short`.

Internal validation rejected `share_repurchase_long` because its 90% primary LCB was `-0.00078597`. `solvency_distress_short` passed with 303 rows, 186 sessions, 219 instruments, mean10 `0.03760873`, unhedged10 `0.03134181`, and 90% LCB `0.01713014`.

Frozen finalist set: `['solvency_distress_short']`.

## Independent finalist blindness / lineage audit — ACCEPTED PASS

The target-machine runner `scripts/run_phase32_finalist_audit.py` independently reproduced the development geometry, chronology, folds, bootstrap, frozen gates, Holm-5 family, winners, and exact finalist without importing the development implementation.

Finalist audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

Protected plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Protected plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

Frozen protected finalist source-only population:

- event rows: **46**;
- signal sessions: **33**;
- unique instruments: **40**.

The preregistered source-only minimum was **50 / 20 / 20**. Event rows therefore fail (`46 < 50`) while sessions and instruments pass.

Audit status: `AUDIT_PASS_PROTECTED_SAMPLE_GATE_IMPOSSIBLE`.

**Protected stock/SPY returns remain unread.** Protected return rows read = 0. Protected holdout consumed = false. Protected-return authorization = false.

## Final disposition — `ACCEPTED_NEGATIVE`

The Phase32 family executed validly but did not earn historical `SUPPORTED` authority. The protected event-row minimum was frozen before performance and cannot be lowered after observing 46 rows. Opening protected returns cannot cure a mandatory source-only sample failure, so the holdout correctly remains unopened.

Supported Phase32 candidates: **0**.

Historical supported alpha after Phase32: **0**.

Phase33 entry satisfied: **false**.

No runner-up substitution, threshold weakening, alternate finalist, post-result horizon change, taxonomy regrouping, or protected-return rescue is allowed.

The next alpha research gate, if any, must test a **materially different alpha mechanism**. Phase33 remains blocked until a later gate earns accepted historical `SUPPORTED` authority.

Detailed closeout: `docs/phase32_closeout.md`.
