# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-24.**

This is the fastest source for a future chat/development session to recover exact ATLAS state without reconstructing prior conversation history.

## 1. Source-of-truth order

When sources disagree, use:

1. accepted code/artifacts on `main` for completed work;
2. active PR branch code for in-progress work;
3. `docs/roadmap.md` for architecture/authority rules;
4. this file for exact current state/evidence/continuation;
5. `docs/post_phase19_stabilization.md` for the unnumbered post-Phase19 closure/performance audit;
6. `docs/phase_flow.md` for phase progression/cadence;
7. active phase living specification, if any;
8. root `README.md`;
9. merged PRs for deeper historical evidence;
10. old phase/fix READMEs as provenance only.

## 2. Repository state

Repository: `nicholaslpollard/ATLAS`

Accepted baseline before the post-Phase19 maintenance batch:

- **Phases 1–19 accepted/merged.**
- Phase 18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase 19 merge / `main`: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase 19 policy: `phase19-policy-v1-phase18-stacked-readonly-operations-observability-no-provider-writes`.
- Phase 19 fingerprint: `ecd30046a7a3258013a29f0a2982de133f3a4f801aee4ad5e24f79b6bd3b4c3d`.
- Final Phase 19 docs-head CI run `32739682576`: Ubuntu **932 passed in 13.78s**; Windows **932 passed in 25.80s**; every validator through Phase 19 PASS.
- Live execution: **DISABLED**.
- Automatic broker failover: **DISABLED**.
- Phase 19 provider reads/writes: **0 / 0**.
- No Phase 20 branch or authority is active.

Current work is an **unnumbered post-Phase19 stabilization/housekeeping batch** only. It cleans documentation/runtime-log hygiene and reviews performance debt without changing provider/broker/model/AI/live authority.

At audit start there were no open issues or open PRs. Only merged Phase 18/19 remote phase branches remained as historical refs.

## 3. Mandatory phase flow

Normative process:

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

Phase 11 strategy support:

- SUPPORTED 0;
- MIXED 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED 5.

Zero supported strategies correctly produced zero accepted promotions on the locked case.

## 7. Accepted execution/control-plane foundation

### Phase 15

Broker-neutral shadow/paper execution includes fresh quote, provider preflight, account/order/position reconciliation, current risk revalidation, protective geometry, deterministic client-order IDs/idempotency, uncertainty fail-closed, same-ticker add/flip disabled, live hard-disabled, Webull primary and Alpaca manual secondary.

### Phase 16

Accepted loopback-first browser control plane includes CSRF/same-origin, audit/idempotency, restart recovery, explicit broker switching/cleanup planning, and no independent browser execution authority.

### Phase 17

Accepted real provider read-only readiness established working Webull sandbox and Alpaca paper account/order/position reads and reconciliation with provider writes 0.

## 8. Phase 18 accepted evidence

Policy:

`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Fingerprint:

`9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`

Accepted Webull target lifecycle on 2026-08-24:

1. fresh regular-session Webull sandbox L1 quote;
2. one-share nonmarketable limit/bracket plan within locked risk/notional caps;
3. explicit exact paper mutation authorization;
4. pre-reconciliation flat/zero-open;
5. deterministic client ID absence proven;
6. provider preview accepted;
7. order submitted exactly once;
8. exact post-submit reconciliation succeeded;
9. cancellation requested exactly once;
10. immediate exact read was inconclusive and ATLAS stopped without retry/failover/flatten;
11. later read-only Order Detail and Order History both reported `CANCELLED`;
12. filled quantity 0;
13. final open orders 0 and positions 0.

Definitive result:

`submit once -> exact reconcile -> cancel once -> exact CANCELLED -> zero fill -> flat/zero-open`

Post-target hardening keeps cancellation exactly-once and uses bounded read-only exact reconciliation instead of repeating a cancel when provider reads lag.

Webull normal sustained read traffic is locked to **80% of the most specific current documented endpoint limit**; endpoint-specific limits outrank broader limits. No automatic failover.

Phase 18 is accepted/merged at `55bdd7446f0bbd4225de264187c7f5fb601991b0`.

## 9. Phase 19 accepted implementation

Purpose: turn the accepted Phase 16 local browser control plane into a useful end-to-end ATLAS operations dashboard without adding trading authority.

Authority lock:

- local artifact reads allowed;
- Phase 19 provider reads 0;
- Phase 19 provider writes 0;
- browser execution authority disabled;
- live promotion disabled;
- automatic cross-broker failover disabled;
- credentials/raw account IDs forbidden;
- missing artifacts shown unavailable rather than synthesized.

Persisted read-only evidence sources:

- Phase 11 candidates;
- Phase 14 AI review;
- Phase 15 descriptive outcomes;
- accepted Phase 16 local control state;
- persisted Phase 5 live-market state.

The accepted Phase 16 explicit read-only broker refresh remains separate. Phase 19 observability refresh initializes no broker adapter or market-data client.

`INPUTS_APPEAR_READY` is diagnostic only and requires <=30-second snapshot/quote age, SUBSCRIBED, REALTIME, delay 0, no open gap, REGULAR session, and at least one fresh persisted quote. It cannot authorize execution or replace the Phase 15 execution quote resolver.

Browser contract:

- dedicated `apps/web/phase19.html` shell;
- GET-only `/api/v1/observability`;
- Phase 16 shell preserved;
- local Overview/Pipeline/Candidates/AI Audit/Outcomes/Brokers/Actions/Lineage navigation;
- optional 5/15/30-second observability refresh, default OFF;
- self-only CSP and loopback deployment.

## 10. Phase 19 final validation/merge evidence

After Phase 18 merged, Phase 19 was rebuilt directly on the accepted Phase 18 tree rather than carrying forward noisy stacked history.

Clean rebased implementation head:

`8c7d045af4f75cb734eeebbd76c84edaccdcc173`

Post-rebase CI run `32738366242`:

- Ubuntu: 932 passed in 16.08s;
- Windows: 932 passed in 23.74s;
- every validator through Phase 19 PASS;
- dependency lock, secret hygiene, ATLAS Doctor, browser JavaScript syntax, and feature self-test PASS;
- exact 33-feature parity max absolute difference 0.0;
- provider calls/writes 0;
- broker writes 0.

Final docs-head `76133cb6331c97ce1bb19319157f944a540f3214` CI run `32739682576`:

- Ubuntu: **932 passed in 13.78s**;
- Windows: **932 passed in 25.80s**;
- every validator through Phase 19 PASS on both platforms;
- dependency lock PASS;
- secret hygiene PASS;
- ATLAS Doctor PASS;
- browser JavaScript syntax PASS;
- feature self-test exact 33-feature parity, max absolute difference 0.0;
- provider writes 0;
- broker writes 0.

PR #19 merged successfully. Accepted Phase 19 merge / `main` baseline:

`8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`

There was no Phase 18 -> Phase 19 integration drift exposed by the full cross-platform regression.

Historical target performance retained from STACKED_PREP:

- 50,000 rows / 7,454 symbols / 7 sessions;
- optimized batch 4.00265s / 12,491.74 rows/s;
- prior pandas baseline 594.58s / 84.09 rows/s;
- ~148.5x batch speedup;
- all 33 features exact parity, max difference 0.0;
- provider/broker calls/writes 0.

## 11. Post-Phase19 stabilization/performance housekeeping

The unnumbered audit is recorded in `docs/post_phase19_stabilization.md`.

Confirmed closure/hygiene:

- no open issues or PRs at audit start;
- `main` authoritative through Phase 19;
- `webull_data_sdk.log*` is local generated runtime output and is ignored;
- active browser UI remains `apps/web/`; root `frontend/` remains historical/non-authoritative;
- PostgreSQL files remain explicitly nonoperational scaffolding;
- no broad scaffold deletion was performed without architectural evidence.

Performance review:

- accepted feature optimization remains exact and fast (~148.5x batch improvement on the accepted 50k target case);
- normalizer and bar builder already use DuckDB `COPY ... RETURN_STATS` to avoid redundant post-write count scans;
- materializer already reuses validator `checked_rows` for canonical row count;
- a possible derived-row-count cache for no-op materialization reruns was reviewed but intentionally deferred because it would alter persisted manifest shape without evidence that those metadata-oriented skip scans are a meaningful bottleneck;
- no staging move/hardlink semantics were added without recovery evidence;
- no Webull limiter/MQTT orchestration was added merely for housekeeping; the 80% read policy remains the operating rule until a production consuming path justifies implementation.

## 12. Current broker authority

### Webull

- primary planned execution broker;
- sandbox reads accepted;
- fresh L1 execution-evidence path accepted;
- Phase 18 sandbox mutation lifecycle accepted;
- live authority **not** granted.

### Alpaca

- manual secondary/fallback;
- paper reads accepted;
- no automatic failover.

### Live

- live execution disabled;
- any live-money transition requires a separately defined phase and separate explicit user authorization.

## 13. Exact continuation point

Do **not** repeat Phase 18 provider mutation merely to reconfirm accepted evidence. Phase 19 is already accepted/merged.

Current sequence:

1. finish and merge the unnumbered `maintenance/post-phase19-stabilization` batch after green CI;
2. verify merged `main` and local worktree;
3. optionally remove merged Phase 18/19 branch refs as repository cosmetics only;
4. explicitly define and authority-lock Phase 20 before substantive numbered-phase implementation;
5. keep live execution and automatic failover disabled unless a future separately accepted authority phase changes them.

## 14. Configuration/security status

Tracked `.env.example` is non-secret and may contain public/default endpoints plus blank secret placeholders.

Never commit or expose API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata. Commented secrets are still secrets.

## 15. Future-session startup

A future session should:

1. inspect `main`, branches, open PRs, and latest CI;
2. read this file;
3. read `docs/roadmap.md`;
4. read `docs/post_phase19_stabilization.md`;
5. read `docs/phase_flow.md`;
6. read the active phase spec, if any;
7. preserve provider/live authority boundaries;
8. continue from section 13 rather than reopening accepted Phase 18/19 work without new evidence.

## 16. Documentation rule

Every meaningful evidence boundary synchronizes, as applicable:

- `README.md`;
- `docs/roadmap.md`;
- this file;
- `docs/phase_flow.md` when process rules change;
- active phase spec;
- active PR acceptance/evidence ledger;
- relevant configuration docs/templates.
