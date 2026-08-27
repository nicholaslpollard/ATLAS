# Phase 28 — Cross-Stock Lead-Lag & Residual Network Alpha

**Status:** ACTIVE / PREREGISTERED BEFORE ANY PHASE28 PERFORMANCE READ  
**Phase type:** research / historical analytical support authority only  
**Upstream authority:** Phase27 `ACCEPTED_NEGATIVE` merge `dc015f51232dc66ba94b6175c276a0227d5a3761`

## 1. Plain-English phase start

### Where ATLAS is now

ATLAS has a large accepted data, analytics, risk, execution-safety, browser, and PAPER foundation, but it still has **zero historically SUPPORTED strategies**. Phase26 rejected 24 deterministic/composite self-feature candidates. Phase27 then tested eight cross-sectional expected-return/ranking architectures over the same-stock feature set and again produced zero selection survivors, zero finalists, zero support, and zero protected-return reads.

### What Phase28 is trying to accomplish

Phase28 changes the **information source** rather than trying another model over the same focal-stock indicators. It asks whether recent moves in other production-relevant stocks can lead a focal candidate's next move after broad/common cross-sectional motion is removed.

In simpler terms: when stock A tends to move before stock B, can A's current residual move help ATLAS judge B's existing bullish or bearish candidate more effectively?

### Why this matters for account growth/profit

Information can diffuse across related securities at different speeds. A relational signal may contain information that is absent from a ticker's own RSI/MACD/return state. If the effect exists in ATLAS's exact production path, it could improve opportunity selection without weakening any existing safety or execution standard.

### What will be built or changed

Phase28 will build one frozen observation-time peer/residual network from canonical daily history and exact PIT candidate identities, four deterministic relational/residual signal families, dependence-aware chronological evaluation, multiplicity control, internal validation, protected finalist-only confirmation, and independent artifact reconciliation.

It will **not** build a graph neural network, mine arbitrary network architectures, use current-only customer/supplier/industry mappings, or tune the network after seeing performance.

### What success means

At most one LONG and one SHORT Phase28 finalist may earn historical analytical `SUPPORTED` authority. A supported Phase28 candidate satisfies the alpha entry condition for Phase29 signal-to-trade construction. It does not create PAPER or LIVE authority.

### What happens on a negative result

If no candidate passes, Phase28 closes `ACCEPTED_NEGATIVE`. Signal-to-trade construction remains blocked. Network windows, peer counts, signal formulas, score tails, costs, chronology, and protected evidence may not be widened or retuned after the result.

### What is explicitly not happening yet

Phase28 does not perform stock/options trade construction, portfolio optimization, broker mutation, PAPER submission, LIVE trading, deployment, or major GUI development.

## 2. Scientific question

Given an accepted WARM/HOT directional production-path-native candidate at finalized session `t`, does a frozen observation-time network of other same-session production candidates contain asymmetric lagged residual-return information that can select a fixed strongest tail with robust positive three-session directional return after realistic costs?

The null is that no frozen Phase28 signal/direction hypothesis earns historical analytical support.

## 3. Source population and lineage

Primary focal-source artifacts are the accepted Phase26 observation artifacts:

- development: `data/derived/strategy_evaluation/phase26/v1/observations/development_observations.parquet`;
- protected predictors: `data/derived/strategy_evaluation/phase26/v1/observations/protected_predictors.parquet`.

Required upstream evidence:

- accepted Phase26 policy fingerprint `24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2`;
- Phase26 independent validation and closeout PASS;
- Phase27 closeout `ACCEPTED_NEGATIVE` and independent PASS;
- Phase27 protected candidate/return reads both zero;
- Phase27 holdout consumed `False`.

The Phase28 research start is `2021-08-16`, labeled development ends `2026-05-06`, the exact 3-session outer purge remains `2026-05-07`, `2026-05-08`, `2026-05-11`, and the inherited protected predictor window is `2026-05-12` through `2026-08-11`.

Outcome horizon is exactly **3 exchange sessions**. No horizon search is allowed.

Direction mapping remains:

- bullish row -> LONG directional return = forward return;
- bearish row -> SHORT directional return = negative forward return.

## 4. Peer universe

For focal candidate row `(instrument_id, as_of_date=t)`:

1. begin with all Phase26 production-path-native candidate rows at the same `t` whose direction is `bullish` or `bearish`;
2. do not require peer direction to equal focal direction;
3. exclude the focal instrument itself from its leader candidates;
4. each ticker's history must remain inside that row's exact `safe_start_date` / `safe_end_date` interval;
5. a ticker with a split during the required network-history window is unavailable for that focal observation;
6. ticker text alone never bridges identity intervals;
7. no current-only sector, customer/supplier, ownership, news, or textual relationship may be projected backward to create peers.

The peer universe is therefore endogenous to the exact production candidate set known at `t` and does not depend on external historical relationship metadata.

## 5. Daily residual-return construction

Use canonical finalized 1d bars only.

For each peer-universe ticker and exchange session in the required trailing history:

`raw_return[t] = close[t] / close[t-1] - 1`

For each historical session `s`, using only peer-universe tickers with a finite valid return at `s`:

`common_return[s] = median(raw_return_i[s])`

and

`residual_i[s] = raw_return_i[s] - common_return[s]`.

A common-return session requires at least **5** valid peer returns. Otherwise every residual on that session is unavailable.

This cross-sectional median is a fixed robust common-move control. It is not fitted to future outcomes and is not tuned.

## 6. Frozen lead-lag network

Network relationships for observation `t` are estimated using residual returns ending at **t-1**. The network may not use focal or peer returns from after `t-1` when choosing leaders.

Frozen settings:

- lag-estimation pairs: **60**;
- minimum valid aligned lag pairs: **50**;
- maximum leaders retained per focal: **3**;
- minimum qualifying leaders required: **2**.

For peer `p` and focal `f`, over the frozen trailing aligned pairs:

`forward_corr = corr(residual_p[s-1], residual_f[s])`

`reverse_corr = corr(residual_f[s-1], residual_p[s])`

`asymmetry = forward_corr - reverse_corr`

A peer qualifies as a leader only when:

- at least 50 aligned finite lag pairs exist;
- `forward_corr > 0`;
- `asymmetry > 0`.

Qualifying peers are sorted by descending asymmetry, then deterministic peer instrument ID. Keep at most the top 3.

Leader weights are:

`weight_j = asymmetry_j / sum(asymmetry_k)`.

No correlation/asymmetry threshold other than positivity is searched or tuned.

## 7. Frozen signal library

Four raw signal families are computed for every complete focal row:

1. **Residual momentum 20d**  
   `residual_momentum_20d = sum(focal residual over t-19 ... t)`

2. **Peer lead 1d**  
   `peer_lead_1d = sum(weight_j * leader_j residual[t])`

3. **Peer lead 5d**  
   `peer_lead_5d = sum(weight_j * sum(leader_j residual over t-4 ... t))`

4. **Peer diffusion gap 1d**  
   `peer_diffusion_gap_1d = peer_lead_1d - focal residual[t]`

All four raw signals must be finite for a row to enter the Phase28 complete-case population. This means every hypothesis is evaluated on the same eligible rows.

The network is chosen using history through t-1, but each frozen signal is allowed to use finalized current-session residual return at t because the production candidate itself is evaluated after session t is finalized.

## 8. Frozen candidate library

Eight global hypotheses = four signal families × LONG/SHORT:

- `residual_momentum_20d_long`
- `residual_momentum_20d_short`
- `peer_lead_1d_long`
- `peer_lead_1d_short`
- `peer_lead_5d_long`
- `peer_lead_5d_short`
- `peer_diffusion_gap_1d_long`
- `peer_diffusion_gap_1d_short`

Score orientation:

- LONG: `score = raw_signal` and row direction must be `bullish`;
- SHORT: `score = -raw_signal` and row direction must be `bearish`.

No model fitting or hyperparameter training occurs in the frozen Phase28 candidate library.

## 9. Complete-case and score-to-signal policy

A session/direction is Phase28-eligible only when at least **5** focal rows have all four frozen raw signals finite.

For every candidate and session/direction:

- sort eligible rows by descending Phase28 score;
- select exactly `ceil(0.20 * n)` rows;
- deterministic instrument-ID tie break;
- no secondary threshold, minimum predicted return, discretionary filter, or tail search.

The fixed **20%** tail is used in selection, internal validation, and protected confirmation.

## 10. Chronology

Labeled development ends `2026-05-06`.

Within labeled development:

- first 75% of ordered eligible exchange sessions -> selection;
- exact 3 exchange sessions -> purge;
- remaining sessions -> internal validation.

Selection uses six chronological folds. Internal validation uses three chronological folds. Protected confirmation uses three chronological folds where sample support allows.

All network features are observation-time only. Outcome labels are joined only after signals are frozen for the relevant evaluation tranche.

## 11. Frozen economics and dependence treatment

Cost grid in basis points:

`0, 5, 10, 25, 50`

Primary acceptance cost: **10 bps**.  
Stress cost: **25 bps**.

Signal rows are first averaged within exchange session before confidence tests so a day with many candidates does not masquerade as many independent observations.

Moving-block bootstrap:

- block length: **6 sessions**;
- replicates: **2000**;
- deterministic base seed: **280228**.

Confidence levels:

- selection: **95%**;
- internal: **90%**;
- protected: **80%**.

## 12. Minimum evidence and robustness gates

Selection:

- >= 750 raw signal rows;
- >= 250 signal sessions;
- >= 5 of 6 positive fold means at 10 bps;
- 10 bps session mean > 0;
- 95% block-bootstrap lower confidence bound > 0;
- 25 bps stress session mean > 0;
- concentration/robustness gates pass.

Internal validation:

- >= 250 raw signal rows;
- >= 80 signal sessions;
- >= 2 of 3 positive fold means;
- 10 bps mean > 0;
- 90% lower confidence bound > 0;
- 25 bps stress mean > 0;
- concentration/robustness gates pass.

Protected confirmation:

- >= 75 raw signal rows;
- >= 24 signal sessions;
- >= 2 of 3 positive fold means;
- 10 bps mean > 0;
- 80% lower confidence bound > 0;
- 25 bps stress mean > 0;
- concentration gates pass.

Robustness:

- positive eligible year fraction >= 60%, with >=20 signal sessions per eligible year;
- positive eligible market-state fraction >= 50%, >=20 sessions per eligible state;
- positive eligible ticker-state fraction >= 50%, >=20 sessions per eligible state;
- maximum one-session raw-row fraction <= 10%.

Trade win rate and median trade return are diagnostics, not hard gates.

A deflated-performance-style diagnostic is required but is not an undeclared hidden gate.

## 13. Multiplicity and winner selection

Global Holm-Bonferroni family: all **8** candidate/direction hypotheses, alpha `0.05`.

A candidate may survive selection only if its frozen selection checks pass and its dependence-aware one-sided bootstrap p-value survives global Holm.

At most one selection winner per direction advances. Among passing/Holm-surviving candidates of the same direction, choose:

1. highest selection primary lower confidence bound;
2. then highest selection primary mean return;
3. then lexical candidate ID.

If the winner fails internal validation, **no runner-up substitution** is allowed.

At most one finalist per direction may be frozen.

## 14. Protected holdout rule

The inherited master protected predictor window is `2026-05-12` through `2026-08-11` and remains outcome-unopened after Phases26 and 27.

Before any Phase28 protected outcome is materialized, an independent blindness audit must prove:

1. Phase26 protected candidate/return reads = 0;
2. Phase27 protected candidate/return reads = 0;
3. Phase27 holdout consumed = False;
4. Phase27 closeout is `ACCEPTED_NEGATIVE` and passing;
5. Phase28 spec/policy/fingerprint are frozen;
6. Phase28 finalist artifact is frozen with zero protected reads;
7. Phase28 protected outcome/read-plan artifacts do not preexist.

If no finalists exist, protected confirmation must skip with exactly zero candidate rows and zero return rows read; the holdout remains unconsumed.

If finalists exist, Phase28 must first score protected predictors and freeze an immutable exact signal-key read plan. Only those finalist-fired keys may have future returns joined. Creation of a nonempty protected read plan permanently consumes the holdout.

## 15. External authority boundary

Phase28 allows no provider API reads/writes, broker reads/writes, order writes, PAPER submits, LIVE writes, automation writes, or automatic broker failover. It uses already accepted local historical artifacts only.

Historical analytical support does not itself authorize execution.

## 16. Phase-end acceptance gate

The complete phase gate must include:

- frozen policy/spec validation;
- deterministic network primitive tests;
- exact source-lineage and PIT/split/history-boundary validation;
- independent reconstruction of residual/network/signal evidence;
- chronology/leakage tests;
- dependence-aware economics and global Holm verification;
- winner/finalist cardinality and no-runner-up-substitution checks;
- protected blindness and finalist-only read-plan verification;
- independent persisted-artifact reconciliation;
- end-to-end anti-workaround audit;
- provider/broker/order/PAPER/LIVE/automation zero activity;
- all retained repository validators;
- full pytest;
- Ubuntu and Windows CI;
- target-machine cumulative/closeout evidence.

Possible dispositions:

- `ACCEPTED_POSITIVE`: >=1 candidate earns Phase28 historical analytical `SUPPORTED` authority;
- `ACCEPTED_NEGATIVE`: frozen question answered correctly but zero support;
- `NOT_ACCEPTED`: implementation/evidence/acceptance defect remains.

Only `ACCEPTED_POSITIVE` satisfies Phase29 signal-to-trade entry.
