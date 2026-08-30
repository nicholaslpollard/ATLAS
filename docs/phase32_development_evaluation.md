# Phase32 Development-Only Performance Evaluation

**Status:** DEVELOPMENT PASS. One frozen finalist, `solvency_distress_short`, proceeds to the independent blindness/lineage audit. Protected returns remain closed.

Frozen Phase32 scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Independent predictor/source acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

Frozen predictor SHA-256:

`c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`

Frozen filing-entity evidence SHA-256:

`18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`

## Accepted target-machine result

The development runner completed successfully at branch head `777015507c6f01c2b175ac3103b62cee557bb603` after the focused unit tests and contract validator passed.

Observed development evidence:

- development predictor rows read: **18,819**;
- usable development outcome rows: **18,448**;
- missing exact stock paths censored: **294**;
- split crossings censored: **79**;
- prior market-state missing rows: **0**;
- prior ticker-state missing rows: **3,189**;
- protected predictor rows observed for partition validation: **973**;
- protected return rows read: **0**;
- protected holdout consumed: **false**.

Chronology reproduced the frozen partition:

- selection: `2021-08-16..2025-02-27`;
- purge: `2025-02-28, 2025-03-03, 2025-03-04, 2025-03-05, 2025-03-06`;
- internal validation: `2025-03-07..2026-05-04`.

All five frozen candidates passed selection and the global Holm-5 correction:

- `equity_issuance_short`: mean10 `0.01623558`, LCB `0.01027448`;
- `share_repurchase_long`: mean10 `0.00691016`, LCB `0.00290945`;
- `financial_integrity_adverse_short`: mean10 `0.01863677`, LCB `0.00823589`;
- `listing_distress_short`: mean10 `0.01538459`, LCB `0.00077330`;
- `solvency_distress_short`: mean10 `0.04564517`, LCB `0.02781914`.

The frozen one-per-direction winner rule selected `share_repurchase_long` and `solvency_distress_short`.

Internal validation then produced:

- `share_repurchase_long`: **FAIL** only on `primary_lcb_positive`; 897 rows, 255 sessions, 724 instruments, mean10 `0.00509553`, LCB `-0.00078597`. No runner-up substitution is allowed.
- `solvency_distress_short`: **PASS**; 303 rows, 186 sessions, 219 instruments, mean10 `0.03760873`, unhedged10 `0.03134181`, LCB `0.01713014`.

Frozen finalist set:

`['solvency_distress_short']`

This is a development finalist, not yet supported historical alpha.

## One-way authority boundary

This gate was the **first Phase32 operation authorized to read development stock/SPY outcomes**. It did not read protected stock/SPY returns.

Before any market outcome was read, the runner:

1. reproduced and pinned the accepted independent predictor/source fingerprint;
2. verified the frozen predictor and filing-entity hashes;
3. verified the acquisition report against the source-report hash accepted by the independent audit;
4. isolated exactly the 18,819 development predictor rows under the frozen stage partition;
5. resolved one exact execution ticker for each `(instrument_id, decision_session, candidate_id)` from already-frozen eligible filing-entity evidence;
6. failed closed on any missing or ambiguous execution-ticker lineage;
7. bound accepted corporate-action/split evidence before the price read.

No ticker was chosen because it had a usable market-data path. Outcome availability did not resolve source/identity ambiguity.

## Development outcome contract

`phase32-development-outcome-v1-exact-open-t5-close-spy-relative-split-censored`

For each frozen development event:

- stock entry = exact decision-session open;
- stock exit = exact close five XNYS sessions later;
- SPY benchmark = exact same entry-open and exit-close sessions;
- primary gross return = direction × (stock return − SPY return);
- unhedged gross return = direction × stock return;
- primary after-cost gate = 10 bps;
- mandatory stress = 25 bps;
- cost-grid diagnostics = 0 / 5 / 10 / 25 / 50 bps.

Missing exact stock entry/exit paths were censored fail-closed. A missing exact SPY benchmark path would have been a hard study error. Accepted split/corporate-action crossings between entry and exit were censored fail-closed. No nearest-session substitution was permitted.

## Chronology and dependence

Development signal scope is `2021-08-16..2026-05-04`, with the last five-session exit on `2026-05-11`.

The complete frozen XNYS development calendar determined:

- first 75% of sessions = selection region;
- next 5 XNYS sessions = purge;
- remaining sessions = internal validation.

Selection used 6 fixed chronological folds; internal validation used 3. Empty fixed folds were retained explicitly and could not be silently dropped when counting positive folds.

The bootstrap was the frozen five-session block bootstrap with 2,000 replicates and seed 320832. Previous-session accepted market and ticker regimes were used for robustness; current decision-session close-derived state remained forbidden because entry is at the open.

## Frozen gates

Selection required at least 500 event rows, 200 signal sessions, 200 unique instruments, and >=5/6 positive folds. Internal validation required 150 / 60 / 60 and >=2/3 positive folds.

At each applicable stage, every frozen economic/robustness gate remained mandatory: positive 10-bps SPY-relative mean, positive applicable LCB, positive 25-bps stress mean, positive 10-bps unhedged mean, year robustness, prior-market-state robustness, prior-ticker-state robustness, <=10% single-session concentration, and <=5% single-instrument concentration.

The complete five-candidate selection family was corrected globally by `HOLM_BONFERRONI_GLOBAL_5` at alpha 0.05. Win rate and median return remained diagnostic only. Deflated performance remained a required diagnostic and could not substitute for a failed gate.

## Winner/finalist rule

Among fully passing selection survivors, at most one winner per direction was frozen using highest primary selection LCB, then `candidate_id` ascending.

Only those winners entered internal validation. The failed LONG winner cannot be replaced by another LONG candidate. At most one finalist per direction may be frozen.

The exact next action is the independent blindness/lineage audit and immutable finalist-only protected plan in `docs/phase32_finalist_blindness_audit.md`. Protected returns remain unread.

## Implementation

- `packages/backtesting/phase32_development.py`
- `scripts/run_phase32_development.py`
- `scripts/validate_phase32_development.py`
- `tests/unit/test_phase32_development.py`

Derived outputs:

- `data/derived/strategy_evaluation/phase32/v1/development/development_outcomes.parquet`
- `data/derived/strategy_evaluation/phase32/v1/development/development_signals.parquet`
- `data/derived/strategy_evaluation/phase32/v1/development/finalists.json`
- `data/derived/strategy_evaluation/phase32/v1/development/development_study.json`

## Unauthorized

This development PASS grants no provider mutation, broker/account access, order submission, PAPER, LIVE, automation writes, Phase33 authority, automatic broker failover, taxonomy reinterpretation, alternate horizon/entry, sample-gate relaxation, runner-up substitution, or protected-return read.
