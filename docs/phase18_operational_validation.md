# Phase 18 — Paper Provider Mutation Lifecycle Validation

**Status: ACTIVE / draft PR #18. Last synchronized: 2026-08-23.**

Phase 18 certifies the first real paper/sandbox provider-mutation lifecycle on top of accepted Phase 17 read-only readiness. It does **not** promote live trading and does not fabricate production strategy/model/AI lineage merely to test a broker API.

The phase is explicitly split at the real-provider authority boundary:

- **Phase 18A — Pre-mutation software validation: ACCEPTED / COMPLETE**.
- **Phase 18B — Real paper-provider operational certification: WAITING_EXTERNAL**.

Phase 19 is not active while Phase 18 remains open.

## 1. Accepted upstream binding

- Phases 1–17 accepted and merged.
- Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.
- Phase 17 policy fingerprint: `693113bbb09458ed2939e486f9f6e0a0bda44e331c6419065760586047b93ff8`.
- Phase 17 real provider read-only acceptance:
  - Webull sandbox reconciled/flat;
  - Alpaca paper reconciled/flat;
  - provider mutation endpoint invocations 0;
  - provider writes 0;
  - live writes 0;
  - target-machine regression 874 passed;
  - Windows/Ubuntu CI passed.

## 2. Phase 18 policy lock

Contract:

`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Fingerprint:

`9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`

Locked requirements:

- required brokers exactly Webull and Alpaca;
- reads allowed;
- provider mutation disabled by default;
- explicit target-machine per-run authorization required;
- exactly one broker selected per mutation run;
- pre/post reconciliation required;
- fresh realtime quote required;
- current risk revalidation required;
- provider preflight required;
- protective geometry required;
- deterministic/idempotent client-order identity required;
- uncertain write blocks further mutation until exact reconciliation;
- destructive cleanup/flatten is separate authority;
- live execution not promoted;
- automatic cross-broker failover disabled;
- credential/raw account secret exposure forbidden.

## 3. Authority gate

Real paper-provider mutation remains behind:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

The operational runner requires both:

- `--authorize-paper-provider-mutation`;
- exact confirmation text `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credentials, configured endpoints, `ATLAS_ENV`, account connectivity, Phase 17 acceptance, Phase 18A acceptance, implementation existence, or passing tests/CI cannot substitute for this authorization.

Without authorization the runner must stop before broker initialization.

## 4. Two validation paths

### 4.1 Production execution semantic validation

`packages/execution/phase18_lifecycle.py`

This path wraps the accepted Phase 15 `ExecutionEngine` against fake providers to prove the production path still enforces:

- selected broker authority;
- fresh quote;
- Phase 13 risk envelope;
- account/order/position reconciliation;
- provider preflight;
- protective geometry;
- deterministic client IDs/idempotency;
- existing exposure blocking;
- uncertainty blocking;
- no automatic failover;
- no automatic flatten after fills.

### 4.2 Real-provider operational certification

`packages/execution/phase18_operational_validation.py`

This is a deliberately separate validation-only order. It is **not**:

- a strategy signal;
- a Phase 13 production case;
- a Phase 14 AI-reviewed case;
- a model outcome;
- performance evidence;
- a live-money trade authorization.

This separation prevents broker plumbing certification from contaminating model/strategy/AI lineage.

## 5. Operational validation order

Contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

Locked order:

- environment: PAPER/SANDBOX only;
- instrument: EQUITY only;
- side: BUY only;
- quantity: exactly 1 share;
- order type: LIMIT;
- time in force: DAY;
- extended hours: false;
- entry: 5% below a fresh realtime bid;
- stop: 2% below entry;
- target: 2% above entry;
- absolute notional cap: $1,000;
- accepted Phase 13 single-name notional cap: 10% of current equity;
- accepted Phase 13 loss-at-stop cap: 0.5% of current equity.

The entry is intentionally 5% below bid so it is normally nonmarketable and expected to remain open long enough to exercise submit/reconcile/cancel. This is not a fill guarantee.

Expected normal lifecycle:

`submit once -> exact deterministic client-ID reconcile -> cancel once while open -> reconcile zero-open/flat`

## 6. Fill/partial-fill behavior

If a validation order fills or partially fills:

- do not submit an opposite order automatically;
- do not flatten automatically;
- do not switch brokers automatically;
- stop and require separate explicit cleanup authority.

Paper/sandbox does not eliminate the need for deterministic mutation semantics.

## 7. Uncertain mutation behavior

If submit or cancel becomes uncertain:

1. attempt read-only exact reconciliation if possible;
2. do not retry blindly;
3. do not perform a second mutation;
4. do not auto-flatten;
5. do not fail over to Alpaca;
6. stop until exact provider state is established.

An uncertainty result is not certification success.

## 8. Pre-submit gates

Before any real submit:

1. exact Phase 18 per-run authorization and selected-broker match;
2. PAPER adapter only;
3. broker/account reconciliation succeeds;
4. zero open orders;
5. zero positions for the initial certification run;
6. account not trading-blocked;
7. positive current equity;
8. adequate buying power;
9. Phase 13 risk envelope passes;
10. deterministic validation client-order ID proven absent;
11. provider preflight accepts;
12. fresh realtime quote/geometry/notional contract passes.

Only a specific order-not-found result proves the deterministic client ID is absent. Ambiguous lookup errors block mutation.

## 9. Realtime quote authority

Real operational certification uses the accepted Phase 5/15 live-state path rather than a new ad hoc quote client.

Launcher:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_market_state.py `
  --feed realtime `
  --minute-symbols "" `
  --quote-symbols <TICKER> `
  --no-journal
```

The stream must remain running while the operational validation command reads the live-state snapshot.

`Phase15LiveQuoteResolver` requires:

- `connection_state == SUBSCRIBED`;
- `feed_mode == REALTIME`;
- expected delay 0;
- no open transport gap;
- regular-session state;
- exact provider-native ticker exactly once;
- quote exists and is `FRESH`;
- quote itself is realtime/undelayed/regular-session.

Weekends, holidays, stopped streams, stale/delayed data, premarket, and after-hours fail closed. The quote gate must never be weakened merely to force certification.

## 10. Target-machine runner

`scripts/run_phase18_operational_validation.py`

Requires:

- `--broker webull|alpaca`;
- `--ticker <exact provider-native ticker>`.

No default ticker and no quantity parameter exist.

### Plan-only behavior

Without mutation authorization:

- no broker adapter initialization;
- no provider reads through a broker adapter;
- no provider writes;
- plan evidence may be inspected from accepted local live-state data only;
- output returns the plan-only/zero-provider-call disposition when valid.

Wrong confirmation also stops before broker initialization.

## 11. Mutation gate diagnostic

`scripts/diagnose_phase18_mutation_gate.py --broker webull`

Expected default result:

- selected broker webull;
- provider adapter initialized NO;
- provider calls 0;
- provider writes 0;
- live disabled;
- automatic failover disabled;
- authorization gate DENIED;
- required confirmation `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

DENIED is the correct result before explicit authorization.

## 12. Automated coverage

### Authorization

- no authorization denied;
- false flag denied;
- wrong confirmation denied;
- unknown broker denied;
- exact Webull/Alpaca local authorization accepted only as a gate object, not provider authority by itself.

### Production semantic fake lifecycle

- submit/reconcile/cancel/reconcile flat;
- fill -> no automatic flatten;
- uncertain submit -> no second mutation;
- uncertain cancel -> no retry;
- existing exposure blocks;
- broker mismatch blocks.

### Operational validation

- one-share nonmarketable BUY geometry;
- deterministic broker-specific order identity;
- delayed/nonrealtime rejection;
- nonregular-session rejection;
- >$1,000 notional rejection;
- trading-blocked rejection;
- buying-power rejection;
- Phase 13 risk rejection;
- preflight rejection -> no submit;
- existing client ID -> no new write;
- unexpected terminal status not accepted as success;
- fill -> no automatic flatten;
- uncertain submit/cancel -> no retry;
- existing position blocks;
- broker mismatch blocks.

### Runner

- plan-only initializes no broker;
- wrong confirmation initializes no broker;
- blocked/stale quote initializes no broker.

## 13. Independent validator

`scripts/validate_phase18.py` verifies:

- exact Phase 17 binding;
- exact Phase 18 fingerprint;
- provider mutations disabled by default;
- exact confirmation token;
- live disabled;
- auto-failover disabled;
- operational contract exact;
- quantity 1;
- entry offset 5%;
- protective fraction 2%;
- max notional $1,000;
- accepted Phase 13 risk fraction 0.5%;
- accepted Phase 13 single-name fraction 10%.

## 14. Phase 18A — repository and CI evidence

First portability-hardening code head:

`45a2abeba7a51401ee708ab777d960d2f7fea88f`

CI run `32657554236`:

- all validators through Phase 18 PASS;
- Ubuntu: 908 passed;
- Windows: 908 passed;
- both jobs SUCCESS;
- provider writes 0.

Contract-preserving Windows transport hardening code head:

`38c09c21d4fc636667921c779fbe59341839e9e8`

CI run `32662398274`:

- all validators through Phase 18 PASS;
- Ubuntu: **908 passed in 13.95s**;
- Windows: **908 passed in 22.59s**;
- both jobs SUCCESS;
- provider writes 0.

Baseline `94a859fc6d44c22a6f8852c1488215a6677806a0` also completed GitHub Actions run `32662817172` successfully on Ubuntu and Windows with all validators through Phase 18 green.

## 15. Phase 18A — target-machine evidence

Initial pre-mutation block:

- Phase 18 validator PASS;
- focused Phase 18 tests 34 passed in 2.23s;
- Webull sandbox read-only recheck: selected account configured, account list/balance/orders/positions HTTP 200, 0 open orders, 0 positions;
- Alpaca paper: reconciled, 0 open orders, 0 positions;
- mutation gate: adapter initialized NO, provider calls 0, provider writes 0, authorization DENIED correctly.

The first local full regression exposed only a Windows loopback transport abort in the pre-existing Phase 16 CSRF test. The issue was isolated to test-host transport behavior and hardened without modifying production Phase 16 HTTP code or broker/execution behavior.

Final target-machine acceptance at baseline:

`94a859fc6d44c22a6f8852c1488215a6677806a0`

- isolated CSRF test: **1 passed in 3.30s**;
- full regression: **908 passed in 23.50s**;
- final `git status --short`: clean;
- provider calls during final recheck: 0;
- provider writes during final recheck: 0.

**Phase 18A disposition: ACCEPTED / COMPLETE. No software or portability blocker remains.**

## 16. Windows loopback portability hardening

First test-only hardening:

`45a2abeba7a51401ee708ab777d960d2f7fea88f`

- deterministic loopback test opener includes `urllib.request.ProxyHandler({})` so ambient proxy configuration does not intercept `127.0.0.1` traffic.

Second test-only hardening:

`38c09c21d4fc636667921c779fbe59341839e9e8`

The foreign-origin test:

1. directly calls `ControlPlaneSessionGuard.authorize_write()` and requires `allowed is False` with `SAME_ORIGIN_REQUIRED`;
2. still requires HTTP 403 normally;
3. accepts only exact Windows `ConnectionAbortedError` with `winerror == 10053` as an alternate host-transport manifestation after rejection is already proven;
4. still requires zero action/audit events;
5. fails every other transport error.

Unchanged production scope:

- `packages/control_plane/http_server.py` unchanged;
- `packages/control_plane/session.py` unchanged;
- broker adapters unchanged;
- execution lifecycle unchanged;
- Phase 18 policy unchanged;
- provider authority unchanged.

## 17. Phase 18B — remaining real certification sequence

**State: WAITING_EXTERNAL**

Waiting conditions:

- regular U.S. equity session;
- accepted Massive realtime focused quote state;
- explicit user authorization only after plan-only review.

When those conditions are available:

1. choose exact provider-native ticker suitable for the one-share <$1,000 validation cap;
2. start focused Massive realtime `Q.<ticker>` stream;
3. keep the stream active;
4. run Phase 18 plan-only operational validation;
5. verify 0 broker/provider calls/writes in plan-only mode;
6. inspect the one-share entry/stop/target/risk plan;
7. obtain explicit `PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION` approval;
8. certify Webull sandbox first;
9. submit exactly once;
10. reconcile exact deterministic client ID;
11. cancel exactly once if still open;
12. reconcile zero-open/flat;
13. if filled/partially filled, stop for separate cleanup authorization;
14. never automatically fail over to Alpaca;
15. save only sanitized evidence;
16. rerun validators/regression only if code changes or acceptance evidence requires it;
17. update README/roadmap/current-status/spec/PR;
18. mark PR #18 ready and merge only after accepted target-machine Phase 18B evidence;
19. verify `main` and delete merged Phase 18 branch;
20. only then define and activate Phase 19.

## 18. Acceptance boundary after Phase 18

Successful Phase 18 acceptance will mean only that ATLAS can safely perform the accepted **paper/sandbox provider mutation lifecycle** under explicit authority and reconciliation.

It will **not** mean:

- live trading is authorized;
- automatic broker failover is authorized;
- strategy/model authority changed;
- browser actions independently authorize execution;
- cleanup/flatten is universally authorized.

Any live-money transition remains a separate future preregistered phase with explicit user authorization.

## 19. Phase-flow binding

Phase 18 follows `docs/phase_flow.md`.

The phase cannot be marked accepted/merged until Phase 18B evidence is complete. Phase 19 cannot become active until Phase 18 is accepted and merged, then Phase 19 must itself be defined and locked before implementation.