# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-24.**

This is the fastest recovery point for a future ATLAS development session.

## 1. Source-of-truth order

When sources disagree, use:

1. accepted code/artifacts on `main` for completed work;
2. active maintenance/phase branch code and exact-head CI for in-progress work;
3. active phase specification when a numbered phase is active;
4. `docs/roadmap.md` for architecture/authority rules;
5. this file for exact current continuation;
6. `docs/phase_flow.md` for development cadence;
7. root `README.md`;
8. merged PRs and historical phase docs as provenance.

Repository: `nicholaslpollard/ATLAS`.

## 2. Exact repository state

Accepted/merged numbered work:

- **Phases 1–22 ACCEPTED / MERGED.**
- Phase18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase19 merge: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase20 merge: `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.
- Phase21 merge: `ed9e156437e3924293b90f06620ebbe9534fab15`.
- Phase22 merge: `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.
- Post-Phase19 stabilization baseline: `121503590d3c0b18fa9cc19e4c8210b04e2f8d47`.
- Post-Phase20 anti-drift baseline: `4afe8e0a5238b176edd47eb6e70359ccff6d65b1`.

Current work:

- **Unnumbered maintenance: post-Phase22 documentation closeout.**
- Branch: `maintenance/post-phase22-closeout`.
- Purpose: synchronize living docs and acceptance evidence after Phase22 implementation was merged before the target-machine zero-case preparation was recorded.
- Authority change: **NONE**.
- No Phase23 is active or accepted yet.

Live execution remains **DISABLED**. Automatic cross-broker failover remains **DISABLED**.

Read `docs/post_phase22_closeout.md` for the exact closeout evidence.

## 3. Mandatory phase flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Use coherent batches. Authority/external checkpoints override batching. Credentials, configured endpoints, provider connectivity, passing tests, registered jobs, or connected accounts never silently expand provider, broker, automation, or LIVE authority.

The Phase22 merge occurred before its living-document and target-machine closeout was recorded. This maintenance branch repairs that procedural sequencing drift without changing the accepted implementation or authority.

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
- Phase22 creates no new submit seam, scheduler authority, browser authority, or LIVE authority.

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

Phase11 strategy support remains:

- SUPPORTED: 0;
- MIXED: 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: 5.

Zero supported strategies correctly produced zero promotions for the accepted 2026-08-14 chain.

## 7. Accepted execution/control-plane foundation

### Phase15

Broker-neutral SHADOW/PAPER execution includes fresh quote, provider preflight, broker reconciliation, current-risk revalidation, protective geometry, deterministic client-order IDs/idempotency, uncertainty fail-closed, same-ticker add/flip disabled, Webull primary, Alpaca manual secondary, and LIVE disabled.

### Phase16

Loopback-first browser control plane with CSRF/same-origin, audit/idempotency, restart recovery, explicit broker-switch/cleanup planning, and no independent browser execution authority.

### Phase17

Accepted Webull sandbox and Alpaca paper read-only account/order/position reconciliation with provider writes 0.

### Phase18

Policy fingerprint `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.

Accepted Webull sandbox lifecycle:

`fresh L1 -> explicit Phase18 paper authorization -> flat/zero-open pre-reconcile -> preview -> submit once -> exact reconcile -> cancel once -> bounded read-only reconciliation -> exact CANCELLED -> zero fill -> flat/zero-open`

Do not repeat this real mutation merely to reconfirm it.

### Phase19

Accepted local read-only observability for candidate/AI/outcome/lineage/persisted-live-market diagnostics. Phase19 initializes no provider client for observability and gives the browser no execution authority.

### Phase20

Policy fingerprint `b4f9bd37c3c425e182e4a0da255e8a903d95101d119c833c38c7fd2c0cd3741a`.

Accepted deterministic local orchestration substrate: immutable stage registry/DAG, deterministic pipeline/run identity, bounded retry for retry-safe local stages, atomic manifest + append journal, fail-closed lease, restart/resume, semantic persisted-state validation, and provider-free shadow rehearsal. External mutation stages, scheduler authority, PostgreSQL runtime promotion, LIVE, and automatic failover remain outside its authority.

## 8. Phase21 accepted authority boundary

Policy:

`phase21-policy-v1-unified-paper-execution-authority-run-scoped-default-deny`

Fingerprint:

`0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`

Final exact head: `174110e3688a0b8c087555a56adafaab99905c66`.

Final CI: `32782618589`.

Phase21 guarantees:

- every **new PAPER provider submit** crosses `ExecutionEngine.submit_authorized_plan(...)`;
- exactly one raw `adapter.submit(plan)` remains under `packages/`, in `packages/execution/engine.py`;
- Webull PAPER and Alpaca PAPER require exact run-scoped authority;
- missing/false/mismatched/malformed/stale authority fails before provider submit;
- exact deterministic existing-order reuse performs no new mutation and needs no new submit authority;
- SHADOW remains unchanged;
- original Phase18 certification authorization remains a separate outer gate;
- both Phase18 submit paths cross the same centralized submit seam;
- Phase15 PAPER validates authority before live quote/provider initialization;
- browser and Phase20 cannot acquire Phase21 submit authority;
- LIVE and automatic failover remain disabled.

## 9. Phase22 accepted operator binding

Policy:

`phase22-policy-v1-operational-paper-runner-webull-primary-explicit-run-authority`

Fingerprint:

`1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`

Implementation head: `68f16256c8f9976ae5b6283dde437e93fbe70155`.

Merge: `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.

Cross-platform CI `32787337500`:

- Ubuntu: **974 passed in 13.80s**;
- Windows: **974 passed in 33.93s**;
- every validator through Phase22 PASS;
- dependency lock / secret hygiene / ATLAS Doctor / compile / browser JavaScript / feature self-test PASS;
- Phase22 validator reproduced the exact fingerprint;
- raw submit seam count: 1;
- provider calls/writes/broker writes: 0 / 0 / 0.

Phase22 operator semantics:

- `prepare|execute` only;
- Webull default/primary; Alpaca explicit manual selection;
- PAPER only;
- accepted Phase13/14 evidence through the Phase15 input resolver only;
- no arbitrary ticker, quantity, price, geometry, LIVE, or command-line confirmation input;
- exact interactive Phase21 confirmation when nonzero accepted execution cases exist;
- coordination delegates to `Phase15ExecutionRunEngine`;
- no direct broker adapter, live quote provider, order builder, or raw submit call in Phase22;
- uncertainty stops without blind retry/failover and requires deterministic reconciliation;
- Phase15 outcome artifacts remain authoritative; Phase19 reads them locally/read-only.

## 10. Phase22 target-machine evidence

Target command on 2026-08-24:

`python scripts/run_phase22_paper.py prepare --broker webull`

Result:

- fingerprint: exact accepted Phase22 fingerprint;
- accepted as-of: `2026-08-14`;
- broker: Webull;
- environment: PAPER/SANDBOX ONLY;
- accepted execution cases: **0**;
- explicit run authority required: **False**;
- disposition: `PREPARED_ZERO_PROVIDER_CALLS`.

This is accepted target-machine evidence for the currently accepted zero-case population. It confirms the routine operator resolves the accepted evidence and does not request mutation authority or initialize provider work when no execution case exists.

A real routine Webull PAPER submit is deferred until a future accepted upstream run naturally produces one or more executable cases. `execute` must not be invoked merely to manufacture target mutation evidence.

## 11. Performance baseline

Post-Phase19 accepted feature evidence remains:

- 50,000 rows / 7,454 symbols / 7 sessions;
- optimized batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x speedup;
- all 33 features exact parity, max difference 0.0.

## 12. Exact continuation point

Do not repeat accepted Phase18 mutation and do not fabricate a Phase22 execution case.

Current continuation sequence:

1. finish documentation-only `maintenance/post-phase22-closeout` synchronization;
2. run the normal Ubuntu/Windows CI on the maintenance PR;
3. if green, merge the maintenance branch and verify authoritative `main`;
4. independently audit the merged code for the smallest remaining operator/run gap toward a **current** end-to-end chain: `market/reference -> discovery/regimes/ML/strategies/research/risk/AI -> accepted Phase13/14 -> Phase22 PAPER -> reconciliation/observability/outcomes`;
5. define/lock the next numbered phase from that evidence;
6. do not assume autonomous scheduler or PostgreSQL runtime promotion is next.

Until a later explicit phase changes authority: LIVE disabled, broker switching explicit/manual, automatic failover forbidden, browser execution authority absent, autonomous scheduling out of scope, PostgreSQL runtime promotion out of scope.

## 13. Configuration/security

Tracked `.env.example` is non-secret and may contain public/default endpoints plus blank secret placeholders.

Never commit or expose API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata. Commented secrets are still secrets.

## 14. Future-session startup

Inspect `main`, branches/open PRs/latest CI. Read this file, `docs/roadmap.md`, `docs/post_phase22_closeout.md`, `docs/phase22_operational_paper_runner.md`, `docs/phase21_unified_paper_execution_authority.md`, and `docs/phase_flow.md`. Preserve explicit authority boundaries and continue from section 12 rather than reopening accepted work without new evidence.