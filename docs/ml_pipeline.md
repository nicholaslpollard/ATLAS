# Phase 10 - ML Probability & Evaluation Layer

Phase 10 adds conventional statistical/ML probability estimates on top of ATLAS's accepted point-in-time market data, features, discovery state, and regime context.

The ML layer does **not** select a strategy, trade instrument, position size, or execution action. Its job is to estimate future-outcome probabilities with strict out-of-sample evaluation so downstream strategy routing can consume calibrated evidence rather than an opaque score.

## Core principles

- no LLM is used as a market predictor
- no model is trained before the historical training population and labels are proven point-in-time safe
- current 2026 membership is never silently projected backward as the historical training universe
- provider-native ticker case remains exact and case-sensitive
- no ticker-text history splicing
- current/future observations are excluded from every training feature and calibration threshold
- train/validation/test splits are chronological and walk-forward; random row splitting is forbidden
- overlapping forward labels require an explicit purge/embargo policy
- probability calibration is evaluated separately from discrimination
- immutable out-of-sample predictions are retained for later outcome learning
- model promotion requires measurable improvement over simple/base-rate baselines
- strategy selection remains a later phase

## Phase 10 gate structure

Phase 10 is locked at 13 gates.

### Gate 1 - historical training-universe / survivorship / data-adjustment audit: CURRENT

Contract:

`ml-training-universe-probe-v1-historical-observation-survivorship-identity-audit`

Measure the real permanent 1d historical lake from 2021-08-16 through the selected end date and compare it against the current reference/universe snapshots.

Evidence includes:

- historical daily bar/feature rows and unique provider symbols
- current reference and routed-universe symbol counts
- historical symbols/rows absent from the current reference and current routed universe
- the same survivorship gap for fully warmed 33-feature observations at the existing $250k daily-dollar-volume benchmark floor
- yearly survivorship-gap shares
- provider `is_adjusted` state counts
- large adjacent-observation price discontinuities
- long provider-symbol history gaps that may require segmentation/identity investigation

Gate 1 does **not** choose a historical identity policy, training population, or prediction label.

### Gate 2 - historical identity and eligibility policy

Use Gate 1 evidence to define safe historical observation identity/segmentation and an anti-survivorship training population. The policy must allow securities that later disappeared while preventing ticker reuse/rename contamination.

### Gate 3 - outcome-label feasibility

Measure strategy-neutral future outcomes before choosing a target. Candidate families may include fixed-horizon forward returns and volatility-scaled path/barrier outcomes. Measure class balance, censoring, ambiguous path ordering, corporate-action distortion, and horizon overlap.

### Gate 4 - prediction-label policy

Lock the production target(s), horizon(s), censoring rules, label timestamp semantics, and any volatility scaling from Gate 3 evidence. Labels must use information strictly after the feature timestamp.

### Gate 5 - point-in-time ML feature and leakage contract

Define the model input matrix from accepted Phase 6 quantitative features plus only historical Phase 9 context that can be reproduced point-in-time. Audit nulls, availability timestamps, regime lineage, categorical handling, scaling, and prohibited future-derived fields.

### Gate 6 - training-dataset materialization

Persist an immutable feature/label dataset with stable observation keys, source hashes, policy versions, eligibility reasons, and deterministic replay. Dataset construction must be reproducible without a model library.

### Gate 7 - walk-forward and embargo policy

Select expanding/rolling chronological folds, minimum training history, validation/test windows, and purge/embargo lengths appropriate to the locked forward-label horizon. No random row-level split is permitted.

### Gate 8 - baseline probability models

Train deliberately simple benchmarks first, including empirical/base-rate and regularized linear/logistic probability models where applicable. Establish log loss, Brier score, discrimination, calibration, and segment baselines.

### Gate 9 - candidate model benchmark

Only after Gate 8, benchmark a bounded set of conventional tabular models. Added dependencies must be justified by measured out-of-sample improvement, runtime, memory, and reproducibility.

### Gate 10 - probability calibration policy

Compare raw probabilities with point-in-time calibration candidates such as logistic/Platt or isotonic calibration using training/validation data only. Lock a policy from Brier/log-loss/reliability evidence, not visual preference.

### Gate 11 - regime and segment robustness

Evaluate out-of-sample performance across market regime, ticker regime, risk mode, liquidity, security type, direction family, and time. A globally good score cannot hide a materially broken segment.

### Gate 12 - model registry and immutable prediction contract

Persist model metadata, training-data lineage, feature/label contracts, calibration contract, evaluation metrics, artifact hashes, and immutable prediction records. Promotion/rollback must be explicit and auditable.

### Gate 13 - final reproducibility, leakage, and out-of-sample validation

Rebuild the accepted dataset/model from lineage, reproduce predictions, verify chronological isolation and embargo rules, reconcile immutable predictions, and run the final untouched out-of-sample acceptance set.

## Phase boundary

Phase 10 ends with calibrated probability evidence and an auditable prediction interface.

The next phase remains the **Strategy Catalog + Regime Router**, which decides how deterministic strategies should use market/sector/ticker context and ML probabilities. Phase 10 must not pull strategy selection forward into the model itself.
