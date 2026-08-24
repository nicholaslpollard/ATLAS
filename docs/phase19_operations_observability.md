# Phase 19 — Operations Dashboard & Paper/Shadow Observability

**State: ACCEPTED / MERGED. Last synchronized: 2026-08-24.**

Phase 19 turns the accepted Phase 16 browser control plane into an end-to-end ATLAS operations dashboard without creating provider-write, live-trading, automatic-failover, model, strategy, or AI authority.

## 1. Upstream and merge binding

- historical branch: `phase-19-operations-dashboard-observability`;
- merged PR: `#19 — Phase 19: Operations Dashboard & Paper/Shadow Observability`;
- accepted Phase 18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`;
- clean rebased Phase 19 implementation head: `8c7d045af4f75cb734eeebbd76c84edaccdcc173`;
- final docs-closeout head: `76133cb6331c97ce1bb19319157f944a540f3214`;
- accepted Phase 19 merge / `main`: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`;
- live execution: disabled;
- automatic failover: disabled.

The old STACKED_PREP implementation/evidence is development provenance only. After Phase 18 merged, Phase 19 was rebuilt directly on accepted `main`, revalidated end-to-end on Ubuntu and Windows, accepted, and merged.

## 2. Authority lock

Policy:

`phase19-policy-v1-phase18-stacked-readonly-operations-observability-no-provider-writes`

Fingerprint:

`ecd30046a7a3258013a29f0a2982de133f3a4f801aee4ad5e24f79b6bd3b4c3d`

Locked authority:

- local artifact reads allowed;
- Phase 19 provider reads 0;
- Phase 19 provider writes 0;
- browser execution authority disabled;
- live promotion disabled;
- automatic cross-broker failover disabled;
- credentials/raw account IDs forbidden;
- missing artifacts explicit unavailable, never synthesized.

The accepted Phase 16 explicit read-only broker refresh remains separate. Phase 19 intelligence refresh initializes no broker adapter or market-data client.

## 3. Persisted evidence sources

- Phase 11 candidates: `data/derived/candidates/phase11/v1`;
- Phase 14 AI review: `data/derived/ai_review/phase14/v1/manifests`;
- Phase 15 descriptive outcomes: `data/derived/execution/phase15/v1/outcomes`;
- accepted Phase 16 local control state;
- persisted Phase 5 live-market state: `data/live/market_state/current.json`.

Only sanitized/public fields are exposed. Internal instrument IDs, raw account IDs, provider/client order IDs, intent IDs, filesystem paths, prompts/provider responses, credentials, and secrets remain excluded.

Candidate display cap is 50. Outcome/live-quote displays remain bounded. Phase 19 reuses persisted ordering and creates no new candidate ranking.

## 4. Market-input diagnostics

Candidate/AI artifact recency uses a display-only 96-hour threshold.

`INPUTS_APPEAR_READY` requires all:

1. snapshot age <= 30 seconds;
2. connection `SUBSCRIBED`;
3. feed `REALTIME`;
4. expected delay 0;
5. no open transport gap;
6. session `REGULAR`;
7. at least one persisted `FRESH` quote with provider timestamp age <= 30 seconds.

This is diagnostic only. It does not replace the execution quote resolver, prove an intended trade ticker, or authorize provider mutation.

Phase 18 additionally accepted a Webull sandbox L1 execution-evidence path, but Phase 19 does not call that provider path automatically and does not inherit mutation authority from Phase 18.

## 5. Browser architecture

Components:

- `packages/control_plane/phase19_policy.py`;
- `packages/control_plane/phase19_observability.py`;
- `packages/control_plane/phase19_http_server.py`;
- GET-only `/api/v1/observability`;
- `scripts/run_phase19_control_plane.py`;
- `apps/web/phase19.html`;
- `apps/web/observability.js`;
- `apps/web/observability.css`;
- `apps/web/observability_controls.js`.

Accepted Phase 16 `apps/web/index.html` remains unchanged. The Phase 19 handler maps `/` and `/index.html` to `phase19.html`. POST to `/api/v1/observability` is method-not-allowed and creates zero action-ledger events.

Local launcher:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase19_control_plane.py
```

Open `http://127.0.0.1:8765`.

## 6. Operator UX

The local UI provides:

- Overview, Pipeline, Candidates, AI Audit, Outcomes, Brokers, Actions, Lineage navigation;
- `LOCAL · READ ONLY` authority indicator;
- phase/authority/system summaries;
- pipeline evidence;
- candidate search/filter/detail;
- market/sector/ticker regimes;
- all three ML probabilities and accepted model;
- fired/supported strategy evidence and promotion/reason codes;
- independent AI-audit summary;
- descriptive outcome W/L/flat, win rate, gross P&L, average realized R;
- artifact-age diagnostics;
- persisted live-market health and focused quote table;
- market-input readiness checklist;
- optional local-only 5/15/30-second observability refresh;
- accepted Phase 16 explicit read-only broker reconciliation/actions;
- lineage.

Auto-refresh defaults OFF, pauses when hidden, calls only `/api/v1/observability`, performs no automatic broker refresh, starts no market-data socket, and creates no provider-mutation authority.

## 7. Frontend deployment boundary

See `docs/frontend_deployment_boundary.md`.

The server remains loopback-only. Do not expose it by changing the bind address, opening router/firewall ports, or using an unaudited tunnel.

Progression remains:

1. `LOCAL_OPERATOR_UI` — current;
2. `PRIVATE_REMOTE_READONLY` — future authenticated HTTPS sanitized replication/read-only API;
3. `AUTHENTICATED_REMOTE_CONTROL` — later separate identity/action-authorization/audit/reconciliation security contract.

## 8. Local doctor and repository hardening

`scripts/atlas_doctor.py`

Contract:

`atlas-doctor-v1-local-sanitized-zero-provider-calls`

It checks repository/runtime/configuration health, dependency lock, secret hygiene, credential presence only, artifacts, and safety posture. It prints no credential values, initializes no provider, performs zero provider calls/writes, and cannot authorize mutation.

Cross-cutting repository hardening retained in Phase 19 includes:

- exact `requirements.lock` pins including `scikit-learn==1.9.0`;
- dependency-lock validation;
- tracked secret-hygiene validation;
- SHA-pinned GitHub Actions with `contents: read` and checkout credential persistence disabled;
- PostgreSQL `database/` scaffold explicitly marked nonoperational.

## 9. Feature-performance evidence retained

Provider/broker-free benchmark:

`scripts/benchmark_local_features.py`

Accepted optimized target-machine evidence from STACKED_PREP:

- 50,000 rows / 7,454 symbols / 7 sessions;
- prior pandas batch baseline 594.58s / 84.09 rows/s;
- optimized batch 4.00265s / 12,491.74 rows/s;
- production incremental comparator 3.80612s / 13,136.74 rows/s;
- ~148.5x batch speedup;
- incremental/batch ratio 1.05163;
- all 33 features exact parity, max absolute difference 0.0;
- provider/broker calls/writes 0.

Fully warmed incremental diagnostic:

- 1,000 symbols;
- 200 warm-up bars/symbol;
- 10 timed bars/symbol / 10,000 rows;
- 3.97736s / 2,514.23 rows/s;
- 330,000 / 330,000 expected feature cells finite;
- ~99.39% one-core utilization;
- ~24.8 MB peak traced Python memory;
- provider/broker calls/writes 0.

The optimization preserves provider-native ticker case, session segmentation, deterministic ordering, legacy feature-column order, metadata, all 33 feature mathematics, and the independent pandas reference oracle.

## 10. Data-path efficiency retained

- `packages/data/normalizer.py`: DuckDB `COPY ... RETURN_STATS` supplies exact write count without reopening freshly written Parquet solely for `count(*)`;
- `packages/aggregation/bar_builder.py`: same optimization for derived bars;
- `packages/data/materializer.py`: canonical row count reuses staging validator `checked_rows` after byte-for-byte copy.

Staging-to-canonical move/hardlink semantics remain intentionally unimplemented pending recovery/failure evidence.

The post-Phase19 stabilization audit also reviewed caching derived-row counts for no-op materialization reruns. That change was deliberately deferred because it would alter persisted manifest shape without measured evidence that the existing metadata-oriented skip scans are a meaningful bottleneck.

## 11. Previous STACKED_PREP validation evidence

Validated code head `a6736de45de5d5d0aca5876b6b543f2a924a2111`, CI `32686662335`:

- Ubuntu: 921 passed in 14.45s;
- Windows: 921 passed in 34.85s;
- every validator through Phase 19 PASS;
- dependency lock PASS;
- secret hygiene PASS;
- ATLAS Doctor PASS;
- feature benchmark self-test PASS;
- provider/broker calls/writes 0.

This is provenance only; final acceptance is based on the clean post-Phase18 rebase evidence.

## 12. Final post-Phase18 acceptance evidence

Clean rebased implementation head:

`8c7d045af4f75cb734eeebbd76c84edaccdcc173`

Implementation CI `32738366242`:

- Ubuntu: 932 passed in 16.08s;
- Windows: 932 passed in 23.74s;
- Phase 19 validator and every prior validator through Phase 18 PASS;
- dependency lock, secret hygiene, ATLAS Doctor, browser JavaScript, feature benchmark self-test PASS;
- exact 33-feature parity max absolute difference 0.0;
- provider calls 0;
- provider writes 0;
- broker writes 0;
- live promotion disabled;
- automatic failover disabled.

Final docs-closeout head:

`76133cb6331c97ce1bb19319157f944a540f3214`

Final docs-head CI `32739682576`:

- Ubuntu: **932 passed in 13.78s**;
- Windows: **932 passed in 25.80s**;
- every validator through Phase 19 PASS on both platforms;
- dependency lock, secret hygiene, ATLAS Doctor, browser JavaScript, and feature self-test PASS;
- exact 33-feature parity max absolute difference 0.0;
- provider writes 0;
- broker writes 0.

The rebase and closeout exposed no Phase 18 -> Phase 19 integration drift.

## 13. Final merge boundary — complete

1. Phase 18 accepted/merged — COMPLETE at `55bdd7446f0bbd4225de264187c7f5fb601991b0`;
2. Phase 19 rebuilt/retargeted to merged `main` — COMPLETE;
3. `scripts/validate_phase19.py` — PASS;
4. full regression — PASS;
5. Ubuntu + Windows CI — PASS;
6. integration drift resolution — none required;
7. living docs/PR synchronized — COMPLETE;
8. final docs-head CI — PASS;
9. PR #19 marked ready and merged — COMPLETE;
10. merged `main` verified at `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe` — COMPLETE.

No target-machine broker/provider test was required solely for Phase 19 observability. No Phase 18 provider mutation should be repeated for this phase.

The next numbered phase is not implicitly active. Post-Phase19 stabilization is unnumbered housekeeping only.

## 14. Explicit non-goals

Phase 19 does not authorize or perform provider mutation, add submit/cancel/replace/flatten endpoints, automatically refresh brokers, start market-data sockets, enable automatic failover, promote live trading, alter ML/strategy/promotion authority, let AI create trade authority, activate the PostgreSQL scaffold, or expose the control plane publicly.
