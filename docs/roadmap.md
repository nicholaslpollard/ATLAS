# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-23.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This file is the long-term architecture and authority lock. Implementation may evolve when measured evidence requires it, but changes must preserve the data-integrity, validation, and trading-authority boundaries below unless an explicit replacement decision is documented and independently validated.

For exact operational continuation, read [`current_status.md`](current_status.md). For the mandatory development sequence, read [`phase_flow.md`](phase_flow.md). During active Phase 18, also read [`phase18_operational_validation.md`](phase18_operational_validation.md). The root [`README.md`](../README.md) is project orientation.

## 1. Mission

Build a broad-market system that can:

1. observe a large U.S. market universe;
2. maintain point-in-time-safe market/reference data, instrument identity, features, and regimes;
3. discover candidates cheaply before spending expensive research;
4. estimate outcome probabilities with conventional ML;
5. route candidates to deterministic strategies appropriate to context/regime;
6. promote only evidence-supported candidates into deeper analogue/scenario/options/news analysis;
7. produce deterministic entry/stop/target/horizon/risk plans;
8. subject the deterministic case to an independent AI audit;
9. alert, shadow, paper-trade, and eventually trade live only under explicit authority;
10. learn descriptively from outcomes without silently changing accepted model/strategy authority;
11. expose operational state through a browser control plane without making the browser an execution authority.

## 2. Architecture

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/compute roles:

- Parquet: durable analytical/history lake.
- DuckDB: analytical/query engine.
- PostgreSQL: target persistent operational state.
- Massive: primary accepted market/reference-data provider.

## 3. Mandatory phase execution contract

ATLAS advances by explicit numbered phases. The normative process is defined in `docs/phase_flow.md`.

Every numbered phase follows:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

This is a control framework, not a requirement to stop after every arrow. When a full phase is well-defined, its dependencies are available, and no external/authority boundary interrupts it, the preferred cadence is to implement the **entire phase in one coherent batch** and then perform the strongest required validation at the phase evidence boundary.

Required principles:

- define purpose, upstream binding, scope, non-goals, authority, deliverables, validation, evidence, and failure behavior before substantive implementation;
- do not treat code existence or passing tests alone as phase acceptance;
- do not silently expand provider/live authority from credentials, configuration, connectivity, or prior acceptance;
- use subphases only when a genuine authority/external-condition boundary exists;
- combine related code/tests/validators/orchestration/docs instead of creating artificial checkpoints;
- use focused tests during development where they provide useful feedback, but do not require full regression after every small commit;
- run full regression and Windows/Ubuntu CI at meaningful evidence boundaries, normally once per coherent phase batch unless risk justifies an intermediate boundary;
- target-machine work is required only for evidence unavailable in CI/mocks and should not be repeated when relevant code has not changed;
- complete and merge the current numbered phase before activating the next numbered phase unless an explicit roadmap exception is documented;
- synchronize living docs and PR evidence at meaningful evidence/acceptance boundaries rather than after every minor edit;
- explicit user/provider/live authority checkpoints override batching and may never be crossed implicitly.

Current application:

- Phase 18A — Pre-mutation software validation: **ACCEPTED / COMPLETE**.
- Phase 18B — Real paper-provider operational certification: **WAITING_EXTERNAL**.
- Phase 19: **NOT ACTIVE / NOT YET DEFINED**.

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

- Alpaca raw SIP daily controlled extension: 2016-01-04 through 2021-08-13.
- Massive authority: 2021-08-16 onward.
- Pre-2021 1h/4h history remains absent rather than fabricated.

## 5. ML authority rules

Production ML emits raw three-class probabilities:

- `p_down`;
- `p_neutral`;
- `p_up`.

Argmax is diagnostic only and is never a standalone trade signal. Accepted production model authority is immutable until an explicit challenger/acceptance process replaces it; longer-history or challenger research cannot silently overwrite the accepted model.

Accepted model:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- deterministic replay exact.

## 6. Strategy/research rules

- Regime routing belongs in scanner/router orchestration, not embedded inside strategy implementations.
- Strategies emit deterministic case evidence, not opaque conclusions.
- Expensive historical analogue, Monte Carlo/scenario, options, and event/news work is promoted-candidate only.
- No-op/zero-promotion states are valid outcomes; thresholds are never relaxed after seeing results merely to create trades.
- Accepted Phase 11 support: 0 SUPPORTED, 3 MIXED, 5 UNSUPPORTED among eight tested variants.

## 7. AI authority rules

AI is an independent auditor/reviewer. It may approve, caution, or reject a deterministic case and identify risks, but it cannot:

- rewrite accepted historical/quantitative evidence;
- change deterministic direction/instrument/geometry/position size as authoritative facts;
- manufacture a trade from a rejected deterministic case;
- create provider-order authority;
- promote live execution.

## 8. Geometry and portfolio-risk rules

Mandatory geometry:

- LONG: `stop < entry < target`;
- SHORT: `stop > entry > target`.

Accepted Phase 13 operational risk envelope used by Phase 18 certification includes:

- risk at stop <= 0.5% of current equity;
- single-name notional <= 10% of current equity;
- liquidity/buying-power/account-state checks;
- current exposure/concentration/correlation revalidation when applicable.

## 9. Broker architecture

### Webull

Primary planned broker for paper/sandbox and, only after a future separate live-authority phase, controlled live execution.

### Alpaca

Manually selectable secondary/fallback. It is not an automatic failover destination.

### Switching

Broker switching is explicit only. Before switching, ATLAS must inspect/reconcile open orders and positions. Any cancel/close/flatten required to make a broker safe is itself a provider mutation and must possess the corresponding explicit authority. Unknown broker state fails closed.

### Live

Live execution is disabled. Paper-provider acceptance is not live acceptance. A later live-money phase must preregister limits, operational observation, failure handling, and explicit authorization independently.

## 10. Accepted phase ledger

### Phase 1 — Foundation

Project/config/session/time foundations, environment separation, canonical timezone and basic validation.

### Phase 2 — Provider ingestion foundation

Restartable provider acquisition, storage contracts, checkpoints, and raw evidence handling.

### Phase 3 — Canonical/session-aware data

Parquet/DuckDB canonical data foundations, exchange/session semantics, duplicate-safe/replay-safe handling.

### Phase 4 — Instrument identity/history

Security-safe instrument identity, point-in-time reference evidence, stable identifiers where authoritative, ambiguity quarantine.

### Phase 5 — Live market state

Massive delayed/realtime WebSocket state, explicit freshness/delay/gap semantics, provisional journal/snapshot behavior, finalized-data authority.

### Phase 6 — Feature engine

33 deterministic point-in-time features with explicit warmup and deterministic batch/incremental behavior.

### Phase 7 — Universe registry

Point-in-time instrument routing/eligibility with no retrospective survivor projection or guessed identity.

### Phase 8 — Broad discovery

Cheap-first broad-market discovery, health/activity routing, absolute setup-state thresholds, persistence/hysteresis.

### Phase 9 — Regime engine

Market/sector/ticker regime hierarchy, prior-only thresholds, persistence, ticker risk, optional authoritative SIC, no guessed sector crosswalk.

### Phase 10 — ML probability/evaluation

Point-in-time training population, label/feature leakage controls, walk-forward evaluation, model registry/acceptance, protected holdout, raw probability surface.

### Historical extension/audit

Controlled Alpaca raw-SIP daily extension back to 2016, provider seam validation, cumulative data/lineage integrity audit. No synthetic pre-2021 intraday.

### Phase 11 — Strategy evaluation/regime routing

Deterministic strategy variants, external regime routing, historical support classification, candidate-promotion policy.

### Phase 12 — Deep candidate research

Promoted-only historical analogue and deterministic empirical scenario/bootstrap research.

### Phase 13 — Context/instrument/geometry/portfolio risk

Deterministic instrument choice, geometry, position sizing, liquidity, exposure/concentration/correlation and risk planning.

### Phase 14 — Independent AI audit/alerting

Structured independent AI review and Engine-vs-AI artifact alerts with AI authority strictly bounded.

### Phase 15 — Broker-neutral shadow/paper execution + outcome learning

Webull primary/Alpaca manual secondary, fresh quote, provider preflight, reconciliation, current risk, protective geometry, deterministic client IDs, uncertain-write fail-closed behavior, descriptive outcome records, live disabled.

### Phase 16 — Browser control plane/production operations

Loopback-first browser/API control plane, CSRF/same-origin protections, action audit/idempotency, restart recovery, explicit broker switch and cleanup planning. Browser is not execution authority; provider cleanup writes/live money not promoted.

### Phase 17 — Provider-readonly operational readiness

Accepted real Webull sandbox + Alpaca paper reads/reconciliation while provider mutation remained disabled.

Accepted target-machine evidence:

- Webull account-list/balance/orders/positions reads reached successfully;
- explicit sanitized Webull account selection after five readable accounts;
- Webull 0 open orders, 0 positions;
- Alpaca paper reconciled, 0 open orders, 0 positions;
- both brokers AVAILABLE/reconciled;
- provider mutation endpoint invocations 0;
- provider writes 0;
- live writes 0;
- local 874 tests passed;
- Windows/Ubuntu CI passed.

Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.

## 11. Active Phase 18 — Paper Provider Mutation Lifecycle Validation

Phase 18 is active on draft PR #18 and branch `phase-18-paper-provider-mutation-lifecycle-validation`.

Policy contract:

`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Policy fingerprint:

`9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`

### Phase 18A — Pre-mutation software validation

**State: ACCEPTED / COMPLETE**

Accepted evidence:

- authority gate and paper lifecycle implementation complete;
- fake-provider production semantic coverage complete;
- separate operational validation-order path complete;
- independent Phase 18 validator PASS;
- focused target-machine Phase 18 suite: 34 passed;
- final target-machine full regression at baseline `94a859fc6d44c22a6f8852c1488215a6677806a0`: **908 passed in 23.50s**;
- final target-machine working tree clean;
- GitHub Actions run `32662817172`: SUCCESS on Ubuntu and Windows with all validators through Phase 18 green;
- no provider mutation performed;
- live execution still disabled;
- automatic failover still disabled.

Windows loopback portability hardening remained test-only and did not modify accepted production HTTP/broker/execution authority.

### Phase 18B — Real paper-provider operational certification

**State: WAITING_EXTERNAL**

Real provider mutation remains behind:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

A real run requires:

- one selected broker;
- `--authorize-paper-provider-mutation`;
- exact confirmation `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credential presence, endpoint configuration, environment state, connected account, Phase 17/18A success, or passing tests do not grant mutation authority.

Locked operational order:

- PAPER/SANDBOX only;
- EQUITY BUY;
- exactly 1 share;
- LIMIT / DAY;
- no extended hours;
- entry 5% below fresh realtime bid;
- stop 2% below entry;
- target 2% above entry;
- max notional $1,000;
- Phase 13 10% single-name cap;
- Phase 13 0.5% loss-at-stop cap.

Expected lifecycle:

`realtime quote -> plan-only validation -> review -> explicit authorization -> reconcile flat -> prove deterministic client ID absent -> preflight -> Webull sandbox submit once -> exact reconcile -> cancel once if still open -> exact reconcile flat -> sanitized evidence`

If filled/partially filled, ATLAS stops for separate cleanup authorization and does not auto-flatten. Alpaca is not an automatic failover destination.

Certification requires an actively running accepted Phase 5 realtime focused `Q.<ticker>` stream and Phase 15 quote evidence that is SUBSCRIBED, REALTIME, delay 0, gap-free, regular-session, exact ticker, and FRESH. Weekends, holidays, stale/delayed data, premarket, after-hours, and stopped streams fail closed.

## 12. Phase 18 closeout sequence

Phase 18A is complete. The remaining flow is Phase 18B only:

1. wait for a regular U.S. equity session;
2. choose exact provider-native ticker suitable for the one-share <$1,000 cap;
3. start focused Massive realtime `Q.<ticker>` stream and keep it active;
4. run plan-only operational validation first;
5. verify 0 broker/provider calls/writes in plan-only mode;
6. review exact one-share plan;
7. obtain explicit paper-provider mutation authorization;
8. certify Webull sandbox first;
9. submit exactly once;
10. reconcile exact deterministic client ID;
11. cancel exactly once if still open;
12. reconcile zero-open/flat;
13. if filled/partially filled, stop for separate cleanup authorization;
14. never auto-fail over to Alpaca;
15. record sanitized target-machine evidence;
16. rerun validators/regression only if code changes or acceptance evidence requires it;
17. synchronize README/roadmap/current-status/phase spec/PR;
18. mark PR #18 ready and merge after accepted Phase 18B evidence;
19. verify `main` and delete merged Phase 18 branch;
20. only then define and activate Phase 19.

## 13. Batch-first development protocol

ATLAS uses coherent implementation batches and evidence boundaries, not micro-step ceremony.

Normal coherent work package:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status`

Preferred cadence:

- implement the largest coherent portion of the active phase that can be safely completed with the currently available dependencies;
- when feasible, implement the **whole phase** before the formal full-regression/CI boundary;
- use focused tests during coding as cheap feedback rather than as mandatory stop points;
- run full regression + Windows/Ubuntu CI at batch/evidence boundaries, especially before acceptance/merge, after broad shared-code changes, or when failures indicate wider regression risk;
- keep independent validators mandatory at data/model/broker-authority transitions even when the rest of the phase is batched;
- automate read-only diagnostics/preregistration where possible;
- request target-machine interaction only where local/external evidence is genuinely required;
- do not rerun target-machine/provider evidence solely because documentation or unrelated code changed;
- synchronize living docs once per meaningful batch/evidence boundary rather than after every small edit;
- split a phase only for a genuine external, risk, dependency, or authority boundary — not to manufacture checkpoints;
- fail closed on ambiguous identity, missing lineage/data, invalid geometry, broker uncertainty, and uncertain writes.

The goal is the fastest cadence that preserves high-quality evidence, reproducibility, and explicit authority control.

## 14. Documentation policy

Documentation synchronization is part of implementation, not optional cleanup.

Every meaningful batch/evidence boundary must update, as applicable:

- root `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- `docs/phase_flow.md` when the process changes;
- active phase living specification;
- active PR acceptance/evidence ledger;
- `.env.example` / configuration notes when configuration changes.

Historical phase/fix READMEs remain frozen provenance unless correcting a factual historical error.

## 15. Configuration/security policy

Tracked `.env.example` may contain public/default endpoint values and blank secret placeholders. It must never contain:

- API secrets;
- passwords;
- security codes;
- raw broker account IDs;
- tokens.

Current non-secret defaults include Massive file endpoint, Alpaca paper/live endpoints, and optional local IBKR host/port/client ID. Their presence does not grant provider or live authority.

## 16. Next-phase rule

Phase 19 is not active and should not be substantively implemented while Phase 18 remains open.

After Phase 18B is accepted and merged:

1. inspect the remaining architectural roadmap and operational gaps;
2. define Phase 19 purpose and accepted upstream binding;
3. lock scope/non-goals/authority;
4. preregister tests, validators, target evidence, and acceptance criteria;
5. create the focused Phase 19 branch/PR;
6. implement as much of Phase 19 as possible in one coherent batch — preferably the entire phase — before stopping for the formal evidence boundary unless measured risk, an external prerequisite, or an authority checkpoint makes an earlier boundary materially useful.

## 17. Future-chat recovery protocol

A new session should:

1. inspect current `main`, branches, open PRs, and latest CI;
2. read `docs/current_status.md`;
3. read this roadmap;
4. read `docs/phase_flow.md`;
5. read the active phase spec;
6. read root README;
7. inspect active PR evidence;
8. preserve provider/live authority boundaries;
9. preserve the batch-first/evidence-boundary cadence rather than reverting to micro-checkpoints;
10. continue from the exact active phase/subphase rather than reopening accepted phases without new evidence.

The exact continuation point is maintained in `docs/current_status.md`.
