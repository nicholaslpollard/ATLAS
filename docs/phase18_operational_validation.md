# Phase 18 — Paper Provider Mutation Operational Validation

**Living Phase 18 implementation/acceptance document. Last synchronized: 2026-08-23.**

This document records the exact design and evidence for the first real paper/sandbox provider-mutation certification. It supplements `README.md`, `docs/roadmap.md`, and `docs/current_status.md`; those remain the project-level living handoff documents.

## 1. Purpose

Phase 18 validates that ATLAS can safely perform and reconcile a real paper/sandbox provider write without granting live-money authority or weakening accepted Phase 15/16 execution controls.

This is an **operational broker certification**, not a strategy trade. It must not fabricate Phase 13/14 trade-case lineage merely to exercise a broker API.

Current branch:

`phase-18-paper-provider-mutation-lifecycle-validation`

Current PR:

`#18 — Phase 18: Paper Provider Mutation Lifecycle Validation`

Accepted upstream:

- Phases 1–17 accepted and merged;
- Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`;
- Phase 17 policy fingerprint: `693113bbb09458ed2939e486f9f6e0a0bda44e331c6419065760586047b93ff8`;
- Phase 17 real-provider readiness: Webull sandbox + Alpaca paper AVAILABLE/reconciled, zero orders/positions, zero provider mutation endpoint invocations, zero provider writes, zero live writes;
- Phase 17 target-machine regression: 874 passed.

## 2. Authority boundary

Phase 18 repository/CI preparation is allowed without real provider writes.

Real paper/sandbox mutation is **disabled by default** and remains behind:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

A real mutation run must provide both:

1. `--authorize-paper-provider-mutation`;
2. exact confirmation text `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

The selected broker must also match the adapter and validation plan.

None of the following grants authority by itself:

- credential presence;
- endpoint configuration;
- `ATLAS_ENV`;
- broker selection;
- a connected account;
- Phase 17 acceptance;
- Phase 18 code existence;
- a passing test/validator;
- a successful plan-only preview.

Live execution remains disabled. Automatic cross-broker failover remains disabled.

## 3. Phase 18 policy contract

Contract:

`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Policy fingerprint:

`9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`

Locked rules:

- required brokers exactly Webull and Alpaca;
- provider reads allowed;
- provider mutations disabled by default;
- explicit per-run target-machine authorization required;
- one broker per mutation run;
- pre- and post-mutation reconciliation required;
- fresh quote required;
- current risk revalidation required;
- protective geometry required;
- deterministic client-order ID required;
- uncertain provider write blocks all further mutation until exact reconciliation;
- destructive cleanup/flatten requires separate explicit authority;
- live promotion forbidden;
- automatic cross-broker failover forbidden;
- credential/account-secret exposure forbidden.

## 4. Two validation paths and why they are separate

### 4.1 Production-path semantic validation

`packages/execution/phase18_lifecycle.py` wraps the accepted Phase 15 `ExecutionEngine` with fake providers in tests. Its purpose is to prove the production execution path retains:

- accepted `ExecutionIntent` validation;
- fresh-quote semantics;
- current risk revalidation;
- provider preflight;
- reconciliation;
- protective geometry;
- deterministic/idempotent client-order IDs;
- uncertain-write fail-closed behavior;
- no automatic failover;
- no automatic flatten after fill.

This path is exercised in CI with synthetic/fake execution evidence only. It is **not** used to invent a fake production trade for real-provider certification.

### 4.2 Real-provider operational certification

`packages/execution/phase18_operational_validation.py` defines a separate validation-only order contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

This order is explicitly **not** a strategy signal, Phase 13 case, Phase 14 AI-reviewed case, production execution intent, or model/strategy outcome. It exists only to certify broker plumbing and reconciliation.

It must never be interpreted as strategy performance evidence or persisted as a production trade recommendation.

## 5. Locked operational validation order

The operational order shape is intentionally small and conservative:

- environment: PAPER/SANDBOX only;
- instrument: EQUITY only;
- side: BUY only;
- quantity: exactly **1 share**;
- order type: LIMIT;
- time in force: DAY;
- extended hours: false;
- bracket/protective geometry required;
- entry limit: **5% below the fresh realtime bid**;
- stop: **2% below entry**;
- target: **2% above entry**;
- maximum validation notional: **$1,000**.

The 5% below-bid entry is intentionally nonmarketable under normal conditions so the expected certification lifecycle is:

`accepted order -> exact reconcile -> cancel -> exact reconcile flat`

It is not a guarantee against a fill. If the market moves enough to fill or partially fill the order, ATLAS stops and requires a separate cleanup authority; it does not auto-flatten.

## 6. Quote requirements

The plan builder independently requires:

- `LiveFeedMode.REALTIME`;
- expected feed delay = 0;
- regular-session quote;
- positive bid and ask;
- ask >= bid;
- valid protective geometry after 2-decimal price rounding;
- notional <= $1,000.

The runner obtains quote evidence through the already accepted Phase 15 `Phase15LiveQuoteResolver`, which reads the ATLAS live-state snapshot. That resolver additionally requires:

- live-state file exists and validates;
- connection state = `SUBSCRIBED`;
- effective feed = realtime;
- expected delay = 0;
- no unresolved WebSocket transport gap;
- session segment = regular;
- exactly one exact provider-native ticker match;
- quote exists;
- quote freshness = `FRESH`;
- quote itself is realtime/undelayed/regular-session.

The resolver does **not** start a stream and does not silently fall back to stale/delayed data.

## 7. Accepted live-state startup path

The existing accepted launcher is:

`scripts/run_live_market_state.py`

For Phase 18 certification it should run a focused quote subscription only, rather than broad minute data:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_market_state.py `
  --feed realtime `
  --minute-symbols "" `
  --quote-symbols <TICKER> `
  --no-journal
```

This uses `LiveMarketService` and the accepted Massive realtime WebSocket path. The focused subscription is `Q.<ticker>`.

The stream must remain active while the Phase 18 runner reads the live-state snapshot. When the live service stops it writes a final STOPPED snapshot, which is intentionally rejected by `Phase15LiveQuoteResolver` for execution evidence.

Because regular-session realtime evidence is mandatory, a real Phase 18 mutation cannot be accepted on weekends, market holidays, premarket, or after-hours. The gate must not be weakened merely to make a test convenient.

## 8. Operational risk revalidation

Before provider preview/submission, the selected broker must reconcile and satisfy:

- `reconciled=true`;
- zero open orders;
- zero positions;
- account not trading-blocked;
- positive equity;
- validation notional <= current buying power;
- validation notional / equity <= accepted Phase 13 single-name notional limit **10%**;
- loss-at-stop / equity <= accepted Phase 13 risk-per-trade limit **0.5%**.

The validation order also retains the separate absolute $1,000 notional cap.

If any risk/account check fails, no provider preview or submit is attempted.

## 9. Idempotency and order identity

The validation client-order ID is deterministic from:

- operational-validation contract version;
- selected broker;
- exact provider-native ticker;
- exact provider quote timestamp;
- entry/stop/target prices.

Before submitting, ATLAS queries the exact client-order ID:

- `BrokerOrderNotFound` is the only accepted proof that the ID is absent;
- another lookup failure is ambiguous and blocks the write;
- if the client-order ID already exists, a new write is blocked.

Provider acknowledgement must preserve the expected client-order ID and broker identity.

## 10. Provider preflight and mutation sequence

The selected broker must pass provider/local preflight before submit.

Expected lifecycle:

1. exact per-run authorization validated;
2. selected broker adapter initialized;
3. account/orders/positions reconciled;
4. flat/zero-open state proven;
5. current risk envelope proven;
6. exact client-order ID absence proven;
7. provider preflight accepted;
8. submit exactly once;
9. reconcile exact client-order ID;
10. if open, cancel exactly once;
11. post-cancel reconcile;
12. success only if broker returns to flat/zero-open state.

No second broker is used if the selected broker rejects, disconnects, times out, or becomes uncertain.

## 11. Uncertain-write handling

### Submit uncertainty

If submit throws `BrokerSubmissionUncertain`:

- attempt read-only broker reconciliation if possible;
- do **not** retry submit;
- do **not** cancel blindly;
- do **not** flatten;
- do **not** switch/fail over to Alpaca;
- stop with provider state marked uncertain.

### Cancel uncertainty

If cancel throws `BrokerMutationUncertain`:

- attempt read-only reconciliation if possible;
- do **not** retry cancel;
- do **not** flatten;
- do **not** fail over;
- stop until exact state is established.

Unknown state is never treated as permission for another mutation.

## 12. Fill / partial-fill handling

If the validation order is FILLED or PARTIAL_FILLED:

- automatic flatten = **disabled**;
- automatic opposite-side order = **disabled**;
- automatic broker failover = **disabled**;
- lifecycle returns/raises a cleanup-required disposition;
- a separate explicit cleanup authorization is required before any close/flatten mutation.

This keeps the first certification write from silently escalating into a second economic decision.

## 13. Target-machine runner

Runner:

`scripts/run_phase18_operational_validation.py`

Required arguments:

- `--broker webull|alpaca`;
- `--ticker <exact provider-native ticker>`.

There is no default ticker and no quantity argument. Quantity is locked in code.

### Plan-only default

Without `--authorize-paper-provider-mutation`, the runner:

- reads only local ATLAS live-state;
- builds/prints the validation plan if quote evidence is valid;
- initializes **no broker adapter**;
- performs **0 broker/provider calls**;
- performs **0 provider writes**;
- exits with `PLAN_ONLY_ZERO_PROVIDER_CALLS`.

### Authorization-denied behavior

If the mutation flag is present but confirmation text is wrong:

- broker adapter is not initialized;
- provider calls = 0;
- provider writes = 0;
- run stops fail-closed.

### Authorized behavior

Only after the exact authorization gate passes does the runner initialize exactly one selected paper/sandbox broker adapter and enter the operational lifecycle.

Raw broker account IDs are not printed; account identity is rendered as a 16-character SHA-256 reference.

## 14. Automated test matrix

Phase 18 tests currently cover:

### Authorization

- no authorization object denied;
- provider-mutation boolean false denied;
- incorrect confirmation denied;
- unknown broker denied;
- exact Webull authorization accepted locally;
- exact Alpaca authorization accepted locally.

### Production-path lifecycle with fakes

- pending order submit/reconcile/cancel/reconcile flat;
- filled order never auto-flattened;
- uncertain submit causes no second mutation;
- uncertain cancel causes no retry;
- existing exposure blocks first mutation;
- broker authority mismatch blocks before submit.

### Operational validation plan/lifecycle

- locked one-share BUY shape;
- deterministic same-quote identity;
- broker-specific identity;
- delayed/non-realtime quote rejected;
- non-regular quote rejected;
- >$1,000 notional rejected;
- trading-blocked account rejected before provider preflight;
- insufficient buying power rejected before provider preflight;
- Phase 13 single-name risk breach rejected before provider preflight;
- provider preflight rejection causes no submit;
- existing deterministic client ID blocks new write;
- rejected/terminal post-submit status is not certified as success;
- fill does not auto-flatten;
- uncertain submit/cancel never retries;
- pre-existing position blocks certification;
- broker authorization mismatch blocks.

### CLI runner

- plan-only mode initializes no broker;
- wrong confirmation initializes no broker;
- blocked/stale quote initializes no broker.

## 15. Independent validator

`scripts/validate_phase18.py` verifies:

- accepted Phase 17 merge/policy/readiness binding;
- exact Phase 18 policy fingerprint;
- required broker set;
- provider mutation disabled by default;
- exact authorization confirmation text;
- live disabled;
- automatic failover disabled;
- operational validation contract version;
- quantity = 1;
- entry offset = 5%;
- protective fraction = 2%;
- notional cap = $1,000;
- accepted Phase 13 risk fraction = 0.5%;
- accepted Phase 13 single-name notional fraction = 10%.

## 16. Current CI evidence

Code head:

`062efedfdc7537222c929f72ebf1f1bb57f903af`

GitHub Actions run:

- run ID `32656692232`;
- all validators through Phase 18: PASS;
- Ubuntu: **908 passed in 17.80s**;
- Windows: **908 passed in 31.79s**;
- both jobs: SUCCESS.

No CI job has provider credentials or permission to perform a real Phase 18 broker mutation. CI exercises fake-provider semantics and static/contract validation only.

## 17. Remaining Phase 18 acceptance sequence

Repository/CI preparation is now green. Remaining steps are target-machine evidence and explicit authority:

1. pull exact Phase 18 branch head;
2. run Phase 18 validator + full/targeted tests locally;
3. rerun Phase 17 provider-read diagnostic to prove both paper brokers still reconcile;
4. during a regular U.S. market session, run focused Massive realtime quote state for the chosen validation ticker;
5. run Phase 18 plan-only runner first and verify zero broker/provider calls/writes;
6. review the exact one-share validation plan;
7. obtain explicit user authorization for the real paper-provider mutation checkpoint;
8. run **Webull sandbox first** because Webull is the primary broker;
9. reconcile result;
10. if the order remains open, cancellation should return the broker to flat state;
11. if any fill/partial fill occurs, stop and obtain separate cleanup authorization;
12. never auto-fail over to Alpaca;
13. record sanitized target-machine evidence in PR #18 and living docs;
14. rerun validators/regression if code changed during target-machine closeout;
15. only then mark PR ready/merge Phase 18;
16. delete the merged Phase 18 branch after closeout.

## 18. What Phase 18 acceptance will and will not mean

If accepted, Phase 18 will prove real paper/sandbox provider mutation and reconciliation under the locked safety envelope.

It will **not** mean:

- production strategy performance is proven;
- model/strategy thresholds are changed;
- AI can authorize execution;
- automatic broker failover is allowed;
- live credentials are active;
- live trading is authorized;
- real capital may be traded.

Any future live-money promotion remains a separate architecture/design/authority phase with its own preregistration, tests, operational observation, and explicit user approval.
