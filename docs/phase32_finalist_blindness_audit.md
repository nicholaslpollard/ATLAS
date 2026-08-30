# Phase32 Finalist Blindness / Lineage Audit and Protected Plan

**Status:** READY FOR TARGET-MACHINE SOURCE-ONLY AUDIT. Protected stock/SPY returns remain unread.

Frozen scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Independent predictor/source acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

## Accepted development result

The target-machine Phase32 development study passed under the unchanged frozen five-hypothesis contract.

Development evidence:

- development predictors read: **18,819**;
- usable development outcome rows: **18,448**;
- missing exact stock paths censored: **294**;
- split crossings censored: **79**;
- protected return rows read: **0**;
- protected holdout consumed: **false**.

All five frozen candidates passed the selection gates and global Holm-5 correction. The frozen one-per-direction winner rule selected:

- LONG: `share_repurchase_long`;
- SHORT: `solvency_distress_short`.

Internal validation then produced:

- `share_repurchase_long`: FAIL because the 90% primary LCB was negative (`-0.00078597`); no runner-up substitution is allowed;
- `solvency_distress_short`: PASS with 303 rows, 186 signal sessions, 219 instruments, 10-bps SPY-relative mean `0.03760873`, 10-bps unhedged mean `0.03134181`, and 90% LCB `0.01713014`.

The only frozen finalist is therefore:

`solvency_distress_short`

This is not yet historical alpha support. It is a development finalist that must survive the frozen protected gate.

## Audit contract

`phase32-finalist-blindness-lineage-audit-v1-independent-development-recompute-protected-unread`

The audit implementation is intentionally independent of `packages/backtesting/phase32_development.py`. It reads the already-opened development artifacts and independently reproduces:

1. exact open-to-T+5-close stock/SPY return geometry;
2. the frozen 75% selection / five-session purge / internal chronology;
3. six selection folds and three internal folds;
4. five-session block bootstrap with 2,000 replicates and seed 320832;
5. every frozen selection/internal economic, robustness, sample, and concentration gate;
6. global `HOLM_BONFERRONI_GLOBAL_5`;
7. the one-winner-per-direction rule;
8. no runner-up substitution;
9. the exact finalist set.

The audit must independently reproduce exactly one finalist, `solvency_distress_short`, or stop.

## Protected plan contract

`phase32-protected-plan-v1-finalist-only-source-predictor-three-fold-no-returns`

After reproducing the finalist, the audit may read only the already-frozen protected predictor metadata and filing-entity identity lineage. It must not read any protected stock/SPY return.

The protected plan freezes, before returns:

- only `solvency_distress_short` protected predictor rows;
- exact instrument identity and source-derived execution ticker;
- decision session and T+5 exit session;
- the complete three-fold protected calendar assignment;
- a SHA-256 for every source predictor row;
- the deterministic protected-plan-row SHA-256;
- a protected-plan fingerprint;
- the audit fingerprint.

Market-data availability may not choose or repair execution identity.

## Source-only protected sample precheck

Before spending the holdout, the audit counts the finalist's frozen protected predictor population. The protected contract requires at least:

- **50 event rows**;
- **20 signal sessions**;
- **20 unique instruments**.

These three requirements are source-only and can be decided without protected returns. If any is impossible from the frozen protected predictor population, protected returns remain unread and Phase32 proceeds to negative closeout.

If all three are possible, that still does **not** open the holdout. The exact audit fingerprint and protected-plan hashes must first be frozen into a separate finalist-only protected evaluator. Only that later evaluator may perform the one-way protected return read.

The return-dependent protected requirements remain unchanged: >=2/3 positive folds, positive 10-bps SPY-relative mean, positive 80% LCB, positive 25-bps stress mean, positive 10-bps unhedged mean, required year/prior-state robustness where eligible, and frozen concentration limits.

## Implementation

- `packages/backtesting/phase32_finalist_audit.py`
- `scripts/run_phase32_finalist_audit.py`
- `scripts/validate_phase32_finalist_audit.py`
- `tests/unit/test_phase32_finalist_audit.py`

Derived source-only outputs:

- `data/derived/strategy_evaluation/phase32/v1/finalist_audit/finalist_blindness_audit.json`
- `data/derived/strategy_evaluation/phase32/v1/finalist_audit/protected_plan.json`
- `data/derived/strategy_evaluation/phase32/v1/finalist_audit/protected_plan_rows.jsonl`

## Authority boundary

Allowed in this gate: already-opened development artifacts, frozen predictor/source metadata, exact identity lineage, XNYS calendar structure, deterministic statistical recomputation, source-only protected sample counts, local audit/plan artifacts, tests, validators, and documentation.

Forbidden: protected stock/SPY returns, protected market-outcome ranking, alternate finalists, runner-up substitution, hypothesis/taxonomy/horizon/entry retuning, provider network calls or writes, broker/account reads or writes, orders, PAPER, LIVE, automation writes, automatic broker failover, and Phase33 authority.
