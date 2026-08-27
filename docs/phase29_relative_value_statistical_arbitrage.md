# Phase 29 — Relative-Value Statistical-Arbitrage Confirmation Alpha

**Status:** ACTIVE / PREREGISTERED BEFORE ANY PHASE29 PERFORMANCE READ  
**Phase type:** research / historical analytical support authority only  
**Upstream authority:** Phase28 `ACCEPTED_NEGATIVE` merge `285f112d51463dd1e06ea4e874a882ad98f71dc5`

## 1. Plain-English phase start

### Where ATLAS is now

Phases26–28 answered three materially different alpha questions and all three were valid negatives. Hand-designed self-feature rules failed, same-stock cross-sectional ML/ranking failed, and cross-stock lead-lag/residual-network signals failed. ATLAS still has zero historically `SUPPORTED` alpha, so signal-to-trade construction remains blocked.

The important positive fact is methodological: all three phases stopped before protected outcomes were read. The inherited `2026-05-12` through `2026-08-11` holdout is still outcome-unopened.

### What Phase29 is trying to accomplish

Phase29 changes the **economic mechanism** rather than adding another classifier or another lag rule. It asks whether an existing bullish/bearish production candidate becomes more attractive when its finalized current price move is temporarily cheap or rich relative to a relationship estimated only from prior finalized prices.

Two finite mechanisms are tested:

1. a PCA common-factor equilibrium, using a focal stock's current idiosyncratic residual after estimating the current common-factor move from its peers without using the focal stock's current return;
2. a Gatev-style nearest historical price-path pair, using the focal stock's current spread dislocation relative to a pair selected only from the prior formation window.

These are **confirmation signals for the existing focal stock candidate**, not a claim that ATLAS already supports a market-neutral paired execution product. Historical economics remain the focal stock's exact three-session directional return so any positive result stays compatible with the existing downstream single-candidate authority model.

### Why this is materially different

Phase26 used focal technical/rule conditions. Phase27 learned cross-sectional rankings from same-stock features. Phase28 used asymmetric peer-to-focal lag prediction. Phase29 instead estimates a contemporaneous **relative-value equilibrium** from trailing finalized prices and tests subsequent mean reversion of current dislocations. It has no learned outcome model and no lead-lag edge selection.

### Research basis, not assumed evidence

Classic pairs-trading research matched stocks by minimum distance between normalized historical price paths and tested reversion after relative divergence. PCA statistical-arbitrage research decomposed equity returns into common-factor and idiosyncratic residual components and used residual mean reversion as a contrarian mechanism. Those historical results motivate hypotheses only; they do not grant ATLAS support and do not justify weakening modern after-cost gates.

### What success means

At most one LONG and one SHORT Phase29 candidate may earn historical analytical `SUPPORTED` authority. A positive Phase29 result satisfies the entry condition for the subsequent signal-to-trade construction phase. It does not create PAPER or LIVE authority.

### What happens on a negative result

If no candidate passes, Phase29 closes `ACCEPTED_NEGATIVE`. PCA component count, formation window, peer minimum, pair-distance definition, signal orientation, tail fraction, outcome horizon, cost assumptions, chronology, robustness requirements, and statistical gates may not be retuned after seeing the result.

## 2. Scientific question

Given an accepted WARM/HOT directional production-path-native focal candidate at finalized session `t`, does a current-session relative-value dislocation—measured against a PCA equilibrium or nearest historical normalized-price pair estimated only through `t-1`—identify a fixed strongest tail with robust positive focal-stock three-session directional return after realistic costs?

The null is that none of the four frozen Phase29 hypotheses earns historical analytical support.

## 3. Source population and lineage

Focal/source artifacts remain the accepted Phase26 production-path-native observation frames:

- development: `data/derived/strategy_evaluation/phase26/v1/observations/development_observations.parquet`;
- protected predictors: `data/derived/strategy_evaluation/phase26/v1/observations/protected_predictors.parquet`.

Required upstream evidence:

- Phase26 policy fingerprint `24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2` and accepted-negative closeout;
- Phase27 policy fingerprint `63030d55fbdb60ce61ea0c84081ae95d62d68fc717f494aa41a23d31c410aab0` and accepted-negative closeout;
- Phase28 policy fingerprint `0f15966f61a0baf52513cd46dc4fa8492c98e7dc8cf9ed3d551c2ebc955adea5` and accepted-negative closeout;
- Phase26/27/28 protected-return reads all zero;
- Phase28 protected holdout consumed `False`;
- exact Phase28 merge `285f112d51463dd1e06ea4e874a882ad98f71dc5`.

The research start is `2021-08-16`, labeled development ends `2026-05-06`, the outer purge remains `2026-05-07`, `2026-05-08`, `2026-05-11`, and protected predictors span `2026-05-12` through `2026-08-11`.

Outcome horizon is exactly **3 exchange sessions**. No horizon search is allowed.

Focal direction mapping remains:

- bullish production candidate -> LONG directional return = focal forward return;
- bearish production candidate -> SHORT directional return = negative focal forward return.

Phase29 does not evaluate a synthetic pair-portfolio P&L and must not represent its evidence as market-neutral execution authority.

## 4. Observation-time peer universe

For each focal row `(instrument_id, as_of_date=t)`:

1. begin with all Phase26 production-path-native bullish/bearish candidate rows at the same `t`;
2. peer direction need not equal focal direction;
3. each peer/focal history must stay inside that row's exact `safe_start_date` / `safe_end_date`;
4. any split crossing the required formation/current history makes that instrument unavailable for the observation;
5. ticker text never bridges identity intervals;
6. no current-only sector/customer/supplier/ownership/news relationship may be projected backward;
7. all price history comes from already accepted canonical finalized 1d bars; Phase29 performs no provider calls.

A focal row is unavailable unless the session has enough complete peers to compute **both** frozen relative-value mechanisms.

## 5. Frozen price-history geometry

Phase29 uses exactly **62 consecutive canonical closes** per safe instrument from `t-61` through `t`:

- the first 61 closes generate **60 formation returns** ending at `t-1`;
- the final close produces the current return at `t`;
- pair formation uses exactly the last **60 formation closes ending at `t-1`** from this same safe history.

Missing sessions are not forward/back filled and do not cause the formation window to reach farther backward. A noncomplete history is unavailable.

## 6. Frozen PCA residual-dislocation mechanism

The PCA mechanism requires at least **8** complete safe instruments on the observation session, including the focal instrument.

### 6.1 Formation standardization

For every instrument `i`, calculate its 60 formation simple returns ending at `t-1`.

Using only those 60 formation returns, compute:

- `mu_i = mean(return_i)`;
- `sigma_i = population_std(return_i)`.

An instrument with nonfinite values or nonpositive `sigma_i` is unavailable.

Standardize the 60 formation returns:

`X[s,i] = (return_i[s] - mu_i) / sigma_i`.

No current-session `t` return enters the formation matrix.

### 6.2 Frozen PCA basis

Compute the deterministic SVD of the formation matrix and retain exactly the first **3** right-singular-vector components. No component-count search, variance-explained threshold, shrinkage search, or rolling-window search is allowed.

SVD sign indeterminacy does not affect reconstructed values; nevertheless implementation must use deterministic ordering and fail closed on nonfinite/rank-deficient geometry that prevents the fixed three-component reconstruction.

### 6.3 Current leave-focal-out factor score

Standardize every instrument's finalized current return at `t` using its own frozen formation `mu_i` and `sigma_i`.

For a focal instrument `f`, solve the three current factor scores by least squares using **only the current standardized returns of the other peers** and their frozen PCA loadings. The focal's own current standardized return may not enter that solve.

Then reconstruct the focal's expected standardized current return from its frozen loadings and the leave-focal-out factor score.

Frozen raw signal:

`pca_residual_dislocation = focal_current_standardized_return - focal_factor_reconstruction`.

A negative value means the focal is currently cheap/underperforming its estimated common-factor equilibrium; a positive value means rich/outperforming.

This leave-focal-out rule is mandatory to prevent the focal current move from mechanically explaining itself.

## 7. Frozen nearest-distance-pair mechanism

For each focal instrument, use exactly the **60 formation closes ending at `t-1`**.

Normalize every complete instrument's formation price path by its first formation close:

`normalized_price_i[s] = close_i[s] / close_i[first]`.

For every potential peer `p != f`, compute:

`distance(f,p) = sum_s((normalized_price_f[s] - normalized_price_p[s])^2)`.

Choose exactly one peer with the minimum finite distance. Ties are broken by lexical peer instrument ID. No distance threshold or top-k search is allowed.

For the frozen pair, define the formation spread:

`spread[s] = normalized_price_f[s] - normalized_price_p[s]`.

Compute its formation mean and population standard deviation. The pair is unavailable if spread standard deviation is <= `1e-8` or nonfinite.

Normalize the finalized current `t` focal and peer closes using the **same formation-start closes**, calculate current spread, and freeze:

`distance_pair_spread_z = (current_spread - formation_spread_mean) / formation_spread_std`.

Negative means focal cheap versus its frozen nearest pair; positive means focal rich.

The pair is selected entirely through `t-1`; current `t` prices may measure dislocation but may not change pair identity or formation statistics.

## 8. Frozen candidate library

Exactly four hypotheses:

- `pca_residual_reversion_long`
- `pca_residual_reversion_short`
- `distance_pair_reversion_long`
- `distance_pair_reversion_short`

Direction and score:

- LONG rows must be bullish production candidates;
- SHORT rows must be bearish production candidates;
- PCA LONG score = `-pca_residual_dislocation`;
- PCA SHORT score = `+pca_residual_dislocation`;
- pair LONG score = `-distance_pair_spread_z`;
- pair SHORT score = `+distance_pair_spread_z`.

No outcome-trained model or hyperparameter fitting occurs in Phase29.

## 9. Complete-case and signal extraction policy

Every focal row must have **both** frozen raw signals finite. Therefore all four hypotheses are compared on the same complete-case population.

A session/direction is eligible only when at least **5** complete focal rows exist.

For each candidate/session/direction:

1. sort eligible rows by descending Phase29 score;
2. select exactly `ceil(0.20 * n)` rows;
3. lexical instrument ID breaks ties;
4. no secondary z threshold, residual magnitude threshold, discretionary filter, or tail search is permitted.

The fixed **20%** tail applies to selection, internal validation, and protected confirmation.

## 10. Chronology

Labeled development ends `2026-05-06`.

Within eligible labeled-development sessions:

- first 75% -> selection;
- exact next 3 eligible exchange sessions -> purge;
- remainder -> internal validation.

Selection uses six chronological folds. Internal uses three. Protected uses three where sample support permits.

All relative-value relationships and signals are observation-time only. Outcome labels are joined only after score/signal keys for the relevant tranche are frozen.

## 11. Frozen economics and dependence treatment

Cost grid: `0, 5, 10, 25, 50` bps.  
Primary acceptance cost: **10 bps**.  
Stress cost: **25 bps**.

These are focal-stock directional-return costs for the Phase29 confirmation question. They are not a claim about future two-leg market-neutral execution costs.

Signal rows are averaged within exchange session before confidence testing.

Moving-block bootstrap:

- block length: **6 sessions**;
- replicates: **2000**;
- deterministic base seed: **290229**.

Confidence:

- selection: **95%**;
- internal: **90%**;
- protected: **80%**.

## 12. Minimum evidence and robustness gates

Selection:

- >=750 raw rows;
- >=250 signal sessions;
- >=5/6 positive fold means at 10 bps;
- 10 bps session mean >0;
- 95% moving-block-bootstrap LCB >0;
- 25 bps stress mean >0;
- robustness and concentration gates pass.

Internal:

- >=250 raw rows;
- >=80 sessions;
- >=2/3 positive folds;
- 10 bps mean >0;
- 90% LCB >0;
- 25 bps stress mean >0;
- robustness and concentration pass.

Protected:

- >=75 raw rows;
- >=24 sessions;
- >=2/3 positive folds;
- 10 bps mean >0;
- 80% LCB >0;
- 25 bps stress mean >0;
- concentration passes.

Robustness:

- positive eligible-year fraction >=60%, with >=20 signal sessions per eligible year;
- positive eligible market-state fraction >=50%, >=20 sessions/state;
- positive eligible ticker-state fraction >=50%, >=20 sessions/state;
- max one-session raw-row fraction <=10%.

Trade win rate, median trade return, PCA explained variance, pair distance, residual magnitude, and score IC are diagnostics only, not hidden gates.

A deflated-performance-style diagnostic is required but is not an undeclared acceptance criterion.

## 13. Multiplicity and winner selection

Global Holm-Bonferroni family = all **4** candidate/direction hypotheses, alpha `0.05`.

Selection survival requires all frozen selection checks plus global Holm survival of the dependence-aware one-sided bootstrap p-value.

At most one selection winner per direction advances. Among qualifying candidates in one direction choose:

1. highest primary selection LCB;
2. then highest primary selection mean;
3. then lexical candidate ID.

If a direction's winner fails internal validation, **no runner-up substitution** is allowed.

At most one finalist per direction may be frozen.

## 14. Protected holdout rule

The inherited protected predictor window is `2026-05-12` through `2026-08-11` and remains outcome-unopened after Phases26–28.

Before any Phase29 protected outcome can be materialized, an independent blindness audit must prove:

1. Phase26 protected return reads = 0;
2. Phase27 protected candidate/return reads = 0 and holdout unconsumed;
3. Phase28 protected candidate/return reads = 0 and holdout unconsumed;
4. Phase28 closeout is `ACCEPTED_NEGATIVE` and passing;
5. Phase29 spec/policy/fingerprint were frozen before target performance;
6. Phase29 finalist artifact is frozen with zero protected reads;
7. no Phase29 protected read-plan/outcome artifact preexists.

Zero finalists => confirmation must stop with exactly zero protected candidate rows and zero protected return rows read, with no read plan and holdout still unconsumed.

If finalists exist, Phase29 must first compute protected predictors/scores and persist an immutable exact finalist-tail signal-key read plan. Only those keys may have future returns joined. Creation of a nonempty protected read plan permanently consumes the holdout.

## 15. External authority boundary

Phase29 permits no provider API reads/writes, broker reads/writes, order writes, PAPER submits, LIVE writes, automation writes, automatic broker failover, or frontend trading authority.

Historical analytical support alone never authorizes execution.

## 16. Phase-end acceptance gate

Complete acceptance requires:

- frozen spec/policy/fingerprint validation;
- deterministic PCA and distance-pair primitive tests;
- exact PIT/split/history-boundary validation;
- leakage test proving formation ends `t-1` and focal current return is leave-focal-out for current PCA factor scoring;
- deterministic nearest-pair identity and tie-break tests;
- same-complete-case population across all four candidates;
- chronology/purge validation;
- dependence-aware economics and global Holm verification;
- winner/finalist cardinality and no-runner-up-substitution checks;
- independent protected blindness audit;
- zero-finalist skip or immutable finalist-only protected read-plan validation;
- independent persisted-artifact/economic reconstruction;
- end-to-end anti-workaround audit;
- provider/broker/order/PAPER/LIVE/automation zero activity;
- all retained validators and full pytest;
- exact-head Ubuntu and Windows CI;
- target-machine cumulative and closeout evidence;
- living-doc synchronization.

Possible dispositions:

- `ACCEPTED_POSITIVE`: >=1 Phase29 candidate earns historical analytical `SUPPORTED` authority;
- `ACCEPTED_NEGATIVE`: frozen question answered correctly with zero support;
- `NOT_ACCEPTED`: an implementation/evidence/acceptance defect remains.

Only `ACCEPTED_POSITIVE` satisfies the entry condition for the subsequent signal-to-trade construction phase.
