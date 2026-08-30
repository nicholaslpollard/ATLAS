# Phase32 Finalist Blindness / Lineage Audit and Protected Plan

**Status:** ACCEPTED PASS — source-only protected sample gate impossible; protected returns remain unread; proceed to negative closeout.

Frozen scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Independent predictor/source acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

## Accepted development result

The target-machine Phase32 development study passed under the unchanged frozen five-hypothesis contract.

- development predictors read: **18,819**;
- usable development outcome rows: **18,448**;
- missing exact stock paths censored: **294**;
- split crossings censored: **79**;
- protected return rows read: **0**;
- protected holdout consumed: **false**.

All five frozen candidates passed selection plus global Holm-5. The frozen one-per-direction winners were `share_repurchase_long` and `solvency_distress_short`. Internal validation rejected `share_repurchase_long` on its required primary LCB and accepted only `solvency_distress_short`; no runner-up substitution was allowed.

## Audit contract

`phase32-finalist-blindness-lineage-audit-v1-independent-development-recompute-protected-unread`

The audit implementation is independent of `packages/backtesting/phase32_development.py`. It independently reproduces exact return geometry, frozen chronology/folds, five-session block bootstrap, all sample/economic/robustness/concentration gates, global `HOLM_BONFERRONI_GLOBAL_5`, the one-winner-per-direction rule, no runner-up substitution, and the exact finalist set.

The accepted target-machine run reproduced:

- selection survivors: `equity_issuance_short`, `financial_integrity_adverse_short`, `listing_distress_short`, `share_repurchase_long`, `solvency_distress_short`;
- selection winners: `share_repurchase_long`, `solvency_distress_short`;
- finalist: `solvency_distress_short`.

Finalist audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

## Protected plan contract

`phase32-protected-plan-v1-finalist-only-source-predictor-three-fold-no-returns`

The audit read only frozen protected predictor metadata and filing-entity identity lineage. It did not read protected stock/SPY returns. The protected plan freezes exact finalist identity, source-derived execution ticker, decision/exit sessions, three protected folds, per-row source hashes, and deterministic plan hashes.

Protected plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Protected plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

## Accepted source-only protected sample precheck

Frozen finalist protected population:

- **46 event rows**;
- **33 signal sessions**;
- **40 unique instruments**.

Frozen minimums:

- **50 event rows**;
- **20 signal sessions**;
- **20 unique instruments**.

Result:

- event rows: **FAIL** (`46 < 50`);
- signal sessions: **PASS**;
- unique instruments: **PASS**.

Audit status:

`AUDIT_PASS_PROTECTED_SAMPLE_GATE_IMPOSSIBLE`

Because the source-only population cannot satisfy the preregistered event-row minimum, there is no admissible reason to open protected returns. The holdout remains pristine and Phase32 must close `ACCEPTED_NEGATIVE`.

## Protected boundary

- protected return rows read: **0**;
- protected holdout consumed: **false**;
- provider network/broker/order/PAPER/LIVE/automation activity: **0**;
- protected-return authorization after audit: **false**.

No separate protected evaluator is authorized for Phase32 because the mandatory source-only sample gate already fails.

## Implementation / derived evidence

- `packages/backtesting/phase32_finalist_audit.py`
- `scripts/run_phase32_finalist_audit.py`
- `scripts/validate_phase32_finalist_audit.py`
- `tests/unit/test_phase32_finalist_audit.py`
- `data/derived/strategy_evaluation/phase32/v1/finalist_audit/finalist_blindness_audit.json`
- `data/derived/strategy_evaluation/phase32/v1/finalist_audit/protected_plan.json`
- `data/derived/strategy_evaluation/phase32/v1/finalist_audit/protected_plan_rows.jsonl`

The immutable negative closeout and authority consequence are recorded in `docs/phase32_closeout.md`.
