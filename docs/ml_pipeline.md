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

### Gate 1 - historical training-universe / survivorship / data-adjustment audit: ACCEPTED

Contract:

`ml-training-universe-probe-v1-historical-observation-survivorship-identity-audit`

Accepted 2026-08-14 target-machine evidence:

- historical 1d bars/features: 13,856,199 / 13,856,199
- historical provider symbols: 20,655
- current inclusive reference symbols: 36,417
- current routed-universe symbols: 12,066
- historical symbols absent current reference: 215
- historical symbols absent current routed universe: 8,592
- historical rows absent current reference: 48,486 (0.35%)
- fully warmed 33-feature rows: 10,244,060
- fully warmed rows at >=$250k daily dollar volume: 7,058,860
- liquid complete rows absent current reference: 9,993 (0.14%)
- canonical `is_adjusted`: NULL for all 13,856,199 rows
- provider-symbol histories with >=30 calendar-day gaps: 1,193 symbols / 2,789 gaps
- adjacent-observation close moves >=50%: 28,268
- adjacent-observation close moves >=100%: 8,047

Accepted conclusions:

- the current Phase 07/08 routed universe is **rejected** as a retrospective training population
- historical training population must be observation-driven
- the current inclusive reference is useful identity/metadata evidence but is not itself a historical membership filter
- current `active` / `delisted` status must not be projected backward as historical eligibility
- adjustment/corporate-action safety moves to outcome-label feasibility before labels are locked

### Gate 2 - historical identity and eligibility: ACCEPTED

Evidence contract:

`ml-historical-identity-probe-v1-authority-unique-reference-structural-eligibility`

Reuse sub-audit contract:

`ml-ticker-reuse-audit-v1-stable-vs-weak-identity-authority-enrichment`

Production policy contract:

`ml-historical-identity-policy-v1-authoritative-or-unique-no-reuse-structural`

Accepted 2026-08-14 target-machine evidence:

- liquid/complete candidate rows: 7,058,860 across 14,626 symbols
- `AUTHORITATIVE_INTERVAL`: 584,692 rows
- `UNIQUE_REFERENCE_NO_REUSE`: 6,056,512 rows
- identity-safe total: 6,641,204 rows (94.08%)
- structurally eligible: 6,588,579 rows (93.34%) across 12,596 symbols
- structurally ineligible: 52,625 rows, dominated by unsupported security types (51,913)
- unresolved identity rows: 417,656
- `UNRESOLVED_TICKER_REUSE`: 379,355 rows across 1,467 symbols

Reuse composition:

- `MULTI_STABLE_IDENTITIES`: 343,901 rows / 1,234 symbols (90.65% of reuse-blocked rows)
- `ONE_STABLE_PLUS_WEAK`: 28,803 rows / 219 symbols (7.59%)
- `WEAK_IDENTITIES_ONLY`: 6,651 rows / 14 symbols (1.75%)
- only 15 `ONE_STABLE_PLUS_WEAK` symbols already had any dated authority

Accepted policy:

- a historical row is identity-safe only when its observation date is covered by one exact provider-authoritative ticker interval, or when its exact provider ticker maps to one strong/medium stable identity with no observed reuse conflict
- after identity safety, the row must pass the structural market/locale/exchange/security-type family gate
- current routed membership is never a historical training filter
- current active/delisted state is never projected backward
- unresolved multi-stable ticker reuse stays blocked
- current Composite FIGI alone does not retroactively prove historical ticker ownership
- sparse reference observation dates are not continuity bounds
- ticker-text history splicing is forbidden

A targeted provider-enrichment campaign was rejected at this gate. Even recovering every `ONE_STABLE_PLUS_WEAK` row would add only about 0.41 percentage points of candidate coverage, while dated authority existed for only 15 of those symbols. The accepted 93.34% population is therefore preferred to a lower-integrity recovery attempt.

### Gate 3 - outcome-label feasibility: ACCEPTED

Primary evidence contract:

`ml-outcome-feasibility-probe-v1-contiguous-horizons-provider-split-adjustment-audit`

Query-plan contract:

`ml-gate3-query-plan-v2-materialized-candidates-direct-session-lookups`

Volatility-family evidence contract:

`ml-outcome-family-audit-v2-natr14-schema-reconciled-split-censored-grid`

Accepted feasibility policy contract:

`ml-outcome-feasibility-policy-v1-split-censored-endpoint-natr-feasible`

Primary 2026-08-14 target-machine evidence:

- accepted Gate 2 population: 6,588,579 rows / 12,596 symbols
- labelable coverage: 99.81% at 1 session, 99.53% at 3, 99.26% at 5, 98.59% at 10, 97.29% at 20
- fetched provider split events: 6,334 across 4,540 symbols
- material split events: 5,320
- diagnostic material split events with exact adjacent local bars: 2,647
- unadjusted-like material split events: 1,964
- adjusted-like material split events: 21
- ambiguous material split events: 662
- median absolute raw return across diagnostic material split dates: 9.2932
- median absolute split-ratio residual: 0.0719
- split evidence SHA-256: `4c67e22d8e611ce805640dddb31f335ecefec97c955d08a6284319ee034c179c`

The canonical daily history therefore behaves overwhelmingly like **unadjusted** prices around known material stock splits. Split-crossing windows are rare relative to the full population but disproportionately populate the extreme-return tail, so Gate 3 requires those windows to be censored rather than treated as ordinary outcomes.

The first volatility-family run was rejected as invalid because it returned only 7,253 rows / 590 symbols and an implausible exact median `natr_14` of 1.0. The defect was a heterogeneous multi-file Parquet read without schema unification. The v2 audit reads the permanent feature lake with `union_by_name=true` and hard-fails unless feature integrity reconciles before label evidence is emitted.

Accepted v2 feature-integrity evidence:

- base population: 6,588,579 rows / 12,596 symbols
- feature join: 6,588,579 rows / 12,596 symbols
- stored finite/positive `natr_14`: 6,588,579 / 6,588,579
- stored/derived comparable rows: 6,588,579
- stored `natr_14` vs `atr_14 / close` mismatches: 0
- median stored and derived `natr_14`: 0.02599449612787421
- maximum absolute difference: 0.0

The schema-read issue does not invalidate Phase 8/9. Phase 8 production discovery reads individual date partitions, while Phase 9 historical feature-glob consumers already use `union_by_name=true`.

Volatility-scaled endpoint evidence uses `natr_14 * sqrt(horizon)` and censors split-crossing windows. At 0.5x NATR, the directional population remains large and roughly balanced across every tested horizon:

- 1 session: 41.36% directional; 51.73% UP among directional
- 3 sessions: 42.67% directional; 52.44% UP among directional
- 5 sessions: 43.60% directional; 52.91% UP among directional
- 10 sessions: 44.62% directional; 53.85% UP among directional
- 20 sessions: 45.62% directional; 55.27% UP among directional

At 1.0x NATR, only about 14-16% of rows remain directional; 1.5x and 2.0x are much sparser tail families. Gate 3 therefore accepts volatility-scaled endpoint labels as feasible and carries **0.5x NATR as the leading Gate 4 candidate**, but does not lock it as the production threshold.

Gate 3 policy:

- exact future exchange-session continuity required
- same exact provider ticker required
- ticker-text splicing forbidden
- split-crossing labels censored
- endpoint outcomes are feasible
- daily path/barrier labels are not selected because daily OHLC cannot order same-bar dual touches without intraday path data
- plain return-sign labels are not accepted as a production target because they classify economically trivial moves as directional
- production horizon, threshold, and neutral handling remain Gate 4 decisions

### Gate 4 - prediction-label policy: CURRENT

Evidence contract:

`ml-label-policy-probe-v1-annual-stability-3-5-10-natr-grid`

Gate 4 narrows the plausible production candidates to 3, 5, and 10 exchange sessions. The 0.5x NATR threshold is the primary candidate; 1.0x is retained as a sensitivity reference. The probe measures annual usable coverage, UP/DOWN/NEUTRAL class balance, directional support, and directional skew before the production target is locked.

The intended production form remains a strategy-neutral endpoint classification using only information strictly after the feature timestamp. Gate 4 must explicitly lock the horizon, NATR multiplier, neutral-class treatment, split censoring, exact timestamp semantics, and the overlap length that later informs Gate 7 purge/embargo.

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
