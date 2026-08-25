# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-24.**

This is the fastest recovery point for a future ATLAS development session.

## 1. Source-of-truth order

When sources disagree, use:

1. accepted code/artifacts on `main` for completed work;
2. active phase/maintenance branch code and exact-head CI for in-progress work;
3. active phase specification;
4. `docs/roadmap.md` for architecture/authority rules;
5. this file for exact continuation;
6. `docs/phase_flow.md` for development cadence;
7. root `README.md`;
8. merged PRs and historical phase docs as provenance.

Repository: `nicholaslpollard/ATLAS`.

## 2. Exact repository state

- **Phases 1–23 ACCEPTED / MERGED.**
- Phase18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase19 merge: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase20 merge: `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.
- Phase21 merge: `ed9e156437e3924293b90f06620ebbe9534fab15`.
- Phase22 merge: `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.
- Post-Phase22 synchronized baseline: `dd0d6838d76a15edde0783f471ad7e212453cd94`.
- **Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.**
- Phase23 PR: **#25**, merged.
- Phase23 policy fingerprint: `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`.
- Phase23 implementation/repair head: `803d43e43e8931f03ba836a23b781a7c3d3ee687`.
- Phase23 final documentation head before merge: `99425a0fa04d2a4faf0b4477343d11434cebd885`.
- State: **PHASE23 ACCEPTED / MERGED; NEXT PHASE NOT YET LOCKED.**

LIVE execution remains **DISABLED**. Automatic cross-broker failover remains **DISABLED**.

Read `docs/phase23_operational_current_analysis_cycle.md` for the accepted Phase23 contract and evidence.

## 3. Mandatory phase flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Use coherent batches. Authority/external checkpoints override batching. Credentials, endpoints, provider connectivity, passing tests, registered jobs, connected accounts, or locally present files never silently expand provider, broker, automation, or LIVE authority.

## 4. Architecture and anti-drift anchor

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/Monte Carlo/scenarios -> news/events -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Roles:

- Parquet: durable analytical/history lake.
- DuckDB: analytical engine.
- PostgreSQL: target operational state; not an accepted runtime prerequisite.
- Massive: primary broad-market/reference provider.
- Webull: primary PAPER/sandbox execution broker; future LIVE only under separate authority.
- Alpaca: manually selectable secondary/fallback; never automatic failover.

The destination remains the complete operational chain, especially accepted current evidence into **Webull-primary SHADOW/PAPER execution, exact reconciliation, observability, and outcome learning** before any future LIVE transition. Infrastructure is subordinate to that objective.

## 5. Non-negotiable rules

- Preserve exact provider-native ticker text/case.
- Ticker text never proves identity continuity.
- Historical populations remain point-in-time/observation-driven.
- Ambiguity is quarantined/excluded, never guessed.
- No synthetic pre-2021 intraday history from daily data.
- Finalized canonical facts outrank provisional live observations.
- ML emits probability evidence; it does not create trade authority.
- AI is independent audit only and cannot create execution authority.
- LONG: `stop < entry < target`; SHORT: `stop > entry > target`.
- Unknown broker/provider/run state fails closed.
- Uncertain writes are never retried blindly.
- Automatic cross-broker failover is forbidden.
- PAPER/sandbox authority does not imply LIVE authority.
- Zero-promotion and zero-execution-case states are valid; thresholds/cases are never weakened or fabricated to force activity.
- Phase20 job registration cannot create provider/broker/scheduler authority.
- Phase21 central PAPER authority cannot be created by the browser/control plane.
- Phase22 is the routine PAPER operator and creates no new raw submit seam.
- Phase23 performs no broker reads/writes and cannot invoke Phase22 execution.
- A partial/failed Phase23 run cannot become the next accepted baseline merely because it wrote newer local artifacts.

## 6. Accepted data/model evidence

Historical boundary:

- Alpaca raw SIP daily controlled authority: 2016-01-04 through 2021-08-13.
- Massive authority: 2021-08-16 onward.
- No synthetic pre-2021 1h/4h history.

Accepted cumulative lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Accepted production ML:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

Phase11 strategy support remains frozen:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Only SUPPORTED strategies may promote. The zero-SUPPORTED result is an evidence gate, not a tuning inconvenience.

## 7. Accepted execution/control-plane foundation

### Phase15

Broker-neutral SHADOW/PAPER execution includes fresh quote, provider preflight, broker reconciliation, current-risk revalidation, protective geometry, deterministic client-order IDs/idempotency, uncertainty fail-closed, same-ticker add/flip disabled, Webull primary, Alpaca manual secondary, and LIVE disabled.

For dates after the frozen cumulative endpoint `2026-08-14`, Phase15 requires the exact Phase23 current-analysis handoff rather than pretending the cumulative audit extends into the future.

### Phase16–19

Accepted loopback browser control plane, restart/audit/idempotency safeguards, explicit broker-switch/cleanup planning, Webull sandbox + Alpaca paper read-only reconciliation, the real Phase18 Webull sandbox submit/reconcile/cancel certification lifecycle, and local read-only observability. Do not repeat the accepted Phase18 mutation merely to reconfirm it.

### Phase20

Accepted deterministic local orchestration substrate: immutable stage registry/DAG, deterministic pipeline/run identity, bounded retry for retry-safe local stages, atomic manifest + append journal, fail-closed lease, restart/resume, semantic persisted-state validation, and provider-free shadow rehearsal. External mutation stages, scheduler authority, PostgreSQL runtime promotion, LIVE, and automatic failover remain outside its authority.

### Phase21

Policy fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`.

Every new real PAPER provider submit crosses `ExecutionEngine.submit_authorized_plan(...)`. Exactly one raw `adapter.submit(plan)` remains under `packages/`, in `packages/execution/engine.py`. Webull/Alpaca PAPER require exact run-scoped authority; SHADOW and deterministic existing-order reuse do not create a new submit.

### Phase22

Policy fingerprint `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`.

Routine PAPER operator: `scripts/run_phase22_paper.py prepare|execute`; Webull default/primary; Alpaca explicit manual selection; PAPER only; accepted Phase13/14 evidence through Phase15 input resolution; no arbitrary ticker/quantity/price/geometry/LIVE input; exact interactive Phase21 confirmation only for nonzero accepted execution cases; provider uncertainty stops without blind retry/failover.

Accepted target-machine Phase22 prepare on the 2026-08-14 lineage found 0 execution cases and returned `PREPARED_ZERO_PROVIDER_CALLS`. Do not run Phase22 `execute` merely to manufacture activity.

## 8. Phase23 accepted evidence

Purpose: advance an explicit finalized session through existing accepted analytical primitives without widening Phase20 provider authority and without crossing into broker/PAPER execution.

Operator:

- `python scripts/run_phase23_analysis.py prepare --as-of YYYY-MM-DD [--broker webull|alpaca]` — provider-free;
- `python scripts/run_phase23_analysis.py execute --as-of YYYY-MM-DD [--broker webull|alpaca]` — exact interactive read authorization only when finalized Massive market/reference evidence is missing.

Reachable external read class: `MASSIVE_MARKET_REFERENCE_READS` only.

Forbidden/unreachable in Phase23 v2: broker account/order/position reads; broker/order mutations; Massive promoted research/news/options reads; Phase14 AI provider calls; Phase21 submit authority; Phase22 execution; LIVE; automatic failover; scheduler/PostgreSQL/browser execution authority.

### Target recovery and repair

Initial provider-free prepare for finalized `2026-08-21` from accepted baseline `2026-08-14` found five sessions to advance and missing Massive/reference evidence. Exact run-scoped market/reference read authority was supplied once.

The first execution stopped fail-closed on a real local serialization defect: nullable `previous_effective_state` was represented by Parquet/Pandas as float `NaN`, which Pydantic rejected as an invalid enum.

Repair head `803d43e43e8931f03ba836a23b781a7c3d3ee687`:

- normalizes null-like persisted values only for that nullable field;
- preserves discovery thresholds/hysteresis/bootstrap semantics;
- keeps the accepted baseline anchored to a valid handoff rather than the newest partial file;
- verifies exact market-session completion/zero entitlement skips;
- verifies exact feature checkpoint/source-lineage completion;
- adds regression tests for the observed failure/recovery paths.

### CI and target result

Repair-head CI:

- push run `32802151860`: Ubuntu SUCCESS, Windows SUCCESS;
- PR run `32802154831`: Ubuntu SUCCESS, Windows SUCCESS;
- 988 tests on each OS; every validator through Phase23 PASS.

Final documentation-head CI run `32803119880`:

- Ubuntu: **988 passed**;
- Windows: **988 passed in 33.87s**;
- every validator through Phase23 PASS.

Successful target run for finalized 2026-08-21:

- status: **COMPLETE**;
- sessions advanced: **5**;
- WARM/HOT directional cases considered: **23**;
- promoted candidates: **0**;
- Phase12 research cases: **0**;
- Phase13 case files: **0**;
- Phase14 AI reviews: **0**;
- Phase22-ready execution cases: **0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- independent validation: **PASS**;
- overall: **PASS**.

Run scope: `a9f398fcd32e302af125bcf9d81789efadb417da879ff178942880580ab69209`.

Persisted target evidence:

- `data/derived/operations/phase23/v1/runs/year=2026/date=2026-08-21/broker=webull/manifest.json`;
- `data/derived/operations/phase23/v1/runs/year=2026/date=2026-08-21/broker=webull/independent_validation.json`.

The 23 current directional cases are useful current evidence. Zero promotion is correct because the frozen historical-support gate contains zero SUPPORTED strategies.

Phase23 was accepted and merged through PR #25 at `2004338624766c42b5f4db2bb0976b2047a5c6b0`.

## 9. Performance baseline

Retained post-Phase19 feature evidence:

- 50,000 rows / 7,454 symbols / 7 sessions;
- optimized batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x speedup;
- all 33 features exact parity, max difference 0.0.

## 10. Exact continuation point

Do not repeat accepted Phase18 mutation, do not fabricate a Phase22 execution case, and do not weaken Phase11 support merely because the Phase23 current run produced zero promotions.

The next numbered phase is **not yet locked**. First perform a merged-code/current-artifact audit from authoritative `main`, centered on the 2026-08-21 discovery/regime/ML/current-strategy evidence and exact rejection reasons.

The principal analytical bottleneck currently exposed is the frozen **0-SUPPORTED strategy set**. Unless that audit reveals a higher-priority correctness issue, the likely next substantive phase is an evidence-driven strategy challenger/support-replacement process using historical/current out-of-sample evidence. It must not simply relax thresholds to create trades.

GUI development can consume the stable Phase23 current-artifact contracts when scheduled, using the approved ATLAS browser design direction, but browser work remains a control/observability surface and cannot replace strategy evidence or create execution authority.

Do not assume autonomous scheduling or PostgreSQL runtime promotion is next merely because those remain future infrastructure goals.

## 11. Configuration/security

Tracked `.env.example` is non-secret and may contain public/default endpoints plus blank secret placeholders.

Never commit or expose API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata. Commented secrets are still secrets.

## 12. Future-session startup

Inspect `main`, open PRs/branches/latest CI. Read this file, `docs/roadmap.md`, `docs/phase23_operational_current_analysis_cycle.md`, `docs/phase22_operational_paper_runner.md`, `docs/phase21_unified_paper_execution_authority.md`, and `docs/phase_flow.md`.

Preserve explicit authority boundaries. Continue from section 10 rather than reopening accepted provider mutations or weakening evidence gates without new evidence.