# Phase 10 Final Acceptance

Phase 10 — ML Probability & Evaluation Layer — is accepted.

## Accepted production probability model

- Model ID: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`
- Model fingerprint: `d485e6c287bacce1e079f86c2a1150bc1c7f6d16362e8cafcc846754112f61f0`
- Model specification: `hgb_leaf15_iter100`
- Family: scikit-learn histogram gradient boosting
- Predictors: exactly 33 accepted point-in-time quantitative features
- Output: raw `p_down`, `p_neutral`, `p_up` probabilities
- Post-hoc calibration: none
- Argmax class: diagnostic only; not a trade signal

## Historical OOS evidence

Gate 9 evaluated 10 chronological OOS folds / 3,978,577 rows with the accepted deterministic 1,000,000-row training-cap semantics.

Aggregate OOS evidence:

- log loss: 0.967042
- multiclass Brier: 0.572424
- accuracy: 57.3086%
- macro OVR AUC: 0.565518
- macro ECE: 0.022187
- log-loss improvement vs class-prior baseline: 1.233%
- Brier improvement vs class-prior baseline: 1.489%
- prior wins: 10/10 folds on both log loss and Brier

Gate 10 retained raw probabilities because Platt and isotonic calibration both worsened aggregate log loss, Brier, and ECE despite tiny AUC gains.

Gate 11 accepted the model's probability/ranking role with explicit segment caveats. Market-regime context covered 100% of historical OOS test rows. The weakest supported AUC was 0.527412 in the 2–4% NATR bucket, and the largest supported calibration weakness was market-structure DOWN with ECE 0.089148. Snapshot-only sector regime, ticker regime, risk mode, and security type were not retroactively attached.

## Gate 12 registry

Gate 12 bound the accepted model specification to immutable dataset, feature, label, walk-forward, calibration, robustness, and software lineage. All 10 historical OOS prediction artifacts were normalized into the immutable prediction contract and hash-anchored.

- immutable OOS rows: 3,978,577
- prediction artifacts verified: 10
- Gate 12 final fit artifact: absent
- Gate 12 final holdout access: false

## Gate 13 protected final holdout

The acceptance criteria were fixed before opening the holdout:

- final model log loss must beat the pre-holdout train-class-prior baseline
- final model multiclass Brier must beat the same baseline
- final model macro OVR AUC must be at least 0.52
- deterministic replay maximum absolute probability difference must be at most 1e-12
- three full exchange sessions must be purged before the holdout
- no training-label endpoint may enter the holdout
- Gate 12 identity and artifact hashes must reconcile
- final holdout must equal the locked 63 sessions / 454,773 rows

Final training population:

- eligible pre-holdout rows: 6,077,548
- deterministic sampled rows: 1,000,860
- training span: 2022-05-31 through 2026-05-06
- purged sessions: 2026-05-07, 2026-05-08, 2026-05-11
- training label endpoints entering holdout: 0

Protected holdout:

- 2026-05-12 through 2026-08-11
- 63 exchange sessions
- 454,773 rows

Pre-holdout class-prior baseline:

- log loss: 0.964301
- Brier: 0.570568
- accuracy: 58.6205%
- AUC: 0.500000
- ECE: 0.009342

Final HGB:

- log loss: 0.948693
- Brier: 0.560422
- accuracy: 58.8074%
- macro OVR AUC: 0.570016
- ECE: 0.009895
- log-loss improvement vs prior: 1.619%
- Brier improvement vs prior: 1.778%

Reproducibility:

- deterministic replay max absolute probability difference: `0.000e+00`
- replay passed: true

All locked Gate 13 checks passed.

## Final artifacts

- final model: `final_fit/model.joblib`
- final model SHA-256: `18a2a68c1655e5c3aff54c24a275d4a70f9d85e12dd5d12206dc979de14942a0`
- final holdout predictions: `predictions/role=final_holdout/part-000.parquet`
- final prediction SHA-256: `1e0176fa27efa98236f781c46bb046d5f3b438871ed0b2d5c9fff0774eb1c088`
- production manifest: registry-local `production_manifest.json`

## Phase boundary

Phase 10 provides probability evidence only. It does not choose a trading strategy, instrument, position size, or broker action. Strategy catalog construction and regime routing remain downstream work.
