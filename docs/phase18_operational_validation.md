# Phase 18 — Paper Provider Mutation Lifecycle Validation

**Status: ACTIVE / draft PR #18. Last synchronized: 2026-08-23.**

Phase 18 certifies the first real paper/sandbox provider-mutation lifecycle on top of accepted Phase 17 read-only readiness. It does **not** promote live trading and does not fabricate production strategy/model/AI lineage merely to test a broker API.

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

Credentials, configured endpoints, `ATLAS_ENV`, account connectivity, Phase 17 acceptance, Phase 18 implementation, or passing tests/CI cannot substitute for this authorization.

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

Therefore weekends, holidays, stopped streams, stale/delayed data, premarket, and after-hours fail closed. Since 2026-08-23 is Sunday, a real provider-mutation certification is intentionally invalid today.

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
- required confirmation shown as `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

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

## 14. Repository/CI evidence

The main Phase 18 implementation reached 908/908 Windows+Ubuntu test success with all validators green before target-machine pre-mutation testing.

First portability-hardening code head:

`45a2abeba7a51401ee708ab777d960d2f7fea88f`

CI run:

`32657554236`

Results:

- all validators through Phase 18 PASS;
- Ubuntu: **908 passed in 13.57s**;
- Windows: **908 passed in 20.98s**;
- both jobs SUCCESS;
- real provider writes in CI: 0.

Current contract-preserving Windows transport hardening code head:

`38c09c21d4fc636667921c779fbe59341839e9e8`

This change is test-only and is being validated by the current GitHub Actions run. Ubuntu has completed successfully; Windows must also complete successfully before repository-side closeout of this portability issue.

## 15. Target-machine pre-mutation evidence

### 15.1 Initial pre-mutation block

At local head `e1631e741a547c78eb6c3c9b943ba1473c805cf6`, the complete pre-mutation block produced:

- Phase 18 validator PASS;
- Phase 18 focused tests **34 passed in 2.23s**;
- Webull sandbox:
  - selected sanitized account ref configured;
  - account list HTTP 200;
  - balance HTTP 200;
  - open orders HTTP 200 / 0 orders;
  - positions HTTP 200 / 0 positions;
- Alpaca paper:
  - reconciled true;
  - 0 open orders;
  - 0 positions;
  - safe-to-switch true;
- mutation gate:
  - adapter initialized NO;
  - provider calls 0;
  - provider writes 0;
  - authorization DENIED correctly;
- final Git working tree clean.

Full local suite: **907 passed / 1 failed in 31.73s**.

The only failure was the pre-existing Phase 16 loopback CSRF test:

`tests/unit/test_phase16_action_api.py::test_csrf_failure_creates_no_action_event`

Windows reported `WinError 10053` while waiting for the expected HTTP 403 response.

### 15.2 Rerun after proxy bypass

At local documentation head `36c9832891b8565f75b727db7dfc231719be5006` after pulling the first test-client hardening:

- isolated CSRF test: **1 passed in 3.52s**;
- immediately following full regression: **907 passed / 1 failed in 24.04s**;
- sole failure: same CSRF test on its second foreign-origin request;
- error: `ConnectionAbortedError: [WinError 10053]` while waiting for the expected 403;
- final working tree clean.

The fact that the exact isolated test passed immediately before the full-suite failure demonstrates the local behavior is nondeterministic host transport/security interception under suite load, not a deterministic ATLAS authorization failure.

## 16. Loopback test portability hardening

### 16.1 First fix — remove ambient proxy routing

Commit:

`45a2abeba7a51401ee708ab777d960d2f7fea88f`

The test opener includes:

```python
urllib.request.ProxyHandler({})
```

before the cookie handler so deterministic loopback requests do not inherit user/OS proxy configuration.

### 16.2 Current fix — separate application security proof from host transport

Commit:

`38c09c21d4fc636667921c779fbe59341839e9e8`

The foreign-origin test now first calls `ControlPlaneSessionGuard.authorize_write()` directly and requires:

- `allowed is False`;
- `error_code == "SAME_ORIGIN_REQUIRED"`.

It then exercises the actual loopback HTTP request:

- normal/clean-host result must be HTTP `403`;
- only `ConnectionAbortedError` with exact Windows `winerror == 10053` is accepted as an alternate host-transport manifestation of the already-proven rejection;
- every other socket/transport error still fails;
- ledger event count must remain 0.

This preserves the accepted Phase 16 same-origin security contract while preventing local Windows endpoint-security behavior from being misclassified as an ATLAS application failure.

Scope remains deliberately narrow:

- production `packages/control_plane/http_server.py`: unchanged;
- `packages/control_plane/session.py`: unchanged;
- broker adapters: unchanged;
- execution lifecycle: unchanged;
- Phase 18 policy: unchanged;
- provider authority: unchanged;
- provider writes: none.

## 17. Immediate local recheck

After the current CI and documentation commits settle, pull the latest branch and rerun only:

1. the isolated CSRF test;
2. the full suite;
3. `git status --short`.

Expected full result: **908 passed**.

No broker/provider read diagnostics are required solely because the code changes since the prior target-machine run are test-harness-only plus documentation.

## 18. Real certification sequence — future regular session

After local regression is green:

1. choose an exact provider-native ticker suitable for the one-share <$1,000 validation cap;
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
16. rerun validators/regression as needed;
17. update README/roadmap/current-status/spec/PR;
18. mark PR ready and merge only after accepted target-machine evidence;
19. delete merged Phase 18 branch after closeout.

## 19. Acceptance boundary after Phase 18

Successful Phase 18 acceptance will mean only that ATLAS can safely perform the accepted **paper/sandbox provider mutation lifecycle** under explicit authority and reconciliation.

It will **not** mean:

- live trading is authorized;
- automatic broker failover is authorized;
- strategy/model authority changed;
- browser actions independently authorize execution;
- cleanup/flatten is universally authorized.

Any live-money transition remains a separate future preregistered phase with explicit user authorization.
