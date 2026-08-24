# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-24.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This file is the long-term architecture and authority lock. Implementation may evolve when measured evidence requires it, but changes must preserve the data-integrity, validation, and trading-authority boundaries below unless an explicit replacement decision is documented and independently validated.

For exact operational continuation, read [`current_status.md`](current_status.md). For the mandatory development sequence, read [`phase_flow.md`](phase_flow.md). Phase 19 evidence is in [`phase19_operations_observability.md`](phase19_operations_observability.md). Phase 18 provider-mutation evidence is in [`phase18_operational_validation.md`](phase18_operational_validation.md). The root [`README.md`](../README.md) is project orientation.

## 1. Mission

Build a broad-market system that can:

1. observe a large U.S. market universe;
2. maintain point-in-time-safe market/reference data, instrument identity, features, and regimes;
3. discover candidates cheaply before expensive research;
4. estimate outcome probabilities with conventional ML;
5. route candidates to deterministic strategies appropriate to context/regime;
6. promote only evidence-supported candidates into deeper analogue/scenario/options/news analysis;
7. produce deterministic entry/stop/target/horizon/risk plans;
8. subject the deterministic case to an independent AI audit;
9. alert, shadow, paper-trade, and eventually trade live only under explicit authority;
10. learn descriptively from outcomes without silently changing accepted model/strategy authority;
11. expose operational state through a browser control plane without making the browser an execution authority.

## 2. Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/compute roles:

- **Parquet**: durable analytical/history lake.
- **DuckDB**: analytical/query engine.
- **PostgreSQL**: target persistent operational state; current SQL scaffold is not accepted operational implementation.
- **Massive**: primary accepted broad-market/reference-data provider path.
- **Webull**: primary planned execution broker; accepted downstream realtime L1 execution-evidence source where locally entitled.
- **Alpaca**: manually selectable secondary/fallback execution broker; never automatic failover.

## 3. Mandatory phase execution contract

ATLAS advances by explicit numbered phases. The normative process is defined in `docs/phase_flow.md`.

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Required principles:

- code existence or passing tests alone is never acceptance;
- credentials/configuration/connectivity never silently expand provider/live authority;
- use coherent batches rather than artificial micro-checkpoints;
- full regression and Windows/Ubuntu CI belong at meaningful evidence boundaries;
- target-machine interaction is required only where CI/mocks cannot establish the evidence;
- explicit provider mutation, cleanup, broker switching, and future live authority remain separate gates;
- stacked preparation may occur only under `docs/phase_flow.md` and never bypass upstream authority.

Current phase state:

- **Phases 1–18: ACCEPTED / MERGED.**
- Phase 18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- **Phase 19: ACCEPTED** after clean rebase to accepted Phase 18 and full Ubuntu/Windows revalidation; PR #19 is the merge vehicle.
- Phase 19 post-rebase CI run `32738366242`: Ubuntu 932 passed / Windows 932 passed; every validator through Phase 19 PASS.
- Final docs-head CI must remain green before PR #19 merges.
- If this file is read from `main` after PR #19 merged, Phase 19 is **ACCEPTED / MERGED**.
- The next numbered phase has not yet been activated.

## 4. Non-negotiable data rules

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

- Alpaca raw SIP daily controlled extension: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- Pre-2021 1h/4h history remains absent rather than fabricated.

Accepted cumulative data/lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

## 5. ML authority rules

Production ML emits raw three-class probabilities:

- `p_down`;
- `p_neutral`;
- `p_up`.

Argmax is diagnostic only and is never a standalone trade signal. Accepted production model authority is immutable until an explicit challenger/acceptance process replaces it.

Accepted production model:

- ID `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- deterministic replay exact.

## 6. Strategy/research rules

- Regime routing belongs in scanner/router orchestration, not inside strategies.
- Strategies emit deterministic case evidence, not opaque conclusions.
- Expensive analogue/Monte Carlo/scenario/options/news work is promoted-candidate only.
- No-op/zero-promotion states are valid; thresholds are never weakened merely to create trades.
- Accepted Phase 11 support: 0 SUPPORTED, 3 MIXED, 5 UNSUPPORTED among eight tested variants.

## 7. AI authority rules

AI is an independent auditor/reviewer. It may approve, caution, or reject a deterministic case and identify risks, but it cannot:

- rewrite accepted historical/quantitative evidence;
- manufacture a trade from a rejected deterministic case;
- create provider-order authority;
- silently replace deterministic direction/instrument/geometry/risk authority;
- promote live execution.

## 8. Geometry and portfolio-risk rules

Mandatory geometry:

- LONG: `stop < entry < target`;
- SHORT: `stop > entry > target`.

Accepted Phase 13 risk envelope used by Phase 18 includes:

- risk at stop <= 0.5% current equity;
- single-name notional <= 10% current equity;
- liquidity/buying-power/account-state checks;
- exposure/concentration/correlation revalidation where applicable.

## 9. Broker and provider architecture

### 9.1 Webull

Primary planned broker for paper/sandbox and, only after a future separate live-authority phase, controlled live execution.

Accepted Phase 18 evidence proves the Webull sandbox can:

- provide fresh L1 bid/ask data under the local OpenAPI entitlement;
- preview the locked one-share validation bracket;
- accept one deterministic sandbox order;
- reconcile it by exact client order ID;
- accept one cancellation;
- later report the exact order `CANCELLED` with zero fills;
- reconcile flat with zero open orders.

### 9.2 Alpaca

Manually selectable secondary/fallback. It is not an automatic failover destination.

### 9.3 Switching

Broker switching is explicit only. ATLAS must inspect/reconcile open orders and positions first. Any cancel/close/flatten required to make a broker safe is itself a provider mutation and requires corresponding explicit authority. Unknown state fails closed.

### 9.4 Provider rate-limit operating policy

Locked 2026-08-24 policy:

- normal sustained Webull **read** traffic targets **80% of the most specific current documented endpoint limit**;
- endpoint-specific limits override broader/global limits;
- 90% is not the normal sustained target;
- any higher temporary read burst must be explicitly bounded, read-only, and below hard provider limits;
- trading mutations are governed by ATLAS risk/reconciliation/idempotency, not by the provider's advertised maximum write rate;
- sustained realtime candidate monitoring should prefer Webull MQTT/streaming rather than high-rate HTTP polling;
- HTTP 429 read handling uses cooldown/backoff;
- any ambiguous mutation response requires reconciliation before further mutation;
- no automatic cross-broker failover.

### 9.5 Live

Live execution is disabled. Paper-provider acceptance is not live acceptance. A future live phase must preregister limits, observation, failure handling, and explicit authorization independently.

## 10. Accepted phase ledger

### Phase 1 — Foundation
Project/config/session/time foundations, environment separation, canonical timezone and basic validation.

### Phase 2 — Provider ingestion foundation
Restartable provider acquisition, storage contracts, checkpoints, and raw evidence handling.

### Phase 3 — Canonical/session-aware data
Parquet/DuckDB canonical foundations, exchange/session semantics, duplicate/replay-safe handling.

### Phase 4 — Instrument identity/history
Point-in-time reference evidence, stable identifiers where authoritative, ambiguity quarantine.

### Phase 5 — Live market state
Massive delayed/realtime WebSocket state, freshness/delay/gap semantics, provisional journal/snapshot behavior.

### Phase 6 — Feature engine
33 deterministic point-in-time features with deterministic batch/incremental behavior.

### Phase 7 — Universe registry
Point-in-time instrument routing/eligibility without survivor projection or guessed identity.

### Phase 8 — Broad discovery
Cheap-first broad-market discovery, activity/health routing, persistence/hysteresis.

### Phase 9 — Regime engine
Market/sector/ticker regime hierarchy, prior-only thresholds, persistence, no guessed sector crosswalk.

### Phase 10 — ML probability/evaluation
Point-in-time training/labels/features, walk-forward evaluation, model registry/acceptance, raw probability surface.

### Historical extension/audit
Controlled Alpaca raw-SIP daily extension back to 2016, provider seam validation, cumulative lineage audit. No synthetic pre-2021 intraday.

### Phase 11 — Strategy evaluation/regime routing
Deterministic strategy variants, external regime routing, support classification, promotion policy.

### Phase 12 — Deep candidate research
Promoted-only historical analogue and deterministic empirical scenario/bootstrap research.

### Phase 13 — Context/instrument/geometry/portfolio risk
Deterministic instrument choice, geometry, position sizing, liquidity, exposure/concentration/correlation and risk planning.

### Phase 14 — Independent AI audit/alerting
Structured independent AI review and Engine-vs-AI alerts with AI authority bounded.

### Phase 15 — Broker-neutral shadow/paper execution + outcome learning
Webull primary/Alpaca manual secondary, fresh quote, provider preflight, reconciliation, current risk, protective geometry, deterministic client IDs, uncertain-write fail-closed, descriptive outcomes, live disabled.

### Phase 16 — Browser control plane/production operations
Loopback-first browser/API control plane, CSRF/same-origin, audit/idempotency, recovery, explicit broker switch/cleanup planning. Browser is not execution authority.

### Phase 17 — Provider-readonly operational readiness
Accepted real Webull sandbox + Alpaca paper reads/reconciliation while provider mutation remained disabled.

Accepted Phase 17 merge:
`65d5a7b58c6894eba27722465741c92db9a33aaf`

### Phase 18 — Paper Provider Mutation Lifecycle Validation

Policy:
`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Fingerprint:
`9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`

**State: ACCEPTED / MERGED.**

Accepted target-machine lifecycle on 2026-08-24:

- ticker AAPL;
- fresh regular-session Webull sandbox L1;
- exact one-share risk-bounded nonmarketable bracket;
- explicit exact paper mutation authorization;
- pre-reconciliation flat/zero-open;
- exact deterministic client-ID absence;
- provider preview accepted;
- order submitted exactly once;
- exact post-submit reconciliation;
- cancellation requested exactly once;
- no blind retry/failover/flatten during immediate read uncertainty;
- later independent Order Detail and Order History both `CANCELLED`;
- filled quantity 0;
- final open orders 0;
- final positions 0;
- no cleanup required.

Phase 18 hardening includes explicit Webull order-absence normalization, sensitive SDK request-log suppression, bounded read-only post-cancel reconciliation, a 30-second execution quote-age cap, premarket fail-closed behavior, and the 80% sustained Webull read policy.

Accepted Phase 18 merge:
`55bdd7446f0bbd4225de264187c7f5fb601991b0`

### Phase 19 — Operations Dashboard & Paper/Shadow Observability

Policy:
`phase19-policy-v1-phase18-stacked-readonly-operations-observability-no-provider-writes`

Fingerprint:
`ecd30046a7a3258013a29f0a2982de133f3a4f801aee4ad5e24f79b6bd3b4c3d`

**State: ACCEPTED; PR #19 merge vehicle.**

Accepted scope:

- local sanitized operations dashboard over accepted persisted evidence;
- dedicated Phase 19 shell with Overview/Pipeline/Candidates/AI Audit/Outcomes/Brokers/Actions/Lineage views;
- GET-only observability endpoint;
- optional local 5/15/30-second refresh, default OFF;
- persisted live-market diagnostics and `INPUTS_APPEAR_READY` display-only checklist;
- candidate/AI/outcome artifact recency diagnostics;
- existing accepted Phase 16 explicit read-only broker refresh kept separate;
- Phase 19 provider reads 0 and writes 0;
- browser execution authority disabled;
- live promotion disabled;
- automatic failover disabled.

Cross-cutting accepted support retained with Phase 19:

- exact dependency lock including `scikit-learn==1.9.0`;
- dependency-lock and tracked secret-hygiene validators;
- SHA-pinned Actions with `contents: read` and checkout credential persistence disabled;
- local sanitized zero-provider-call ATLAS Doctor;
- exact-parity feature batch optimization;
- low-risk data-I/O count-scan removals.

Post-Phase18 clean rebase head:
`8c7d045af4f75cb734eeebbd76c84edaccdcc173`

Final implementation CI run `32738366242`:

- Ubuntu 932 passed in 16.08s;
- Windows 932 passed in 23.74s;
- every validator through Phase 19 PASS;
- dependency lock, secret hygiene, doctor, browser JS, and feature self-test PASS;
- 33-feature exact parity max difference 0.0;
- provider calls/writes 0;
- broker writes 0.

The final documentation head must remain green before PR #19 merge. If this roadmap is read from `main` after PR #19 has merged, Phase 19 is accepted/merged and the ledger is closed through Phase 19.

## 11. Next-phase boundary

No Phase 20 authority is implicitly active.

After Phase 19 merge:

1. verify `main` and final CI;
2. define the next numbered phase as a coherent architecture increment;
3. lock its data/provider/execution authority before implementation;
4. preserve live execution disabled unless a future separately defined live-authority phase explicitly changes that state;
5. preserve manual-only broker switching and no automatic failover.

No additional real provider mutation is required merely to repeat Phase 18 evidence or validate Phase 19 observability.

## 12. Batch-first development protocol

Normal coherent work package:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status`

Use the largest safe coherent batch, independent validators and full regression at meaningful evidence boundaries, target-machine interaction only when necessary, and fail closed on identity/data/geometry/broker/mutation ambiguity.

## 13. Documentation and security policy

Every meaningful boundary synchronizes, as applicable:

- root `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- `docs/phase_flow.md` when process changes;
- active phase spec;
- active PR evidence;
- configuration templates/docs.

Tracked `.env.example` may contain public/default endpoints and blank secret placeholders. It must never contain API secrets, passwords, security codes, raw broker account IDs, or tokens. Commented secrets are still secrets.

## 14. Recovery protocol

A new session should:

1. inspect `main`, open PRs/branches, and latest CI;
2. read `docs/current_status.md`;
3. read this roadmap;
4. read `docs/phase_flow.md`;
5. read the active phase spec, if any;
6. preserve explicit provider/live authority boundaries;
7. continue from the exact phase state rather than reopening accepted work without new evidence.
