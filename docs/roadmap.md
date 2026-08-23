# ATLAS Master Roadmap

**Living architecture and authority document. Last synchronized: 2026-08-23.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This roadmap is the project-level direction lock. Implementation may evolve when measured evidence requires it, but changes must preserve the architectural and safety boundaries below unless an explicit design decision replaces them.

For the detailed current handoff and accepted evidence ledger, read [`current_status.md`](current_status.md) together with this roadmap. The root [`README.md`](../README.md) provides orientation.

## 1. Mission

Build a broad-market discovery, quantitative analysis, decision-support, learning, and eventually automated-trading platform that can:

1. observe a large U.S. market universe;
2. maintain point-in-time-safe market data, instrument identity, features, and regimes;
3. discover promising candidates cheaply and quickly;
4. estimate outcome probabilities with conventional ML;
5. route candidates to strategies appropriate to current regime/context;
6. spend expensive research only on promoted candidates;
7. combine quantitative, historical-analogue, simulation, news/event/sentiment, instrument, and risk evidence into one case;
8. subject that case to an independent AI review rather than letting AI replace the deterministic engine;
9. construct an executable trade plan only after risk and geometry checks;
10. operate paper/shadow before live execution;
11. record outcomes so models, strategies, routing, and risk policies can be evaluated and improved;
12. expose the system through a browser control plane with clear reasoning, broker/mode controls, candidates, alerts, positions, and operational health.

The legacy Chart Monitor is preserved. ATLAS is the redesign/rebuild path; legacy components are not deleted merely because equivalent ATLAS functionality is introduced.

## 2. Target architecture

Primary flow:

`market/reference data -> Parquet data lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> strategy routing/evaluation -> candidate promotion -> historical analogue + Monte Carlo/scenario research -> news/events/sentiment -> instrument selection -> entry/stop/target/horizon -> portfolio/risk -> consolidated deterministic case -> independent AI audit -> alert/paper/shadow/live execution -> outcome/performance learning -> browser control plane`

Storage/state roles:

- **Parquet** remains the durable analytical and historical lake.
- **DuckDB** remains the local analytical query engine.
- **PostgreSQL** is the target persistent operational-state store for state that should not live in the analytical lake.
- Provider-native facts, canonical facts, derived features, strategy/regime state, model evidence, AI audit, and broker state remain explicitly separated.

## 3. Non-negotiable boundaries

### Data and identity

- Preserve exact provider-native ticker text/case.
- Literal ticker text alone never proves identity continuity.
- Historical populations are observation-driven and point-in-time safe; current survivor state is not projected backward.
- Strong security-level evidence is preferred; false split is safer than false merge when continuity evidence is absent.
- Unresolved identity/structural evidence is quarantined or excluded rather than guessed.
- Long-running acquisition/replay jobs must be resumable, idempotent, checkpointed, and duplicate-safe.
- Provider/canonical/derived promotions require explicit lineage and independent validation.
- Do not fabricate unavailable intraday history from daily bars.
- Finalized canonical facts remain authoritative over provisional live observations.

### Discovery, regimes, and strategies

- Broad discovery is intentionally cheap and instrument-agnostic.
- Default discovery health/activity filtering is separate from watchlist/position/custom mandatory routing.
- Regime classification is context and routing evidence.
- Strategy-to-regime routing belongs in the router/orchestration layer, not hidden inside individual strategy implementations.
- Strategy implementations emit deterministic setup evidence; they do not silently own broker/order semantics.
- Expensive analogue, Monte Carlo/scenario, options-chain, and deep contextual work runs only after candidate promotion.
- Missing authoritative sector/identity/history context stays unavailable rather than being guessed.

### Machine learning

- The accepted conventional ML layer produces `p_down`, `p_neutral`, and `p_up` probability evidence.
- ML argmax is diagnostic only; it is **not** a trade signal.
- Chronological walk-forward evaluation, purge/embargo where required, leakage controls, immutable OOS predictions, and reproducibility remain mandatory.
- A new dataset/model never silently replaces an accepted production model.
- Challengers require separately versioned evidence and a separate acceptance decision before production authority changes.
- The LLM/AI layer is not the predictive model.

### AI review

- AI receives the consolidated deterministic case and independently returns an approve/cautious/reject-style audit with grounded reasons, risks, and plan observations.
- AI may challenge engine conclusions, but it does not rewrite historical facts, probability outputs, strategy evidence, trade geometry, sizing, or validation evidence.
- Engine evidence and AI review remain separately visible for auditability.
- AI review does not create broker authority.

### Trade geometry and portfolio risk

- LONG geometry requires `stop < entry < target`.
- SHORT geometry requires `stop > entry > target`.
- A case with invalid geometry cannot advance.
- Sizing/exposure/concentration/correlation/liquidity decisions remain deterministic and independently verifiable.
- Missing portfolio evidence is unavailable, not guessed.

### Execution

- Webull is the planned primary execution broker for paper/sandbox and later controlled live operation.
- Alpaca is the manually selectable secondary/fallback broker.
- Broker adapters must be replaceable without changing strategy logic.
- Automatic cross-broker failover is disabled.
- Broker changes are explicit only and require broker-state reconciliation.
- Browser broker switching must inspect open orders/positions, warn, and may cancel/close only when the corresponding provider-mutation authority has been explicitly granted; after any mutation the broker must be reconciled before switching.
- Fresh-quote translation, current risk checks, reconciliation, protective stop/target, idempotent client identifiers, and uncertainty fail-closed behavior are mandatory before provider mutation.
- Unknown/uncertain provider state never authorizes a retry or second mutation without exact reconciliation.
- Live money is never the first validation environment: **paper -> shadow/observation -> controlled live**.

### Browser/control plane

- The browser is a control/monitoring plane, not a separate execution authority.
- Credential values are never exposed to browser/API status output.
- Local loopback bind is the default; remote bind is disabled by default.
- Operational actions must be audited and idempotent.

## 4. Accepted foundation through Phase 10

### Phases 1-3

Established foundation/configuration/secret handling, Massive restartable flat-file ingestion, canonical market schemas/storage, session-aware derived bars, manifest/checkpoint lineage, and validation.

### Phase 4 — Instrument Identity and Historical Lake

Accepted provider-native symbol case, point-in-time reference snapshots, security-safe identity, authoritative ticker-event continuity when available, ticker-reuse protection, anomaly reconciliation, and complete provider/canonical/derived historical-lake auditing.

Massive production history authority begins at **2021-08-16**.

### Phase 5 — Live Market State

Accepted explicit delayed/realtime Massive live modes, provisional live state, freshness/reconnect-gap accounting, journal/restart behavior, and finalized-data reconciliation. Live observations remain provisional and never overwrite finalized canonical data.

### Phase 6 — Feature Engine

Accepted 33 deterministic point-in-time quantitative features, batch/incremental equivalence, recursive-state checkpoints, and persistent feature policy:

- 1d permanent;
- 4h permanent;
- 1h permanent;
- 15m on-demand/cache;
- 1m live/current state only.

The accepted permanent 2021-08-16 through 2026-08-14 feature lake contained **154,188,221 rows** and passed deep lineage plus historical-to-incremental continuation checks.

### Phase 7 — Universe Registry

Accepted point-in-time security-safe universe construction and explicit routing/exclusion semantics. Accepted 2026-08-14 routed discovery universe: **12,066 instruments**.

### Phase 8 — Broad Discovery

Accepted cheap-first broad discovery, explicit health/activity filtering, vectorized setup/evidence scoring, deterministic state thresholds/hysteresis, and an accepted 2026-08-14 broad-ready population of **8,034 instruments**.

Locked state thresholds:

- WATCH >= 0.35;
- WARM >= 0.50;
- HOT >= 0.60 plus direction/coverage guards.

### Phase 9 — Market/Sector/Ticker Regime Engine

Accepted market and sector-proxy context, optional authoritative SIC evidence, stable-identity ticker regimes, persistence, self-relative risk state, and hierarchy validation. Missing context remains explicit absence. Accepted 2026-08-14 ticker-state input population: 8,034; effective current ticker states: 7,338.

### Phase 10 — Conventional ML Probability/Evaluation

Accepted production model:

- id `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- specification `hgb_leaf15_iter100`;
- 33 point-in-time quantitative predictors;
- raw `p_down/p_neutral/p_up` probabilities;
- no post-hoc calibration;
- final protected holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

The accepted HGB remains production authority unless a separately versioned challenger is explicitly accepted later.

## 5. Accepted historical extension

The post-Phase-10 historical-data work is a **foundation extension**, not a replacement phase hierarchy.

Accepted source boundary:

- Alpaca raw SIP daily history: **2016-01-04 through 2021-08-13**;
- Massive production history: **2021-08-16 onward**;
- no synthetic pre-2021 4h/1h data from daily bars.

The historical source audit and backfill preserved exact provider symbols, observation-driven historical membership, identity segmentation, corporate-action/continuity evidence, source-seam validation, feature/regime replay, and ML research lineage.

The longer-history C result remains separately versioned challenger/research evidence. It may support deeper regime/strategy/backtest/analogue work but did not silently replace the accepted Phase 10 model.

## 6. Accepted phases 11-17

### Phase 11 — Strategy Evaluation and Regime Routing

Accepted strategy interface/catalog, deterministic external regime router, identity-safe historical strategy evaluation, accepted Phase 10 probability attachment as evidence, and candidate promotion.

Eight deterministic strategy variants were evaluated. Accepted support classification:

- SUPPORTED: 0;
- MIXED: 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: 5.

Promotion requires supported history + current route compatibility + current firing. Therefore zero supported strategies correctly produced zero promoted research candidates rather than triggering threshold relaxation.

### Phase 12 — Deep Candidate Research

Accepted promoted-only historical analogue retrieval, forward distributions, similarity diagnostics, and deterministic empirical scenario/bootstrap research. Zero promotions is a valid no-op; expensive history is not opened for non-promoted names.

### Phase 13 — Context, Instrument, Geometry, and Portfolio Risk

Accepted contextual evidence, instrument selection, deterministic entry/stop/target/horizon construction, liquidity/sizing, exposure/concentration/correlation, and portfolio-risk admissibility.

Equity is the accepted v1 primary execution instrument. Options can be finalist context when authoritative chain evidence exists but cannot become primary without a separately accepted relative-value model.

### Phase 14 — Independent AI Audit and Alerting

Accepted structured AI audit dispositions `APPROVE`, `CAUTIOUS`, `REJECT`, provider-independent contracts, schema-constrained output, independent validation, and Engine-vs-AI artifact presentation. AI remains observational/audit context, never execution authority.

### Phase 15 — Broker Execution and Outcome Learning

Accepted broker-neutral order/execution schemas and shadow/paper execution semantics with Webull primary, Alpaca manually selectable secondary/fallback, explicit switching, no automatic failover, fresh-quote entry translation, current risk/reconciliation, protective orders, idempotent client IDs, uncertainty fail-closed semantics, and descriptive outcome learning.

Phase 15 acceptance did **not** promote live execution and did not by itself authorize real provider mutation.

### Cumulative Data and Lineage Integrity Audit

Accepted a read-only cumulative historical/source/canonical/feature/regime/identity integrity gate before execution advancement. It became an upstream execution prerequisite and did not mutate production analytical or broker state.

### Phase 16 — Browser Control Plane and Production Operations

Accepted browser status/action APIs, operational health, audit ledger, restart/recovery, broker-switch processor, cleanup planning/confirmation semantics, and loopback-first operation.

Phase 16 did **not** promote provider cleanup/cancel/flatten writes or live money. The browser cannot bypass Phase 15 broker/risk/reconciliation/idempotency contracts.

### Phase 17 — Provider-Readonly Operational Readiness

Accepted 2026-08-23 using real Webull sandbox and Alpaca paper **read-only** provider calls while preserving accepted Phase 16 artifacts unchanged and hash-bound.

Webull account discovery returned five readable sandbox accounts; ambiguity failed closed. An operational sandbox account was explicitly selected by sanitized ref `3d64d273c694250b`; raw account identity remained local.

Accepted target-machine evidence:

- Webull account-list/balance/open-orders/positions read path passed;
- Webull open orders 0 / positions 0;
- Alpaca paper reconciled with open orders 0 / positions 0;
- both broker rows `AVAILABLE`, reconciled=true, safe-to-switch=true;
- exactly two provider adapter initializations;
- provider mutation endpoint invocations 0;
- provider writes 0;
- live writes 0;
- automatic cross-broker failover disabled;
- live execution disabled;
- Phase 16 acceptance artifacts unchanged/hash-bound;
- Phase 17 validator PASS;
- target-machine regression **874 passed in 24.83s**;
- Ubuntu CI PASS;
- Windows CI PASS.

Deliverable: accepted dual-broker provider-readiness evidence **without** provider-mutation or live authority.

## 7. Accelerated delivery protocol

Quality gates remain; **micro-step ceremony does not**.

### Batch by evidence boundary

A normal implementation batch should include, where applicable:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status update`

These should usually land as one coherent work package rather than a separate conversational approval and commit for every small sub-step.

### Validation cadence

During a batch:

- run focused tests while changing code;
- run the full regression suite and cross-platform CI at the batch boundary;
- run independent validators for data promotion, model selection/registration, broker-state transitions, or other authority-changing operations;
- keep read-only diagnostics and preregistration checks automated inside the batch rather than turning each into a user-facing micro-gate.

Independent validation is retained because it has caught real semantic defects. Acceleration comes from automating/grouping checks, not removing them.

### User interaction / local target-machine work

When local data/provider/hardware evidence is required, provide one PowerShell block containing the smallest complete safe sequence for the batch, including expected test/output landmarks.

Stop for user input only when one of these is true:

1. required local/external evidence is unavailable to repo/CI;
2. validation failure changes the technical decision;
3. an irreversible or authority-changing write needs explicit approval;
4. a broker/live-money transition is involved;
5. a genuine product/design choice cannot be resolved from locked architecture or measured evidence.

Otherwise continue autonomously through the work package.

### Evidence policy

- Do not invent thresholds to force acceptance; measure first or preregister before viewing decision data.
- Do not advance merely because code ran; advance on evidence appropriate to the risk.
- Fail closed on ambiguous identity, lineage, missing data, broker state, provider-write uncertainty, or trade geometry.
- Preserve rollback artifacts for production data/state promotions.
- Keep PR descriptions/acceptance records as the concise evidence ledger.

## 8. Repository and branch policy

- `main` contains accepted work.
- Substantial phases and authority-changing work packages use focused branches/PRs.
- Acceptance evidence is recorded in the active PR before merge.
- Completed phase branches are deleted after merge unless there is a concrete retention reason.
- Branch deletion never removes merged commits/PR history.
- Real `.env` stays local and ignored; `.env.example` remains a non-secret template.

## 9. Documentation synchronization policy

Documentation is part of the acceptance package for every meaningful ATLAS change.

At each coherent work-package/phase boundary:

1. update root `README.md` when current project state, architecture summary, broker authority, or next checkpoint changes;
2. update this roadmap when architecture, phase status/responsibility, validation protocol, or authority boundaries change;
3. update [`current_status.md`](current_status.md) with the latest accepted evidence, current operating state, and exact continuation point;
4. update the active PR body with concise target-machine + CI acceptance evidence;
5. preserve old `README_PHASE_*`, `README_ATLAS_*`, phase-fix notes, and historical acceptance documents as historical evidence unless correcting a factual error in that historical record.

A future chat/session should be able to recover the project accurately from the repository without depending on conversational memory.

## 10. Immediate priority / authority boundary

**Phase 17 is accepted and merged.** The exact next checkpoint is:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

No implementation or provider call may infer mutation authorization merely from Phase 17 success.

Until the user explicitly authorizes that checkpoint:

- real provider order submission remains disabled;
- real provider order cancellation/replacement remains disabled;
- provider flatten/close mutation remains disabled;
- browser broker-switch cleanup may not mutate a provider;
- live execution remains disabled;
- automatic cross-broker failover remains disabled.

When explicitly authorized, the next coherent work package may validate real Webull sandbox / Alpaca paper order lifecycle behavior under the already accepted Phase 15/16 safety contracts. The package should cover, as supported by the provider and accepted adapter semantics:

- exact provider preflight or documented local preflight equivalent;
- fresh quote and entry-drift validation;
- current account/risk/position/order reconciliation;
- valid protective stop/target geometry;
- idempotent client order identifiers;
- submit acknowledgement and exact-client-order reconciliation;
- partial-fill/terminal-state handling;
- cancel/replace behavior where supported;
- uncertain-write recovery without blind retry;
- broker-state reconciliation after mutation;
- safe cleanup/flat-state proof when required;
- evidence ledger and outcome attribution;
- zero live writes and zero automatic failover.

Paper-provider mutation acceptance must remain a separate checkpoint from any later live-money promotion.

## 11. Future-chat startup rule

Before changing ATLAS in a new chat/session:

1. inspect current `main`, open PRs, and active branches;
2. read root `README.md`;
3. read this roadmap;
4. read `docs/current_status.md` completely;
5. inspect the latest merged PR(s) when detailed acceptance evidence is needed;
6. confirm the planned work does not cross an authority boundary without explicit approval;
7. do not revive superseded legacy Chart Monitor pipeline assumptions or old phase instructions when they conflict with the living roadmap/current-status documents.

**Current correct continuation point: after accepted Phase 17, before any real paper/sandbox provider mutation.**
