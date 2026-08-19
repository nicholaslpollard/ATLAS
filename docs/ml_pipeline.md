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
- adjustment/corporate-action safety remains unresolved and moves to outcome-label feasibility before labels are locked

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

### Gate 3 - outcome-label feasibility: CURRENT

Primary evidence contract:

`ml-outcome-feasibility-probe-v1-contiguous-horizons-provider-split-adjustment-audit`

Query-plan contract:

`ml-gate3-query-plan-v2-materialized-candidates-direct-session-lookups`

Volatility-scaled family sub-audit contract:

`ml-outcome-family-audit-v1-natr14-sqrt-horizon-split-censored-grid`

The primary probe measures strategy-neutral fixed-horizon outcomes at 1, 3, 5, 10, and 20 exchange sessions. A forward outcome is labelable only when the same exact provider ticker has the exact future exchange-session observation; missing sessions, suspensions, or ticker changes censor the row instead of being bridged.

Captured 2026-08-14 target-machine evidence:

- accepted Gate 2 population: 6,588,579 rows / 12,596 symbols
- 1-session labelable: 6,576,166 (99.81%)
- 3-session labelable: 6,557,686 (99.53%)
- 5-session labelable: 6,539,838 (99.26%)
- 10-session labelable: 6,495,739 (98.59%)
- 20-session labelable: 6,410,184 (97.29%)
- fetched provider split events: 6,334 across 4,540 symbols
- material split events: 5,320
- diagnostic material split events with exact adjacent local bars: 2,647
- unadjusted-like material split events: 1,964
- adjusted-like material split events: 21
- ambiguous material split events: 662
- median absolute raw return across diagnostic material split dates: 9.2932
- median absolute split-ratio residual: 0.0719
- split evidence SHA-256: `4c67e22d8e611ce805640dddb31f335ecefec97c955d08a6284319ee034c179c`

Gate 3 conclusions already established:

- the canonical daily price history behaves overwhelmingly like **unadjusted** data around known material stock splits
- split-crossing windows therefore cannot be used as ordinary forward-return labels
- split-crossing windows are small relative to the full population and can be censored without materially reducing label coverage
- those windows disproportionately populate the extreme-return tail, so leaving them in would materially distort label distributions
- exact exchange-session continuity is feasible at all candidate horizons
- a plain return-sign target is near-balanced but treats many economically trivial moves as directional outcomes; this is insufficient evidence for a production label

The bounded Gate 3 sub-audit therefore compares endpoint returns against point-in-time `natr_14 * sqrt(horizon)` thresholds at 0.5x, 1.0x, 1.5x, and 2.0x after censoring split-crossing windows. `natr_14` is the accepted Phase 6 feature available at the observation timestamp, so no future volatility enters the target threshold.

Daily OHLC path/barrier labels are not selected for this sub-audit. A daily bar can touch both an upper and lower barrier without revealing touch order, and resolving that would require intraday path semantics that belong closer to strategy/backtest evaluation. Endpoint outcomes remain strategy-neutral and avoid importing execution assumptions into the ML target layer.

Gate 3 remains open until the volatility-scaled family evidence is reviewed. Gate 4 will then lock the production horizon, threshold/target family, split censoring, exact timestamp semantics, and any neutral-class handling.

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
