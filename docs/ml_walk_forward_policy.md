# Phase 10 Gate 7 — Walk-Forward / Purge Policy

Status: **ACCEPTED**

Production contract:

`ml-walk-forward-policy-v1-expanding-quarterly-252train-purge3-holdout63`

Evidence contract:

`ml-walk-forward-probe-v1-expanding-session-folds-purged-final-holdout`

Accepted Gate 6 dataset:

- dataset id: `mltrain-2026-08-14-f31596905f0c7b7f`
- lineage SHA-256: `f31596905f0c7b7f6c442df3f99304360706fd922b3179635d64dfc7c9ff8d68`
- 1,053 exchange sessions
- 6,553,856 labeled observations
- observation range: 2022-05-31 through 2026-08-11

## Accepted split semantics

- split unit: complete exchange-session cross section
- random row splitting: forbidden
- training history: expanding
- minimum training history: 252 sessions
- validation window: 63 sessions
- test window: 63 sessions
- fold step: 63 sessions
- boundary purge: 3 sessions
- additional embargo: 0 sessions
- final untouched Gate 13 holdout: 63 sessions

The three-session purge equals the full prediction horizon, not merely the two-session overlap count. A training observation three sessions before an evaluation boundary has its endpoint on the first evaluation session, so it must be removed. The same purge applies between validation and test and before the final untouched holdout.

No additional embargo is applied. The folds are strictly chronological and expanding; observations after an evaluation window never enter the training set used to predict that earlier window. An arbitrary extra embargo would discard information without evidence of an additional leakage path.

## Candidate comparison

### quarterly-train252 — ACCEPTED

- 10 folds
- first/last OOS test dates: 2023-09-11 / 2026-03-16
- 630 distinct test sessions
- 3,978,577 OOS test rows
- training rows expand from 1,448,662 to 4,905,554
- test class-fraction ranges: DOWN 8.79 pp / NEUTRAL 7.38 pp / UP 6.23 pp

### quarterly-train378

- 8 folds
- 504 distinct test sessions
- 3,244,408 OOS test rows
- minimum training rows: 2,167,983
- class ranges do not improve enough to offset the loss of two quarterly OOS folds and the earlier 2023 evaluation period

### quarterly-train504

- 6 folds
- 378 distinct test sessions
- 2,494,022 OOS test rows
- minimum training rows: 2,916,563
- the additional training history materially reduces temporal OOS coverage without a compensating stability gain

### halfyear-train252

- 4 folds
- 504 distinct test sessions
- 3,174,169 OOS test rows
- lower observed class-fraction ranges are partly mechanical because each test window aggregates two quarters
- four folds provide substantially less temporal diagnostic resolution for model degradation and regime sensitivity

## Selection rationale

The accepted 252-session minimum already supplies approximately 1.45 million rows in the first fold for a 33-feature conventional tabular model, while retaining the broadest chronological OOS evidence. ATLAS therefore values additional independent quarterly stress periods over increasing the initial training window from one year to 1.5 or 2 years.

The policy does not claim that 252 sessions is universally optimal for every model family. Gate 8 and Gate 9 models must all be evaluated under the same accepted fold contract so model-family comparisons remain fair and leakage-safe.

## Final untouched holdout

The last 63 dataset sessions are reserved exclusively for Gate 13:

- 2026-05-12 through 2026-08-11
- 454,773 rows
- DOWN 19.00%
- NEUTRAL 58.62%
- UP 22.38%

Gate 8-12 model selection, hyperparameter choice, calibration choice, thresholding, and promotion decisions may not consume this holdout.

## Next gate

Gate 8 is **CURRENT**: baseline probability models. ATLAS will first establish empirical/base-rate and deliberately simple regularized probability baselines before any more complex tabular candidate is benchmarked.
