# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-26.**

Read `docs/roadmap.md` first. It is now the normative mission/anti-drift/remaining-phase source of truth. This file records the exact current project state and immediate handoff.

## Repository state

- **Phases 1–25 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950` through PR #27.
- Phase25 target-tested code head: `302bf6db5d807884f3b74cda049fc95864c5a194`; cumulative CI `32981080421` passed Ubuntu/Windows through all Phase25 evidence plus full regression.
- Phase25 final docs head: `f2d10465b71446b253b5d73a50845d2ea1e704d3`; CI `33025699177` passed Ubuntu/Windows.
- Phase25 disposition: **NO SUPPORT REPLACEMENT — DEVELOPMENT ROBUSTNESS FAILED**.
- Post-Phase25 synchronized main baseline: `b4dd62ded815d4b2d5a734f07c4272cc05d92567`.
- Active branch: `phase-26-materially-different-strategy-architectures`, created from that synchronized baseline.
- **Current next phase/gate: Phase26 — Production-Path-Native Alpha Discovery & Validation.**
- Phase26 implementation has not yet been accepted or merged.

## Mission lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

The system is not optimized for trade count. A PASS/no-trade decision is correct when the available evidence, instrument, expected payoff, or risk does not justify a position.

## Architecture lock

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> promotion -> deep research/news -> stock/options instrument selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome learning -> browser control plane`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary market/reference; Webull is primary PAPER/sandbox and intended primary LIVE broker only after separate acceptance; Alpaca is manual secondary only. ML is probability/predictive evidence; AI is independent audit; browser is monitoring/control rather than business-logic authority.

LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## What has been proven through Phase25

The data, analytical, execution-safety, and operator foundations are substantial and remain accepted. ATLAS already has PIT/reference/canonical data, features, broad discovery, regimes, ML probability evidence, deterministic strategy routing, promoted-only research, context/options/geometry/portfolio-risk planning, independent AI audit, broker-neutral SHADOW/PAPER execution, Webull sandbox lifecycle evidence, browser/observability primitives, restart-safe orchestration, central PAPER-submit authority, routine PAPER runner, and a current finalized-session analysis binding.

The unresolved problem is strategy edge.

Accepted Phase11 support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Phase24 tested 28 bounded challenger variants and produced 0 acceptable replacements.

Phase25 then reconstructed the actual historical production path:

- 1,260 replay sessions;
- 23,177 WARM/HOT directional rows;
- 15,283 fully route-eligible candidates;
- 61,132 eligible strategy-route decisions;
- 185,416 total route decisions;
- every non-empty incumbent had negative 10 bps production-path mean and worsened versus its broad comparator;
- no strategy survived the preregistered robustness framework;
- protected evidence remained unread because there were zero finalists;
- Phase11 support therefore remained unchanged.

**Plain-English conclusion:** the lack of supported strategies is real under the evidence tested so far. The next priority is finding and validating genuinely different alpha, not weakening old rules or adding unrelated infrastructure.

## Development-process rebaseline

Starting with Phase26, **the numbered phase itself is the project acceptance gate**.

Internal work packages/checkpoints are allowed for efficient development and research, but they are not separate project gates. The full applicable regression suite, historical validators, independent validation, Ubuntu/Windows CI, negative/recovery testing, reproducibility checks, and target-machine/provider/broker evidence where required are run together at the end of the completed phase before acceptance/merge.

Future phase reports must first explain Goal, Built, Full Gate PASS/FAIL, Evidence Meaning, Authority Change, Limitations/Risks, and Next Phase in plain English before raw hashes/statistics.

Read `docs/phase_flow.md` for the normative acceptance contract.

## Active Phase26 boundary

Phase26 solves the current alpha bottleneck as one coherent phase rather than exposing a chain of Gate0/Gate1/etc. project milestones.

It must:

1. construct its primary research population directly from accepted Phase25 production-path identities/context plus canonical features/outcomes;
2. avoid using the incomplete legacy Phase11/24 broad research join as its primary source;
3. preregister materially different architecture/hypothesis search spaces and validation methodology before protected performance inspection;
4. test long and short ideas independently rather than assuming mirror symmetry;
5. include realistic instrument/strategy-specific costs and liquidity constraints;
6. control chronology, overlapping outcomes/session dependence, multiple testing/selection bias, concentration, year/regime robustness, and backtest overfitting;
7. compare complex candidates against simpler baselines;
8. allow community/market ideas such as relative strength, mean reversion, gaps/opening-range/VWAP/RVOL, multi-timeframe evidence, and volatility/option structures only as testable hypotheses;
9. independently validate/protected-confirm any finalist before support can change;
10. finish with one full Phase26 acceptance gate.

Phase26 may replace the Phase11 support map only if the preregistered evidence standard is met. It creates **no provider mutation, broker submit, PAPER, or LIVE authority**.

If Phase26 finds no acceptable edge, accept the negative result and keep downstream LIVE progression blocked; define the next alpha-research phase from the failure evidence instead of weakening standards.

## Planned route after Phase26

Subject to the entry conditions in `docs/roadmap.md`:

- Phase27 — Signal-to-Trade Construction & Portfolio Optimization;
- Phase28 — End-to-End Historical Replay & Stress Certification;
- Phase29 — Prospective SHADOW/PAPER Certification;
- Phase30 — Outcomes, Learning, Drift Monitoring & Governance;
- Phase31 — Production Operations & Browser Control Plane;
- Phase32 — LIVE Readiness, Reconciliation & Failure Certification;
- Phase33 — Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent non-negotiables

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; do not synthesize unavailable history; finalized facts outrank provisional state; ML/AI do not create trade authority; community trading ideas are hypotheses rather than assumed edge; uncertain mutation state requires reconciliation; no automatic broker failover; PAPER does not imply LIVE; and downstream phases do not advance past a missing validated-alpha requirement merely because their infrastructure could be built.
