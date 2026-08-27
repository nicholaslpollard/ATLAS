# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-27.**

Read `docs/roadmap.md` first. It is the normative mission/anti-drift/remaining-phase source of truth. Read `docs/phase_plain_english_contract.md` before beginning or closing any numbered phase. This file records the exact current project state and immediate handoff.

## Repository state

- **Phases 1–25 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950` through PR #27.
- Mission/roadmap rebaseline merged through PR #28 at `398bdba248bc196d619b8340d01851a3a4c63602`.
- GUI/web/deployment roadmap rebaseline merged through PR #29 at `a1ee179a18187723ad2b55a082db127e28914e4e`.
- Active branch: `phase-26-materially-different-strategy-architectures`.
- Phase26 target research is **COMPLETE / VALID NEGATIVE**.
- Phase26 full phase-end closeout gate is being finalized; Phase26 is not yet merged.
- Phase27 entry is currently **BLOCKED** because validated supported alpha remains zero.

## Mission lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

The system is not optimized for trade count. A PASS/no-trade decision is correct when the available evidence, instrument, expected payoff, or risk does not justify a position.

## Architecture lock

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> promotion -> deep research/news -> stock/options instrument selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome learning -> browser/web control plane -> production deployment/operations`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary market/reference; Webull is primary PAPER/sandbox and intended primary LIVE broker only after separate acceptance; Alpaca is manual secondary only. ML is probability evidence; AI is independent audit; the browser/web GUI is operator experience rather than business-logic authority.

LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Root-cause / no-workaround lock

A failed check must be traced to the component, data artifact, assumption, interface, or process that owns the failure and corrected there. ATLAS must not obtain acceptance by bypassing a validator, weakening an invariant, ignoring a discrepancy, adding a parallel special-case path, or changing a research threshold merely to turn failure into PASS.

Temporary workarounds may be used only for diagnosis/containment and cannot confer acceptance. Repeated repair wrappers, duplicate validators, or circular recovery/provenance logic are architectural defects to simplify. After a root fix, the applicable validation suite must be rerun.

A legitimate negative research result is not an engineering failure and must not be "repaired" into a positive result.

## Accepted foundation through Phase25

The data, analytical, execution-safety, and operator foundations remain accepted. ATLAS already has PIT/reference/canonical data, features, broad discovery, regimes, ML probability evidence, deterministic strategy routing, promoted-only research, context/options/geometry/portfolio-risk planning, independent AI audit, broker-neutral SHADOW/PAPER execution, Webull sandbox lifecycle evidence, browser/API/observability primitives, restart-safe orchestration, central PAPER-submit authority, routine PAPER runner, and a finalized-session current-analysis binding.

The unresolved problem remains strategy edge.

Accepted Phase11 support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Phase24 tested 28 bounded challenger variants and produced zero replacements.

Phase25 reconstructed the actual production path and found every non-empty incumbent negative at 10 bps and worse versus its broad comparator. No strategy survived its preregistered robustness framework. Phase11 support remained unchanged.

## Phase25 prerequisite recovery for Phase26

Before Phase26 could run, missing local Phase25 derived prerequisites had to be restored from authoritative source lineage rather than fabricated.

Final recovery evidence through 2026-08-11:

- PIT reference sessions: **1,252**;
- reused: **1,251**;
- authoritative Massive reacquisition: **1 session (2021-08-16)**;
- routed-universe semantic drift: **0**;
- exclusion-ledger diagnostic drift: **1** (non-routing diagnostic only);
- Gate6: **PASS**, 23,019 directional rows;
- Gate6 independent validation: **PASS**;
- Gate7: **PASS**, 15,153 route-eligible rows / 184,152 route decisions;
- Gate7 independent validation: **PASS**;
- broker/order/PAPER/LIVE authority: **0**.

The recovery implementation was simplified during this work: the redundant reference-rebind wrapper and duplicate validator path were removed. Historical recovery remains bounded provenance/rehydration functionality and is not runtime trading authority.

Current-data catch-up remains intentionally deferred until it is useful for a later testing/production transition.

## Phase26 frozen research design

Frozen policy fingerprint:

`24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2`

Phase26 tested 24 materially different candidates across six families: cross-sectional relative strength, volatility/liquidity mean reversion, volatility-normalized breakout, multi-timeframe state transition, gap behavior, and independent feature-block composites.

The research used exact accepted Phase25 production-path identities/context, PIT-safe observation joins, t+3 outcomes, chronological selection/internal partitions with exact purge sessions, block-bootstrap session dependence, 10 bps primary / 25 bps stress costs, global Holm-Bonferroni multiplicity control across all 24 candidates, year/regime/concentration robustness, and finalist-only protected evidence.

Candidate definitions, thresholds, chronology, economics, bootstrap, multiplicity, and protected boundaries were frozen before target performance inspection.

## Phase26 target result

Exact valid target-tested research head:

`8c9153c966ada116199fc45867bf5734efafeee4`

Result:

- development usable observations: **21,483**;
- protected predictor observations: **1,096**;
- selection survivors: **0**;
- internal-validation finalists: **0**;
- protected-confirmed supported candidates: **0**;
- protected return rows read: **0**;
- independent validation: **PASS**;
- provider/broker/order/PAPER/LIVE activity: **0 / 0 / 0 / 0 / 0**;
- cumulative target evidence: **PASS**.

**Plain-English conclusion:** Phase26 ran correctly, but none of the frozen alpha hypotheses earned support. Because no candidate survived development selection, internal/protected evidence was not used to rescue a weak candidate. The negative result is scientifically valid and must not be threshold-tuned after the fact.

Phase11 support therefore remains unchanged with zero SUPPORTED strategies.

## Phase26 implementation defects corrected before valid target evidence

Two Phase26 implementation defects were caught by target execution and fixed at their owning boundaries before the valid result:

1. Pandas/NumPy boolean scalars leaked through the observation-report JSON persistence boundary. The expressions were normalized and the artifact contract now rejects non-native booleans, with regression coverage.
2. Development research had an impossible acceptance predicate that inserted `protected_returns_read=False` into an `all(checks.values())` map. The state/predicate confusion was removed and replaced with positive invariants that prove protected reads remain zero, with regression coverage.

Neither correction changed strategy performance rules or evidence thresholds.

## End-to-end anti-workaround audit

The bounded provider-to-execution architectural audit required for Phase26 closeout is documented in `docs/phase26_end_to_end_anti_workaround_audit.md`.

Current audit conclusion: **PASS — no acceptance-blocking workaround or parallel trading authority found.**

Key machine-verifiable conclusions include:

- Phase25 recovery authority is not imported by routine discovery/operations/risk/control-plane/execution modules;
- exactly one raw broker `adapter.submit(plan)` seam remains, in `packages/execution/engine.py`;
- promotion still requires historically supported, routed, fired strategy evidence;
- Phase22 is PAPER-only and delegates to the central authority path;
- Phase23 routine analysis cannot mutate broker/order/PAPER/LIVE state and does not silently rebootstrap missing accepted baselines;
- automatic broker failover remains disabled;
- current browser control plane exposes no provider-write/LIVE execution endpoint;
- ML remains probability evidence only;
- conservative identity fallback preserves uncertainty instead of guessing continuity.

## Immediate handoff

The remaining Phase26 action is the full phase-end closeout validation over the already-produced target artifacts and the anti-workaround audit.

Run only after pulling the exact closeout head supplied in the active handoff:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase26_closeout.py
```

The closeout command does not rerun strategy search or expose new protected performance. It validates artifact contracts/hashes/relationships, the support overlay, protected-read state, zero external authority, and the architecture audit.

Given the target evidence above, the correct expected disposition is **ACCEPTED_NEGATIVE** with `phase27_entry_satisfied=False`.

After target closeout PASS and exact-head Ubuntu/Windows CI PASS: document final acceptance, merge Phase26, verify main post-merge CI, then define a separately preregistered next alpha-research phase. Do **not** enter Phase27 and do **not** tune Phase26 near-misses.

## GUI/web/deployment path remains explicit

- Phase27 — case/trade/risk web contracts + read-only prototype, but only after supported alpha exists.
- Phase28 — historical replay/stress dashboard.
- Phase29 — SHADOW/PAPER operator web beta.
- Phase30 — outcome/performance/learning/drift dashboards.
- Phase31 — complete production web application + PostgreSQL/scheduler/service/deployment/backup/recovery.
- Phase32 — deployed-stack failure/security/reconciliation hardening.
- Phase33 — controlled LIVE visibility/actions and emergency/risk controls through the production control plane.

The Python backend remains authoritative throughout. A rendered button or deployed page never creates broker, PAPER, or LIVE authority.

## Persistent non-negotiables

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; do not synthesize unavailable history; finalized facts outrank provisional state; ML/AI do not create trade authority; community ideas are hypotheses rather than assumed edge; uncertain mutation state requires reconciliation; frontend/UI controls never create or bypass authority; no automatic broker failover; PAPER does not imply LIVE; negative research is accepted rather than manipulated; and downstream phases do not advance past a missing validated-alpha requirement merely because their GUI or infrastructure could be built.
