# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-24.**

This is the fastest recovery point for a future ATLAS development session.

## 1. Source-of-truth order

When sources disagree, use:

1. accepted code/artifacts on `main` for completed work;
2. active phase/maintenance branch code and exact-head CI for in-progress work;
3. active phase specification;
4. `docs/roadmap.md`;
5. this file;
6. `docs/phase_flow.md`;
7. root `README.md`;
8. merged PRs/historical docs as provenance.

Repository: `nicholaslpollard/ATLAS`.

## 2. Exact repository state

- **Phases 1–23 ACCEPTED / MERGED.**
- Phase18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase19 merge: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase20 merge: `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.
- Phase21 merge: `ed9e156437e3924293b90f06620ebbe9534fab15`.
- Phase22 merge: `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0` through PR #25.
- Post-Phase23 synchronized `main`: `8fa832decc2f1be7762373f8ba4cc05a38b8404a`.

### Phase24 current state

- Branch: `phase-24-strategy-evidence-challenger`.
- PR: **#26 — Phase 24: strategy evidence challenger — no support replacement**.
- State: **ACCEPTANCE EVIDENCE COMPLETE / NO SUPPORT REPLACEMENT / MERGE PENDING**.
- Gate0 code head: `b2be471c983c1f4be3e23b83d06a561820b83145`.
- Gate1 preregistration head: `7a4f5d599e39af65612a9e7e4609c959c97daf64`.
- Gate1 policy fingerprint: `9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`.
- Gate2 implementation/target head: `f591942413973107d7abc9d21325623e2e7000f1`.
- Phase24 evidence-closeout head before living-doc sync: `ba0721dd717ae8bdda877a376549cdef69ca00d9`.
- Closeout CI run `32806363124`: Ubuntu/Windows SUCCESS; every validator through Phase24 Gate2 and full regression passed.

LIVE execution is **DISABLED**. Automatic cross-broker failover is **DISABLED**.

## 3. Mandatory phase flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Use coherent batches. Credentials, endpoints, passing tests, connected accounts, registered jobs, or local artifacts never silently expand provider, broker, support, automation, or LIVE authority.

## 4. Architecture and anti-drift anchor

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/Monte Carlo/scenarios -> news/events -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Roles:

- Parquet: durable analytical/history lake.
- DuckDB: analytical engine.
- PostgreSQL: target operational state; not an accepted runtime prerequisite.
- Massive: primary broad-market/reference provider.
- Webull: primary PAPER/sandbox broker; future LIVE only under separate authority.
- Alpaca: manual secondary/fallback only; never automatic failover.

The destination remains the complete operational chain, especially accepted current evidence into safe Webull-primary SHADOW/PAPER execution, reconciliation, observability, and outcome learning before any LIVE transition.

## 5. Non-negotiable rules

- Preserve provider-native ticker text/case; ticker text never proves identity continuity.
- Historical populations remain PIT/observation-driven; current survivors are not projected backward.
- Ambiguity is quarantined/excluded, never guessed.
- No synthetic pre-2021 intraday history from daily data.
- Finalized canonical facts outrank provisional live observations.
- ML emits probability evidence; it does not create trade authority.
- AI is independent audit only.
- LONG: `stop < entry < target`; SHORT: `stop > entry > target`.
- Unknown provider/broker/run state fails closed.
- Uncertain writes are never retried blindly; reconcile first.
- Automatic cross-broker failover is forbidden.
- PAPER/sandbox authority does not imply LIVE.
- Zero-promotion, zero-execution-case, and zero-finalist states are valid.
- Never weaken data/strategy/risk/authority thresholds to force activity.
- Phase20 cannot create provider/broker/scheduler authority.
- Phase21 central PAPER authority cannot be created by the browser/control plane.
- Phase22 is the routine PAPER operator and creates no new raw submit seam.
- Phase23 performs no broker/PAPER execution.
- Phase24 research performs no provider/broker/order/PAPER/LIVE/support mutation.

## 6. Accepted data/model evidence

Historical boundary:

- Alpaca raw SIP daily controlled authority: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- Ticker/intraday regime history origin: **2021-08-16**.
- No synthetic pre-2021 1h/4h history.

Accepted cumulative lineage:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Accepted production ML:

- model `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 PIT predictors;
- holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

Phase11 support remains the accepted production authority:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

## 7. Accepted execution/control-plane foundation

### Phase15

Broker-neutral SHADOW/PAPER execution: fresh quote, provider preflight, broker reconciliation, current-risk revalidation, protective geometry, deterministic client-order IDs/idempotency, uncertainty fail-closed, same-ticker add/flip disabled, Webull primary, Alpaca manual secondary, LIVE disabled. Post-2026-08-14 input requires an exact Phase23 handoff.

### Phase16–19

Accepted loopback browser control plane, audit/idempotency/recovery, explicit broker-switch/cleanup planning, Webull sandbox + Alpaca paper read-only reconciliation, real Phase18 Webull sandbox submit/reconcile/cancel certification, and local read-only observability. Do not repeat the accepted Phase18 mutation merely to reconfirm it.

### Phase20

Accepted deterministic local orchestration substrate: immutable DAG, deterministic run identity, bounded local retry, atomic manifest/journal, fail-closed lease and resume. No provider mutation, scheduler authority, PostgreSQL runtime promotion, LIVE, or automatic failover.

### Phase21

Policy fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`. Every new PAPER provider submit crosses `ExecutionEngine.submit_authorized_plan(...)`. Exactly one raw `adapter.submit(plan)` remains under `packages/`, in `packages/execution/engine.py`.

### Phase22

Policy fingerprint `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`. Routine PAPER operator: `scripts/run_phase22_paper.py prepare|execute`; Webull default; Alpaca manual; no arbitrary trade inputs; exact run-scoped authority only for nonzero accepted execution cases. Accepted zero-case prepare returned `PREPARED_ZERO_PROVIDER_CALLS`.

### Phase23

Policy fingerprint `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`. `scripts/run_phase23_analysis.py prepare|execute` advances an explicit prior finalized session from the latest accepted baseline. Only `MASSIVE_MARKET_REFERENCE_READS` may be authorized if finalized market/reference evidence is missing. No broker reads/writes, provider mutations, Phase21 submit, Phase22 execute, scheduler/PostgreSQL/browser/LIVE authority.

## 8. Phase23 accepted target evidence

Finalized `2026-08-21`, baseline `2026-08-14`:

- sessions advanced: **5**;
- current WARM/HOT directional cases: **23**;
- promoted: **0**;
- Phase12/13/14 cases: **0 / 0 / 0**;
- Phase22-ready execution cases: **0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- independent validation: **PASS**;
- run scope: `a9f398fcd32e302af125bcf9d81789efadb417da879ff178942880580ab69209`.

The first attempt exposed a real nullable persisted-state `NaN` defect; repair head `803d43e43e8931f03ba836a23b781a7c3d3ee687` fixed only persistence/recovery semantics without threshold/support/model/risk/authority changes.

## 9. Phase24 evidence and decision

Read `docs/phase24_strategy_evidence_challenger.md` for complete details.

### Gate0

Accepted target diagnostic:

- WARM/HOT directional cases: **23**;
- authoritative promotions: **0**;
- eligible incumbent route evaluations: **92**;
- counterfactual rule fires: **48**;
- candidates with at least one fire: **21 / 23**;
- all provider/broker/order/PAPER/LIVE/support writes: **0**;
- PASS.

This proved current rules are not dormant.

### Gate1

Before challenger results were read, Gate1 preregistered exactly 28 bounded variants and stronger evidence criteria: development-only chronological selection/internal validation, purge, session-level dependence handling, block bootstrap, 10/25 bps costs, distribution/uncertainty/year/regime gates, multiplicity control, and zero protected-read/support-replacement authority.

### Gate2

Target-machine result on exact head `f591942413973107d7abc9d21325623e2e7000f1`:

- challengers: **28**;
- basic-pass: **0**;
- multiplicity-pass: **0**;
- frozen selections: **0**;
- fresh finalists: **0**;
- protected reads: **0**;
- all external/execution/support writes: **0**;
- independent validation: **PASS**;
- overall: **PASS**.

Post-run forensic evidence:

- positive chronological folds failed **28/28**;
- positive bootstrap LCB failed **28/28**;
- positive 25 bps stress mean failed **28/28**;
- year robustness failed **24/28**;
- primary mean/median/positive-rate and regime robustness failed **20/28** each;
- sample minimums failed only a small minority.

The strongest long trend variant had 1,188 signal sessions, +0.000737 mean after 10 bps, but LCB -0.000452 and 25 bps stress mean -0.000763. Short trend/momentum/breakdown families remained materially negative at the primary cost.

### Phase24 disposition

**NO SUPPORT REPLACEMENT.**

- Do not relax Gate1 thresholds after observing failures.
- Do not open the protected interval for zero finalists.
- Do not promote any v2 challenger.
- Do not change Phase11 support.
- Do not assume symmetric mirrored short rules are valid.
- Do not continue blind threshold tightening of the same daily rule families.

## 10. Methodological finding and exact continuation

The post-evidence audit found a population-fidelity mismatch:

- historical Phase11/24 support studies evaluate rules across broad historical daily rows with a broad market-regime direction route;
- production promotion first requires WARM/HOT discovery qualification, non-neutral discovery direction, then strategy routing using market/sector/ticker context before a supported rule can fire.

Current sector context is intentionally unavailable/nonblocking because no authoritative ticker-to-sector mapping is accepted. Market and ticker routing still matter. Historical support is therefore not yet estimated on the same population production tries to trade.

### Next numbered phase

After Phase24 merges, DEFINE and LOCK **Phase25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence**.

Initial Phase25 objective:

1. no provider/broker/execution/support authority;
2. preflight legitimate local historical inputs beginning no earlier than **2021-08-16**;
3. reconstruct the production candidate path point-in-time: universe -> discovery foundation -> multi-timeframe scoring -> state hysteresis -> WARM/HOT direction -> market/ticker routing;
4. preserve sector `UNAVAILABLE` semantics unless authoritative historical sector mapping exists;
5. hold incumbent strategy rules and three-session outcome fixed initially;
6. compare broad-population vs production-path-conditioned strategy evidence with exact attribution;
7. independently validate the reconstructed population before considering any support replacement or new strategy family.

If route-fidelity conditioning still has no robust edge, the next challenger generation should move to materially different signal architectures such as relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, or composite strategies.

Do not assume scheduler/PostgreSQL or GUI work is next merely because those remain future goals. GUI may consume stable artifacts when scheduled but remains a monitoring/control surface.

## 11. Performance baseline

Retained post-Phase19 feature evidence:

- 50,000 rows / 7,454 symbols / 7 sessions;
- optimized batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x speedup;
- all 33 features exact parity.

## 12. Security/recovery

Tracked `.env.example` is non-secret. Never commit API secrets, passwords, security codes, raw broker IDs, tokens, or signed request metadata.

Future startup: inspect `main`, PRs/branches/latest CI; read this file, roadmap, Phase24 doc, Phase23 doc, Phase22/21 authority docs, and phase flow. Continue from section 10 rather than reopening accepted mutations or weakening evidence gates.
