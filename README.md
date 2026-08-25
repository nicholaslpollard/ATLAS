# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the rebuild/redesign path for Chart Monitor; the legacy system remains preserved while ATLAS matures.

## Start here

For a future development session, read in this order:

1. [`docs/current_status.md`](docs/current_status.md) — exact current handoff and continuation.
2. [`docs/roadmap.md`](docs/roadmap.md) — architecture, phase ledger, data/safety rules, and authority boundaries.
3. [`docs/phase23_operational_current_analysis_cycle.md`](docs/phase23_operational_current_analysis_cycle.md) — current finalized-session analytical operator and Phase23 evidence.
4. [`docs/phase22_operational_paper_runner.md`](docs/phase22_operational_paper_runner.md) — accepted routine Webull-primary PAPER operator contract.
5. [`docs/phase21_unified_paper_execution_authority.md`](docs/phase21_unified_paper_execution_authority.md) — accepted centralized PAPER-submit authority.
6. [`docs/phase20_run_orchestration.md`](docs/phase20_run_orchestration.md) — accepted provider-free deterministic orchestration contract.
7. [`docs/phase_flow.md`](docs/phase_flow.md) — mandatory development/acceptance/merge flow.
8. Older phase documents for deeper provenance only.

When historical documents conflict with accepted code or the living handoff, accepted `main` and the current living documents control.

## Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Core roles:

- **Parquet** — durable analytical/history lake.
- **DuckDB** — analytical/query engine.
- **PostgreSQL** — target transactional operational state; not yet an accepted runtime prerequisite.
- **Massive** — primary broad-market/reference provider path.
- **Webull** — primary PAPER/sandbox execution broker; future LIVE only under a separate explicit authority phase.
- **Alpaca** — manually selectable secondary/fallback; never automatic failover.
- **ML** — point-in-time `p_down/p_neutral/p_up` evidence, never direct trade authority.
- **Strategies/router** — deterministic setup semantics and regime-aware routing.
- **Deep research** — promoted-candidate-only analogue/scenario/options/news work.
- **AI** — independent audit/reviewer only.
- **Browser** — monitoring/control plane only; it cannot create trading authority.
- **Phase20** — deterministic local orchestration only; no provider/broker/scheduler/LIVE authority.
- **Phase21** — centralized default-deny authority for every new real PAPER provider submit.
- **Phase22** — routine Webull-primary PAPER operator binding over accepted Phase15 + Phase21 authority.
- **Phase23** — routine explicit-finalized-session analytical cycle; provider-free prepare, narrowly authorized Massive market/reference reads only when missing, and no broker/PAPER execution.

## Strategic anti-drift anchor

The destination remains the complete operational evidence chain: **broad-market discovery -> deterministic analysis/risk -> independent AI review -> safe Webull-primary SHADOW/PAPER execution -> exact reconciliation -> observability -> outcome learning**, before any separately authorized LIVE transition.

Infrastructure is a means to that system, not a replacement destination. Scheduler, PostgreSQL, browser, or other infrastructure work must not silently displace the end-to-end paper/shadow objective.

## Mandatory development flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Credentials, endpoints, connected accounts, passing tests, locally present artifacts, or registered jobs never silently change provider, broker, automation, or LIVE authority.

## Current state — 2026-08-24

Accepted/merged numbered work on the upstream baseline:

- **Phases 1–22 ACCEPTED / MERGED.**
- post-Phase22 synchronized `main`: `dd0d6838d76a15edde0783f471ad7e212453cd94`.

Current work:

- **Phase23 — Operational Current Analysis Cycle**;
- branch `phase-23-operational-current-analysis-cycle`;
- PR #25;
- policy fingerprint `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`;
- validated implementation/repair head before documentation closeout `803d43e43e8931f03ba836a23b781a7c3d3ee687`;
- state **VALIDATED / TARGET EVIDENCE COMPLETE / MERGE PENDING**.

### Phase23 target result

ATLAS successfully ran a finalized current analytical cycle through **2026-08-21** from the accepted **2026-08-14** baseline.

The first authorized attempt exposed a real local persisted-null deserialization defect (`previous_effective_state=NaN`) after finalized Massive/reference evidence had been populated. The repair:

- normalized only the nullable persisted field;
- preserved discovery thresholds/hysteresis and the frozen strategy-support gate;
- prevented partial failed discovery artifacts from becoming an accepted baseline;
- added exact market-session/entitlement and feature-checkpoint completion guards.

Repair-head CI:

- push run `32802151860`: Ubuntu/Windows SUCCESS;
- PR run `32802154831`: Ubuntu/Windows SUCCESS;
- **988 tests passed on each OS**;
- every validator through Phase23 PASS.

Final repaired target run:

- sessions advanced: **5** — Aug 17–21;
- WARM/HOT directional cases considered: **23**;
- promoted candidates: **0**;
- Phase12 research cases: **0**;
- Phase13 case files: **0**;
- Phase14 AI reviews: **0**;
- Phase22-ready execution cases: **0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- independent persisted validation: **PASS**;
- overall run: **PASS**.

The zero-promotion result is correct. Accepted Phase11 still has **0 SUPPORTED strategies**, so current directional evidence cannot pass the historical-support gate. ATLAS must not lower thresholds or manufacture a case merely to create downstream activity.

LIVE execution remains **DISABLED**. Automatic cross-broker failover remains **DISABLED**.

## Accepted data/model foundation

Historical provider boundary:

- Alpaca raw SIP daily controlled authority: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- No synthetic pre-2021 1h/4h history from daily bars.

Accepted cumulative lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Accepted production ML:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- protected holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

Phase11 strategy support remains: SUPPORTED 0; MIXED 3 (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`); UNSUPPORTED 5.

## Accepted execution/control-plane foundation

### Phase15

Broker-neutral SHADOW/PAPER execution bound to accepted Phase13/14 lineage with fresh quotes, preflight, reconciliation, current-risk revalidation, protective geometry, deterministic client IDs/idempotency, and fail-closed provider uncertainty. Webull primary; Alpaca manual secondary; LIVE disabled.

For dates after 2026-08-14, current Phase15 input is accepted only through the exact Phase23 current-analysis handoff.

### Phase16–19

Loopback browser/control-plane safety, explicit broker-switch/cleanup planning, accepted dual-broker read-only reconciliation, accepted Phase18 real Webull sandbox submit/reconcile/cancel lifecycle, and Phase19 local read-only observability. Browser actions never bypass execution authority.

### Phase20

Provider-free deterministic run substrate: immutable DAG/stage definitions, deterministic run identity, bounded local retries for retry-safe work, atomic manifest/journal persistence, fail-closed leases/resume, and provider-free shadow rehearsal. External mutation stages, autonomous scheduling, PostgreSQL runtime promotion, LIVE, and automatic failover remain outside its authority.

### Phase21

Every new PAPER provider submit crosses `ExecutionEngine.submit_authorized_plan(...)`. Missing, stale, false, malformed, or mismatched authority fails before submit. Exactly one raw `adapter.submit(plan)` remains under `packages/`, in `packages/execution/engine.py`.

### Phase22

`scripts/run_phase22_paper.py` supplies the routine PAPER operator entrypoint:

- `prepare|execute` only;
- Webull default/primary, Alpaca explicit manual selection;
- accepted Phase13/14 -> Phase15 input only;
- no arbitrary ticker, quantity, price, geometry, LIVE, or command-line confirmation input;
- exact interactive Phase21 confirmation only when accepted executable cases exist;
- provider uncertainty stops with reconciliation required, no blind retry/failover.

Accepted Phase22 target prepare on 2026-08-14 found 0 execution cases and returned `PREPARED_ZERO_PROVIDER_CALLS`. Do not invoke Phase22 `execute` merely to fabricate mutation evidence.

### Phase23

`scripts/run_phase23_analysis.py` supplies the routine current finalized analytical operator:

- provider-free `prepare`;
- explicit prior finalized `as_of`;
- accepted-baseline chronological advancement;
- only `MASSIVE_MARKET_REFERENCE_READS` may be authorized when required;
- no broker reads/writes;
- no provider mutations;
- no Phase21 submit authority;
- no Phase22 execution;
- no downstream research/news/options/AI external calls while the frozen zero-SUPPORTED gate makes them unreachable;
- independent persisted validation and hash-bound current handoff.

## Non-negotiable rules

- Preserve exact provider-native ticker case/text.
- Never infer identity continuity from ticker text alone.
- Historical populations remain point-in-time.
- Quarantine ambiguity; do not guess.
- No fabricated unavailable intraday history.
- Finalized canonical facts outrank provisional live observations.
- ML is evidence, not trade authority.
- AI is independent audit only.
- LONG `stop < entry < target`; SHORT reverse.
- Unknown broker/provider/run state fails closed.
- Uncertain writes require reconciliation before any next mutation.
- Partial failed analytical files do not become accepted state without the applicable handoff.
- Automatic broker failover is forbidden.
- PAPER does not imply LIVE.
- Zero-case/no-promotion states are valid and must not be bypassed.
- Phase20 does not authorize provider mutations, scheduler execution, or PostgreSQL runtime promotion.
- Phase21/22 do not authorize browser execution, automatic failover, scheduler execution, cleanup/flatten beyond separately accepted gates, or LIVE.
- Phase23 does not authorize broker activity or PAPER execution.

## Environment/security

Tracked `.env.example` is non-secret. Public/default endpoints may be populated; secret placeholders remain blank.

Never commit or print API secrets, passwords, security codes, raw broker IDs, tokens, or signed request metadata. Commented secrets are still secrets. Real `.env` remains local/ignored.

## Exact continuation point

1. Complete Phase23 documentation synchronization on PR #25.
2. Run final Ubuntu/Windows CI on the documentation head.
3. If green, mark PR #25 ready/accepted and merge Phase23 to `main`.
4. Verify authoritative `main` and record the merge SHA.
5. Audit the merged 2026-08-21 discovery/regime/ML/current-strategy evidence.
6. Define/lock the next numbered phase from that evidence.

The current principal analytical bottleneck is the frozen **0-SUPPORTED strategy set**. The likely next substantive analytical phase is a preregistered strategy challenger/support-replacement process; it must improve evidence legitimately rather than relax gates merely to create trades.

GUI development can consume the stable Phase23 current-artifact surface when scheduled, but the browser remains a monitoring/control plane and cannot create trading authority.

Do not assume scheduler or PostgreSQL promotion is next merely because those remain future infrastructure goals.