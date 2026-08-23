# ATLAS Current Status and Handoff

**Living status document. Last synchronized: 2026-08-23.**

This file is the fastest way for a new development session or future chat to recover the current ATLAS state without reconstructing the project from old conversations. It is intentionally operational and evidence-focused. `docs/roadmap.md` remains the architecture/authority-policy lock, while the root `README.md` provides orientation.

## 1. Source-of-truth order

When sources disagree, use this order:

1. current `main` code and accepted validation artifacts for accepted work;
2. the active PR/branch for in-progress work;
3. `docs/roadmap.md` for locked architecture, phase boundaries, safety rules, configuration policy, and authority transitions;
4. this file for the latest accepted state, active work, evidence summary, and exact continuation point;
5. root `README.md` for project orientation;
6. merged pull requests for detailed accepted-phase evidence;
7. phase-specific documents and old `README_PHASE_*` / `README_ATLAS_*` files as historical records only.

Old phase/fix READMEs must not be treated as current roadmap instructions. They describe the state at the time that work was performed and are intentionally retained for provenance.

## 2. Current project state

- **Phases 1 through 17 are accepted and merged.**
- **Phase 18 — Paper Provider Mutation Lifecycle Validation is active on draft PR #18.**
- The legacy Chart Monitor is preserved; ATLAS is the redesign/rebuild path.
- Phase 17 merged after successful real-provider read-only reconciliation.
- The accepted Phase 17 provider-readiness code head was `21eeb757d84de33878ab1c8d7c8afe0797dee1f9`.
- Phase 17 merged into `main` at `65d5a7b58c6894eba27722465741c92db9a33aaf`.
- `main` remains the accepted baseline; the active Phase 18 branch is `phase-18-paper-provider-mutation-lifecycle-validation`.
- Completed phase branches have been removed after merge/closeout.
- **Current real-provider authority checkpoint:** `PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`.
- Phase 18 repository/CI code may be developed now, but real Webull/Alpaca paper-provider mutation is **not authorized by default**.
- Live execution is **not promoted**.
- Automatic cross-broker failover remains **disabled**.

## 3. Target architecture

ATLAS is designed around this flow:

`market/reference data -> Parquet data lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> strategy routing/evaluation -> candidate promotion -> historical analogue + Monte Carlo/scenario research -> news/events/sentiment -> instrument selection -> entry/stop/target/horizon -> portfolio/risk -> consolidated deterministic case -> independent AI audit -> alert/paper/shadow/live execution -> outcome/performance learning -> browser control plane`

Durable analytical/history storage is Parquet. DuckDB is the local analytical query engine. PostgreSQL remains the target for operational state that should not live in the analytical lake.

## 4. Accepted phase ledger

### Phases 1-3 — foundation, ingestion, canonical storage

Phase 1 established shared settings, secret handling, UTC/session conventions, canonical schemas, data-quality contracts, and validation. XNYS is the initial U.S. equity calendar; regular-session derived bars are exchange-session anchored.

Phase 2 implemented restartable/idempotent Massive flat-file ingestion with remote inventory, manifests, atomic partial downloads, SHA-256/size/gzip/schema validation, retries, checkpoints, and dry-run planning.

Phase 3 materialized validated provider files into ATLAS-owned canonical Parquet and session-aware derived history. Provider facts remain separate from derived features/strategy state.

### Phase 4 — instrument identity and historical lake

Accepted stable identity/history foundation with exact provider-native ticker case, point-in-time reference snapshots, authoritative continuity evidence where available, ticker-reuse protection, anomaly reconciliation, and provider/canonical/derived historical auditing.

Massive authoritative production history begins at **2021-08-16**. The historical lake proved restartable after a real Windows interruption without rebuilding already committed work.

### Phase 5 — live market state

Accepted provisional Massive live/delayed market state, explicit freshness and reconnect-gap accounting, journal/current-state persistence, and finalized-data reconciliation. Live observations never overwrite finalized canonical facts.

### Phase 6 — feature engine

Accepted **33 versioned quantitative features** with deterministic batch/incremental equivalence and checkpointed recursive state.

Accepted permanent feature persistence policy:

- 1d: permanent;
- 4h: permanent;
- 1h: permanent;
- 15m: on-demand/cache;
- 1m: live/current state only.

The accepted 2021-08-16 through 2026-08-14 permanent feature lake contained **154,188,221 rows** across 1d/4h/1h and passed deep source/hash/state-lineage audits plus historical-to-incremental continuation checks.

### Phase 7 — point-in-time universe registry

Accepted security-safe identity correction and point-in-time universe construction. The default discovery universe uses active U.S.-listed STRONG/MEDIUM identities on accepted exchanges/security types; ambiguous routing is excluded rather than guessed. Position/watchlist/custom routes can explicitly bypass default discovery eligibility while retaining audit reasons.

Accepted 2026-08-14 routed discovery universe: **12,066 instruments**.

### Phase 8 — broad discovery funnel

Accepted cheap-first, instrument-agnostic discovery foundation and vectorized multi-family scoring. Normal broad discovery requires valid daily data and the locked finalized/as-of daily dollar-volume floor; intraday availability is tracked rather than used to erase otherwise valid names.

Accepted 2026-08-14 broad-ready population: **8,034 instruments**.

Locked discovery-state thresholds:

- WATCH: priority >= 0.35;
- WARM: priority >= 0.50;
- HOT: priority >= 0.60 plus dominant-direction, non-neutral, and full-timeframe requirements.

Persistence/hysteresis is deterministic; missing prior-session state bootstraps conservatively rather than inventing continuity.

### Phase 9 — market/sector/ticker regime engine

Accepted deterministic point-in-time market, sector-proxy, optional authoritative SIC, stable-identity ticker-regime, persistence, and self-relative risk hierarchy. Missing classification/history remains explicit absence; no guessed sector crosswalk or ticker-text history splice is allowed.

Accepted 2026-08-14 ticker-state population: 8,034 routed instruments, with 7,338 effective current ticker states.

### Phase 10 — conventional ML probability/evaluation layer

Accepted production model:

- model id: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- specification: `hgb_leaf15_iter100`;
- predictors: 33 point-in-time quantitative features;
- outputs: raw `p_down`, `p_neutral`, `p_up`;
- post-hoc calibration: none;
- argmax: diagnostic only, never a trade signal.

Protected final holdout:

- 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- deterministic replay maximum probability difference 0.

The accepted HGB model remains production authority. Later longer-history model evidence is challenger/research evidence unless separately accepted as a production replacement.

### Historical source audit and backfill extension

A read-only source audit accepted Alpaca raw SIP daily as the preferred pre-Massive history source. The controlled historical extension then established:

- Alpaca raw SIP daily history from **2016-01-04 through 2021-08-13**;
- Massive production authority from **2021-08-16 onward**;
- no synthetic pre-2021 1h/4h bars from daily data;
- observation-driven historical populations;
- explicit identity segmentation and no literal-ticker continuity assumptions;
- accepted feature/regime/ML research handoff across the source seam.

The longer-history C result improved research depth and some proper-score evidence but remains separately versioned challenger/research evidence; it did not silently replace the Phase 10 production model.

### Phase 11 — strategy evaluation and regime routing

Accepted versioned deterministic strategy catalog, external regime router, identity-safe historical strategy study, Phase 10 probability attachment as context, and candidate-promotion policy.

Eight strategy variants were evaluated. Accepted historical support classification at closeout:

- SUPPORTED: 0;
- MIXED: 3 (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`);
- UNSUPPORTED: 5.

Because promotion requires historical support + current route compatibility + current firing, the accepted 2026-08-14 state legitimately produced **zero promoted candidates**. Thresholds were not weakened after seeing the result.

### Phase 12 — promoted-candidate deep research

Accepted promoted-only historical analogue and deterministic empirical scenario/bootstrap research. Expensive history is not opened for non-promoted names. Zero Phase 11 promotions is a valid strict no-op and does not relax promotion thresholds.

### Phase 13 — context, instrument, trade geometry, portfolio risk

Accepted deterministic case enrichment across contextual evidence, instrument selection, geometry, liquidity/sizing, exposure/concentration/correlation, and portfolio-risk admissibility.

Required geometry:

- LONG: `stop < entry < target`;
- SHORT: `stop > entry > target`.

Equity is the accepted v1 primary execution instrument. Options may provide finalist context when authoritative chain evidence exists but cannot silently become the primary instrument without a separately accepted relative-value model.

### Phase 14 — independent AI audit and alerting

Accepted structured AI audit with dispositions `APPROVE`, `CAUTIOUS`, `REJECT`. AI is an independent auditor, not a predictive model and not execution authority. It cannot rewrite deterministic direction, instrument, geometry, sizing, portfolio admission, or historical/model evidence. Engine evidence and AI review remain separately visible.

Phase 14 alerting is artifact-first and auditable.

### Phase 15 — broker execution and outcome learning foundation

Accepted broker-neutral execution contracts and shadow/paper execution semantics with:

- Webull as primary broker;
- Alpaca as manually selectable secondary/fallback;
- no automatic cross-broker failover;
- explicit broker switching only;
- fresh-quote translation before executable entry;
- current risk and reconciliation checks;
- protective stop/target in order plans;
- idempotent client identifiers;
- uncertainty fail-closed behavior;
- descriptive outcome learning only;
- live execution hard-disabled at acceptance.

Same-ticker exposure changes and broker switching must respect accepted reconciliation/safety rules; unknown provider state never authorizes another mutation.

### Cumulative data and lineage audit

Before execution advancement, ATLAS added a read-only cumulative integrity acceptance over historical source/canonical/feature/regime/identity lineage. It did not modify production analytical or broker state. This audit became an upstream execution prerequisite.

Accepted audit evidence included complete canonical daily structural checks, source/manifest lineage verification, deterministic sampled 1m->1h/4h reconstruction, independent feature replay, regime chronology, identity integrity, and zero invalid/duplicate/missing-session findings in the accepted scope.

### Phase 16 — browser control plane and production operations

Accepted browser-facing control plane, status/action APIs, audit/idempotency semantics, restart/recovery handling, broker-switch workflow, cleanup planning, and operational health surfaces.

Critical boundary: the browser is a **control plane, not independent execution authority**. Loopback is the default bind; remote bind is disabled by default. Provider cleanup/cancel/flatten mutations were not promoted by Phase 16 acceptance. Live money remained disabled.

### Phase 17 — provider-readonly operational readiness

Accepted on 2026-08-23 with real Webull sandbox and Alpaca paper reads.

Webull account discovery found five readable sandbox accounts. The account selector correctly failed closed on ambiguity. A sandbox margin account was then explicitly selected locally using a sanitized reference; raw account identity remained local and was not printed or committed.

Target-machine evidence:

- Webull account-list HTTP 200;
- Webull balance HTTP 200;
- Webull open-orders HTTP 200 / count 0;
- Webull positions HTTP 200 / count 0;
- Webull read result: `WEBULL_READ_PATH_REACHED_ALL_REQUIRED_ENDPOINTS`;
- Alpaca paper reconciled=true / open orders 0 / positions 0;
- Alpaca result: `ALPACA_READ_PATH_RECONCILED`;
- both broker rows `AVAILABLE`, reconciled=true, safe-to-switch=true;
- provider adapter initializations: exactly 2;
- provider mutation endpoint invocations: 0;
- provider writes: 0;
- live writes: 0;
- accepted Phase 16 artifacts unchanged and hash-bound;
- Phase 17 contract validator: PASS;
- target-machine full regression: **874 passed in 24.83s**;
- Ubuntu CI: PASS;
- Windows CI: PASS;
- final disposition: `phase17_provider_readonly_readiness_accepted=true`.

Phase 17 grants provider **read/reconciliation evidence only**. It does not grant order-mutation authority.

## 5. Active Phase 18 status

Phase 18 is active on draft PR #18 and is currently in the repository/CI preparation portion of the phase. No real provider write is required or allowed by default to develop this code.

### Branch / PR

- branch: `phase-18-paper-provider-mutation-lifecycle-validation`;
- PR: #18 — `Phase 18: Paper Provider Mutation Lifecycle Validation`;
- base: `main`;
- status: draft while repository/CI evidence is being built.

### Phase 18 policy

Contract: `phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`.

The policy binds to accepted Phase 17:

- merge SHA: `65d5a7b58c6894eba27722465741c92db9a33aaf`;
- Phase 17 policy fingerprint: `693113bbb09458ed2939e486f9f6e0a0bda44e331c6419065760586047b93ff8`;
- readiness contract: `phase17-readiness-v1-phase16-artifact-preserving-dual-broker-readonly-reconciliation`.

Current policy fingerprint is expected to remain exact under the Phase 18 validator. Locked rules:

- Webull + Alpaca are the only accepted real paper-provider targets;
- provider reads allowed;
- provider mutation disabled by default;
- explicit per-run target-machine mutation authorization required;
- one broker per mutation run;
- pre/post reconciliation required;
- fresh quote required;
- current risk revalidation required;
- protective geometry required;
- deterministic client order ID required;
- uncertain provider write blocks any further mutation until exact reconciliation;
- destructive cleanup remains separately explicit;
- live execution disabled;
- automatic failover disabled;
- credential values hidden.

### Phase 18 explicit authorization gate

Real mutation cannot be inferred from credentials, endpoints, environment mode, broker selection, prior Phase 17 success, or passing tests.

A target-machine real mutation run must provide:

- an affirmative mutation authorization flag; and
- exact confirmation text `AUTHORIZE_PAPER_PROVIDER_MUTATION`;
- one broker that matches the execution intent and adapter.

The zero-write diagnostic `scripts/diagnose_phase18_mutation_gate.py` tests this local gate **without initializing a broker adapter and without any provider calls**.

### Phase 18 guarded lifecycle already implemented

`packages/execution/phase18_lifecycle.py` wraps the accepted Phase 15 execution engine instead of bypassing it.

Current behavior:

1. require exact Phase 18 authorization;
2. require PAPER/sandbox intent and adapter;
3. require authorized broker == intent broker == adapter broker;
4. read/reconcile account, open orders, positions;
5. for the first real mutation lifecycle, require zero open orders and zero positions;
6. call the accepted Phase 15 engine, preserving deterministic order-plan, risk, preflight, reconciliation, protective geometry, and idempotency rules;
7. require one newly acknowledged provider submission rather than silently reusing an existing order;
8. reconcile the exact deterministic client order ID;
9. cancel only if the order remains open (`SUBMITTED` or `PARTIAL_FILLED`);
10. reconcile after cancellation;
11. if filled/partial exposure exists, stop and require a separate explicit cleanup rather than auto-flattening;
12. if submit/cancel becomes uncertain, attempt read-only reconciliation and stop—no retry, no second mutation, no failover.

### Fake-provider test matrix

Current Phase 18 unit coverage includes:

- default authorization denied;
- missing/incorrect confirmation denied;
- unknown broker denied;
- exact Webull authorization accepted locally;
- exact Alpaca authorization accepted locally;
- pending paper order -> submit -> exact reconcile -> cancel -> post-reconcile flat;
- immediately filled order -> no automatic flatten, cleanup required;
- uncertain submit -> no cancellation/second mutation;
- uncertain cancel -> no retry;
- existing broker exposure -> first mutation blocked;
- authorization/intent/adapter broker mismatch -> blocked before submission.

### Independent validator / CI

`scripts/validate_phase18.py` checks the accepted Phase 17 binding, exact Phase 18 policy fingerprint, disabled-by-default mutation, exact confirmation text, live disabled, and automatic failover disabled.

The GitHub Actions workflow now includes a Phase 18 validator step on both Windows and Ubuntu before the full test suite.

## 6. Broker and execution authority right now

### Webull

- planned primary execution broker;
- accepted real integration target: Webull US sandbox for paper testing;
- sandbox account selection is explicit and fail-closed when ambiguous;
- read-only account/balance/order/position reconciliation is accepted;
- Phase 18 code is preparing the first guarded real mutation lifecycle;
- real sandbox provider order mutation still requires explicit target-machine authorization;
- production/live execution is not promoted.

### Alpaca

- manually selectable secondary/fallback broker;
- paper account read/reconciliation is accepted;
- Phase 18 fake-provider and policy work covers Alpaca as an explicit selectable broker;
- paper-provider mutation still requires explicit target-machine authorization;
- automatic failover from Webull to Alpaca is forbidden.

### Broker switching

The browser may request a switch, but the switch cannot bypass reconciliation. Open orders/positions must be inspected. Any provider mutation required to cancel/close/flatten exposure requires the corresponding explicit authority. The system must reconcile to the required safe state before activating another broker.

## 7. Current real-provider checkpoint

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

Phase 18 development does not itself cross this checkpoint. Until an actual target-machine mutation run is explicitly authorized, ATLAS must not perform real provider:

- order submission;
- order replacement;
- order cancellation;
- flatten/close writes;
- broker-switch cleanup writes.

Live execution and automatic cross-broker failover remain disabled regardless.

Before asking for/using the real mutation authorization, the repository-side Phase 18 code must first reach a green evidence boundary: focused tests, independent validator, full regression, Windows/Ubuntu CI, synchronized docs, and a sanitized target-machine runner plan.

Paper-provider mutation acceptance must remain separate from any later live-money promotion.

## 8. Current environment/configuration template

The tracked `.env.example` intentionally mirrors the desired provider layout while remaining non-secret.

Current template structure:

```text
ATLAS_ENV=development
OPENAI_API_KEY=
DATABASE_URL=

MASSIVE_API_KEY=
MASSIVE_S3_ACCESS_KEY_ID=
MASSIVE_S3_SECRET_ACCESS_KEY=
MASSIVE_ENDPOINT=https://files.massive.com

WEBULL_PAPER_APP_KEY=
WEBULL_PAPER_APP_SECRET=
WEBULL_LIVE_APP_KEY=
WEBULL_LIVE_APP_SECRET=

ALPACA_PAPER_ENDPOINT=https://paper-api.alpaca.markets/v2
ALPACA_PAPER_API_KEY=
ALPACA_PAPER_API_SECRET=
ALPACA_LIVE_ENDPOINT=https://api.alpaca.markets
ALPACA_LIVE_API_KEY=
ALPACA_LIVE_API_SECRET=

IBKR_HOST=127.0.0.1
IBKR_PORT=4002
IBKR_CLIENT_ID=17
```

The template also keeps a commented `ALPACa_Security_Code` placeholder **blank**. Security-code values, even on commented lines, are credentials and must not be committed.

Important interpretation rules:

- endpoint URLs and localhost/default connection settings are not secrets;
- blank live credential placeholders do not authorize live execution;
- live endpoint presence does not promote a live broker adapter;
- IBKR configuration placeholders do not mean an IBKR integration is accepted;
- real credential values remain in the local `.env` or another approved secret store;
- raw broker account IDs, API secrets, security codes, passwords, tokens, and session credentials must never be committed;
- generated `webull_trade_sdk.log*` files are ignored.

## 9. Development and validation workflow

The project uses an accelerated evidence-boundary workflow:

- batch implementation + targeted tests + validator + CLI/orchestration + documentation/status updates;
- avoid conversational micro-gates when the architecture already resolves the decision;
- run full regression and Windows/Ubuntu CI at coherent batch boundaries;
- use independent validators for data/model/broker authority transitions;
- use one complete PowerShell block when target-machine/local evidence is required;
- fail closed on ambiguity, missing lineage/data, broker-state uncertainty, uncertain provider writes, or invalid geometry;
- do not invent post-hoc thresholds to force acceptance.

User input is normally required only for unavailable local/external evidence, a validation result that changes the technical choice, an irreversible/authority-changing write, a broker/live-money transition, or a genuine unresolved product/design choice.

## 10. Branch and PR policy

- `main` contains accepted work.
- Use a focused branch/PR for substantial new phases or authority-changing work packages.
- Record target-machine and CI acceptance evidence in the PR before merge.
- Delete merged phase branches after closeout unless there is a concrete retention reason.
- Historical commits/PRs remain the evidence ledger even after branch deletion.

## 11. Documentation maintenance policy

Documentation synchronization is part of every meaningful ATLAS change, not an optional cleanup step.

At each coherent work-package/phase boundary:

1. update root `README.md` if current state, architecture summary, provider/broker configuration, broker authority, or next checkpoint changed;
2. update `docs/roadmap.md` if architecture, phase status, evidence boundary, development protocol, configuration policy, or authority transition changed;
3. update this `docs/current_status.md` with the latest accepted evidence, active branch/PR, current authority state, configuration notes, and exact next action;
4. update the active PR body with the concise acceptance ledger;
5. update `.env.example` and related configuration notes when provider/configuration layout changes;
6. keep historical phase/fix documents intact unless correcting a factual error in that historical record.

A future chat should never have to infer the current checkpoint from old conversation memory when the repository can state it directly.

## 12. Future-chat startup procedure

A new chat/session working on ATLAS should do this before changing code:

1. inspect current `main` and any open PR/branch;
2. read `README.md`;
3. read `docs/roadmap.md`;
4. read this file completely;
5. inspect `.env.example` for the current provider variable layout, but never assume configuration presence grants authority;
6. inspect the latest merged PR(s) when more accepted evidence detail is needed;
7. inspect the active PR when a phase is in progress;
8. verify that planned work does not cross an authority boundary without explicit approval;
9. treat older Chart Monitor pipeline plans and old phase READMEs as historical unless the current roadmap explicitly incorporates them.

## 13. Exact continuation point

The correct continuation point is **inside Phase 18 repository/CI preparation, after accepted Phase 17 read-only provider readiness and before any real paper/sandbox provider mutation**.

Immediate next work:

1. inspect/fix Phase 18 CI until Windows and Ubuntu are green;
2. finish any missing lifecycle edge-case coverage or target-machine runner safeguards;
3. update PR #18 with exact code-head CI evidence;
4. only after the repository evidence is clean, request/use explicit authorization for one controlled Webull sandbox mutation lifecycle;
5. reconcile and record the target-machine result; do not auto-failover to Alpaca and do not promote live money.

The real-provider checkpoint remains:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`
