# Phase 24 — Strategy Evidence Challenger & Support Replacement

**Status: ACTIVE / GATE 0 DIAGNOSTIC**

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
- under zero SUPPORTED strategies, current promotion skips strategy-rule evaluation for MIXED/UNSUPPORTED routes, so the 23 Phase23 cases do not tell us whether incumbent rules would currently fire.

This is a valid conservative v1 gate, but it is not a sufficient evidence framework for selecting a better production strategy set.

## Authority boundary

Phase24 Gate 0 and challenger research are **local analytical work only**.

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

## Gate 0 — forensic evidence diagnostic

Before challenger variants or replacement thresholds are selected, produce a provider-free report that binds:

1. accepted Phase11 support decisions with development/half sample sizes and means;
2. the exact Phase11 v1 policy and strategy-registry fingerprints;
3. the accepted Phase23 2026-08-21 current candidate population;
4. a **counterfactual diagnostic** that evaluates currently routed incumbent strategy rules even when their Phase11 status is MIXED/UNSUPPORTED.

The counterfactual diagnostic is non-authoritative. It may answer questions such as “would this existing rule fire now if historical support were ignored?”, but it cannot promote a candidate, change support, or create a trade.

Gate 0 deliberately does not use existing protected-confirmation results to select challenger rules.

## Challenger process lock

After Gate 0 evidence is accepted, Phase24 will preregister the challenger search space and acceptance metrics before evaluating any challenger on protected evidence.

Required properties of the replacement evidence framework:

- development-only strategy/parameter selection;
- explicit minimum effective sample-size requirements stronger than `rows > 0`;
- chronological robustness beyond one two-half split;
- year/regime diagnostics incorporated into acceptance or explicit robustness gates rather than collected and ignored;
- realistic 10 bps primary cost with 25 bps stress evidence;
- distribution/tail and uncertainty evidence, not mean sign alone;
- controls for repeated correlated observations and overlapping three-session outcomes;
- one-shot protected evaluation for newly preregistered challengers;
- incumbent strategies evaluated under the same v2 framework for an apples-to-apples benchmark;
- no support replacement unless independent validation reproduces the result exactly;
- zero SUPPORTED strategies remains a valid final outcome if no challenger earns support.

The existing Phase11 protected-confirmation results for incumbent v1 strategies are considered already observed and cannot be treated as fresh evidence for tuning those incumbents. Challenger handling of protected evidence must be explicitly preregistered before first evaluation.

## Promotion and downstream boundary

Until a Phase24 final acceptance explicitly replaces the support authority:

- Phase11 support v1 remains frozen;
- Phase23 current runs continue to expect zero promotions under that frozen map;
- Phase12/13/14 remain zero-path when no candidate is legitimately promoted;
- Phase21/22 remain the only PAPER authority/operator path;
- no Phase24 research artifact is an order or execution case.

## Gate 0 acceptance criteria

- diagnostic is provider/broker/AI/execution free;
- exact accepted Phase11 and Phase23 lineage is validated before reading evidence;
- no protected-confirmation metric is used to choose or modify a challenger;
- current counterfactual strategy firing is clearly labeled diagnostic/non-authoritative;
- no production support/promotion files are modified;
- focused tests and an independent static validator pass;
- Ubuntu and Windows CI pass at the Gate 0 evidence boundary;
- target-machine diagnostic is run once only because the accepted Phase11/Phase23 artifacts are local and not tracked in GitHub.

## Non-goals

Phase24 is not a model replacement phase, broker phase, execution phase, GUI phase, scheduler phase, PostgreSQL promotion phase, or LIVE phase. It does not manufacture a supported strategy simply because downstream activity is currently zero.
