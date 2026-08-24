# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-24.**

This file is the fastest recovery point for a future ATLAS development session.

## 1. Source-of-truth order

When sources disagree, use:

1. accepted code/artifacts on `main` for completed work;
2. active PR branch code for in-progress work;
3. `docs/roadmap.md` for architecture/authority rules;
4. this file for exact current state/evidence/continuation;
5. `docs/post_phase19_stabilization.md` for the completed post-Phase19 closure/performance audit;
6. `docs/phase_flow.md` for phase progression/cadence;
7. active phase living specification, if any;
8. root `README.md`;
9. merged PRs for deeper historical evidence;
10. old phase/fix READMEs as provenance only.

## 2. Closed baseline

Repository: `nicholaslpollard/ATLAS`

- **Phases 1–19 accepted/merged.**
- Phase 18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase 19 merge / accepted baseline: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase 19 policy fingerprint: `ecd30046a7a3258013a29f0a2982de133f3a4f801aee4ad5e24f79b6bd3b4c3d`.
- Final Phase 19 docs-head CI `32739682576`: Ubuntu 932 passed in 13.78s; Windows 932 passed in 25.80s; every validator through Phase 19 PASS.
- Post-Phase19 stabilization CI `32754626468`: Ubuntu **932 passed in 15.59s**; Windows **932 passed in 25.38s**; every validator through Phase 19 PASS.
- Dependency lock, secret hygiene, ATLAS Doctor, browser JavaScript syntax, and feature self-test PASS.
- Live execution **DISABLED**.
- Automatic cross-broker failover **DISABLED**.
- Post-Phase19 stabilization/performance housekeeping **COMPLETE**.
- Phase 20 has not yet been authority-locked in this baseline.

At stabilization-audit start there were no open issues or PRs. Historical merged Phase 18/19 branch refs were the only remaining phase branches.

## 3. Mandatory phase flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Batch-first is preferred. Authority/external checkpoints override batching. Provider mutation, destructive cleanup, broker switching, and future live authority may never be inferred from credentials/configuration/prior acceptance.

## 4. Architecture snapshot

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/Monte Carlo/scenarios -> news/events -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/provider roles:

- Parquet: durable analytical/history lake.
- DuckDB: analytical engine.
- PostgreSQL: target operational state; current repository SQL scaffold remains nonoperational.
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

Phase 11 strategy support: SUPPORTED 0; MIXED 3 (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`); UNSUPPORTED 5. Zero supported strategies correctly produced zero accepted promotions on the locked case.

## 7. Accepted execution/control-plane evidence

### Phase 15

Broker-neutral shadow/paper execution includes fresh quote, provider preflight, reconciliation, current risk revalidation, protective geometry, deterministic client-order IDs/idempotency, uncertainty fail-closed, same-ticker add/flip disabled, live hard-disabled, Webull primary and Alpaca manual secondary.

### Phase 16

Accepted loopback-first browser control plane includes CSRF/same-origin, audit/idempotency, restart recovery, explicit broker switching/cleanup planning, and no independent browser execution authority.

### Phase 17

Accepted real-provider read-only readiness established working Webull sandbox and Alpaca paper account/order/position reads and reconciliation with provider writes 0.

### Phase 18

Policy `phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`, fingerprint `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.

Accepted Webull sandbox lifecycle:

`fresh L1 -> explicit paper authorization -> pre-reconcile flat -> preview -> submit once -> exact reconcile -> cancel once -> bounded read-only reconciliation -> exact CANCELLED -> zero fill -> flat/zero-open`

Immediate post-cancel read uncertainty was handled fail-closed without repeat cancel, flatten, retry, or failover. Later independent Order Detail and Order History both proved `CANCELLED`.

Normal sustained Webull read traffic is locked to **80% of the most specific current documented endpoint limit**; endpoint-specific limits outrank broader limits. No automatic failover.

### Phase 19

Accepted read-only local operations/observability layer:

- dedicated `apps/web/phase19.html` shell;
- GET-only `/api/v1/observability`;
- local sanitized candidate, AI-audit, outcome, lineage, and persisted live-market diagnostics;
- optional 5/15/30-second observability refresh, default OFF;
- accepted Phase 16 explicit read-only broker refresh remains separate;
- Phase 19 observability initializes no broker adapter or market-data client;
- Phase 19 provider reads/writes 0;
- no browser execution authority;
- no live promotion or automatic failover.

## 8. Performance/housekeeping baseline

The completed stabilization audit is recorded in `docs/post_phase19_stabilization.md`.

Accepted target feature performance:

- 50,000 rows / 7,454 symbols / 7 sessions;
- optimized batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x batch speedup;
- all 33 features exact parity, max difference 0.0;
- provider/broker calls/writes 0.

Data-I/O housekeeping already retained:

- normalizer and bar builder use DuckDB `COPY ... RETURN_STATS` to avoid redundant post-write count scans;
- materializer reuses validated staging `checked_rows` after byte-for-byte canonical promotion;
- staging move/hardlink semantics remain deferred until recovery behavior is proven;
- derived-row-count caching on no-op materialization was reviewed and deferred because it would alter manifest shape without measured bottleneck evidence;
- generated `webull_data_sdk.log*` is ignored as local runtime output.

## 9. Current broker authority

### Webull

Primary planned execution broker. Sandbox reads, fresh L1 execution-evidence path, and Phase 18 sandbox mutation lifecycle are accepted. Live authority is **not** granted.

### Alpaca

Manual secondary/fallback. Paper reads accepted. No automatic failover.

### Live

Live execution disabled. Any live-money transition requires a separately defined phase and separate explicit authorization.

## 10. Exact continuation point

Do **not** reopen accepted Phase 18/19 work merely to reconfirm it.

The next numbered work begins by:

1. defining Phase 20 as one coherent architecture increment;
2. locking its data/provider/execution authority before substantive implementation;
3. creating the Phase 20 branch/PR from the clean accepted baseline;
4. using coherent implementation batches with focused tests, independent validator, full cross-platform CI at evidence boundaries, and target-machine evidence only where CI/mocks cannot prove the requirement.

Until Phase 20 explicitly changes an authority boundary, live execution stays disabled, broker switching stays explicit/manual, and automatic failover stays forbidden.

## 11. Configuration/security status

Tracked `.env.example` is non-secret and may contain public/default endpoints plus blank secret placeholders.

Never commit or expose API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata. Commented secrets are still secrets.

## 12. Future-session startup

A future session should inspect `main`, branches/open PRs/latest CI, then read this file, `docs/roadmap.md`, `docs/post_phase19_stabilization.md`, `docs/phase_flow.md`, and the active phase spec if one exists. Preserve explicit provider/live authority boundaries and continue from section 10 rather than reopening accepted work without new evidence.
