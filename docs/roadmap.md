# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-23.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This file is the long-term architecture and authority lock. Implementation may evolve when measured evidence requires it, but changes must preserve the data-integrity, validation, and trading-authority boundaries below unless an explicit replacement decision is documented and independently validated.

For exact operational continuation, read [`current_status.md`](current_status.md). During active Phase 18, also read [`phase18_operational_validation.md`](phase18_operational_validation.md). The root [`README.md`](../README.md) is project orientation.

## 1. Mission

Build a broad-market system that can:

1. observe a large U.S. market universe;
2. maintain point-in-time-safe market/reference data, instrument identity, features, and regimes;
3. discover candidates cheaply before spending expensive research;
4. estimate outcome probabilities with conventional ML;
5. route candidates to deterministic strategies appropriate to context/regime;
6. promote only evidence-supported candidates into deeper analogue/scenario/options/news analysis;
7. produce deterministic entry/stop/target/horizon/risk plans;
8. subject the deterministic case to an independent AI audit;
9. alert, shadow, paper-trade, and eventually trade live only under explicit authority;
10. learn descriptively from outcomes without silently changing accepted model/strategy authority;
11. expose operational state through a browser control plane without making the browser an execution authority.

## 2. Architecture

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/compute roles:

- Parquet: durable analytical/history lake.
- DuckDB: analytical/query engine.
- PostgreSQL: target persistent operational state.
- Massive: primary accepted market/reference-data provider.

## 3. Non-negotiable data rules

- Preserve exact provider-native ticker text and case.
- Ticker text alone never proves instrument identity or historical continuity.
- Historical populations are point-in-time/observation-driven; current survivors are not projected backward.
- Current active/delisted state is not retrospective historical eligibility.
- Ambiguity is quarantined/excluded, never guessed.
- Acquisition/replay must be restartable, checkpointed, deterministic, duplicate-safe, and auditable.
- No synthetic pre-2021 intraday bars from daily history.
- Finalized canonical data outranks provisional live observations.
- Data/model/authority transitions require explicit lineage and independent validation.

Accepted historical boundary:

- Alpaca raw SIP daily controlled extension: 2016-01-04 through 2021-08-13.
- Massive authority: 2021-08-16 onward.
- Pre-2021 1h/4h history remains absent rather than fabricated.

## 4. ML authority rules

Production ML emits raw three-class probabilities:

- `p_down`;
- `p_neutral`;
- `p_up`.

Argmax is diagnostic only and is never a standalone trade signal. Accepted production model authority is immutable until an explicit challenger/acceptance process replaces it; longer-history or challenger research cannot silently overwrite the accepted model.

Accepted model:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- deterministic replay exact.

## 5. Strategy/research rules

- Regime routing belongs in scanner/router orchestration, not embedded inside strategy implementations.
- Strategies emit deterministic case evidence, not opaque conclusions.
- Expensive historical analogue, Monte Carlo/scenario, options, and event/news work is promoted-candidate only.
- No-op/zero-promotion states are valid outcomes; thresholds are never relaxed after seeing results merely to create trades.
- Accepted Phase 11 support: 0 SUPPORTED, 3 MIXED, 5 UNSUPPORTED among eight tested variants.

## 6. AI authority rules

AI is an independent auditor/reviewer. It may approve, caution, or reject a deterministic case and identify risks, but it cannot:

- rewrite accepted historical/quantitative evidence;
- change deterministic direction/instrument/geometry/position size as authoritative facts;
- manufacture a trade from a rejected deterministic case;
- create provider-order authority;
- promote live execution.

## 7. Geometry and portfolio-risk rules

Mandatory geometry:

- LONG: `stop < entry < target`;
- SHORT: `stop > entry > target`.

Accepted Phase 13 operational risk envelope used by Phase 18 certification includes:

- risk at stop <= 0.5% of current equity;
- single-name notional <= 10% of current equity;
- liquidity/buying-power/account-state checks;
- current exposure/concentration/correlation revalidation when applicable.

## 8. Broker architecture

### Webull

Primary planned broker for paper/sandbox and, only after a future separate live-authority phase, controlled live execution.

### Alpaca

Manually selectable secondary/fallback. It is not an automatic failover destination.

### Switching

Broker switching is explicit only. Before switching, ATLAS must inspect/reconcile open orders and positions. Any cancel/close/flatten required to make a broker safe is itself a provider mutation and must possess the corresponding explicit authority. Unknown broker state fails closed.

### Live

Live execution is disabled. Paper-provider acceptance is not live acceptance. A later live-money phase must preregister limits, operational observation, failure handling, and explicit authorization independently.

## 9. Accepted phase ledger

### Phase 1 — Foundation

Project/config/session/time foundations, environment separation, canonical timezone and basic validation.

### Phase 2 — Provider ingestion foundation

Restartable provider acquisition, storage contracts, checkpoints, and raw evidence handling.

### Phase 3 — Canonical/session-aware data

Parquet/DuckDB canonical data foundations, exchange/session semantics, duplicate-safe/replay-safe handling.

### Phase 4 — Instrument identity/history

Security-safe instrument identity, point-in-time reference evidence, stable identifiers where authoritative, ambiguity quarantine.

### Phase 5 — Live market state

Massive delayed/realtime WebSocket state, explicit freshness/delay/gap semantics, provisional journal/snapshot behavior, finalized-data authority.

### Phase 6 — Feature engine

33 deterministic point-in-time features with explicit warmup and deterministic batch/incremental behavior.

### Phase 7 — Universe registry

Point-in-time instrument routing/eligibility with no retrospective survivor projection or guessed identity.

### Phase 8 — Broad discovery

Cheap-first broad-market discovery, health/activity routing, absolute setup-state thresholds, persistence/hysteresis.

### Phase 9 — Regime engine

Market/sector/ticker regime hierarchy, prior-only thresholds, persistence, ticker risk, optional authoritative SIC, no guessed sector crosswalk.

### Phase 10 — ML probability/evaluation

Point-in-time training population, label/feature leakage controls, walk-forward evaluation, model registry/acceptance, protected holdout, raw probability surface.

### Historical extension/audit

Controlled Alpaca raw-SIP daily extension back to 2016, provider seam validation, cumulative data/lineage integrity audit. No synthetic pre-2021 intraday.

### Phase 11 — Strategy evaluation/regime routing

Deterministic strategy variants, external regime routing, historical support classification, candidate-promotion policy.

### Phase 12 — Deep candidate research

Promoted-only historical analogue and deterministic empirical scenario/bootstrap research.

### Phase 13 — Context/instrument/geometry/portfolio risk

Deterministic instrument choice, geometry, position sizing, liquidity, exposure/concentration/correlation and risk planning.

### Phase 14 — Independent AI audit/alerting

Structured independent AI review and Engine-vs-AI artifact alerts with AI authority strictly bounded.

### Phase 15 — Broker-neutral shadow/paper execution + outcome learning

Webull primary/Alpaca manual secondary, fresh quote, provider preflight, reconciliation, current risk, protective geometry, deterministic client IDs, uncertain-write fail-closed behavior, descriptive outcome records, live disabled.

### Phase 16 — Browser control plane/production operations

Loopback-first browser/API control plane, CSRF/same-origin protections, action audit/idempotency, restart recovery, explicit broker switch and cleanup planning. Browser is not execution authority; provider cleanup writes/live money not promoted.

### Phase 17 — Provider-readonly operational readiness

Accepted real Webull sandbox + Alpaca paper reads/reconciliation while provider mutation remained disabled.

Accepted target-machine evidence:

- Webull account-list/balance/orders/positions reads reached successfully;
- explicit sanitized Webull account selection after five readable accounts;
- Webull 0 open orders, 0 positions;
- Alpaca paper reconciled, 0 open orders, 0 positions;
- both brokers AVAILABLE/reconciled;
- provider mutation endpoint invocations 0;
- provider writes 0;
- live writes 0;
- local 874 tests passed;
- Windows/Ubuntu CI passed.

Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.

## 10. Active Phase 18 — Paper Provider Mutation Lifecycle Validation

Phase 18 is active on draft PR #18 and branch `phase-18-paper-provider-mutation-lifecycle-validation`.

Policy contract:

`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Policy fingerprint:

`9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`

### Authority boundary

Real provider mutation is disabled by default and remains behind:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

A real run requires:

- one selected broker;
- `--authorize-paper-provider-mutation`;
- exact confirmation `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credential presence, endpoint configuration, environment state, connected account, Phase 17 success, Phase 18 implementation, or passing tests do not grant mutation authority.

Live execution and automatic cross-broker failover remain disabled.

### Separate validation paths

Phase 18 deliberately separates:

1. production-path semantic validation through fake providers and accepted Phase 15 execution contracts;
2. a validation-only real-provider operational order.

The real broker-certification order does not fabricate Phase 13/14 case lineage and is not strategy/model/AI/performance evidence.

### Locked operational order

Contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

- PAPER/SANDBOX only;
- EQUITY BUY;
- exactly 1 share;
- LIMIT / DAY;
- no extended hours;
- entry 5% below fresh realtime bid;
- stop 2% below entry;
- target 2% above entry;
- max notional $1,000;
- Phase 13 10% single-name cap still applies;
- Phase 13 0.5% loss-at-stop cap still applies.

Expected lifecycle:

`authorize -> reconcile flat -> prove deterministic client ID absent -> preflight -> submit once -> exact reconcile -> cancel once if open -> exact reconcile flat`

A fill/partial fill causes a stop for separate cleanup authorization; ATLAS does not auto-flatten.

### Uncertain write rule

Uncertain submit/cancel means:

- read-only reconciliation if possible;
- no blind retry;
- no second mutation;
- no flatten;
- no automatic failover;
- stop until exact state is known.

### Realtime quote rule

Certification requires an actively running accepted Phase 5 realtime focused `Q.<ticker>` stream and a Phase 15 resolver result that is:

- SUBSCRIBED;
- REALTIME;
- expected delay 0;
- gap-free;
- regular-session;
- exact ticker;
- FRESH.

Weekends, holidays, stale/delayed data, premarket, after-hours, and stopped streams fail closed. The gate must never be weakened to force a test.

## 11. Phase 18 evidence as of 2026-08-23

Repository/CI implementation is green through the accepted Phase 18 code paths; real provider mutation remains unperformed.

Target-machine pre-mutation evidence at local head `e1631e741a547c78eb6c3c9b943ba1473c805cf6`:

- Phase 18 validator PASS;
- 34 focused Phase 18 tests passed in 2.23s;
- Webull read-only recheck: selected account configured, balance/orders/positions HTTP 200, 0 orders, 0 positions;
- Alpaca read-only recheck: reconciled, 0 orders, 0 positions;
- mutation gate denied before adapter initialization;
- provider adapter initialization NO;
- provider calls 0;
- provider writes 0;
- live disabled;
- automatic failover disabled;
- working tree clean.

That run's full suite was 907 passed / 1 failed due only to `test_csrf_failure_creates_no_action_event` receiving Windows `WinError 10053` on a loopback rejection response.

First hardening commit `45a2abeba7a51401ee708ab777d960d2f7fea88f` disabled ambient proxy use for the deterministic `127.0.0.1` test client. GitHub Actions run `32657554236` then passed all validators and 908 tests on Ubuntu and Windows.

The target-machine rerun at documentation head `36c9832891b8565f75b727db7dfc231719be5006` produced:

- isolated CSRF test: **1 passed in 3.52s**;
- immediate full suite: **907 passed / 1 failed in 24.04s**;
- same test failed only on the second foreign-origin request;
- exact Windows host transport error: `ConnectionAbortedError [WinError 10053]`;
- final working tree clean.

Because the exact isolated test passed immediately before the full-suite failure, this is treated as nondeterministic host transport/security interception under suite load rather than a deterministic failure of ATLAS same-origin authorization.

Current test-only hardening commit `38c09c21d4fc636667921c779fbe59341839e9e8` preserves the contract by:

1. directly asserting `ControlPlaneSessionGuard.authorize_write()` returns `SAME_ORIGIN_REQUIRED` for the foreign origin;
2. still requiring actual HTTP `403` on clean hosts;
3. accepting only Windows `ConnectionAbortedError` with exact `winerror == 10053` as an alternate transport manifestation after rejection is already proven;
4. still requiring zero action/audit events;
5. failing every other transport error.

Production Phase 16 server behavior, broker adapters, execution logic, Phase 18 policy, and provider authority remain unchanged.

## 12. Phase 18 remaining acceptance sequence

1. Pull the latest Phase 18 branch on target machine after the current test/docs commits settle.
2. Run isolated CSRF test and full suite; expected 908 passed.
3. Keep real provider mutation unauthorized until a regular U.S. equity session.
4. Start focused Massive realtime `Q.<ticker>` stream and keep it running.
5. Run Phase 18 plan-only validation first; verify no broker adapter/provider calls/writes.
6. Review the exact one-share plan.
7. Obtain explicit paper-provider mutation authorization.
8. Certify **Webull sandbox first** because Webull is primary.
9. If order remains open, cancel exactly once and reconcile flat.
10. If filled/partially filled, stop for separate cleanup authorization.
11. Never auto-fail over to Alpaca.
12. Record sanitized target-machine mutation evidence in PR/docs.
13. Rerun relevant validators/regression if code changes during closeout.
14. Mark PR ready and merge only after accepted real paper/sandbox mutation evidence.
15. Delete merged Phase 18 branch after closeout.
16. Any live-money promotion is a later separate phase with explicit authority.

## 13. Accelerated development protocol

ATLAS uses evidence boundaries, not micro-step ceremony.

Normal coherent work package:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status`

Rules:

- focused tests during coding;
- full regression + Windows/Ubuntu CI at batch/evidence boundaries;
- independent validators at data/model/broker-authority transitions;
- read-only diagnostics/preregistration automated where possible;
- target-machine interaction only where local/external evidence is genuinely required;
- fail closed on ambiguous identity, missing lineage/data, invalid geometry, broker uncertainty, and uncertain writes.

## 14. Documentation policy

Documentation synchronization is part of implementation, not optional cleanup.

Every meaningful change must update, as applicable:

- root `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- active phase living specification;
- active PR acceptance/evidence ledger;
- `.env.example` / configuration notes when configuration changes.

Historical phase/fix READMEs remain frozen provenance unless correcting a factual historical error.

## 15. Configuration/security policy

Tracked `.env.example` may contain public/default endpoint values and blank secret placeholders. It must never contain:

- API secrets;
- passwords;
- security codes;
- raw broker account IDs;
- tokens.

Current non-secret defaults include Massive file endpoint, Alpaca paper/live endpoints, and optional local IBKR host/port/client ID. Their presence does not grant provider or live authority.

## 16. Future-chat recovery protocol

A new session should:

1. inspect current `main`, branches, and open PRs;
2. read `docs/current_status.md`;
3. read this roadmap;
4. read active phase spec;
5. read root README;
6. inspect active PR body and latest relevant CI;
7. use merged PRs only for deeper historical acceptance evidence;
8. never revive an old Chart Monitor/phase README as current direction when it conflicts with living sources.

The exact current continuation point is maintained in `docs/current_status.md`.
