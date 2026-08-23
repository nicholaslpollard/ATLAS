# ATLAS Current Status and Handoff

**Living status document. Last synchronized: 2026-08-23.**

This file is the fastest way for a new development session or future chat to recover the current ATLAS state without reconstructing the project from conversation history. `docs/roadmap.md` is the architecture/authority lock, `README.md` is orientation, and `docs/phase18_operational_validation.md` contains the exact active Phase 18 certification specification.

## 1. Source-of-truth order

When sources disagree, use this order:

1. accepted `main` code + accepted validation artifacts for completed work;
2. the active PR/branch for in-progress work;
3. `docs/roadmap.md` for architecture, phase boundaries, safety, configuration, and authority rules;
4. this file for latest accepted state, active work, evidence, and exact continuation point;
5. active phase living spec (`docs/phase18_operational_validation.md` while Phase 18 is active);
6. root `README.md`;
7. merged PRs for detailed historical acceptance evidence;
8. old `README_PHASE_*`, `README_ATLAS_*`, fix notes, and phase-specific historical documents as provenance only.

A future session must not treat an old Chart Monitor plan or historical phase README as the current roadmap when it conflicts with these living sources.

## 2. Current state at a glance

- **Phases 1–17: ACCEPTED and merged.**
- **Phase 18: ACTIVE** on draft PR #18.
- Active branch: `phase-18-paper-provider-mutation-lifecycle-validation`.
- Accepted Phase 17 provider-readiness code head: `21eeb757d84de33878ab1c8d7c8afe0797dee1f9`.
- Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.
- Phase 18 green code-bearing head: `062efedfdc7537222c929f72ebf1f1bb57f903af`.
- Current Phase 18 GitHub Actions: Windows SUCCESS + Ubuntu SUCCESS.
- Current Phase 18 test count: **908 passed on each runner**.
- Real provider mutation performed by Phase 18 so far: **NO**.
- Current real-provider checkpoint: `PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`.
- Live execution: **DISABLED**.
- Automatic cross-broker failover: **DISABLED**.
- Webull: primary broker.
- Alpaca: manually selectable secondary/fallback.

Documentation-only commits may advance the branch beyond the green code-bearing SHA. When evaluating code/CI, distinguish the last code-bearing green head from later documentation-only synchronization commits.

## 3. Architecture snapshot

`market/reference data -> Parquet -> DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts/paper/shadow/live execution -> outcome learning -> browser control plane`

Roles:

- Parquet: durable analytical/history lake.
- DuckDB: local analytics/query engine.
- PostgreSQL: target persistent operational state.
- Massive: primary market/reference-data provider.
- Conventional ML: probability evidence only.
- Strategies/router: deterministic setup + routing.
- Expensive research: promoted-candidate only.
- AI: independent auditor, not predictor/execution authority.
- Browser: control/monitoring plane, not execution authority.
- Webull: primary broker.
- Alpaca: explicit manual secondary/fallback.

## 4. Accepted data/history state

### Historical source boundary

- Alpaca raw SIP daily: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- No synthetic pre-2021 1h/4h bars from daily data.
- Historical populations are observation-driven and point-in-time.
- Provider-native ticker text/case is preserved.
- Literal ticker text never proves identity continuity.

### Identity/data safety

Phase 4+ accepted security-safe stable identity, point-in-time reference snapshots, ticker-event continuity where authoritative, ticker-reuse protection, and explicit ambiguity quarantine/exclusion.

### Live state

Phase 5 accepted Massive delayed/realtime WebSocket state, explicit freshness, gap/reconnect accounting, provisional journal/snapshot behavior, and finalized-data authority. Provisional live observations never overwrite finalized canonical facts.

### Feature engine

Phase 6 accepted 33 deterministic point-in-time features and exact batch/incremental continuation.

Permanent feature tiers:

- 1d permanent;
- 4h permanent;
- 1h permanent;
- 15m on-demand/cache;
- 1m live/current state only.

Accepted 2021-08-16 through 2026-08-14 permanent feature lake: **154,188,221 rows**.

## 5. Accepted discovery/regime/ML state

### Universe

Accepted 2026-08-14 routed discovery universe: **12,066 instruments**.

### Discovery

Accepted broad-ready population: **8,034 instruments**.

Locked state thresholds:

- WATCH >= 0.35;
- WARM >= 0.50;
- HOT >= 0.60 plus direction/evidence/full-timeframe guards.

### Regimes

Accepted market/sector-proxy/ticker hierarchy with optional authoritative SIC and explicit missing-context handling. Effective current ticker states at accepted 2026-08-14 state: **7,338**.

### Production ML

Accepted Phase 10 production model:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- raw `p_down`, `p_neutral`, `p_up`;
- no post-hoc calibration;
- protected holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

ML argmax remains diagnostic only. Longer-history C evidence remains separately versioned challenger/research evidence and has not replaced production authority.

## 6. Accepted strategy/research/case state

### Phase 11

Eight deterministic strategy variants were evaluated with routing external to strategies.

Historical support:

- SUPPORTED: 0;
- MIXED: 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: 5.

Zero supported strategies produced zero promoted candidates without threshold relaxation.

### Phase 12

Accepted promoted-only analogue and deterministic empirical scenario/bootstrap research. Zero promotions is a legitimate strict no-op.

### Phase 13

Accepted deterministic context, instrument, geometry, sizing/liquidity, exposure/concentration/correlation, and portfolio-risk planning.

Locked geometry:

- LONG: `stop < entry < target`;
- SHORT: `stop > entry > target`.

Accepted risk envelope includes 0.5% equity risk/trade and 10% single-name notional.

### Phase 14

Accepted independent structured AI audit (`APPROVE`, `CAUTIOUS`, `REJECT`) and artifact-first Engine-vs-AI alerting. AI cannot rewrite deterministic evidence or create execution authority.

## 7. Accepted execution/control-plane foundation

### Phase 15

Accepted broker-neutral shadow/paper execution contracts with:

- Webull primary;
- Alpaca manual secondary/fallback;
- no automatic failover;
- fresh quote translation;
- current risk/reconciliation;
- provider preflight;
- protective stop/target;
- deterministic client-order IDs/idempotency;
- uncertain-write fail-closed handling;
- descriptive outcome learning;
- live hard-disabled.

### Cumulative integrity audit

Accepted read-only cross-layer source/canonical/feature/regime/identity lineage audit before execution advancement.

### Phase 16

Accepted browser control plane, status/action APIs, audit/idempotency, restart/recovery, broker-switch workflow, cleanup planning/confirmation, and loopback-first operation. Browser is not execution authority. Provider cleanup writes/live money were not promoted.

## 8. Phase 17 accepted provider-readiness evidence

Phase 17 accepted real **read-only** Webull sandbox + Alpaca paper reconciliation.

Webull:

- five readable sandbox accounts discovered;
- ambiguity failed closed;
- one sandbox margin account explicitly selected locally via sanitized ref;
- account list/balance/open orders/positions reads successful;
- open orders: 0;
- positions: 0.

Alpaca:

- paper reconciliation successful;
- open orders: 0;
- positions: 0.

Combined:

- both rows `AVAILABLE`;
- reconciled=true;
- safe-to-switch=true;
- exactly two provider adapter initializations;
- provider mutation endpoint invocations: 0;
- provider writes: 0;
- live writes: 0;
- automatic failover disabled;
- live disabled;
- accepted Phase 16 artifacts unchanged/hash-bound;
- validator PASS;
- local regression: **874 passed in 24.83s**;
- Ubuntu/Windows CI PASS.

Phase 17 grants read/reconciliation evidence only.

## 9. Active Phase 18 — exact status

PR #18 is draft/mergeable and remains open until real target-machine mutation acceptance is completed.

### Policy

Contract:

`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Fingerprint:

`9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`

Bound to accepted Phase 17 merge/policy/readiness evidence.

Provider mutation is disabled by default. Real mutation requires one selected broker plus:

- explicit mutation authorization flag;
- exact confirmation `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

One broker per run. Live disabled. Automatic failover disabled. Destructive cleanup separately explicit.

### Production semantic lifecycle tests

`packages/execution/phase18_lifecycle.py` wraps the accepted Phase 15 engine against fakes. It verifies the production path does not lose its quote/risk/preflight/reconciliation/protective/idempotency/uncertainty safety semantics.

### Lineage-safe real-provider certification

A key Phase 18 design correction: the real broker plumbing test **does not fabricate Phase 13/14 trade-case hashes** merely to satisfy `ExecutionIntent`.

Instead, `packages/execution/phase18_operational_validation.py` defines a separate validation-only operational order. This order:

- is not a strategy signal;
- is not a model output;
- is not an AI-reviewed trade;
- is not production performance evidence;
- exists only to certify broker submit/reconcile/cancel plumbing.

Operational validation contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

Locked shape:

- paper/sandbox only;
- equity BUY only;
- exactly 1 share;
- LIMIT / DAY;
- no extended hours;
- entry 5% below fresh realtime bid;
- stop 2% below entry;
- target 2% above entry;
- max notional $1,000;
- Phase 13 10% single-name and 0.5% loss-at-stop limits still apply.

### Quote authority

Operational plan requires realtime, zero-delay, regular-session quote evidence.

Existing accepted startup path:

`scripts/run_live_market_state.py`

Focused certification subscription:

`Q.<ticker>` with no broad minute subscription.

`Phase15LiveQuoteResolver` then requires:

- live-state snapshot valid;
- connection `SUBSCRIBED`;
- realtime;
- delay 0;
- no open transport gap;
- regular session;
- exactly one exact provider-native ticker;
- quote exists and is `FRESH`;
- quote itself realtime/undelayed/regular.

A stopped stream, delayed feed, stale quote, weekend, holiday, premarket, or after-hours is rejected. Today (2026-08-23) is Sunday, so a real Phase 18 mutation cannot be validly certified today without violating the accepted quote contract.

### Current broker/risk gates

Before provider preview/submit:

- explicit auth/broker match;
- paper adapter;
- reconciled flat broker;
- zero open orders;
- account not trading-blocked;
- positive equity;
- sufficient buying power;
- accepted Phase 13 risk envelope;
- deterministic client-order ID proven absent;
- provider preflight accepted.

Only `BrokerOrderNotFound` proves the client ID is absent; ambiguous lookup errors block mutation.

### Mutation lifecycle

Expected:

`submit once -> exact client-ID reconcile -> cancel once if still open -> reconcile flat`

If submit/cancel is uncertain:

- read-only reconcile if possible;
- no blind retry;
- no second mutation;
- no flatten;
- no failover.

If fill/partial fill occurs:

- no automatic flatten;
- no automatic opposite order;
- separate cleanup authority required.

### Runner

`scripts/run_phase18_operational_validation.py`

Requires:

- `--broker webull|alpaca`;
- `--ticker <exact provider-native ticker>`.

No default ticker. No quantity argument.

Plan-only default:

- reads local live-state only;
- initializes no broker adapter;
- provider/broker calls: 0;
- provider writes: 0;
- disposition: `PLAN_ONLY_ZERO_PROVIDER_CALLS`.

Wrong confirmation also stops before broker initialization.

### Automated coverage

Authorization tests cover missing/incorrect auth and exact Webull/Alpaca acceptance.

Production lifecycle fake tests cover open-order cancel, fill/no-auto-flatten, uncertain submit/cancel, existing exposure, and broker mismatch.

Operational tests cover:

- locked order shape/geometry;
- deterministic identity;
- delayed/nonregular quote rejection;
- $1,000 cap;
- trading-blocked account;
- buying power;
- Phase 13 risk limits;
- preflight rejection;
- existing client ID;
- unexpected terminal provider state;
- fill/no-auto-flatten;
- uncertainty/no retry;
- pre-existing position;
- broker mismatch.

Runner tests prove plan-only, wrong-confirmation, and blocked-quote paths initialize no broker.

### Current Phase 18 CI

Green code-bearing head:

`062efedfdc7537222c929f72ebf1f1bb57f903af`

Actions run ID:

`32656692232`

Evidence:

- all validators through Phase 18 PASS;
- Ubuntu: **908 passed in 17.80s**;
- Windows: **908 passed in 31.79s**;
- both jobs SUCCESS.

Detailed active spec: [`phase18_operational_validation.md`](phase18_operational_validation.md).

## 10. Configuration state

Tracked `.env.example` is non-secret and intentionally includes public/default configuration:

- `ATLAS_ENV=development`;
- blank OpenAI/DB placeholders;
- Massive API/S3 placeholders;
- `MASSIVE_ENDPOINT=https://files.massive.com`;
- Webull paper/live credential variable names (values blank);
- Alpaca paper endpoint `https://paper-api.alpaca.markets/v2`;
- Alpaca live endpoint `https://api.alpaca.markets`;
- blank Alpaca credential placeholders;
- optional IBKR `127.0.0.1:4002`, client ID 17.

The commented Alpaca security-code placeholder remains blank. Commenting a secret does not make it safe to commit.

Real `.env` remains local/ignored. Live placeholders/endpoints do not imply live authority. Generated `webull_trade_sdk.log*` files are ignored.

## 11. Development workflow

Normal batch:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status update`

Use focused tests during coding; full regression + Windows/Ubuntu CI at evidence boundaries; independent validators for authority changes; one complete PowerShell sequence for target-machine evidence when practical.

Fail closed on ambiguity, missing lineage/data, invalid geometry, broker-state uncertainty, and uncertain writes. Never create post-hoc thresholds merely to force acceptance.

## 12. Documentation/branch policy

Living docs must stay synchronized on meaningful changes:

- `README.md`;
- `docs/roadmap.md`;
- this file;
- active phase living spec;
- active PR body;
- `.env.example`/configuration notes when relevant.

`main` contains accepted work. Substantial/authority-changing work uses a focused branch/PR. Record target-machine + CI evidence before merge. Delete completed phase branches after closeout unless a concrete retention reason exists.

Historical phase/fix READMEs remain frozen provenance.

## 13. Exact continuation point

Repository/CI Phase 18 preparation is green. The remaining work is target-machine evidence and explicit authority.

Because today is Sunday, **do not attempt to bypass the regular-session quote requirement**.

Safe immediate target-machine work that can be performed without provider mutation:

1. pull Phase 18 branch;
2. run Phase 18 validator;
3. run local regression/targeted Phase 18 tests;
4. rerun Phase 17 provider-read diagnostic to prove broker state still reconciles;
5. run the Phase 18 authorization diagnostic (0 provider calls/writes).

Then, during the next regular U.S. equity session:

1. run focused Massive realtime `Q.<ticker>` state and keep it active;
2. run Phase 18 plan-only validation first;
3. verify exact 1-share plan and zero broker/provider calls/writes;
4. obtain explicit `PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION` approval;
5. run Webull sandbox first;
6. reconcile/cancel if still open;
7. if filled/partial, stop for separate cleanup approval;
8. never auto-fail over to Alpaca;
9. record sanitized evidence in PR/docs;
10. merge Phase 18 only after accepted target-machine closeout.

## 14. Future-chat startup procedure

Before changing ATLAS code, a new session should:

1. inspect `main` and open PRs/branches;
2. read `README.md`;
3. read `docs/roadmap.md`;
4. read this file completely;
5. if Phase 18 is still active, read `docs/phase18_operational_validation.md`;
6. inspect latest merged PR(s) only when more detail is needed;
7. inspect active PR for in-progress evidence;
8. verify planned work does not cross an authority boundary;
9. treat old Chart Monitor plans and historical phase READMEs as historical unless explicitly incorporated by the living roadmap.
