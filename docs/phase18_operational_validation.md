# Phase 18 — Paper Provider Mutation Lifecycle Validation

**Status: ACCEPTED / CLOSEOUT PENDING MERGE. Last synchronized: 2026-08-24.**

Phase 18 certifies the first real paper/sandbox provider-mutation lifecycle on top of accepted Phase 17 read-only readiness. It does **not** promote live trading, automatic broker failover, universal cleanup authority, or fabricated strategy/model/AI lineage.

Subphase disposition:

- **Phase 18A — Pre-mutation software validation: ACCEPTED / COMPLETE**.
- **Phase 18B — Real paper-provider operational certification: ACCEPTED / COMPLETE**.
- **Phase 19 — STACKED_PREP only** on its stacked branch/PR; it remains merge-blocked until Phase 18 is merged, then must be rebased/retargeted to merged `main` and revalidated.

## 1. Accepted upstream binding

- Phases 1–17 accepted and merged.
- Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.
- Phase 17 policy fingerprint: `693113bbb09458ed2939e486f9f6e0a0bda44e331c6419065760586047b93ff8`.
- Phase 17 accepted Webull sandbox + Alpaca paper reconciliation: flat, zero open orders, provider writes 0.

## 2. Phase 18 policy lock

Contract:

`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Fingerprint:

`9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`

Locked requirements:

- required brokers exactly Webull and Alpaca;
- reads allowed;
- provider mutation disabled by default;
- explicit per-run target authorization required;
- exactly one broker selected per mutation run;
- pre/post reconciliation required;
- fresh realtime quote required;
- current risk revalidation required;
- provider preflight required;
- protective geometry required;
- deterministic/idempotent client-order identity required;
- uncertain writes block further mutation until exact reconciliation;
- destructive cleanup/flatten remains separate authority;
- live execution not promoted;
- automatic cross-broker failover disabled;
- credentials/raw account identifiers/request signatures must not appear in operator output.

## 3. Authority gate

Real paper-provider mutation is behind:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

A real run requires both:

- `--authorize-paper-provider-mutation`;
- exact confirmation text `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credentials, endpoints, environment mode, account connectivity, prior acceptance, implementation existence, or passing CI cannot substitute for this gate.

Without authorization the runner stops before broker initialization.

## 4. Validation paths

### 4.1 Production execution semantic validation

`packages/execution/phase18_lifecycle.py`

This path uses fake providers to prove the accepted Phase 15 production path still enforces selected-broker authority, fresh quote, Phase 13 risk, reconciliation, provider preflight, protective geometry, deterministic IDs/idempotency, existing-exposure blocking, uncertainty blocking, no automatic failover, and no automatic flatten after fills.

### 4.2 Real-provider operational certification

`packages/execution/phase18_operational_validation.py`

This is a deliberately separate validation-only provider order. It is not a strategy signal, Phase 13 production case, Phase 14 AI-reviewed case, model outcome, performance evidence, or live-money authorization.

## 5. Locked operational certification order

Contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

Locked order:

- PAPER/SANDBOX only;
- EQUITY BUY only;
- quantity exactly 1 share;
- LIMIT / DAY;
- extended hours false;
- entry 5% below a fresh realtime bid;
- stop 2% below entry;
- target 2% above entry;
- absolute notional <= $1,000;
- accepted Phase 13 single-name notional <= 10% current equity;
- accepted Phase 13 loss-at-stop <= 0.5% current equity.

Expected normal lifecycle:

`fresh quote -> plan-only -> explicit authorization -> flat reconciliation -> prove client ID absent -> provider preview -> submit once -> exact reconcile -> cancel once if open -> exact terminal reconciliation -> flat/zero-open reconciliation`

## 6. Realtime quote authority

Massive remains the accepted broad-market/reference-data provider. Phase 18 discovered that the current Massive plan authorizes delayed aggregate streaming but rejects realtime `Q.<ticker>` quote subscriptions.

Phase 18 therefore added an explicit Webull sandbox L1 execution-evidence path without changing broad-market authority:

1. `scripts/capture_phase18_webull_quote.py` makes exactly one read-only Webull L1 depth request;
2. it stores a sanitized local snapshot;
3. `scripts/run_phase18_operational_validation.py --quote-source webull-snapshot` reads only that local evidence before authorization;
4. plan-only mode still initializes no broker adapter and makes zero provider calls/writes.

Execution evidence requires:

- exact requested ticker;
- positive bid/ask with `ask >= bid`;
- provider timestamp not in the future;
- quote age <= **30 seconds** at the execution boundary;
- realtime/undelayed classification;
- regular U.S. equity session.

Premarket, after-hours, weekend/holiday, stale, delayed, malformed, or wrong-ticker evidence fails closed.

Target-machine entitlement evidence on 2026-08-24 proved local Webull sandbox L1 quotes were fresh rather than the default delayed sandbox behavior.

## 7. Webull provider operating-rate policy

Locked ATLAS policy as of 2026-08-24:

- normal sustained Webull **read** traffic targets **80% of the most specific current documented endpoint limit**;
- endpoint-specific limits override broader/global provider ceilings;
- no normal 90% sustained target;
- any future temporary higher read burst must be separately bounded, read-only, and below the provider hard limit;
- mutation throughput is governed by ATLAS risk/reconciliation/idempotency semantics, **not** by Webull's maximum order-rate allowance;
- sustained realtime candidate monitoring should prefer Webull streaming/MQTT rather than high-rate HTTP polling;
- HTTP 429 on reads triggers cooldown/backoff, never a tight retry loop;
- mutation ambiguity or rate-limit errors fail closed and require reconciliation before any later mutation;
- automatic broker failover remains forbidden.

This policy is intentionally conservative so ATLAS can operate near useful provider capacity without riding the hard boundary.

## 8. Provider-specific hardening discovered during Phase 18B

### 8.1 Webull explicit order absence

Webull sandbox Order Detail can raise an SDK exception for HTTP 417 / `OPENAPI_PARAM_ERR` with the explicit message `Order not present`.

ATLAS now normalizes **only that exact absence condition** to `BrokerOrderNotFound`, allowing deterministic client-order-ID absence to be proven. Other 417/provider errors remain failures.

### 8.2 Sensitive SDK logging

The Webull SDK can log signed request metadata on errors. ATLAS suppresses the relevant SDK loggers and emits sanitized operator-facing errors instead.

### 8.3 Post-cancel read consistency

The accepted target run proved Webull can acknowledge cancellation while immediate exact reads briefly fail to prove `CANCELLED`.

ATLAS now sends the cancel request **at most once**, then performs bounded read-only reconciliation using exact Order Detail and exact Order History. It never issues a second cancel because of read lag. If exact `CANCELLED` cannot be proven inside the bounded window, state remains uncertain and the lifecycle fails closed.

## 9. Phase 18A acceptance evidence

Final Phase 18A target-machine baseline:

`94a859fc6d44c22a6f8852c1488215a6677806a0`

Evidence:

- isolated Phase 16 Windows CSRF transport test: 1 passed in 3.30s;
- full target regression: **908 passed in 23.50s**;
- working tree clean;
- provider calls 0;
- provider writes 0;
- Windows/Ubuntu CI green with all validators through Phase 18.

**Phase 18A: ACCEPTED / COMPLETE.**

## 10. Phase 18B target-machine acceptance evidence — 2026-08-24

### 10.1 Webull market-data entitlement

Read-only AAPL sandbox L1 probe:

- HTTP 200;
- fresh bid/ask returned;
- provider timestamp approximately 20 seconds old on first entitlement probe;
- later captures consistently sub-2-second during active market;
- provider writes 0;
- broker writes 0.

### 10.2 Premarket fail-closed proof

At 09:18 ET and 09:25 ET:

- fresh Webull AAPL quotes were captured;
- `session_segment: premarket`;
- Phase 18 plan returned `BLOCKED` solely because the session was outside regular hours;
- broker adapter initialized NO;
- plan-step provider calls 0;
- provider writes 0.

### 10.3 Regular-session plan-only proof

At 09:31 ET:

- AAPL bid/ask `311.06 / 311.17`;
- quote age `0.322s`;
- session `regular`;
- one-share plan entry/stop/target `295.51 / 289.60 / 301.42`;
- planned notional `$295.51`;
- geometry valid: `289.60 < 295.51 < 301.42`;
- authorization not requested;
- broker adapter initialized NO;
- provider calls 0;
- provider writes 0;
- disposition `PLAN_ONLY_ZERO_PROVIDER_CALLS`.

### 10.4 First authorized attempt — no mutation

An explicitly authorized Webull sandbox run reached the idempotency query and stopped because the SDK's explicit `Order not present` 417 was not yet normalized.

Evidence:

- failure stage `idempotency_query`;
- provider state certain;
- final reconciliation available;
- 0 open orders;
- 0 positions;
- no submit/cancel mutation occurred.

This exposed and led to the exact-absence normalization and SDK-log hardening described above.

### 10.5 Accepted authorized Webull sandbox lifecycle

A later explicitly authorized run used:

- ticker `AAPL`;
- fresh regular-session bid/ask `311.33 / 311.39`;
- provider quote timestamp `2026-08-24T13:51:49.262000+00:00`;
- quote age `0.823s`;
- deterministic validation client ID `p18v-13abada37159d4486df293b3695`;
- entry/stop/target `295.76 / 289.84 / 301.68`;
- planned notional `$295.76`;
- explicit mutation authorization accepted;
- exactly one Webull sandbox adapter initialized.

The run proved:

1. pre-reconciliation flat/zero-open;
2. deterministic client ID absent;
3. provider preflight accepted;
4. validation order submitted exactly once;
5. exact post-submit order reconciliation succeeded;
6. cancellation was attempted exactly once;
7. immediate post-cancel exact read was temporarily inconclusive, so ATLAS stopped with no retry/failover;
8. read-only reconciliation still showed 0 open orders and 0 positions.

A subsequent **read-only** exact postmortem then proved:

- Order Detail: `FOUND`, `CANCELLED`;
- Order History: `FOUND`, `CANCELLED`;
- ticker `AAPL`;
- requested quantity `1.0`;
- filled quantity `0.0`;
- open-order count `0`;
- position count `0`;
- exact client ID not open;
- account flat and zero-open;
- provider writes during postmortem `0`;
- broker writes during postmortem `0`.

This is definitive evidence that the real paper/sandbox lifecycle completed as intended: **submit once -> exact reconcile -> cancel once -> exact CANCELLED -> flat/zero-open**, with no fill, no cleanup required, no blind retry, and no failover.

**Phase 18B: ACCEPTED / COMPLETE.**

## 11. Closeout code evidence

Post-target hardening adds bounded read-only post-cancel reconciliation while retaining exactly-one-cancel semantics. Its regression coverage proves the exact-history fallback can establish `CANCELLED` without invoking cancellation a second time.

The final Phase 18 acceptance boundary requires:

- Phase 18 validator green;
- full pytest regression green;
- Ubuntu CI green;
- Windows CI green;
- living docs/PR synchronized.

No second target-machine mutation is required solely to validate this read-only reconciliation hardening because the real target lifecycle already produced definitive exact `CANCELLED` evidence and the code change does not add provider mutation authority.

## 12. Acceptance meaning

Phase 18 acceptance proves only that ATLAS can safely perform the accepted explicit **paper/sandbox** provider mutation/reconciliation lifecycle.

It does **not** mean:

- live trading is authorized;
- automatic broker failover is authorized;
- cleanup/flatten is universally authorized;
- strategy/model/AI authority changed;
- browser actions independently authorize execution;
- provider rate ceilings are trading throughput targets.

Any live-money transition remains a separate future preregistered phase with separate explicit authorization.

## 13. Phase-flow closeout

Once the final code/docs CI boundary is green:

1. mark PR #18 ready;
2. merge Phase 18 into `main`;
3. verify merged `main`;
4. preserve/delete branches according to repository policy;
5. rebase/retarget the already-stacked Phase 19 observability PR onto merged `main`;
6. rerun Phase 19 validator/full regression/Windows+Ubuntu CI;
7. only then treat Phase 19 as the active numbered phase.
