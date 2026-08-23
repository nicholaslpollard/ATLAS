# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the redesign/rebuild path for the existing Chart Monitor; the legacy system is preserved rather than deleted while ATLAS matures.

## Start here

For any new development session or future chat, read these living documents in order:

1. **[`docs/current_status.md`](docs/current_status.md)** — detailed current handoff, accepted evidence, active branch/PR, broker authority, configuration state, and exact continuation point.
2. **[`docs/roadmap.md`](docs/roadmap.md)** — architecture lock, non-negotiable rules, accepted phase responsibilities, validation protocol, and authority boundaries.
3. **[`docs/phase18_operational_validation.md`](docs/phase18_operational_validation.md)** — exact Phase 18 paper-provider certification design, test matrix, CI evidence, and target-machine procedure while Phase 18 is active.
4. This README — project orientation and concise current state.

Merged pull requests are the detailed acceptance/evidence ledger. Files named `README_PHASE_*`, `README_ATLAS_*`, old phase status documents, and fix notes are historical records, not the current roadmap.

## Core architecture

`market/reference data -> Parquet data lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> strategy routing/evaluation -> candidate promotion -> historical analogue + Monte Carlo/scenario research -> news/events/sentiment -> instrument selection -> entry/stop/target/horizon -> portfolio/risk -> consolidated deterministic case -> independent AI audit -> alert/paper/shadow/live execution -> outcome/performance learning -> browser control plane`

Key architectural roles:

- **Parquet**: durable analytical/historical lake.
- **DuckDB**: local analytical/query engine.
- **PostgreSQL**: target for persistent operational state that does not belong in the analytical lake.
- **Massive**: primary market/reference-data provider in the accepted production-data path.
- **Conventional ML**: produces `p_down`, `p_neutral`, `p_up` probability evidence; argmax is diagnostic only.
- **Strategies/router**: determine deterministic setup/routing semantics; regime logic stays outside strategy implementations.
- **Deep research**: analogue/Monte Carlo/scenario/options/context work is promoted-candidate only.
- **AI**: independent audit/reviewer; it is not the predictive model and is not execution authority.
- **Execution**: broker-neutral contracts with reconciliation, fresh-quote/risk checks, protective geometry, idempotency, and fail-closed uncertainty handling.
- **Browser**: control plane and monitoring surface, never an independent source of trading authority.

## Current accepted state — 2026-08-23

**Phases 1-17 are accepted and merged.** The accepted stack includes foundation/configuration/canonical contracts; restartable Massive ingestion; canonical/session-aware history; security-safe identity; provisional live market state; the 33-feature engine; point-in-time universe registry; broad discovery; market/sector/ticker regimes; conventional ML probabilities; controlled Alpaca raw-SIP historical extension to 2016; strategy evaluation/external regime routing; promoted-only analogue/scenario research; deterministic context/instrument/geometry/portfolio risk; independent AI audit; broker-neutral shadow/paper execution contracts; cumulative lineage acceptance; browser control plane; and real Webull sandbox + Alpaca paper read-only reconciliation.

Phase 17 accepted real provider-readiness with both brokers `AVAILABLE`, reconciled, zero open orders, zero positions, zero provider-mutation endpoint invocations, zero provider writes, and zero live writes. Target-machine regression was **874 passed in 24.83s** and Windows/Ubuntu CI passed.

## Active work — Phase 18

**Phase 18 — Paper Provider Mutation Lifecycle Validation is active on draft PR #18.**

Current branch:

`phase-18-paper-provider-mutation-lifecycle-validation`

Current green code head:

`062efedfdc7537222c929f72ebf1f1bb57f903af`

Current Phase 18 CI evidence at that code head:

- Phase 18 validator: PASS on Windows and Ubuntu;
- all prior validators: PASS;
- Ubuntu: **908 passed in 17.80s**;
- Windows: **908 passed in 31.79s**;
- both GitHub Actions jobs: SUCCESS;
- real provider writes in CI: 0.

### Phase 18 authority model

Provider mutation is **disabled by default**. A real target-machine paper/sandbox mutation requires one selected broker plus both:

- `--authorize-paper-provider-mutation`;
- exact confirmation text `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credentials, endpoints, environment mode, account availability, Phase 17 success, Phase 18 code, or passing tests cannot substitute for the authorization gate.

Live execution remains disabled. Automatic cross-broker failover remains disabled.

### Two distinct Phase 18 validation paths

Phase 18 deliberately keeps two concepts separate:

1. **Production-path semantic validation** — fake-provider tests wrap the accepted Phase 15 `ExecutionEngine` and prove normal execution semantics retain fresh-quote, risk, reconciliation, provider preflight, protective geometry, deterministic client IDs, idempotency, and uncertain-write fail-closed behavior.
2. **Real-provider operational certification** — uses a separate validation-only order and does **not** fabricate Phase 13/14 strategy/AI lineage merely to exercise a broker API.

The real operational certification order is not a strategy signal, trade recommendation, model outcome, or AI-reviewed case. It exists only to prove paper-broker order/reconciliation plumbing.

### Locked real certification order

The validation-only order is intentionally small:

- PAPER/SANDBOX only;
- equity only;
- BUY only;
- exactly **1 share**;
- LIMIT / DAY;
- no extended hours;
- entry = **5% below a fresh realtime bid**;
- stop = **2% below entry**;
- target = **2% above entry**;
- absolute validation notional cap = **$1,000**;
- accepted Phase 13 risk envelope still applies: maximum 10% single-name notional and 0.5% equity loss-at-stop;
- broker must start reconciled, flat, and with zero open orders;
- account must not be trading-blocked and must have positive equity/buying power.

The 5%-below-bid entry is intended to remain nonmarketable so the expected lifecycle is `submit -> exact reconcile -> cancel -> exact reconcile flat`. A fill is still possible; if a fill or partial fill occurs, ATLAS **does not auto-flatten** and instead stops for separate explicit cleanup authority.

### Realtime market-data requirement

The certification plan requires an undelayed Massive realtime **regular-session** quote. It uses the accepted Phase 5/15 path rather than a new quote client:

- live state is produced by `scripts/run_live_market_state.py` / `LiveMarketService`;
- focused subscription is `Q.<ticker>`;
- `Phase15LiveQuoteResolver` requires the live connection to remain `SUBSCRIBED`, realtime, gap-free, regular-session, exact-ticker, and `FRESH`.

A weekend, market holiday, premarket, after-hours, stopped stream, delayed feed, stale quote, or open WebSocket gap is rejected. The gate is not relaxed simply to make certification convenient.

### Mutation and uncertainty behavior

Before submit, ATLAS proves current broker reconciliation, risk, deterministic client-order-ID absence, and provider preflight. It submits exactly once, reconciles the exact client ID, cancels only if the order remains open, and reconciles again.

If submit or cancel becomes uncertain, ATLAS performs read-only reconciliation if possible and then stops. It does **not** blindly retry, perform a second mutation, auto-flatten, or fail over to Alpaca.

If the exact client-order ID already exists, a new write is blocked. A rejected/unexpected terminal provider state is not certified as success.

### Target-machine runner

`scripts/run_phase18_operational_validation.py` requires explicit `--broker` and `--ticker`. It provides no default ticker and no quantity argument.

Without the mutation authorization flag, it is plan-only:

- reads local ATLAS live state;
- initializes no broker adapter;
- performs 0 broker/provider calls;
- performs 0 provider writes;
- returns `PLAN_ONLY_ZERO_PROVIDER_CALLS` when valid plan evidence exists.

With a wrong confirmation string, broker initialization is still blocked and provider calls/writes remain zero.

Full design and target-machine closeout sequence: [`docs/phase18_operational_validation.md`](docs/phase18_operational_validation.md).

## Accepted historical source boundary

- Alpaca raw SIP daily: **2016-01-04 through 2021-08-13**.
- Massive production authority: **2021-08-16 onward**.
- Pre-2021 intraday bars are **not** synthesized from daily history.
- Historical population and identity are point-in-time/observation driven; literal ticker text never proves continuity.
- Provider-native ticker text/case is preserved.
- Unresolved continuity is quarantined/excluded rather than guessed.

## Accepted production ML model

The authoritative Phase 10 model remains:

- model id: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- specification: `hgb_leaf15_iter100`;
- 33 point-in-time quantitative predictors;
- raw `p_down`, `p_neutral`, `p_up` probabilities;
- no post-hoc calibration;
- protected holdout: 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic probability replay.

Longer-history C evidence remains separately versioned challenger/research evidence and does not silently replace production authority.

## Strategy/research state

Phase 11 accepted eight deterministic strategy variants:

- SUPPORTED: 0;
- MIXED: 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: 5.

Therefore the accepted 2026-08-14 path produced zero promoted candidates. Downstream zero-case/no-op behavior is intentional; thresholds are not weakened to manufacture trades.

## Broker architecture

### Webull

Webull is the planned primary execution broker. Current accepted provider target is Webull US sandbox. Account selection is explicit and fail-closed. Phase 17 accepted read-only account/balance/open-order/position reconciliation. Webull remains the intended **first** real Phase 18 mutation target after explicit authorization because it is the primary broker.

### Alpaca

Alpaca is the manually selectable secondary/fallback broker. Alpaca paper read/reconciliation is accepted. It must never be automatically used because a Webull validation attempt rejects, disconnects, times out, partially fills, or becomes uncertain.

### Broker switching

Broker switching is explicit only. Orders/positions must be inspected and reconciled. Any cancel/close/flatten required for safe switching needs the corresponding explicit mutation authority. Automatic cross-broker failover remains disabled.

## Current authority boundary

The real-provider checkpoint remains:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

Until a target-machine mutation run is explicitly authorized, ATLAS may not perform real provider order submission, replacement, cancellation, flatten/close, or broker-switch cleanup writes.

Phase 18 acceptance will still **not** imply live-money authority. Live execution requires a later separately designed and explicitly approved phase.

## Environment/configuration template

The tracked `.env.example` is a non-secret template and may contain public/local endpoint defaults and blank credential placeholders. Presence of live variable names/endpoints is configuration continuity, not authority.

Current groups include:

- application: `ATLAS_ENV`, `OPENAI_API_KEY`, `DATABASE_URL`;
- Massive API/S3 placeholders plus `MASSIVE_ENDPOINT=https://files.massive.com`;
- Webull paper/sandbox + future live credential placeholders;
- Alpaca paper/live endpoints + blank credential placeholders;
- optional IBKR localhost/port/client-ID defaults.

Credential values, raw account IDs, security codes, passwords, tokens, and secrets remain local only. The commented Alpaca security-code placeholder is intentionally blank. Generated `webull_trade_sdk.log*` files are ignored.

## Non-negotiable safety/data rules

- Preserve exact provider-native ticker text/case.
- Never infer identity continuity from ticker text alone.
- Use point-in-time historical populations; never project current survivor state backward.
- Quarantine/exclude ambiguity rather than guessing.
- Keep acquisition/replay restartable, idempotent, checkpointed, and duplicate-safe.
- Require lineage and independent validation at data/model/authority transitions.
- Do not fabricate unavailable intraday history.
- Finalized canonical data remains authoritative over provisional live observations.
- ML probability output is evidence, not a trade signal.
- AI may audit/challenge but cannot rewrite deterministic evidence or authorize execution.
- Valid geometry is mandatory: `LONG stop < entry < target`; `SHORT stop > entry > target`.
- Unknown broker/provider state fails closed.
- Uncertain writes require exact reconciliation before another mutation.
- Live money is never the first validation environment: paper -> shadow/observation -> controlled live.

## Development and documentation workflow

A normal ATLAS work package combines:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status update`

Use focused tests while coding, then full regression and Windows/Ubuntu CI at the evidence boundary. Independent validators remain required for data/model/broker authority changes. Target-machine evidence should use one complete PowerShell sequence where practical.

For every meaningful change, synchronize root `README.md`, `docs/roadmap.md`, `docs/current_status.md`, the active PR acceptance ledger, and configuration docs/templates when their state changes. Historical phase/fix READMEs remain frozen provenance unless correcting a factual error.

## Repository conventions

- `main` contains accepted work.
- Substantial phases/authority-changing work use focused branches/PRs.
- Acceptance evidence is recorded before merge.
- Merged phase branches are deleted after closeout unless there is a concrete retention reason.
- Real `.env` remains local and ignored.
- `.env.example` is tracked and non-secret.

For the complete current handoff, continue with **[`docs/current_status.md`](docs/current_status.md)**. For architecture/authority rules, use **[`docs/roadmap.md`](docs/roadmap.md)**. For the active certification specification, use **[`docs/phase18_operational_validation.md`](docs/phase18_operational_validation.md)**.
