# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the rebuild/redesign path for Chart Monitor; the legacy system remains preserved while ATLAS matures.

## Start here

For any future development session or new chat, read these living sources in this order:

1. [`docs/current_status.md`](docs/current_status.md) — exact current handoff, accepted evidence, active branch/PR, target-machine state, broker authority, and next action.
2. [`docs/roadmap.md`](docs/roadmap.md) — architecture lock, phase ledger, non-negotiable data/safety rules, and authority transitions.
3. [`docs/phase18_operational_validation.md`](docs/phase18_operational_validation.md) — active Phase 18 broker-certification specification and acceptance ledger.
4. This README — project orientation and concise state.
5. Merged PRs — detailed historical acceptance evidence.

Files named `README_PHASE_*`, `README_ATLAS_*`, old fix notes, and old phase-specific status files are historical provenance. They are not the current roadmap when they conflict with the living sources above.

## Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Core roles:

- **Parquet**: durable analytical/history lake.
- **DuckDB**: analytical/query engine over local columnar data.
- **PostgreSQL**: target persistent operational state where relational transactional state is appropriate.
- **Massive**: primary accepted market/reference-data provider path.
- **Conventional ML**: point-in-time probability evidence (`p_down`, `p_neutral`, `p_up`), never direct trade authority.
- **Strategies/router**: deterministic setup semantics and regime-aware routing; regime routing remains outside individual strategies.
- **Deep research**: historical analogue, Monte Carlo/scenario, options/context work only for promoted candidates.
- **AI**: independent audit/reviewer, never the predictive model and never execution authority.
- **Execution**: broker-neutral contracts with fresh quote, reconciliation, current risk, protective geometry, idempotency, and uncertainty fail-closed behavior.
- **Browser**: monitoring/control plane only; it cannot create independent trading authority.

## Current state — 2026-08-23

- **Phases 1–17: ACCEPTED and merged.**
- **Phase 18: ACTIVE** on draft PR #18, branch `phase-18-paper-provider-mutation-lifecycle-validation`.
- Accepted Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.
- Current Phase 18 code/test portability head before this documentation synchronization: `45a2abeba7a51401ee708ab777d960d2f7fea88f`.
- Phase 18 policy fingerprint: `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.
- Real provider mutation performed in Phase 18 so far: **NO**.
- Live execution: **DISABLED**.
- Automatic cross-broker failover: **DISABLED**.
- Required real-provider checkpoint: `PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`.

## Accepted foundation and evidence

### Data/history

- Alpaca raw SIP daily authority for the controlled historical extension: **2016-01-04 through 2021-08-13**.
- Massive production authority: **2021-08-16 onward**.
- No synthetic pre-2021 1h/4h history from daily bars.
- Historical populations are observation-driven and point-in-time.
- Provider-native ticker text/case is preserved exactly.
- Literal ticker text never proves identity continuity.
- Ambiguous identity/continuity is quarantined or excluded rather than guessed.
- Accepted cumulative data/lineage fingerprint: `6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`.

### Feature/discovery/regime

- 33 deterministic core quantitative features.
- Accepted routed discovery universe at the locked 2026-08-14 state: 12,066 instruments.
- Accepted broad-ready discovery population: 8,034 instruments.
- Discovery state thresholds remain WATCH 0.35, WARM 0.50, HOT 0.60 with additional directional/evidence guards.
- Market/sector/ticker regime hierarchy is point-in-time and deterministic; ticker sector context is never guessed.

### Production ML

Authoritative Phase 10 model:

- model id: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB specification: `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- outputs raw `p_down`, `p_neutral`, `p_up`;
- no post-hoc calibration;
- protected holdout: 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss: 0.948693;
- Brier: 0.560422;
- macro OVR AUC: 0.570016;
- exact deterministic replay.

Argmax remains diagnostic only. Longer-history challenger evidence never silently replaces accepted production authority.

### Strategy/research

Phase 11 evaluated eight deterministic strategy variants. Accepted support classification:

- SUPPORTED: 0;
- MIXED: 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: 5.

Zero supported strategies correctly yielded zero promoted candidates in the accepted 2026-08-14 case. Downstream no-op behavior is intentional; thresholds are never weakened to manufacture trades.

## Accepted execution/control-plane foundation

### Phase 15

Broker-neutral shadow/paper execution contracts are accepted with:

- Webull primary;
- Alpaca manually selectable secondary/fallback;
- no automatic failover;
- fresh quote requirements;
- provider preflight;
- account/orders/positions reconciliation;
- current risk revalidation;
- protective stop/target geometry;
- deterministic client-order IDs/idempotency;
- uncertain writes fail closed;
- same-ticker add/flip disabled;
- live hard-disabled.

### Phase 16

Browser control plane, audit/idempotency, recovery, explicit broker-switch workflow, cleanup planning/confirmation, CSRF/same-origin protections, and loopback-first operation are accepted. Browser actions do not bypass Phase 15 execution gates. Provider cleanup writes and live trading were not promoted.

### Phase 17

Real provider **read-only** operational readiness is accepted.

Webull sandbox:

- five readable sandbox accounts were discovered;
- ambiguity failed closed until explicit account selection;
- selected local sanitized margin-account ref: `3d64d273c694250b`;
- account list, balance, open-order, and position reads succeeded;
- accepted closeout had 0 open orders and 0 positions.

Alpaca paper:

- sanitized account ref: `4b5b072f7127b4dc`;
- reconciliation succeeded;
- accepted closeout had 0 open orders and 0 positions.

Combined Phase 17 acceptance:

- both brokers `AVAILABLE` and reconciled;
- provider mutation endpoint invocations 0;
- provider writes 0;
- live writes 0;
- target-machine full suite **874 passed in 24.83s**;
- Windows and Ubuntu CI passed.

## Active Phase 18 — Paper Provider Mutation Lifecycle Validation

Phase 18 validates real **paper/sandbox** broker mutation plumbing while keeping live authority completely separate.

### Authority gate

Provider mutation is disabled by default. A real target-machine mutation run requires:

- exactly one selected broker;
- `--authorize-paper-provider-mutation`;
- exact confirmation text `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credentials, endpoint configuration, environment mode, connected-account availability, Phase 17 acceptance, Phase 18 code, or passing CI cannot substitute for that gate.

### Two separate paths

1. **Production semantic validation** — fake-provider tests wrap accepted Phase 15 execution logic and prove quote/risk/preflight/reconciliation/protective/idempotency/uncertainty semantics.
2. **Operational broker certification** — a separate validation-only order exercises a paper provider without fabricating Phase 13/14 strategy or AI lineage.

Operational validation is not a strategy signal, model outcome, production case, AI recommendation, or performance evidence.

### Locked validation order

Contract: `phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

- PAPER/SANDBOX only;
- EQUITY BUY only;
- quantity exactly 1 share;
- LIMIT / DAY;
- no extended hours;
- entry 5% below fresh realtime bid;
- stop 2% below entry;
- target 2% above entry;
- absolute notional cap $1,000;
- accepted Phase 13 10% single-name notional limit applies;
- accepted Phase 13 0.5% equity loss-at-stop limit applies.

Expected certification is `submit once -> exact client-ID reconcile -> cancel once if still open -> reconcile flat`.

A fill/partial fill is possible. If it occurs, ATLAS does **not** auto-flatten or send an opposite order; it stops for separate cleanup authority.

### Uncertainty rules

If submit or cancel becomes uncertain:

- perform read-only reconciliation if possible;
- no blind retry;
- no second mutation;
- no auto-flatten;
- no automatic Alpaca failover;
- stop until exact state is established.

## Realtime quote authority

Real Phase 18 certification requires accepted Phase 5/15 market-state evidence:

- focused `Q.<ticker>` Massive realtime subscription;
- live connection actively `SUBSCRIBED`;
- realtime feed with expected delay 0;
- no open transport gap;
- regular U.S. equity session;
- exact provider-native ticker;
- quote `FRESH`.

Accepted launcher:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_market_state.py `
  --feed realtime `
  --minute-symbols "" `
  --quote-symbols <TICKER> `
  --no-journal
```

Weekends, holidays, premarket, after-hours, stopped streams, stale data, or delayed data fail closed. Because 2026-08-23 is Sunday, no real mutation certification is valid today.

## Latest target-machine pre-mutation evidence — 2026-08-23

At local branch head `e1631e741a547c78eb6c3c9b943ba1473c805cf6`:

- Phase 18 validator: **PASS**;
- focused Phase 18 suite: **34 passed in 2.23s**;
- Webull sandbox read recheck: configured selected ref, balance/orders/positions HTTP 200, 0 open orders, 0 positions;
- Alpaca paper read recheck: reconciled, 0 open orders, 0 positions;
- Phase 18 mutation gate: **DENIED by default**;
- provider adapter initialized: **NO**;
- provider calls: **0**;
- provider writes: **0**;
- live execution disabled;
- automatic failover disabled;
- working tree clean.

The full local suite produced **907 passed / 1 failed**. The sole failure was `tests/unit/test_phase16_action_api.py::test_csrf_failure_creates_no_action_event`, with Windows `WinError 10053` on a loopback request. This was isolated from Phase 18 broker logic.

Investigation showed the test HTTP client inherited ambient OS/user proxy configuration despite the accepted Phase 16 server being loopback-only. The test harness was hardened in commit `45a2abeba7a51401ee708ab777d960d2f7fea88f` to add `urllib.request.ProxyHandler({})` for deterministic `127.0.0.1` tests. **No production server, broker adapter, execution code, authority contract, or provider behavior changed.**

CI run `32657554236` validated that portability hardening:

- all validators through Phase 18: PASS;
- Ubuntu: **908 passed in 13.57s**;
- Windows: **908 passed in 20.98s**;
- both jobs: SUCCESS.

The remaining local pre-mutation check is to pull the hardened branch and rerun the isolated CSRF test plus the complete suite.

## Environment template

Tracked `.env.example` is non-secret. Public/default endpoints may be populated; secret values may not.

Current template groups:

- `ATLAS_ENV`, OpenAI and DB placeholders;
- Massive credentials + `MASSIVE_ENDPOINT=https://files.massive.com`;
- Webull paper/sandbox and future live credential placeholders;
- Alpaca paper endpoint `https://paper-api.alpaca.markets/v2` and live endpoint `https://api.alpaca.markets`, with blank credential placeholders;
- optional IBKR localhost defaults (`127.0.0.1`, port 4002, client ID 17).

A commented secret is still a secret. The commented Alpaca security-code placeholder stays blank. Real `.env` remains local/ignored. `webull_trade_sdk.log*` is ignored.

## Non-negotiable rules

- Preserve exact provider-native ticker case/text.
- Never infer identity continuity from ticker text alone.
- Historical populations must remain point-in-time.
- Quarantine ambiguity; do not guess.
- No fabricated unavailable intraday history.
- Finalized canonical facts outrank provisional live observations.
- ML output is evidence, not a signal.
- AI is independent audit only and cannot authorize execution.
- LONG geometry: `stop < entry < target`.
- SHORT geometry: `stop > entry > target`.
- Unknown broker/provider state fails closed.
- Uncertain writes require exact reconciliation before any next mutation.
- Automatic broker failover is forbidden.
- Paper/shadow precede any future controlled live authority.

## Development and documentation workflow

Normal work package:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status update`

Use focused tests while coding, full regression + Windows/Ubuntu CI at evidence boundaries, independent validators for data/model/broker authority transitions, and complete target-machine evidence blocks when local/external access is required.

Every meaningful change must synchronize, as applicable:

- `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- active phase living spec;
- active PR acceptance/evidence ledger;
- configuration docs/templates.

Historical phase/fix READMEs remain frozen provenance unless a factual historical error must be corrected.

## Exact continuation point

1. Pull the latest Phase 18 branch.
2. Rerun the isolated Phase 16 CSRF test and full suite locally; expected full result is 908 passed.
3. Do not repeat real provider writes — none are authorized yet.
4. During a future regular market session, start focused Massive realtime quote state and run Phase 18 **plan-only** validation first.
5. Review the exact one-share plan.
6. Only after explicit user authorization may Webull sandbox perform the first real Phase 18 mutation.
7. If filled/partially filled, stop for separate cleanup authorization.
8. Never auto-fail over to Alpaca.
9. Merge Phase 18 only after accepted target-machine mutation/reconciliation evidence.
10. Any later live-money promotion requires a separate phase and separate explicit authorization.
