# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-24.**

This is the fastest recovery point for a future ATLAS development session.

## 1. Source-of-truth order

When sources disagree, use:

1. accepted code/artifacts on `main` for completed work;
2. active PR branch code and exact-head CI for in-progress work;
3. active phase specification;
4. `docs/roadmap.md` for architecture/authority rules;
5. this file for exact current continuation;
6. `docs/phase_flow.md` for development cadence;
7. root `README.md`;
8. merged PRs and historical phase docs as provenance.

## 2. Accepted baseline and current phase

Repository: `nicholaslpollard/ATLAS`

Accepted/merged baseline:

- **Phases 1–20 accepted/merged.**
- Phase 18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase 19 merge: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase 20 merge: `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.
- Post-Phase19 stabilization baseline: `121503590d3c0b18fa9cc19e4c8210b04e2f8d47`.
- Post-Phase20 anti-drift `main` baseline used to define Phase 21: `4afe8e0a5238b176edd47eb6e70359ccff6d65b1`.

Current numbered work:

- **Phase 21 — Unified Paper Execution Authority and Operational Binding: VALIDATED / MERGE PENDING.**
- Branch: `phase-21-unified-paper-execution-authority`.
- Draft PR: **#22 — Phase 21: Unified paper execution authority**.
- Validated implementation head: `d3599f3a184142de4ac5f03b58fc355f0bb11001`.
- Policy: `phase21-policy-v1-unified-paper-execution-authority-run-scoped-default-deny`.
- Policy fingerprint: `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`.
- Authority contract: `phase21-paper-execution-authority-v1-broker-paper-run-scoped`.
- Implementation CI `32781962354`: Ubuntu **964 passed in 15.42s**; Windows **964 passed in 24.52s**; every validator through Phase 21 PASS.
- Phase 21 validator proves exactly one raw `adapter.submit` seam under `packages/`, in `packages/execution/engine.py`.
- Phase 21 implementation validation performed provider calls/writes/broker writes **0 / 0 / 0**.
- Final documentation-head CI is still required before acceptance/merge.

Live execution remains **DISABLED**. Automatic cross-broker failover remains **DISABLED**.

Read `docs/phase21_unified_paper_execution_authority.md` for the complete current phase contract/evidence.

## 3. Mandatory phase flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Use coherent batches. Authority/external checkpoints override batching. Credentials, configured endpoints, prior provider success, registered jobs, or available adapters never silently expand authority.

## 4. Architecture snapshot and anti-drift anchor

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/Monte Carlo/scenarios -> news/events -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Roles:

- Parquet: durable analytical/history lake.
- DuckDB: analytical engine.
- PostgreSQL: target operational state; current scaffold is not an accepted runtime prerequisite.
- Massive: primary broad-market/reference provider.
- Webull: primary paper/sandbox execution broker and future live broker only under separate authority.
- Alpaca: manually selectable secondary/fallback; never automatic failover.

The destination remains the complete ATLAS chain, especially accepted deterministic evidence into **Webull-primary shadow/PAPER execution, exact reconciliation, observability, and outcome learning** before any future live transition. Infrastructure is a means to that objective, not a substitute for it.

## 5. Non-negotiable rules

- Preserve exact provider-native ticker text/case.
- Ticker text never proves identity continuity.
- Historical populations remain point-in-time.
- Ambiguity is quarantined/excluded, never guessed.
- No synthetic pre-2021 intraday from daily data.
- Finalized canonical facts outrank provisional live observations.
- ML emits probability evidence; accepted production model cannot silently change.
- AI is independent audit only and cannot create execution authority.
- LONG: `stop < entry < target`; SHORT: `stop > entry > target`.
- Unknown broker/provider/run state fails closed.
- Uncertain writes are never retried blindly.
- Automatic cross-broker failover is forbidden.
- PAPER/sandbox authority does not imply LIVE authority.
- Phase 20 job registration cannot create provider/broker/scheduler authority.
- Phase 21 PAPER authority cannot be created by the browser/control plane.

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
- exact replay.

Phase 11 strategy support: SUPPORTED 0; MIXED 3 (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`); UNSUPPORTED 5. Zero supported strategies correctly produced zero promotions.

## 7. Accepted execution/control-plane foundation

### Phase 15

Broker-neutral SHADOW/PAPER execution already includes fresh quote, provider preflight, broker reconciliation, current risk revalidation, protective geometry, deterministic client-order IDs/idempotency, uncertainty fail-closed, same-ticker add/flip disabled, Webull primary, Alpaca manual secondary, and LIVE disabled.

### Phase 16

Loopback-first browser/control plane with CSRF/same-origin, audit/idempotency, restart recovery, explicit broker switch/cleanup planning, and no independent browser execution authority.

### Phase 17

Accepted Webull sandbox and Alpaca paper read-only account/order/position reconciliation with provider writes 0.

### Phase 18

Policy fingerprint `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.

Accepted Webull sandbox lifecycle:

`fresh L1 -> explicit Phase18 paper authorization -> flat/zero-open pre-reconcile -> preview -> submit once -> exact reconcile -> cancel once -> bounded read-only reconciliation -> exact CANCELLED -> zero fill -> flat/zero-open`

Immediate post-cancel uncertainty was handled fail-closed with no second cancel, retry, flatten, or failover. Normal sustained Webull reads target 80% of the most specific current documented endpoint limit.

### Phase 19

Accepted local read-only observability: candidate/AI/outcome/lineage/persisted-live-market diagnostics, GET-only observability endpoint, optional local refresh, no Phase19 provider reads/writes, no browser execution authority.

### Phase 20

Policy fingerprint `b4f9bd37c3c425e182e4a0da255e8a903d95101d119c833c38c7fd2c0cd3741a`.

Accepted local deterministic run substrate: immutable stage registry/DAG, deterministic pipeline/run identity, bounded retry for retry-safe local stages, atomic manifest + append journal, fail-closed lease, restart/resume, semantic persisted-state validation, provider-free plan/shadow runner. External mutation-stage registration is blocked; no scheduler daemon/PostgreSQL runtime/live/failover authority.

## 8. Phase 21 exact semantics

Phase 21 fixes a real authority gap discovered by audit: older routine Phase 15 PAPER submission and specialized Phase 18 operational validation did not share one mandatory new-submit authority seam.

Locked behavior:

- every **new PAPER provider submit** must cross `ExecutionEngine.submit_authorized_plan(...)`;
- exactly one raw `adapter.submit(plan)` remains under `packages/`;
- Webull PAPER and Alpaca PAPER require exact run-scoped authority;
- missing/false/mismatched/malformed authority fails before provider submit;
- an exact existing deterministic order may be reused without new mutation authority because no new submit occurs;
- SHADOW behavior is unchanged;
- LIVE stays disabled;
- browser execution stays forbidden;
- Phase20 external mutation stages stay forbidden;
- no automatic broker failover.

Deterministic authority scopes:

- Phase15 operational PAPER scope binds date + accepted Phase15 input fingerprint + Phase15 policy fingerprint + broker/PAPER.
- Phase18 standard certification scope binds the exact execution intent and accepted lineage.
- Phase18 operational-validation scope binds the exact one-share certification order plan, deterministic IDs, ticker, broker/PAPER, and stable plan fingerprint.

Both Phase18 paths retain the original Phase18 explicit mutation authorization as the outer gate. Phase21 compatibility authority is created only after that gate passes and does not broaden Phase18 authority.

Phase15 validates PAPER authority before live quote resolver initialization. The Phase21 scope is included in the Phase15 source fingerprint only for PAPER, preserving historical SHADOW/no-case source-lineage shape.

## 9. Phase 21 defect found and fixed

First Phase21 CI correctly failed because `packages/execution/phase18_operational_validation.py` still directly called `adapter.submit(plan)`. The validator was not weakened. That path now uses the centralized engine seam and an exact plan-bound Phase21 compatibility challenge.

The independent validator now requires exactly one raw `adapter.submit` call in all of `packages/` and requires it to reside in `packages/execution/engine.py` after the authority check.

## 10. Current validation evidence

Validated implementation head:

`d3599f3a184142de4ac5f03b58fc355f0bb11001`

CI `32781962354`:

- Ubuntu: 964 passed in 15.42s;
- Windows: 964 passed in 24.52s;
- every validator through Phase21 PASS;
- dependency lock PASS;
- secret hygiene PASS;
- ATLAS Doctor PASS;
- browser JS syntax PASS;
- exact 33-feature parity retained;
- provider calls 0;
- provider writes 0;
- broker writes 0.

No additional real provider mutation is required to validate Phase21 itself because accepted Phase18 already proved real Webull sandbox mutation/reconciliation; Phase21 is an internal authority-boundary hardening phase.

## 11. Performance baseline

Post-Phase19 accepted feature evidence remains:

- 50,000 rows / 7,454 symbols / 7 sessions;
- optimized batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x speedup;
- all 33 features exact parity, max difference 0.0;
- provider/broker calls/writes 0.

## 12. Exact continuation point

Do **not** repeat the accepted Phase18 real mutation merely to reconfirm it.

Current continuation sequence:

1. treat `d3599f3a184142de4ac5f03b58fc355f0bb11001` + CI `32781962354` as the validated Phase21 implementation evidence boundary;
2. synchronize `docs/phase21_unified_paper_execution_authority.md`, this file, roadmap, phase flow, README, and PR #22;
3. run exact documentation-head Ubuntu/Windows CI;
4. if green, mark Phase21 ACCEPTED in living docs, run final exact-head CI, mark PR ready, and merge to `main`;
5. verify the merge and independently audit the smallest next operational gap toward routine `ATLAS -> accepted analysis/risk/AI -> Webull PAPER -> reconciliation -> observability/outcome learning`;
6. define the next numbered phase from the merged code/roadmap rather than assuming scheduler or PostgreSQL infrastructure is next.

Until a later explicit phase changes authority: LIVE disabled, broker switching explicit/manual, automatic failover forbidden, autonomous scheduling and PostgreSQL runtime promotion out of scope.

## 13. Configuration/security

Tracked `.env.example` is non-secret and may contain public/default endpoints plus blank secret placeholders.

Never commit or expose API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata. Commented secrets are still secrets.

## 14. Future-session startup

Inspect `main`, branches/open PRs/latest CI; read this file, `docs/roadmap.md`, `docs/phase21_unified_paper_execution_authority.md` while Phase21 is active, and `docs/phase_flow.md`; preserve explicit provider/live/automation authority and continue from section 12 rather than reopening accepted work without new evidence.
