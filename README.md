# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the rebuild/redesign path for Chart Monitor; the legacy system remains preserved while ATLAS matures.

## Start here

For a future development session, read in this order:

1. [`docs/current_status.md`](docs/current_status.md) — exact current handoff/evidence/continuation.
2. [`docs/roadmap.md`](docs/roadmap.md) — architecture, phase ledger, data/safety rules, authority transitions.
3. [`docs/phase21_unified_paper_execution_authority.md`](docs/phase21_unified_paper_execution_authority.md) — current Phase21 unified PAPER execution-authority contract/evidence.
4. [`docs/phase20_run_orchestration.md`](docs/phase20_run_orchestration.md) — accepted Phase20 orchestration contract/evidence.
5. [`docs/phase_flow.md`](docs/phase_flow.md) — mandatory phase execution/acceptance/merge rules.
6. [`docs/post_phase19_stabilization.md`](docs/post_phase19_stabilization.md) — stabilization baseline preceding Phase20.
7. [`docs/phase19_operations_observability.md`](docs/phase19_operations_observability.md) — accepted Phase19 observability evidence.
8. [`docs/phase18_operational_validation.md`](docs/phase18_operational_validation.md) — accepted real broker-certification evidence.
9. merged PRs for deeper historical evidence.

Old phase/fix READMEs are provenance only when they conflict with these living sources.

## Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Core roles:

- **Parquet** — durable analytical/history lake.
- **DuckDB** — analytical/query engine.
- **PostgreSQL** — target transactional operational state; current scaffold is not an accepted runtime prerequisite.
- **Massive** — primary broad-market/reference provider path.
- **Webull** — primary PAPER/sandbox execution broker; future LIVE only under separate authority.
- **Alpaca** — manually selectable secondary/fallback; never automatic failover.
- **ML** — point-in-time `p_down/p_neutral/p_up` evidence, never direct trade authority.
- **Strategies/router** — deterministic setup semantics and regime-aware routing.
- **Deep research** — promoted-candidate-only analogue/scenario/options/news work.
- **AI** — independent audit/reviewer only.
- **Browser** — monitoring/control plane only; it cannot create independent trading authority.
- **Phase20 orchestration** — deterministic local run control only; a registered job never creates provider, broker, scheduler, or LIVE authority.
- **Phase21 PAPER authority** — centralized default-deny authority for every new real PAPER provider submit; it does not create LIVE, browser, cleanup, failover, scheduler, or PostgreSQL authority.

## Strategic anti-drift anchor

The destination remains the full architecture above: **ATLAS must operate the evidence chain from broad-market discovery through deterministic analysis/risk and independent AI review into safe Webull-primary SHADOW/PAPER execution, exact reconciliation, observability, and outcome learning before any separately authorized LIVE transition.**

Infrastructure is a means to that operational system, not a replacement destination. Every phase boundary is audited against the roadmap and current authority contract. Lower-value infrastructure must not silently displace the agreed operational paper/shadow objective.

## Mandatory development flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Passing tests, configured credentials, available endpoints, connected accounts, or job registration do not silently change provider/LIVE authority.

## Current state — 2026-08-24

Accepted/merged:

- **Phases 1–20 ACCEPTED and merged.**
- Phase18 merge `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase19 merge `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase20 merge `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.
- Post-Phase19 stabilization baseline `121503590d3c0b18fa9cc19e4c8210b04e2f8d47`.
- Post-Phase20 anti-drift baseline `4afe8e0a5238b176edd47eb6e70359ccff6d65b1`.

Current phase:

- **Phase21 — Unified Paper Execution Authority and Operational Binding: VALIDATED / MERGE PENDING.**
- Branch `phase-21-unified-paper-execution-authority`; draft PR #22.
- Policy `phase21-policy-v1-unified-paper-execution-authority-run-scoped-default-deny`.
- Validated fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`.
- Validated implementation head `d3599f3a184142de4ac5f03b58fc355f0bb11001`.
- CI `32781962354`: Ubuntu **964 passed in 15.42s**, Windows **964 passed in 24.52s**, every validator through Phase21 PASS.
- Phase21 validation: exactly one raw `adapter.submit(plan)` seam, in `packages/execution/engine.py`; provider calls/writes/broker writes 0/0/0.
- Final documentation-head CI remains before acceptance/merge.
- LIVE execution **DISABLED**.
- Automatic cross-broker failover **DISABLED**.

## Accepted data/model foundation

Historical provider boundary:

- Alpaca raw SIP daily controlled authority: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- No synthetic pre-2021 1h/4h history from daily bars.

Accepted cumulative lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Accepted production ML:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- protected holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact replay.

Phase11 strategy support: SUPPORTED 0; MIXED 3 (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`); UNSUPPORTED 5. Zero supported strategies correctly yielded zero promotions.

## Accepted execution/control-plane foundation

### Phase15

Broker-neutral SHADOW/PAPER execution is bound to accepted Phase14/13 lineage and includes fresh quote, preflight, reconciliation, current risk, protective geometry, deterministic client IDs/idempotency, uncertainty fail-closed, Webull primary, Alpaca manual secondary, and LIVE disabled.

### Phase16

Loopback-first browser/control plane with CSRF/same-origin, audit/idempotency, restart recovery, explicit broker-switch/cleanup planning. Browser actions do not bypass execution authority.

### Phase17

Accepted Webull sandbox + Alpaca paper read-only account/order/position reconciliation with provider writes 0.

### Phase18

Accepted Webull sandbox mutation lifecycle:

`fresh L1 -> explicit Phase18 paper authorization -> flat/zero-open pre-reconcile -> preview -> submit once -> exact reconcile -> cancel once -> bounded read-only reconciliation -> exact CANCELLED -> zero fill -> flat/zero-open`

Immediate post-cancel uncertainty was handled fail-closed; later independent order-detail/history reads proved `CANCELLED`. Adapter hardening permits at most one cancel before read-only reconciliation. Normal sustained Webull reads target 80% of the most specific documented endpoint limit.

### Phase19

Accepted read-only local operator observability for candidate/AI/outcome/lineage/persisted-live-market artifacts, with no Phase19 provider writes or browser execution authority.

### Phase20

Accepted provider-free deterministic orchestration: immutable stage definitions/DAG, deterministic pipeline/run identity, bounded retry for retry-safe local work, atomic manifest/journal persistence, fail-closed leases/resume, semantic state validation, and provider-free shadow rehearsal. External mutation stages, autonomous scheduling, PostgreSQL runtime promotion, LIVE, and automatic failover remain outside its authority.

### Phase21

Phase21 fixes a real authority gap without rebuilding execution:

- every **new real PAPER provider submit** crosses `ExecutionEngine.submit_authorized_plan(...)`;
- exactly one raw `adapter.submit(plan)` remains under `packages/`;
- Webull PAPER + Alpaca PAPER require exact broker/PAPER/deterministic-scope authorization;
- missing/false/mismatched authority fails before submit;
- exact existing deterministic order reuse performs no new mutation and requires no new authority;
- SHADOW unchanged;
- original Phase18 explicit certification authorization remains separate and required first;
- both Phase18 submission paths cross the centralized Phase21 seam using narrow intent/plan-bound compatibility scopes;
- Phase15 validates PAPER authority before live quote resolver initialization;
- non-PAPER Phase15 source-lineage shape is preserved;
- browser cannot acquire Phase21 execution authority;
- LIVE and automatic broker failover remain disabled.

The first Phase21 CI exposed a real direct-submit bypass in Phase18 operational validation. The validator was not weakened; the bypass was centralized and the validator now enforces exactly one raw submit seam.

## Non-negotiable rules

- Preserve exact provider-native ticker case/text.
- Never infer identity continuity from ticker text alone.
- Historical populations remain point-in-time.
- Quarantine ambiguity; do not guess.
- No fabricated unavailable intraday history.
- Finalized canonical facts outrank provisional live observations.
- ML is evidence, not trade authority.
- AI is independent audit only.
- LONG `stop < entry < target`; SHORT reverse.
- Unknown broker/provider/run state fails closed.
- Uncertain writes require reconciliation before any next mutation.
- Automatic broker failover forbidden.
- PAPER does not imply LIVE.
- Phase20 does not authorize scheduler/PostgreSQL/provider mutations.
- Phase21 does not authorize browser execution, cleanup/flatten, broker switching, scheduler/PostgreSQL, automatic failover, or LIVE.

## Environment/security

Tracked `.env.example` is non-secret. Public/default endpoints may be populated; secret placeholders remain blank.

Never commit or print API secrets, passwords, security codes, raw broker IDs, tokens, or signed request metadata. Commented secrets are still secrets. Real `.env` remains local/ignored.

## Exact continuation point

Do **not** repeat accepted Phase18 mutation merely to reconfirm it and do not reopen accepted Phase19/20 work without new evidence.

Continue Phase21:

1. synchronize the Phase21 spec/living docs/PR evidence from validated head `d3599f3a184142de4ac5f03b58fc355f0bb11001` and CI `32781962354`;
2. run exact documentation-head Ubuntu/Windows CI;
3. if green, mark Phase21 ACCEPTED in living docs, run final exact-head CI, mark PR #22 ready, and merge;
4. verify authoritative `main`;
5. audit the merged code for the smallest remaining operator/run binding to routine **ATLAS -> accepted analysis/risk/AI -> Webull PAPER -> exact reconciliation -> observability/outcome learning**;
6. define/lock the next numbered phase from that evidence rather than assuming scheduler/PostgreSQL infrastructure is next.
