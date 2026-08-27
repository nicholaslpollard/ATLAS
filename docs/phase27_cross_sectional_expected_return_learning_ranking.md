# Phase 27 — Cross-Sectional Expected-Return Learning & Ranking

**Status:** ACTIVE / PREREGISTERED BEFORE ANY PHASE27 PROTECTED OUTCOME READ  
**Phase type:** research / analytical support authority only  
**Upstream authority:** accepted Phase26 `ACCEPTED_NEGATIVE` merge `2074808605cf85b5462e5999ed1836d68b0434c3`

## 1. Plain-English phase start

### Where ATLAS is now

ATLAS has a substantial accepted data, analytics, risk, execution-safety, browser, and PAPER foundation, but it still has **zero historically SUPPORTED strategies**. Phase24 rejected bounded variants of the original strategy families, Phase25 showed the historical population mismatch was not hiding incumbent edge, and Phase26 rejected all 24 materially different hand-designed rule/composite candidates before protected performance was read.

### What Phase27 is trying to accomplish

Phase27 tests a different question: instead of manually defining conditions that should fire a trade, can a small, preregistered set of statistical/ML models learn which production-path-native candidates are likely to have **better directional returns than their same-session peers**?

The phase learns a cross-sectional score/ranking inside the already accepted bullish and bearish discovery directions and tests whether taking only the strongest fixed tail of those scores produces robust positive after-cost edge.

### Why this matters for account growth/profit

If the feature set contains weak interactions that do not express themselves through hand thresholds, a cross-sectional model can potentially combine them without requiring ATLAS to guess the exact rule boundaries in advance. The phase still judges success by realized after-cost economics and robustness, not prediction accuracy alone.

### What will be built or changed

Phase27 will build:

- one exact development/protected research contract over the accepted Phase26 production-path-native observation artifacts;
- one frozen complete-case predictor set and same-session cross-sectional normalization;
- one simple no-training discovery-priority baseline;
- one Ridge expected-relative-return model;
- one histogram gradient-boosted expected-relative-return model;
- one deterministic pairwise logistic ranking model;
- nested chronological tuning for the learned models;
- fixed top-tail signal extraction;
- dependence-aware economic evaluation, multiplicity control, internal validation, finalist freezing, protected confirmation, and independent artifact reconciliation.

### What will be tested at the end

The full phase gate must prove chronology/leakage integrity, deterministic model fitting/scoring, bounded hyperparameter search, same-population baseline comparison, session/overlap dependence treatment, realistic costs, multiplicity control, concentration/year/regime robustness, protected blindness before finalists, protected finalist-only reads, independent persisted-artifact reconciliation, all retained repository validators, full pytest, and Ubuntu/Windows CI.

### What success means

At most one LONG and one SHORT Phase27 finalist may earn historical analytical `SUPPORTED` authority. A supported Phase27 candidate satisfies the alpha entry condition for Phase28 signal-to-trade construction. It does not create PAPER or LIVE authority.

### What happens on a negative result

If no candidate passes, Phase27 closes `ACCEPTED_NEGATIVE`. Phase28 remains blocked. Phase27 models, grids, features, tail fraction, costs, chronology, and protected evidence may not be widened or retuned after seeing the result; the next research phase must be explicitly declared from the failure evidence.

### What is explicitly not happening yet

Phase27 does not perform stock/options trade construction, portfolio optimization, PAPER submission, broker mutation, LIVE trading, production deployment, or a major GUI build. The browser remains non-authoritative. Phase27 research output contracts may be stabilized for later display only.

## 2. Scientific question

Given an accepted WARM/HOT directional production-path-native candidate at finalized session `t`, can a frozen cross-sectional scoring architecture rank candidates within the same session/direction such that the strongest fixed tail has positive three-session **directional** return after realistic costs, with enough chronological, dependence-aware, multiplicity-controlled, internal, robustness, and protected evidence to justify historical analytical support?

The null is that no frozen architecture/direction pair earns support.

## 3. Source population and lineage

Primary development and protected-predictor sources are the accepted Phase26 observation artifacts because they already bind exact Phase25 production-path identities/context to PIT-safe finalized daily/4h/1h features:

- development: `data/derived/strategy_evaluation/phase26/v1/observations/development_observations.parquet`;
- protected predictors: `data/derived/strategy_evaluation/phase26/v1/observations/protected_predictors.parquet`;
- observation report and SHA lineage must match the accepted Phase26 contracts and policy fingerprint;
- Phase26 independent validation and closeout must both pass.

Development outcome horizon remains exactly **3 exchange sessions**. No horizon search is allowed in Phase27.

Direction mapping remains:

- `bullish` -> LONG directional return = `forward_return`;
- `bearish` -> SHORT directional return = `-forward_return`.

LONG and SHORT are evaluated independently. Neutral rows are not Phase27 research rows.

The research population is the production-path-native WARM/HOT directional population used by Phase26, not the incomplete legacy Phase11/24 broad join.

## 4. One-time protected-holdout rule

The Phase26 protected predictor window is `2026-05-12` through `2026-08-11`. Phase26 read **zero protected return rows** because it produced zero finalists.

Phase27 may use this existing window as the still-unopened master holdout **only after an independent pre-read blindness audit proves all of the following before any Phase27 protected outcome is materialized**:

1. Phase26 cumulative report records zero protected return reads;
2. Phase26 confirmation records `protected_returns_read == 0` and `protected_candidate_rows_read == 0`;
3. Phase26 closeout records zero protected return reads and `ACCEPTED_NEGATIVE`;
4. Phase26 research/finalist artifacts contain no protected performance metrics;
5. the Phase26 protected predictor artifact contains none of `future_date`, `future_close`, `forward_return`, or `directional_return`;
6. no Phase27 protected label/outcome artifact exists before the frozen Phase27 finalist artifact exists;
7. the Phase27 policy/specification fingerprint is frozen before any protected read.

This is not an automatic relabeling merely because data exist. It is a one-time deliberate use of an outcome-blind master holdout whose labels were never opened. The Phase27 architecture is allowed to adapt to **development** failures from Phase26, just as model development may iterate on training data; it may not adapt to the unopened holdout outcomes.

Once any Phase27 protected return is read, the `2026-05-12`–`2026-08-11` holdout is permanently consumed for future strategy/model selection and must never be presented as untouched again.

If the blindness audit cannot prove these conditions exactly, Phase27 must instead establish a later untouched protected window through a separately validated data catch-up. It must not weaken the protected requirement.

## 5. Frozen model-eligible predictor set

All candidates use the same complete-case population. A row is model-eligible only when every frozen predictor below and `priority_score` are finite.

Frozen learned-model predictors, exactly 29:

1. `d1_return_1`
2. `d1_rsi_14`
3. `d1_macd_hist_12_26_9`
4. `d1_natr_14`
5. `d1_price_distance_ema_20`
6. `d1_directional_efficiency_20`
7. `d1_relative_dollar_volume_20`
8. `d1_bb_position_20`
9. `d1_drawdown_20`
10. `d1_relative_volume_20`
11. `d1_breakout_distance_20`
12. `d1_bb_width_20`
13. `d1_volume_zscore_20`
14. `d1_breakdown_distance_20`
15. `d1_range_position_20`
16. `d1_ema_20_slope_1`
17. `d1_realized_volatility_20`
18. `d1_dollar_volume`
19. `h4_rsi_14`
20. `h4_macd_hist_12_26_9`
21. `h4_price_distance_ema_20`
22. `h1_rsi_14`
23. `h1_macd_hist_12_26_9`
24. `h1_price_distance_ema_20`
25. `gap_return`
26. `intraday_return`
27. `return_5d`
28. `return_20d`
29. `vol_scaled_return_20d`

`priority_score` is reserved for the simple baseline and population completeness check; it is **not** an input to the three learned architectures.

Market/ticker regime labels, identity quality, ticker text, instrument ID, dates, safe intervals, top setup, sector state, and Phase10 ML probabilities are not Phase27 model predictors. Market/ticker states may be used only for robustness segmentation. This avoids letting categorical calendar-era/context labels silently drive predictions.

No feature discovery/importance-based feature elimination is allowed after performance inspection.

## 6. Frozen cross-sectional feature transform

For each `as_of_date` and direction independently:

1. require at least **5** complete model-eligible rows;
2. for each of the 29 learned predictors, compute same-session/direction percentile rank using average ties;
3. map percentile `p` to `2*p - 1`, producing a bounded feature in `[-1, 1]`;
4. use only those transformed values for Ridge, HGB, and pairwise ranking.

Sessions/directions with fewer than 5 complete rows are excluded for **all** Phase27 candidates, including the priority baseline, so candidates are compared on the same eligible population.

No imputation from future/global data is allowed.

## 7. Frozen target

For each development row:

`directional_return = forward_return` for bullish rows, otherwise `-forward_return` for bearish rows.

For learned regression models:

`relative_directional_return = directional_return - median(directional_return within same as_of_date and direction)`.

Ridge and HGB predict `relative_directional_return`.

Pairwise ranking learns within-session/direction ordering from `directional_return`; subtracting the session median would not change the ordering.

The no-training priority baseline scores rows with the existing observation-time `priority_score`.

All economic tests use actual `directional_return`, not relative target values.

## 8. Frozen candidate library

Eight architecture/direction hypotheses are tested globally:

1. `priority_tail_long` — family `discovery_priority_baseline`, LONG;
2. `priority_tail_short` — family `discovery_priority_baseline`, SHORT;
3. `ridge_relative_long` — family `ridge_relative_return`, LONG;
4. `ridge_relative_short` — family `ridge_relative_return`, SHORT;
5. `hgb_relative_long` — family `hgb_relative_return`, LONG;
6. `hgb_relative_short` — family `hgb_relative_return`, SHORT;
7. `pairwise_rank_long` — family `pairwise_logistic_rank`, LONG;
8. `pairwise_rank_short` — family `pairwise_logistic_rank`, SHORT.

No additional model family may be added after selection/protected performance is observed.

## 9. Frozen hyperparameter search

Hyperparameters are tuned **inside development selection only** using deterministic expanding chronological inner folds. Internal validation and protected data never choose hyperparameters.

### Ridge

- model: Ridge regression with intercept;
- alpha grid: `(0.1, 1.0, 10.0, 100.0)`.

### Histogram Gradient Boosting

- squared-error regression;
- `max_leaf_nodes`: `(7, 15)`;
- `learning_rate`: `(0.03, 0.05)`;
- `max_iter`: `(100, 200)`;
- `l2_regularization`: `(1.0, 10.0)`;
- `min_samples_leaf`: `50` fixed;
- no early stopping dependent on future/outer-fold evidence.

This is exactly 16 HGB combinations.

### Pairwise logistic ranking

- L2 logistic regression over deterministic within-session feature differences;
- `C`: `(0.1, 1.0, 10.0)`;
- solver/iteration settings are deterministic and fixed by implementation contract;
- maximum unordered training pairs per session/direction before mirrored orientation: `128`;
- deterministic pair-sampling seed: `270127`;
- each selected high-vs-low pair is represented in both orientations so class balance is exact.

Pair generation uses training outcomes only. No validation/protected outcome participates in pair construction for model fitting.

### Inner tuning objective

Five expanding chronological inner folds are used where feasible. Hyperparameters maximize mean validation-session Spearman rank correlation between score and directional return. Ties are broken toward the simpler/lower-capacity setting in a fixed documented order.

Inner rank correlation chooses only hyperparameters. It does not establish strategy support.

## 10. Frozen score-to-signal policy

Direction is inherited from the accepted production candidate:

- LONG candidates operate only on `bullish` rows;
- SHORT candidates operate only on `bearish` rows.

For each session/direction/candidate:

- score every eligible row without using that session's outcomes;
- sort descending by candidate score;
- select the top **20%** of eligible rows, using `ceil(0.20 * n)` and deterministic instrument-ID tie breaking;
- no secondary score threshold, probability threshold, or discretionary minimum-prediction threshold is allowed.

The fixed 20% tail is used for selection, internal validation, and protected confirmation. It is never tuned.

## 11. Chronology and model-selection structure

Phase27 uses the Phase26 labeled development window through `2026-05-06`.

Within labeled development:

- first 75% of ordered eligible exchange sessions -> selection region;
- exact 3 exchange sessions after selection -> purge;
- remaining labeled development sessions -> internal-validation region.

Selection uses six chronological evaluation folds for economic robustness where sample support allows. Learned-model hyperparameters are tuned only inside selection with the five-fold expanding inner process above.

Architecture/direction winners are chosen **only from selection evidence** after global multiplicity control. At most one selection winner per direction may advance to internal validation.

If the chosen winner for a direction fails internal validation, **no runner-up substitution** is allowed.

A passing internal winner becomes a finalist. Its chosen architecture/hyperparameters are frozen, then the model is refit using all allowed labeled development rows through `2026-05-06` before protected prediction. Protected labels remain unread during refit and prediction.

## 12. Frozen economics

Cost grid:

- 0 bps diagnostic;
- 5 bps diagnostic;
- **10 bps primary**;
- **25 bps stress**;
- 50 bps severe-stress diagnostic.

Cost is applied to directional trade return using the same total-trade cost convention as accepted Phase26 research.

Mean evidence is computed from **same-session average net signal return** before confidence/statistical tests so multiple stocks on one date are not treated as independent time observations.

No win-rate or median-return hard veto exists. Both remain diagnostics.

## 13. Frozen dependence and confidence methodology

- moving-block bootstrap unit: exchange session;
- block length: 6 sessions;
- bootstrap replicates: 2,000;
- bootstrap seed: `270227`;
- selection confidence: 95%;
- internal confidence: 90%;
- protected confidence: 80%.

Overlapping 3-session outcomes and same-session cross-sectional observations therefore do not receive naive IID treatment.

## 14. Frozen multiplicity / selection-bias controls

- global family: all 8 architecture/direction hypotheses;
- method: Holm-Bonferroni;
- global alpha: 0.05;
- at most one finalist per direction;
- no runner-up substitution after internal rejection;
- nested hyperparameter tuning is bounded exactly by Section 9;
- deflated-performance / trial-aware diagnostic is required in the persisted report;
- model/hyperparameter count and every evaluated configuration are persisted before protected confirmation.

The project may not reinterpret the three learned architectures' internal hyperparameter trials as uncounted exploratory permission to widen grids after results.

## 15. Frozen minimum evidence and robustness gates

### Selection

A candidate must satisfy all of:

- raw selected signal rows >= 750;
- signal sessions >= 250;
- at least 5 of 6 chronological folds have positive 10 bps mean;
- 10 bps session-mean return > 0;
- 25 bps session-mean return > 0;
- 95% block-bootstrap lower confidence bound at 10 bps > 0;
- global Holm-Bonferroni significance survives at alpha 0.05;
- positive-year fraction >= 60% among years with at least 20 signal sessions;
- positive market-regime fraction >= 50% among regimes with at least 20 signal sessions;
- positive ticker-regime fraction >= 50% among regimes with at least 20 signal sessions;
- maximum single-session share of raw signal rows <= 10%.

### Internal validation

The selection winner for a direction must satisfy:

- raw signal rows >= 250;
- signal sessions >= 80;
- at least 2 of 3 chronological folds have positive 10 bps mean;
- 10 bps mean > 0;
- 25 bps mean > 0;
- 90% block-bootstrap lower confidence bound at 10 bps > 0;
- no material concentration/integrity failure.

### Protected confirmation

A finalist must satisfy:

- raw protected signal rows >= 75;
- protected signal sessions >= 24;
- at least 2 of 3 chronological protected folds have positive 10 bps mean;
- 10 bps mean > 0;
- 25 bps mean > 0;
- 80% block-bootstrap lower confidence bound at 10 bps > 0;
- no protected concentration/integrity failure.

Protected confirmation cannot rescue a candidate that failed selection/internal validation.

## 16. Baselines and diagnostics

`priority_tail_long/short` are explicit candidate baselines rather than hidden comparators. If a simple discovery-priority ranking beats the learned models and satisfies the complete standard, simplicity is allowed to win.

For every candidate, persist at least:

- raw rows and signal sessions;
- session-level mean at all frozen costs;
- confidence bounds;
- fold results;
- year/regime/ticker-state slices;
- maximum one-session concentration;
- raw trade median and win rate diagnostics;
- mean session Spearman rank correlation and fold distribution;
- chosen hyperparameters or `NONE` for priority baseline;
- tuning-trial count;
- trial-aware/deflated performance diagnostic;
- broad eligible-direction session-average comparator.

Prediction diagnostics never override failed economics.

## 17. Protected confirmation procedure

After development/internal evaluation:

1. freeze finalist IDs, direction, feature list, transform, selected hyperparameters, model-training data SHA lineage, and score-to-signal policy;
2. run the independent protected-blindness audit;
3. if zero finalists, protected return reads remain exactly zero and support remains empty;
4. if finalists exist, fit/refit the frozen finalist models using development data only;
5. score all protected predictors without outcome joins;
6. select only the finalist's fixed 20% signal keys per protected session/direction;
7. retrieve exact t+3 same-provider-native-ticker outcomes **only for those frozen signal keys**, with the accepted split censor and exact-session rules;
8. persist protected signal/outcome evidence and metrics;
9. independently reconcile keys, returns, costs, sessions, and support decision.

Non-signal protected predictor rows do not need their outcomes read merely to calculate performance.

## 18. Support authority

Phase27 support is `HISTORICAL_ANALYTICAL_STRATEGY_SUPPORT_ONLY`.

A confirmed candidate can create a versioned support overlay used by later strategy-routing/promotion integration, but:

- Phase11 historical records remain preserved as provenance;
- Phase27 support does not submit orders;
- Phase27 support does not create PAPER authority;
- Phase27 support does not create LIVE authority;
- routine production routing is not changed until the support overlay/integration is itself part of the accepted Phase27 closeout contract.

If there are zero confirmed candidates, existing support remains unchanged.

## 19. External authority

Default Phase27 research authority:

- provider reads: 0 for the frozen Phase26-derived research path;
- provider writes/mutations: 0;
- broker reads: 0;
- broker writes: 0;
- order writes: 0;
- PAPER submits: 0;
- LIVE writes: 0;
- automatic broker failover: false.

If the protected-blindness audit fails and a later protected window is required, bounded provider **read** authority for a validated data catch-up must be separately explicit in the recovery/catch-up command. That contingency cannot create any broker/PAPER/LIVE authority and cannot move the frozen model methodology after performance is known.

## 20. Required artifacts

Phase27 must persist versioned artifacts for:

- policy/preregistration fingerprint;
- source-lineage and complete-case population report;
- transformed development feature matrix or reproducible transform lineage;
- candidate/configuration registry;
- nested tuning evidence;
- selection predictions/signals and metrics;
- global multiplicity results;
- selected direction winners;
- internal-validation evidence;
- finalist artifact frozen before protected reads;
- protected-blindness audit;
- finalist model artifacts/hashes;
- protected predictions/signals/outcomes if finalists exist;
- support overlay;
- independent validation;
- cumulative report;
- full phase closeout report.

Artifacts must distinguish predictor-only data from any future-return/outcome fields.

## 21. Phase-end acceptance gate

Phase27 is accepted only after:

1. the frozen policy/specification is machine-validated;
2. source lineage and complete-case population are independently reconciled;
3. chronology/purge/no-leakage checks pass;
4. deterministic cross-sectional transforms and model fits reproduce;
5. every allowed hyperparameter/configuration trial is accounted for;
6. selection/internal evidence and global multiplicity are independently recomputed;
7. finalist artifact is frozen before protected outcome access;
8. protected blindness is independently proven;
9. zero finalists imply zero protected reads, or finalist-only protected confirmation is independently reconciled;
10. support overlay matches confirmed evidence and is analytical-only;
11. provider/broker/order/PAPER/LIVE authority boundaries remain intact;
12. retained Phase3–26 validators pass;
13. full repository pytest passes;
14. exact acceptance head passes Ubuntu and Windows CI;
15. target-machine run is performed if repository/CI cannot reproduce the required local historical artifacts;
16. plain-English phase end and living docs are synchronized.

Possible final dispositions:

- `ACCEPTED_POSITIVE`: at least one Phase27 direction candidate earns support and Phase28 alpha entry is satisfied;
- `ACCEPTED_NEGATIVE`: phase methodology/software pass, but no candidate earns support; Phase28 remains blocked;
- `NOT_ACCEPTED`: implementation/evidence/gate failure requiring root-cause repair before closeout.

## 22. No-drift reminder

Phase27 is **not** permission to run an unlimited ML tournament. The scientific object is this exact finite cross-sectional comparison. No additional model family, feature, target horizon, tail fraction, cost reduction, alternative protected window, runner-up substitution, or post-result hyperparameter expansion may be introduced merely because the frozen result is disappointing.
