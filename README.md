# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the rebuild/redesign path for Chart Monitor; the legacy system remains preserved while ATLAS matures.

## Start here

For a future development session, read in this order:

1. [`docs/current_status.md`](docs/current_status.md) — exact current handoff/evidence/continuation.
2. [`docs/roadmap.md`](docs/roadmap.md) — architecture, phase ledger, data/safety rules, authority transitions.
3. [`docs/phase_flow.md`](docs/phase_flow.md) — mandatory phase execution/acceptance/merge rules.
4. [`docs/phase18_operational_validation.md`](docs/phase18_operational_validation.md) — accepted Phase 18 broker-certification evidence.
5. active/stacked Phase 19 spec after Phase 18 merge/retarget.
6. merged PRs for deeper historical evidence.

Old phase/fix READMEs are provenance only when they conflict with these living sources.

## Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Core roles:

- **Parquet** — durable analytical/history lake.
- **DuckDB** — analytical/query engine.
- **PostgreSQL** — target transactional operational state.
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

- **Phases 1–17: ACCEPTED and merged.**
- **Phase 18A: ACCEPTED / COMPLETE.**
- **Phase 18B: ACCEPTED / COMPLETE.**
- **Phase 18 overall: ACCEPTED; final docs/CI/merge closeout in progress on PR #18.**
- **Phase 19: STACKED_PREP only** until Phase 18 merges; then rebase/retarget to merged `main` and revalidate before activation/merge.
- Phase 18 policy fingerprint: `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.
- Live execution: **DISABLED**.
- Automatic cross-broker failover: **DISABLED**.

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

Real provider read-only readiness accepted:

- Webull sandbox selected sanitized account ref `3d64d273c694250b`, 0 open orders, 0 positions;
- Alpaca paper sanitized account ref `4b5b072f7127b4dc`, 0 open orders, 0 positions;
- both reconciled;
- provider writes 0;
- target-machine regression 874 passed in 24.83s;
- Windows/Ubuntu CI green.

## Phase 18 — accepted paper-provider mutation lifecycle

Policy:

`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Operational contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

Locked validation order:

- PAPER/SANDBOX only;
- EQUITY BUY only;
- exactly 1 share;
- LIMIT / DAY;
- no extended hours;
- entry 5% below fresh realtime bid;
- stop 2% below entry;
- target 2% above entry;
- max notional $1,000;
- Phase 13 10% single-name notional cap;
- Phase 13 0.5% equity loss-at-stop cap.

### Quote authority

Massive remains broad-market authority. Current Massive entitlement supports delayed aggregate streaming but rejected realtime stock quote subscriptions during Phase 18 certification.

ATLAS therefore added an explicit Webull sandbox L1 capture path:

`one read-only Webull L1 request -> sanitized local snapshot -> Phase 18 local plan`

Execution evidence requires exact ticker, valid bid/ask, REALTIME/undelayed semantics, REGULAR session, and quote age <= **30 seconds**. Premarket/after-hours/stale/delayed evidence fails closed.

Plan-only mode initializes no broker adapter and makes zero provider calls/writes.

### Target-machine acceptance — 2026-08-24

Regular-session plan-only proof:

- AAPL bid/ask `311.06 / 311.17`;
- quote age `0.322s`;
- plan entry/stop/target `295.51 / 289.60 / 301.42`;
- planned notional `$295.51`;
- provider calls 0;
- provider writes 0.

Accepted authorized lifecycle:

- AAPL bid/ask `311.33 / 311.39`;
- quote age `0.823s`;
- client ID `p18v-13abada37159d4486df293b3695`;
- entry/stop/target `295.76 / 289.84 / 301.68`;
- planned notional `$295.76`;
- explicit paper mutation authorization accepted;
- pre-reconciliation flat/zero-open;
- exact client-ID absence proven;
- provider preview accepted;
- order submitted exactly once;
- exact post-submit reconciliation succeeded;
- cancel requested exactly once;
- immediate post-cancel read was inconclusive, so ATLAS stopped with no retry/failover;
- later read-only Order Detail and Order History both reported `CANCELLED`;
- requested quantity 1.0, filled quantity 0.0;
- final open orders 0;
- final positions 0;
- no cleanup required.

This definitively proves:

`submit once -> exact reconcile -> cancel once -> exact CANCELLED -> zero fill -> flat/zero-open`

Phase 18 also hardened:

- Webull explicit `Order not present` normalization;
- suppression of unsafe SDK request logging;
- bounded read-only post-cancel reconciliation with exactly-one-cancel semantics;
- 30-second execution quote-age cap;
- premarket fail-closed behavior.

See [`docs/phase18_operational_validation.md`](docs/phase18_operational_validation.md) for the full acceptance ledger.

## Webull API operating policy

Locked as of 2026-08-24:

- normal sustained Webull **read** traffic target = **80% of the most specific current documented endpoint limit**;
- endpoint-specific limits outrank broad/global ceilings;
- 90% is not the normal sustained target;
- any temporary higher read burst must be bounded, read-only, and below the provider hard limit;
- trading mutation throughput is governed by ATLAS risk/reconciliation/idempotency rather than provider write capacity;
- use MQTT/streaming for sustained realtime candidate data rather than aggressive HTTP polling;
- back off/cool down on read 429s;
- uncertain mutations require reconciliation;
- never auto-fail over brokers.

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

## Exact continuation point

Do **not** repeat the real Phase 18 mutation solely to reconfirm already accepted evidence.

Closeout sequence:

1. require final Phase 18 code/docs CI green on Ubuntu and Windows;
2. synchronize living docs and PR evidence;
3. mark PR #18 ready;
4. merge Phase 18 into `main`;
5. verify merged `main`;
6. retarget/rebase existing Phase 19 stacked branch/PR to merged `main`;
7. run Phase 19 validator + full regression;
8. require Windows/Ubuntu Phase 19 CI green;
9. resolve drift;
10. synchronize Phase 19 docs/PR;
11. only then treat Phase 19 as active/mergeable.

Any later live-money promotion requires a separate numbered phase and separate explicit authorization.
