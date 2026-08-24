# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-24.**

This is the fastest source for a future chat/development session to recover exact ATLAS state without reconstructing prior conversation history.

## 1. Source-of-truth order

When sources disagree, use:

1. accepted code/artifacts on `main` for completed work;
2. active/stacked PR branch code for in-progress work;
3. `docs/roadmap.md` for architecture/authority rules;
4. this file for exact current state/evidence/continuation;
5. `docs/phase_flow.md` for phase progression/cadence;
6. active/stacked phase living specification;
7. root `README.md`;
8. merged PRs for deeper historical evidence;
9. old phase/fix READMEs as provenance only.

## 2. Repository state

Repository: `nicholaslpollard/ATLAS`

Accepted upstream:

- Phases 1–17 accepted/merged.
- Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.

Current merge-authoritative work:

- Phase 18 — Paper Provider Mutation Lifecycle Validation.
- Branch: `phase-18-paper-provider-mutation-lifecycle-validation`.
- PR: #18, currently draft until final closeout boundary is green.
- Policy: `phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`.
- Fingerprint: `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.
- Phase 18A: **ACCEPTED / COMPLETE**.
- Phase 18B: **ACCEPTED / COMPLETE** based on real Webull sandbox target-machine evidence from 2026-08-24.
- Phase 18 overall: **ACCEPTED; closeout docs/CI/merge pending**.
- Live execution: **DISABLED**.
- Automatic broker failover: **DISABLED**.

Stacked work:

- Phase 19 — Operations Dashboard / Observability.
- State: **STACKED_PREP**, not independently mergeable before Phase 18.
- Existing stacked branch/PR must be rebased/retargeted to merged `main` after Phase 18 closes, then Phase 19 must be revalidated before becoming active/mergeable.

## 3. Mandatory phase flow

Normative process:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Batch-first is preferred. Authority/external checkpoints override batching. Provider mutation, destructive cleanup, broker switching, and future live authority may never be inferred from credentials/configuration/prior acceptance.

## 4. Architecture snapshot

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/Monte Carlo/scenarios -> news/events -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/provider roles:

- Parquet: durable analytical/history lake.
- DuckDB: analytical engine.
- PostgreSQL: target operational state.
- Massive: primary broad-market/reference provider.
- Webull: primary planned execution broker; downstream realtime L1 execution evidence where entitled.
- Alpaca: manually selectable secondary/fallback; never automatic failover.

## 5. Non-negotiable architecture/authority rules

- Preserve exact provider-native ticker text/case.
- Ticker text never proves identity continuity.
- Historical populations remain point-in-time.
- Ambiguity is quarantined/excluded, never guessed.
- No synthetic pre-2021 intraday from daily data.
- Finalized canonical facts outrank provisional live observations.
- ML emits probability evidence; argmax is diagnostic only.
- Accepted production model cannot be silently replaced by a challenger.
- AI is independent audit only and cannot create execution authority.
- LONG geometry: `stop < entry < target`.
- SHORT geometry: `stop > entry > target`.
- Unknown broker/provider state fails closed.
- Uncertain writes are never retried blindly.
- Automatic cross-broker failover is forbidden.
- Paper/sandbox authority does not imply live authority.

## 6. Accepted data/model evidence

Historical provider boundary:

- Alpaca raw SIP daily controlled authority: 2016-01-04 through 2021-08-13.
- Massive authority: 2021-08-16 onward.
- No synthetic pre-2021 1h/4h history.

Accepted cumulative data/lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Accepted production ML:

- ID `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- outputs `p_down/p_neutral/p_up`;
- protected holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact replay.

Phase 11 strategy support:

- SUPPORTED 0;
- MIXED 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED 5.

Zero supported strategies correctly produced zero accepted promotions on the locked case.

## 7. Accepted execution/control-plane foundation

### Phase 15

Broker-neutral shadow/paper execution includes fresh quote, provider preflight, account/order/position reconciliation, current risk revalidation, protective geometry, deterministic client-order IDs/idempotency, uncertainty fail-closed, same-ticker add/flip disabled, live hard-disabled, Webull primary and Alpaca manual secondary.

### Phase 16

Accepted loopback-first browser/control plane includes CSRF/same-origin, audit/idempotency, restart recovery, explicit broker switching/cleanup planning, and no independent browser execution authority.

### Phase 17

Accepted real provider read-only readiness:

- Webull sandbox selected sanitized account ref `3d64d273c694250b`, 0 open orders, 0 positions;
- Alpaca paper sanitized ref `4b5b072f7127b4dc`, 0 open orders, 0 positions;
- both brokers reconciled;
- provider writes 0;
- target regression 874 passed in 24.83s;
- Windows/Ubuntu CI green.

## 8. Phase 18 accepted design

### 8.1 Authority gate

Real paper-provider mutation is disabled by default and requires:

- one selected broker;
- `--authorize-paper-provider-mutation`;
- exact confirmation `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credentials/endpoints/environment/connectivity/prior acceptance cannot substitute.

### 8.2 Locked validation order

Contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

- PAPER/SANDBOX only;
- EQUITY BUY only;
- exactly 1 share;
- LIMIT / DAY;
- extended hours false;
- entry 5% below fresh realtime bid;
- stop 2% below entry;
- target 2% above entry;
- absolute notional <= $1,000;
- Phase 13 10% single-name cap;
- Phase 13 0.5% loss-at-stop cap.

Expected lifecycle:

`fresh quote -> plan-only -> explicit authorization -> flat reconcile -> prove client ID absent -> preview -> submit once -> exact reconcile -> cancel once -> exact terminal reconcile -> flat/zero-open`

### 8.3 Quote-source evolution

Massive remains primary broad-market/reference authority. The current Massive plan rejected realtime stock quote subscriptions while allowing delayed aggregate streaming.

Phase 18 added an explicit read-only Webull sandbox L1 capture path:

`one Webull L1 read -> sanitized local snapshot -> Phase 18 plan reads local file`

Plan-only still initializes no broker adapter and makes zero provider calls/writes.

Execution evidence requires exact ticker, valid bid/ask, undelayed/realtime semantics, REGULAR session, and provider quote age <= **30 seconds**. Premarket/after-hours/stale/delayed/wrong-ticker evidence fails closed.

### 8.4 Webull rate policy

Locked as of 2026-08-24:

- normal sustained Webull **read** target = **80% of the most specific current documented endpoint limit**;
- endpoint-specific limit outranks broader/global limit;
- no normal 90% sustained target;
- any higher temporary read burst must be bounded/read-only/below the hard provider limit;
- mutation throughput is governed by ATLAS risk/reconciliation/idempotency, not provider write capacity;
- sustained realtime monitoring should prefer MQTT/streaming over aggressive HTTP polling;
- 429 reads back off/cool down;
- ambiguous mutation state requires reconciliation;
- no automatic failover.

## 9. Phase 18A evidence

Final target-machine Phase 18A baseline:

`94a859fc6d44c22a6f8852c1488215a6677806a0`

- isolated Windows CSRF transport case: 1 passed in 3.30s;
- full regression: **908 passed in 23.50s**;
- working tree clean;
- provider calls 0;
- provider writes 0;
- Windows/Ubuntu CI green.

**Phase 18A: ACCEPTED / COMPLETE.**

## 10. Phase 18B target evidence — 2026-08-24

### 10.1 Webull L1 entitlement

Local sandbox credentials returned fresh AAPL L1 quotes. First explicit entitlement probe was ~20 seconds old; subsequent active-market captures were consistently sub-2-second.

### 10.2 Premarket fail-closed

Fresh premarket quotes were captured at 09:18 and 09:25 ET, but Phase 18 returned `BLOCKED` because session was premarket. Plan-step broker adapter remained uninitialized and provider writes remained 0.

### 10.3 Regular-session plan-only

At 09:31 ET:

- AAPL bid/ask `311.06 / 311.17`;
- quote age `0.322s`;
- session REGULAR;
- plan `295.51 / 289.60 / 301.42` entry/stop/target;
- notional `$295.51`;
- broker adapter NO;
- provider calls 0;
- provider writes 0;
- disposition `PLAN_ONLY_ZERO_PROVIDER_CALLS`.

### 10.4 First authorized attempt — safely blocked before write

The first authorized Webull run stopped at `idempotency_query` because the SDK surfaced explicit `Order not present` as HTTP 417/exception. Final reconciliation was flat/zero-open; no submit or cancel occurred.

ATLAS then added:

- exact Webull order-absence normalization;
- suppression of SDK loggers that could emit signed request/account metadata.

### 10.5 Accepted authorized lifecycle

Later explicitly authorized Webull sandbox run:

- AAPL bid/ask `311.33 / 311.39`;
- quote timestamp `2026-08-24T13:51:49.262000+00:00`;
- quote age `0.823s`;
- client ID `p18v-13abada37159d4486df293b3695`;
- entry/stop/target `295.76 / 289.84 / 301.68`;
- notional `$295.76`;
- authorization accepted;
- exactly one sandbox adapter initialized.

Lifecycle evidence:

1. pre-reconciliation flat/zero-open;
2. deterministic client ID absent;
3. preview accepted;
4. order submitted exactly once;
5. exact post-submit reconciliation succeeded;
6. cancellation attempted exactly once;
7. immediate post-cancel exact read was inconclusive, so ATLAS stopped with **no retry, no failover, no flatten**;
8. read-only account reconciliation already showed 0 open orders and 0 positions;
9. subsequent read-only exact diagnostic reported Order Detail `CANCELLED` and Order History `CANCELLED`;
10. requested quantity `1.0`, filled quantity `0.0`;
11. final open orders `0`, positions `0`, exact client ID not open, flat/zero-open true.

This is definitive target-machine proof of:

`submit once -> exact reconcile -> cancel once -> exact CANCELLED -> zero fill -> flat/zero-open`

**Phase 18B: ACCEPTED / COMPLETE. Cleanup not required.**

### 10.6 Post-target hardening

Because Webull showed a short post-cancel read-consistency window, the hardened Webull adapter now:

- sends cancellation at most once;
- performs bounded **read-only** exact Order Detail + Order History reconciliation;
- returns only after exact `CANCELLED` is proven;
- fails uncertain if exact terminal proof is unavailable;
- never retries cancellation solely because reads lag.

Regression coverage verifies the history fallback proves `CANCELLED` while the cancel endpoint is called exactly once.

No second target mutation is required solely for this read-only hardening because the accepted real lifecycle already produced exact `CANCELLED`, zero-fill, zero-open, flat evidence.

## 11. Current broker authority

### Webull

- primary planned execution broker;
- sandbox reads accepted;
- fresh L1 execution-evidence path accepted;
- Phase 18 sandbox mutation lifecycle accepted;
- live authority **not** granted.

### Alpaca

- manual secondary/fallback;
- paper reads accepted;
- no automatic failover;
- no requirement to repeat Phase 18 certification on Alpaca before closing Webull-first Phase 18 unless a future phase explicitly requires it.

### Live

- live execution disabled;
- any live-money transition requires a separately defined phase and separate explicit user authorization.

## 12. Exact continuation point

Phase 18 target evidence is complete. Do **not** perform another real provider mutation merely to repeat the accepted lifecycle.

Current closeout sequence:

1. require final Phase 18 code/docs CI green on Ubuntu and Windows;
2. synchronize README/roadmap/current-status/phase spec/PR evidence;
3. mark PR #18 ready;
4. merge Phase 18 into `main`;
5. verify merged `main`;
6. retarget/rebase existing Phase 19 stacked branch/PR onto merged `main`;
7. run Phase 19 validator;
8. run full regression;
9. require Windows + Ubuntu Phase 19 CI green;
10. resolve any rebase drift;
11. synchronize Phase 19 docs/PR;
12. only then treat Phase 19 as active/mergeable.

## 13. Configuration/security status

Tracked `.env.example` is non-secret and may contain public/default endpoints plus blank secret placeholders.

Never commit or expose API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata. Commented secrets are still secrets.

## 14. Future-session startup

A future session should:

1. inspect `main`, branches, open PRs, and latest CI;
2. read this file;
3. read `docs/roadmap.md`;
4. read `docs/phase_flow.md`;
5. read the active/stacked phase spec;
6. preserve provider/live authority boundaries;
7. continue from section 12 rather than repeating accepted Phase 18 provider mutations.

## 15. Documentation rule

Every meaningful evidence boundary synchronizes, as applicable:

- `README.md`;
- `docs/roadmap.md`;
- this file;
- `docs/phase_flow.md` when process rules change;
- active/stacked phase spec;
- active PR acceptance/evidence ledger;
- relevant configuration docs/templates.
