# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-27.**

Read `docs/roadmap.md` first. It is the normative mission/anti-drift/remaining-phase source of truth. Read `docs/phase_plain_english_contract.md` before beginning or closing any numbered phase. The active Phase27 specification is `docs/phase27_cross_sectional_expected_return_learning_ranking.md`.

## Repository state

- **Phases 1–26 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950` through PR #27.
- Mission/roadmap rebaseline: PR #28 / `398bdba248bc196d619b8340d01851a3a4c63602`.
- GUI/web/deployment roadmap rebaseline: PR #29 / `a1ee179a18187723ad2b55a082db127e28914e4e`.
- Phase26 merge: PR #30 / `2074808605cf85b5462e5999ed1836d68b0434c3`.
- Phase26 disposition: **ACCEPTED_NEGATIVE**.
- Phase26 post-merge CI `33075333287`: Ubuntu PASS / Windows PASS, including all retained validators and full regression.
- Active branch: `phase-27-cross-sectional-expected-return-ranking`.
- **Current phase/gate: Phase27 — Cross-Sectional Expected-Return Learning & Ranking.**
- Phase28 signal-to-trade entry remains blocked unless Phase27 or a later alpha phase earns accepted `SUPPORTED` authority.

## Mission lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

The system is not optimized for trade count. A PASS/no-trade decision is correct when available evidence, instrument economics, or risk does not justify a position.

## Architecture lock

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> promotion -> deep research/news -> stock/options instrument selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome learning -> browser/web control plane -> production deployment/operations`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary market/reference; Webull is primary PAPER/sandbox and intended primary LIVE broker only after separate acceptance; Alpaca is manual secondary only. ML is evidence, AI is independent audit, and the browser is an operator surface rather than business-logic authority.

LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Root-cause / no-workaround lock

A failed check must be traced to the component, data artifact, assumption, interface, or process that owns the failure and corrected there. ATLAS cannot earn acceptance by bypassing a validator, weakening an invariant, ignoring a discrepancy, adding a parallel special-case path, changing a research threshold after results, or stacking repair wrappers merely to produce PASS.

Legitimate negative research is accepted rather than repaired into a positive result.

## Accepted strategy authority

Accepted Phase11 support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

No later phase has replaced that support map yet.

## Phase25 production-path foundation

Phase25 established the exact historical production candidate/routing population. The locally restored prerequisite lineage used authoritative Massive PIT evidence rather than fabricated history and independently passed Gate6/Gate7 reconstruction. Historical recovery code remains bounded provenance/rehydration functionality, not runtime trading authority.

Current-data catch-up remains deferred because Phase27 can initially use the already accepted Phase26 research population and still-unopened protected predictor window. If the Phase27 protected-blindness audit cannot prove that holdout remains outcome-blind, a later untouched window must be created through a separate validated catch-up rather than weakening the requirement.

## Phase26 final evidence

Frozen Phase26 policy fingerprint:

`24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2`

Valid target result:

- development usable observations: **21,483**;
- protected predictor observations: **1,096**;
- selection survivors: **0**;
- internal-validation finalists: **0**;
- protected-confirmed supported candidates: **0**;
- protected return rows read: **0**;
- independent validation: **PASS**;
- provider/broker/order/PAPER/LIVE activity: **0**.

Target closeout head `0c22889d0e8d33f19aab9ac405478255d990bdb6` returned **PASS / ACCEPTED_NEGATIVE**, anti-workaround audit PASS, protected reads 0, Phase27-old signal-to-trade entry false, and all external trading authority zero.

Phase26 merged as PR #30 at `2074808605cf85b5462e5999ed1836d68b0434c3`. Post-merge workflow `33075333287` passed Ubuntu and Windows.

**Practical conclusion:** hand-designed threshold/rule architectures tested so far have not demonstrated acceptable alpha. Do not tune Phase26 near-misses.

## Phase27 rationale

Phase27 changes the research architecture rather than thresholds. It asks whether the exact production-path-native feature set contains **continuous cross-sectional directional-return information** that can be learned well enough to rank same-session candidates and produce positive after-cost top-tail returns.

The scientific rationale is consistent with published cross-sectional asset-pricing work showing that nonlinear ML can capture predictor interactions missed by linear models, that regularized cross-sectional expected-return forecasting can improve out-of-sample prediction, and that ranking formulations are a plausible distinct way to optimize the relative ordering problem. These findings are hypothesis motivation only; they do not count as ATLAS evidence.

## Phase27 frozen design

Active specification:

`docs/phase27_cross_sectional_expected_return_learning_ranking.md`

Frozen high-level design:

- source population: accepted Phase26 production-path-native development/protected predictor artifacts;
- horizon: exactly 3 exchange sessions; no horizon search;
- direction: bullish/LONG and bearish/SHORT evaluated independently;
- same complete-case population for every candidate;
- 29 explicit observation-time technical predictors;
- same-session/direction percentile-rank transform to `[-1,1]`;
- target for learned regressors: session/direction median-residualized directional return;
- fixed top 20% score tail; no signal-threshold tuning;
- eight global architecture/direction hypotheses:
  - discovery-priority baseline LONG/SHORT;
  - Ridge relative-return LONG/SHORT;
  - histogram-gradient-boosted relative-return LONG/SHORT;
  - pairwise-logistic ranking LONG/SHORT;
- bounded nested chronological hyperparameter tuning only inside selection;
- 75% selection / exact 3-session purge / remaining internal validation;
- global Holm-Bonferroni across all 8 hypotheses;
- session/block dependence treatment, realistic 10 bps primary / 25 bps stress costs, concentration/year/regime robustness;
- at most one selection winner/finalist per direction;
- no runner-up substitution after internal rejection;
- finalist-only protected outcomes;
- analytical support only, with broker/PAPER/LIVE authority zero.

## Protected-holdout rule

Phase26's `2026-05-12`–`2026-08-11` protected predictor window had **zero return reads**. Phase27 may use it as the still-unopened master holdout only after a pre-read independent blindness audit proves no protected outcomes/metrics were materialized or consumed and the Phase27 policy is frozen first.

If that proof fails, the holdout cannot be used. A later untouched window must be built through validated data catch-up. Once Phase27 reads any outcome from this holdout, it is permanently consumed and cannot be called untouched in a future alpha phase.

## Phase27 implementation path

Implement the phase as one coherent gate:

1. machine-readable frozen policy/fingerprint;
2. source-lineage + complete-case cross-sectional population reconstruction;
3. deterministic model/scoring utilities and bounded tuning;
4. development selection + global multiplicity;
5. internal validation and finalist freeze;
6. pre-read protected-blindness audit;
7. zero-read skip or finalist-only protected confirmation;
8. independent persisted-artifact reconciliation;
9. cumulative runner + one target-machine command;
10. full Phase27 closeout, retained validators, pytest, Ubuntu/Windows CI, plain-English end, docs, accept/repair, merge.

No user-local command is required until repository/CI implementation reaches the genuine target-evidence boundary.

## Rebaselined downstream roadmap

- **Phase27:** Cross-Sectional Expected-Return Learning & Ranking — active alpha gate.
- **Phase28:** Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype — requires supported alpha.
- **Phase29:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase30:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase31:** Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI.
- **Phase32:** Production Web Application, Operations & Deployment.
- **Phase33:** LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification — LIVE still disabled.
- **Phase34:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent non-negotiables

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; do not synthesize unavailable history; finalized facts outrank provisional state; ML/AI do not create trade authority; community/research ideas are hypotheses rather than assumed edge; uncertain mutation state requires reconciliation; frontend/UI controls never create or bypass authority; no automatic broker failover; PAPER does not imply LIVE; negative research is accepted rather than manipulated; and LIVE authority exists only after Phase34 acceptance.
