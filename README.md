# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the rebuild/redesign path for Chart Monitor; the legacy system remains preserved while ATLAS matures.

## Start here

For a future development session, read in this order:

1. [`docs/current_status.md`](docs/current_status.md) — exact current handoff and continuation.
2. [`docs/roadmap.md`](docs/roadmap.md) — architecture, phase ledger, data/safety rules, and authority boundaries.
3. [`docs/post_phase22_closeout.md`](docs/post_phase22_closeout.md) — Phase22 merge/CI/target-machine closeout and documentation correction.
4. [`docs/phase22_operational_paper_runner.md`](docs/phase22_operational_paper_runner.md) — accepted routine Webull-primary PAPER operator contract.
5. [`docs/phase21_unified_paper_execution_authority.md`](docs/phase21_unified_paper_execution_authority.md) — accepted centralized PAPER-submit authority.
6. [`docs/phase20_run_orchestration.md`](docs/phase20_run_orchestration.md) — accepted provider-free deterministic orchestration contract.
7. [`docs/phase_flow.md`](docs/phase_flow.md) — mandatory development/acceptance/merge flow.
8. Phase18/19 and older phase documents for deeper provenance only.

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
- **Phase22** — routine operator binding over accepted Phase15 + Phase21 PAPER execution; no new submit seam or authority class.

## Strategic anti-drift anchor

The destination remains the complete operational evidence chain: **broad-market discovery -> deterministic analysis/risk -> independent AI review -> safe Webull-primary SHADOW/PAPER execution -> exact reconciliation -> observability -> outcome learning**, before any separately authorized LIVE transition.

Infrastructure is a means to that operational system, not a replacement destination. Scheduler, PostgreSQL, browser, or other infrastructure work must not silently displace the end-to-end paper/shadow objective.

## Mandatory development flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Credentials, endpoints, connected accounts, passing tests, or registered jobs never silently change provider, broker, automation, or LIVE authority.

## Current state — 2026-08-24

Accepted/merged numbered work:

- **Phases 1–22 ACCEPTED / MERGED.**
- Phase18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase19 merge: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase20 merge: `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.
- Phase21 merge: `ed9e156437e3924293b90f06620ebbe9534fab15`.
- Phase22 merge: `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.

Phase21 final authority evidence:

- policy fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`;
- final exact head `174110e3688a0b8c087555a56adafaab99905c66`;
- final CI `32782618589`;
- exactly one raw `adapter.submit(plan)` seam remains in `packages/execution/engine.py`.

Phase22 evidence:

- policy `phase22-policy-v1-operational-paper-runner-webull-primary-explicit-run-authority`;
- fingerprint `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`;
- implementation head `68f16256c8f9976ae5b6283dde437e93fbe70155`;
- CI `32787337500`: Ubuntu **974 passed in 13.80s**, Windows **974 passed in 33.93s**, every validator through Phase22 PASS;
- validation provider calls/writes/broker writes: `0 / 0 / 0`;
- target-machine `prepare --broker webull` on accepted as-of `2026-08-14`: **0 accepted execution cases**, authority required `False`, disposition `PREPARED_ZERO_PROVIDER_CALLS`.

The Phase22 zero-case target result is correct. Phase11 has 0 `SUPPORTED` strategies, so no accepted downstream execution case exists. ATLAS must not weaken thresholds, manufacture a case, or run `execute` merely to force broker activity.

The current work is an **unnumbered post-Phase22 documentation closeout** on `maintenance/post-phase22-closeout`; it changes no numbered-phase authority. No Phase23 scope is accepted yet.

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

Phase11 strategy support remains: SUPPORTED 0; MIXED 3 (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`); UNSUPPORTED 5. Zero supported strategies correctly yields zero promotions under the accepted evidence.

## Accepted execution/control-plane foundation

### Phase15

Broker-neutral SHADOW/PAPER execution bound to accepted Phase13/14 lineage with fresh quotes, preflight, reconciliation, current-risk revalidation, protective geometry, deterministic client IDs/idempotency, and fail-closed provider uncertainty. Webull primary; Alpaca manual secondary; LIVE disabled.

### Phase16–19

Loopback browser/control-plane safety, explicit broker-switch/cleanup planning, accepted dual-broker read-only reconciliation, accepted Phase18 real Webull sandbox submit/reconcile/cancel lifecycle, and Phase19 local read-only observability. Browser actions never bypass execution authority.

### Phase20

Provider-free deterministic run substrate: immutable DAG/stage definitions, deterministic run identity, bounded local retries for retry-safe work, atomic manifest/journal persistence, fail-closed leases/resume, and provider-free shadow rehearsal. External mutation stages, autonomous scheduling, PostgreSQL runtime promotion, LIVE, and automatic failover remain outside its authority.

### Phase21

Every new PAPER provider submit crosses `ExecutionEngine.submit_authorized_plan(...)`. Missing, stale, false, malformed, or mismatched authority fails before submit. Exact deterministic existing-order reuse performs no new mutation and therefore requires no new submit authority. Phase18 retains its separate explicit certification gate. Browser and Phase20 cannot acquire this authority.

### Phase22

`run_phase22_paper.py` supplies the routine PAPER operator entrypoint:

- `prepare|execute` only;
- Webull default/primary, Alpaca explicit manual selection;
- accepted Phase13/14 -> Phase15 input only;
- no arbitrary ticker, quantity, price, geometry, LIVE, or command-line confirmation input;
- exact interactive Phase21 confirmation only when accepted executable cases exist;
- no new adapter/quote/order-builder/submit path;
- provider uncertainty stops with reconciliation required, no blind retry/failover;
- Phase15 remains the immutable outcome store and Phase19 remains the read-only observability consumer.

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
- Automatic broker failover is forbidden.
- PAPER does not imply LIVE.
- Zero-case/no-promotion states are valid and must not be bypassed.
- Phase20 does not authorize provider mutations, scheduler execution, or PostgreSQL runtime promotion.
- Phase21/22 do not authorize browser execution, automatic failover, scheduler execution, cleanup/flatten beyond separately accepted gates, or LIVE.

## Environment/security

Tracked `.env.example` is non-secret. Public/default endpoints may be populated; secret placeholders remain blank.

Never commit or print API secrets, passwords, security codes, raw broker IDs, tokens, or signed request metadata. Commented secrets are still secrets. Real `.env` remains local/ignored.

## Exact continuation point

Do not repeat the accepted Phase18 mutation merely to reconfirm it and do not fabricate a Phase22 execution case.

1. Complete cross-platform CI and merge the documentation-only `maintenance/post-phase22-closeout` branch.
2. Verify authoritative `main` is synchronized through Phase22.
3. Audit the merged code for the smallest remaining operator/run gap toward a **current** end-to-end ATLAS analytical run that can naturally produce accepted Phase13/14 cases.
4. Define and authority-lock the next numbered phase from that evidence rather than assuming scheduler/PostgreSQL work is next.

No Phase23 implementation should begin until that audit and definition are complete.