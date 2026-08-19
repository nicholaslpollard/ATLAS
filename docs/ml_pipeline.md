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

### Gate 2 - historical identity and eligibility: CURRENT

Primary evidence contract:

`ml-historical-identity-probe-v1-authority-unique-reference-structural-eligibility`

Initial 2026-08-14 target-machine evidence:

- liquid/complete candidate rows: 7,058,860 across 14,626 symbols
- `AUTHORITATIVE_INTERVAL`: 584,692 rows
- `UNIQUE_REFERENCE_NO_REUSE`: 6,056,512 rows
- identity-safe total: 6,641,204 rows (94.08%)
- structurally eligible: 6,588,579 rows (93.34%) across 12,596 symbols
- structurally ineligible: 52,625 rows, dominated by unsupported security types (51,913)
- unresolved identity rows: 417,656
- `UNRESOLVED_TICKER_REUSE`: 379,355 rows across 1,467 symbols
- current active, current delisted, and current routing filters are not used

Identity evidence classes:

- `AUTHORITATIVE_INTERVAL`: one provider-authoritative ticker validity interval covers the observation date
- `UNIQUE_REFERENCE_NO_REUSE`: exact provider ticker maps to one strong/medium stable identity and no ticker-reuse conflict is observed
- unresolved ticker reuse, multiple reference identities, fallback-only identity, metadata conflict, or unmapped reference remain blocked

Historical structural eligibility reuses only lifetime-structural Phase 07 fields: supported market, locale, exchange, security type, and stable identity quality. It deliberately ignores **current** active/delisted status and current routing. Authoritative date-bounded identity evidence takes precedence over ticker reuse. No old/new ticker series are spliced by ticker text.

Because Phase 07 fallback identities are deliberately date-scoped, a ticker can have more than one observed `instrument_id` without proving that multiple stable securities actually reused it. The 379,355-row reuse block is therefore large enough to require one bounded sub-audit before the Gate 2 policy is locked.

Reuse sub-audit contract:

`ml-ticker-reuse-audit-v1-stable-vs-weak-identity-authority-enrichment`

The sub-audit separates blocked reuse tickers into:

- `MULTI_STABLE_IDENTITIES`: two or more strong/medium identities have used the ticker
- `ONE_STABLE_PLUS_WEAK`: one strong/medium identity plus one or more weak/date-scoped identities
- `WEAK_IDENTITIES_ONLY`: no stable identity evidence

It also measures current Composite-FIGI availability and any already-cached authoritative ticker interval for each reuse ticker. This is diagnostic only: no blocked row becomes safe from category membership, sparse reference bounds, or a current FIGI. Recovery requires a date-bounded authoritative interval covering the historical observation date. Ticker-text splicing remains forbidden.

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
