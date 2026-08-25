# Phase 24 — Strategy Evidence Challenger & Support Replacement

**Status: ACTIVE / GATE 0 EVIDENCE COMPLETE / GATE 1 PREREGISTRATION LOCKED**

Upstream authority: Phase23 accepted merge `2004338624766c42b5f4db2bb0976b2047a5c6b0`; synchronized `main` handoff `8fa832decc2f1be7762373f8ba4cc05a38b8404a`.

## Purpose

Phase24 addresses the analytical bottleneck exposed by the accepted 2026-08-21 Phase23 cycle: 23 WARM/HOT directional cases were current enough to be considered, but the frozen Phase11 support map contains zero SUPPORTED strategies, so no candidate may promote.

Phase24 does **not** weaken or edit the accepted Phase11 map in place. It builds a separate, preregistered challenger evidence process. The Phase11 map remains authoritative until a Phase24 replacement mapping independently satisfies its acceptance contract and is explicitly adopted.

## Audit basis

The authoritative-main audit established that Phase11 support v1 is intentionally narrow:

- eight fixed daily rule strategies;
- a three-session direction-adjusted endpoint-return signal study, not an execution/fill simulation;
- flat transaction-cost grid 0/5/10/25 bps;
- support classification uses only the 10 bps mean return;
- SUPPORTED requires positive development mean and positive means in both chronological development halves;
- MIXED means aggregate development mean positive but at least one half is non-positive;
- UNSUPPORTED means aggregate development mean is non-positive;
- any nonempty slice is considered sufficient; there is no stronger minimum sample-size rule;
- yearly and market-regime distributions are computed but do not participate in support classification;
- the existing protected confirmation interval cannot change support classification;
- under zero SUPPORTED strategies, current promotion skips strategy-rule evaluation for MIXED/UNSUPPORTED routes.

This is a valid conservative v1 gate, but it is not a sufficient evidence framework for selecting a better production strategy set.

## Authority boundary

Phase24 research is **local analytical work only** unless a later explicitly reviewed gate changes this contract.

Allowed:

- read accepted local Phase11/Phase23/canonical/feature/regime/model artifacts;
- compute diagnostic and challenger research evidence locally;
- write local Phase24 research/validation artifacts;
- use the accepted historical research dataset and accepted finalized local market data.

Forbidden unless a later Phase24 gate explicitly changes this contract after separate review:

- provider reads or writes;
- broker reads or writes;
- order submit/replace/cancel/close/flatten;
- Phase21 PAPER-submit authority;
- Phase22 execution;
- LIVE;
- automatic broker failover;
- browser execution authority;
- scheduler/daemon authority;
- PostgreSQL runtime promotion;
- production ML retraining/replacement;
- changing Phase23 frozen support or promotion authority before Phase24 acceptance;
- using current or protected results to silently tune thresholds after results are seen.

## Gate 0 — forensic evidence diagnostic — COMPLETE

Gate 0 produced a provider-free report binding:

1. accepted Phase11 support decisions with development/half sample sizes and means;
2. exact Phase11 study/support-policy/strategy-registry lineage;
3. the accepted Phase23 2026-08-21 current candidate population;
4. a non-authoritative counterfactual evaluation of currently routed incumbent rules even when their Phase11 status is MIXED/UNSUPPORTED.

### Accepted target-machine result

Finalized `2026-08-21` Gate 0 evidence:

- accepted current WARM/HOT directional cases: **23**;
- accepted authoritative promotions: **0**;
- counterfactual eligible route evaluations: **92**;
- counterfactual incumbent rule fires: **48**;
- candidates with at least one counterfactual fire: **21**;
- support status counts: **3 MIXED / 5 UNSUPPORTED / 0 SUPPORTED**;
- provider reads/writes: **0 / 0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- Phase11 support writes: **0**;
- pass: **true**.

This establishes that current zero promotion is not because incumbent setup logic is dormant. Existing rules fire frequently on current routed cases, but no incumbent has earned historically stable support under the frozen v1 authority.

The current Gate 0 results are **descriptive only** and may not be used to select or tune challengers.

## Gate 1 — preregistered challenger methodology — LOCKED

Gate 1 freezes the v2 research methodology **before any challenger is evaluated on protected evidence**.

Canonical methodology document:

`docs/phase24_gate1_preregistered_methodology.md`

Code lock:

`packages/backtesting/phase24_gate1_policy.py`

Gate 1 requires:

- development-only search and ranking;
- chronological 75% selection / purged internal-validation split;
- three-session purge at the split;
- six chronological selection folds;
- session-level dependence handling for same-day cross-sectional signals;
- six-session moving/block bootstrap for three-session outcomes;
- minimum raw-row and unique-signal-session requirements;
- 10 bps primary and 25 bps stress costs;
- positive mean, median, positive-rate and uncertainty evidence;
- yearly and market-regime robustness gates;
- Holm-Bonferroni multiplicity control within family/direction;
- at most one selected finalist per family/direction before internal validation;
- a bounded set of exactly **28 new v2 challenger variants** using only already accepted features/rules;
- zero protected-evidence reads during Gate 1;
- current Gate 0 evidence excluded from selection;
- incumbent protected evidence treated as already observed/contaminated, never fresh;
- Phase11 support authority unchanged.

## Gate 2 — development-only challenger evaluation — NEXT

Gate 2 may implement and execute the selection/internal-validation engine exactly against the locked Gate 1 fingerprint.

Gate 2 may not:

- alter the Gate 1 search space after seeing performance;
- use Gate 0 current firing results for selection;
- read protected evidence before the fresh finalist set is frozen;
- promote a strategy or replace Phase11 support;
- create provider/broker/order/PAPER/LIVE authority.

If no challenger survives selection/internal validation, that is a valid result and the protected interval remains untouched.

## Promotion and downstream boundary

Until a Phase24 final acceptance explicitly replaces the support authority:

- Phase11 support v1 remains frozen;
- Phase23 current runs continue to expect zero promotions under that frozen map;
- Phase12/13/14 remain zero-path when no candidate is legitimately promoted;
- Phase21/22 remain the only PAPER authority/operator path;
- no Phase24 research artifact is an order or execution case.

## Non-goals

Phase24 is not a model replacement phase, broker phase, execution phase, GUI phase, scheduler phase, PostgreSQL promotion phase, or LIVE phase. It does not manufacture a supported strategy simply because downstream activity is currently zero.
