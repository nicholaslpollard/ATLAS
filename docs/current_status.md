# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-27 after Phase28 merge/post-merge acceptance and Phase29 preregistration.**

Read `docs/roadmap.md` first. It is the normative mission/anti-drift/remaining-phase source of truth. Read `docs/phase_plain_english_contract.md` before beginning/closing a numbered phase. Active specification: `docs/phase29_relative_value_statistical_arbitrage.md`.

## Repository state

- **Phases 1–28 ACCEPTED / MERGED.**
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950`.
- Phase26 PR #30 merge: `2074808605cf85b5462e5999ed1836d68b0434c3` — `ACCEPTED_NEGATIVE`.
- Phase27 PR #31 merge: `dc015f51232dc66ba94b6175c276a0227d5a3761` — `ACCEPTED_NEGATIVE`.
- Phase28 PR #32 merge: `285f112d51463dd1e06ea4e874a882ad98f71dc5` — `ACCEPTED_NEGATIVE`.
- Phase28 post-merge workflow `33114372397`: Ubuntu PASS / Windows PASS, including retained validators and full regression.
- Active branch: `phase-29-relative-value-statistical-arbitrage`.
- **Current gate: Phase29 — Relative-Value Statistical-Arbitrage Confirmation Alpha.**
- Signal-to-trade construction is Phase30 and remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.

## Mission / authority lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> learning -> browser control plane -> deployment`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary market/reference; Webull is primary PAPER/sandbox and intended primary LIVE only after separate acceptance; Alpaca is manual secondary only. ML and AI do not create trade authority. Browser/UI never bypasses backend authority.

LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Root-cause / no-workaround lock

A failed check must be traced to the owning layer and corrected there. ATLAS cannot earn acceptance by weakening a validator, ignoring a discrepancy, adding a bypass/parallel authority path, changing a research threshold after results, or stacking repair wrappers merely to obtain PASS.

Legitimate negative research is accepted rather than repaired into a positive result.

## Accepted strategy authority

Phase11 support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Phases26–28 did not replace this map.

## Phase26 evidence

Policy fingerprint `24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2`.

- development observations **21,483**;
- protected predictors **1,096**;
- survivors/finalists/supported **0 / 0 / 0**;
- protected returns **0**;
- independent + anti-workaround PASS;
- disposition `ACCEPTED_NEGATIVE`.

## Phase27 evidence

Policy fingerprint `63030d55fbdb60ce61ea0c84081ae95d62d68fc717f494aa41a23d31c410aab0`.

- development rows **18,111**;
- protected predictors **920**;
- survivors/winners/finalists/supported **0 / 0 / 0 / 0**;
- protected candidate/return reads **0 / 0**;
- holdout consumed **False**;
- independent + anti-workaround PASS;
- disposition `ACCEPTED_NEGATIVE`.

## Phase28 evidence

Policy fingerprint `0f15966f61a0baf52513cd46dc4fa8492c98e7dc8cf9ed3d551c2ebc955adea5`.

- development network rows **14,466**;
- protected network predictors **741**;
- survivors/winners/finalists/supported **0 / 0 / 0 / 0**;
- protected candidate/return reads **0 / 0**;
- holdout consumed **False**;
- independent validation PASS;
- end-to-end anti-workaround PASS;
- provider/broker/order/PAPER/LIVE **0**;
- target closeout at `945adf9b2722da3822e6dcc79467ae9620d5d439`: PASS / `ACCEPTED_NEGATIVE`;
- final documented head `2861d57b4e7941457f7d7e44dc22cc75fb52c1c8` green Ubuntu/Windows;
- PR #32 merged at `285f112d51463dd1e06ea4e874a882ad98f71dc5`;
- post-merge workflow `33114372397` green Ubuntu/Windows.

## Protected-holdout state

Master protected predictor window: `2026-05-12` through `2026-08-11`.

Phases26, 27, and 28 read **zero protected returns**. Phase28 had zero finalists, so no protected read plan was created. The holdout remains genuinely outcome-unopened.

Phase29 may use it only after an independent blindness audit proves all prior zero-read state plus absence of Phase29 protected outcome artifacts. First future protected-outcome read permanently consumes it.

## Research failure map

Rejected under frozen standards:

1. Phase26 — deterministic/composite focal self-feature rules;
2. Phase27 — same-stock cross-sectional learned expected-return/ranking models;
3. Phase28 — cross-stock residual/lead-lag predictive signals.

Phase29 therefore tests a different **relative-value mean-reversion mechanism**, not another prediction architecture.

## Active Phase29 frozen design

Machine-readable policy: `packages/backtesting/phase29_policy.py`.  
Specification: `docs/phase29_relative_value_statistical_arbitrage.md`.

Exactly four hypotheses:

- `pca_residual_reversion_long`;
- `pca_residual_reversion_short`;
- `distance_pair_reversion_long`;
- `distance_pair_reversion_short`.

Frozen mechanics:

- source focal/peer set = exact same-session Phase26 production-path-native directional candidates;
- canonical finalized 1d history only, exact PIT/split-safe intervals;
- exactly 62 closes per complete instrument (`t-61` ... `t`);
- PCA formation = 60 returns ending `t-1`;
- PCA components = 3, minimum complete peers = 8;
- current PCA factor score solved leave-focal-out so focal current return cannot explain itself;
- nearest pair = minimum squared distance over 60 normalized formation prices ending `t-1`;
- pair identity/statistics frozen before current `t` dislocation is measured;
- both PCA and pair signals must be finite for every eligible focal row;
- minimum 5 complete rows per session/direction;
- fixed top 20% tail;
- outcome = exact focal-stock t+3 directional return;
- costs = 10 bps primary / 25 bps stress;
- first 75% eligible development sessions selection, exact 3-session purge, remaining internal;
- 6 selection folds / 3 internal / 3 protected;
- block bootstrap 6 sessions / 2000 reps / frozen seed;
- global Holm across 4 hypotheses;
- at most one winner/finalist per direction;
- no runner-up substitution;
- finalist-only protected read plan;
- provider/broker/order/PAPER/LIVE/automation = zero.

**Scope clarification:** Phase29 tests relative-value information as confirmation of existing single-stock directional candidates. It does not claim pair-portfolio or market-neutral execution authority.

No Phase29 performance has been inspected. Formation length, component count, pair rule, tail, costs, chronology, and acceptance gates are now frozen before target evidence.

## Phase29 implementation path

1. frozen spec/policy/fingerprint;
2. deterministic PCA and nearest-pair primitives + tests;
3. exact PIT/split-safe relative-value population builder;
4. development selection/global Holm;
5. internal validation/finalist freeze;
6. independent inherited-holdout blindness audit;
7. zero-finalist skip or immutable finalist-tail protected read plan;
8. independent evidence/economics reconstruction;
9. cumulative target runner;
10. provider-free retained contract validator + full cross-platform CI;
11. target-machine run;
12. full closeout/anti-workaround audit, docs, accept/repair, merge.

## Rebaselined downstream roadmap

- **Phase29:** Relative-Value Statistical-Arbitrage Confirmation Alpha — active.
- **Phase30:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — requires supported alpha.
- **Phase31:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase32:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase33:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase34:** Production Web App/Operations/Deployment.
- **Phase35:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase36:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent non-negotiables

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; do not synthesize unavailable history; finalized facts outrank provisional state; ML/AI do not create trade authority; research ideas are hypotheses; uncertain mutation state requires reconciliation; UI never creates/bypasses authority; no automatic broker failover; PAPER does not imply LIVE; negative research is accepted rather than manipulated; LIVE authority exists only after a separately accepted activation phase.
