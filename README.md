# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the rebuild/redesign path for Chart Monitor; the legacy system remains preserved while ATLAS matures.

## Start here

For a future development session, read in this order:

1. [`docs/current_status.md`](docs/current_status.md) — exact current handoff/evidence/continuation.
2. [`docs/roadmap.md`](docs/roadmap.md) — architecture, phase ledger, data/safety rules, authority transitions.
3. [`docs/post_phase19_stabilization.md`](docs/post_phase19_stabilization.md) — unnumbered post-Phase19 closure/performance-housekeeping audit.
4. [`docs/phase_flow.md`](docs/phase_flow.md) — mandatory phase execution/acceptance/merge rules.
5. [`docs/phase19_operations_observability.md`](docs/phase19_operations_observability.md) — accepted Phase 19 operations/observability contract and evidence.
6. [`docs/phase18_operational_validation.md`](docs/phase18_operational_validation.md) — accepted Phase 18 broker-certification evidence.
7. merged PRs for deeper historical evidence.

Old phase/fix READMEs are provenance only when they conflict with these living sources.

## Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Core roles:

- **Parquet** — durable analytical/history lake.
- **DuckDB** — analytical/query engine.
- **PostgreSQL** — target transactional operational state; current `database/` tree remains a nonoperational scaffold.
- **Massive** — primary broad-market/reference-data provider path.
- **Webull** — primary execution broker; accepted downstream realtime L1 execution-evidence source where locally entitled.
- **Alpaca** — manually selectable secondary/fallback; never automatic failover.
- **ML** — point-in-time `p_down/p_neutral/p_up` evidence, never direct trade authority.
- **Strategies/router** — deterministic setup semantics and regime-aware routing.
- **Deep research** — promoted-candidate-only analogue/scenario/options/news work.
- **AI** — independent audit/reviewer only.
- **Browser** — monitoring/control plane only; it cannot create independent trading authority.

## Mandatory development flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Passing tests, configured credentials, available endpoints, or connected accounts do not silently change provider/live authority.

## Current state — 2026-08-24

- **Phases 1–19: ACCEPTED and merged.**
- Phase 18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase 19 merge / accepted `main` baseline before post-Phase19 maintenance: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Final Phase 19 docs-head CI run `32739682576`: Ubuntu **932 passed in 13.78s**; Windows **932 passed in 25.80s**; every validator through Phase 19 PASS.
- Phase 19 policy fingerprint: `ecd30046a7a3258013a29f0a2982de133f3a4f801aee4ad5e24f79b6bd3b4c3d`.
- Phase 19 provider reads/writes: **0 / 0**.
- Live execution: **DISABLED**.
- Automatic cross-broker failover: **DISABLED**.
- **Phase 20 is not active.**
- The current work after Phase 19 is unnumbered stabilization/housekeeping only and creates no new trading authority.

## Accepted data/model foundation

Historical provider boundary:

- Alpaca raw SIP daily controlled authority: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- No synthetic pre-2021 1h/4h history from daily bars.

Accepted cumulative lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Accepted production ML:

- model `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- protected holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact replay.

Phase 11 accepted strategy support:

- SUPPORTED 0;
- MIXED 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED 5.

Zero supported strategies correctly yielded zero promotions on the locked case; thresholds were not weakened.

## Accepted execution/control-plane foundation

### Phase 15

Broker-neutral shadow/paper execution with fresh quote, preflight, reconciliation, current risk, protective geometry, deterministic client IDs/idempotency, uncertainty fail-closed, same-ticker add/flip disabled, Webull primary, Alpaca manual secondary, live disabled.

### Phase 16

Loopback-first browser/control plane with CSRF/same-origin protection, audit/idempotency, restart recovery, explicit broker-switch/cleanup planning. Browser actions do not bypass execution authority.

### Phase 17

Real provider read-only readiness accepted for Webull sandbox and Alpaca paper with both brokers reconciled, zero open exposure at acceptance, provider writes 0, and cross-platform CI green.

### Phase 18

Accepted Webull sandbox mutation lifecycle:

`submit once -> exact reconcile -> cancel once -> exact CANCELLED -> zero fill -> flat/zero-open`

The target lifecycle used explicit paper mutation authorization and a fresh regular-session Webull L1 quote. Immediate post-cancel read uncertainty was handled fail-closed; later independent Order Detail and Order History reads both proved `CANCELLED`. The adapter was hardened to issue at most one cancel and then use bounded read-only reconciliation.

Phase 18 also locked the normal sustained Webull read target at **80% of the most specific current documented endpoint limit**, with endpoint-specific limits taking precedence and no automatic failover.

### Phase 19

Accepted read-only local operations/observability layer:

- dedicated `apps/web/phase19.html` operator shell;
- GET-only `/api/v1/observability`;
- local sanitized candidate, AI-audit, outcome, lineage, and persisted live-market diagnostics;
- optional 5/15/30-second local observability refresh, default OFF;
- accepted Phase 16 explicit read-only broker reconciliation kept separate;
- no Phase 19 provider reads/writes;
- no browser execution authority;
- no live promotion or automatic failover;
- dependency lock, secret-hygiene validation, SHA-pinned CI actions, ATLAS Doctor, feature-performance optimization, and low-risk data-I/O scan removal retained.

The accepted feature optimization preserves exact 33-feature parity and historical column order. Target evidence measured 50,000-row batch computation at ~4.00s versus ~594.58s prior baseline (~148.5x), with exact max feature difference 0.0 and zero provider/broker calls or writes.

## Non-negotiable rules

- Preserve exact provider-native ticker case/text.
- Never infer identity continuity from ticker text alone.
- Historical populations must remain point-in-time.
- Quarantine ambiguity; do not guess.
- No fabricated unavailable intraday history.
- Finalized canonical facts outrank provisional live observations.
- ML output is evidence, not a signal.
- AI is independent audit only and cannot authorize execution.
- LONG: `stop < entry < target`.
- SHORT: `stop > entry > target`.
- Unknown broker/provider state fails closed.
- Uncertain writes require exact reconciliation before any next mutation.
- Automatic broker failover is forbidden.
- Paper/shadow precede any future controlled live authority.

## Environment/security

Tracked `.env.example` is non-secret. Public/default endpoints may be populated; secret placeholders remain blank.

Never commit or print API secrets, passwords, security codes, raw broker IDs, tokens, or signed request metadata. Commented secrets are still secrets. Real `.env` remains local/ignored.

Generated Webull SDK logs are local runtime artifacts and are ignored; they are not source or acceptance evidence.

## Exact continuation point

Do **not** repeat the accepted Phase 18 mutation merely to reconfirm it. Phase 19 is already accepted/merged.

Current continuation:

1. complete the unnumbered post-Phase19 stabilization/housekeeping PR;
2. verify its CI and merge to `main`;
3. keep Phase 20 inactive until its scope and authority boundary are explicitly defined;
4. preserve live execution disabled and automatic failover disabled;
5. use `docs/post_phase19_stabilization.md` for the maintenance audit and performance-housekeeping findings.

No live-money promotion, destructive cleanup, broker mutation, or automatic failover is implied by this maintenance work; any such authority requires a separately defined gate and explicit authorization where applicable.
