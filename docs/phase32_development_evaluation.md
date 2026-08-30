# Phase32 Development-Only Performance Evaluation

**Status:** READY FOR TARGET-MACHINE DEVELOPMENT OUTCOME READ. Protected returns remain closed.

Frozen Phase32 scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Independent predictor/source acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

Frozen predictor SHA-256:

`c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`

Frozen filing-entity evidence SHA-256:

`18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`

## One-way authority boundary

This gate is the **first Phase32 operation authorized to read development stock/SPY outcomes**. It may not read protected stock/SPY returns.

Before any market outcome is read, the runner must:

1. reproduce and pin the accepted independent predictor/source fingerprint;
2. verify the frozen predictor and filing-entity hashes;
3. verify the current acquisition report against the source-report hash accepted by the independent audit;
4. isolate exactly the 18,819 development predictor rows under the frozen stage partition;
5. resolve one exact execution ticker for each `(instrument_id, decision_session, candidate_id)` from already-frozen eligible filing-entity evidence;
6. fail closed if execution-ticker lineage is missing or ambiguous;
7. bind the accepted corporate-action/split evidence before the price read.

No ticker may be chosen because it has a usable market-data path. Outcome availability cannot resolve source/identity ambiguity.

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

Missing exact stock entry/exit paths are censored fail-closed. A missing exact SPY benchmark path is a hard study error. Accepted split/corporate-action crossings between entry and exit are censored fail-closed. No nearest-session substitution is permitted.

## Chronology and dependence

Development signal scope is `2021-08-16..2026-05-04`, with the last five-session exit on `2026-05-11`.

The complete frozen XNYS development calendar determines:

- first 75% of sessions = selection region;
- next 5 XNYS sessions = purge;
- remaining sessions = internal validation.

Selection uses 6 fixed chronological folds; internal validation uses 3. Empty fixed folds are retained explicitly and cannot be silently dropped when counting positive folds.

The bootstrap is the frozen five-session block bootstrap with 2,000 replicates and seed 320832. Previous-session accepted market and ticker regimes are used for robustness; current decision-session close-derived state is forbidden because entry is at the open.

## Frozen gates

Selection requires at least 500 event rows, 200 signal sessions, 200 unique instruments, and >=5/6 positive folds. Internal validation requires 150 / 60 / 60 and >=2/3 positive folds.

At each applicable stage, every frozen economic/robustness gate remains mandatory: positive 10-bps SPY-relative mean, positive applicable LCB, positive 25-bps stress mean, positive 10-bps unhedged mean, year robustness, prior-market-state robustness, prior-ticker-state robustness, <=10% single-session concentration, and <=5% single-instrument concentration.

The complete five-candidate selection family is corrected globally by `HOLM_BONFERRONI_GLOBAL_5` at alpha 0.05. Win rate and median return are diagnostic only. Deflated performance is required as a diagnostic and cannot substitute for a failed gate.

## Winner/finalist rule

Among fully passing selection survivors, at most one winner per direction is frozen using highest primary selection LCB, then `candidate_id` ascending.

Only those winners enter internal validation. A failed winner cannot be replaced by a runner-up. At most one finalist per direction may be frozen.

If there are zero finalists, the next action is independent negative closeout and protected returns remain unread. If one or more finalists survive, the next action is an independent blindness/lineage audit and immutable finalist-only protected plan. Protected returns are still not opened by this development gate.

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

The runner emits lightweight stage progress. Progress reporting has no scientific authority.

## Unauthorized

This gate grants no provider mutation, broker/account access, order submission, PAPER, LIVE, automation writes, Phase33 authority, automatic broker failover, taxonomy reinterpretation, alternate horizon/entry, sample-gate relaxation, or protected-return read.
