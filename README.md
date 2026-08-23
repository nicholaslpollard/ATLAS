# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the rebuild/redesign path for Chart Monitor; the legacy system remains preserved while ATLAS matures.

## Start here

For any future development session or new chat, read these living sources in this order:

1. [`docs/current_status.md`](docs/current_status.md) — exact current handoff, accepted evidence, active branch/PR, target-machine state, broker authority, and next action.
2. [`docs/roadmap.md`](docs/roadmap.md) — architecture lock, phase ledger, non-negotiable data/safety rules, and authority transitions.
3. [`docs/phase_flow.md`](docs/phase_flow.md) — mandatory numbered-phase execution flow and acceptance/merge rules.
4. [`docs/phase18_operational_validation.md`](docs/phase18_operational_validation.md) — active Phase 18 broker-certification specification and acceptance ledger.
5. This README — project orientation and concise state.
6. Merged PRs — detailed historical acceptance evidence.

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

## Mandatory development flow

ATLAS advances by explicit numbered phases:

`DEFINE -> LOCK -> IMPLEMENT -> FOCUSED TEST -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

The current phase must satisfy its acceptance boundary before the next numbered phase becomes active. Passing tests, configured credentials, available endpoints, or connected accounts do not silently change provider/live authority.

## Current state — 2026-08-23

- **Phases 1–17: ACCEPTED and merged.**
- **Phase 18: ACTIVE** on draft PR #18, branch `phase-18-paper-provider-mutation-lifecycle-validation`.
- **Phase 18A — Pre-mutation software validation: ACCEPTED / COMPLETE.**
- **Phase 18B — Real paper-provider operational certification: WAITING_EXTERNAL.**
- **Phase 19: NOT ACTIVE / NOT YET DEFINED.**
- Accepted Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.
- Phase 18 policy fingerprint: `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.
- Final target-machine Phase 18A baseline: `94a859fc6d44c22a6f8852c1488215a6677806a0`.
- Final target-machine Phase 18A regression: **908 passed in 23.50s**.
- Matching Windows/Ubuntu CI: **SUCCESS**.
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

Zero supported strategies correctly yielded zero promoted candidates in the accepted locked case. Downstream no-op behavior is intentional; thresholds are never weakened to manufacture trades.

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

### Phase 18A — ACCEPTED / COMPLETE

Completed evidence includes:

- explicit mutation authority gate;
- fake-provider production lifecycle semantics;
- separate validation-only operational order path;
- independent Phase 18 validator;
- focused Phase 18 target-machine tests;
- Windows loopback test-harness portability hardening without production behavior changes;
- final target-machine regression **908 passed in 23.50s**;
- clean working tree;
- Windows and Ubuntu CI green;
- provider calls/writes during final software recheck: 0.

There is no remaining Phase 18A software/portability blocker.

### Phase 18B — WAITING_EXTERNAL

Provider mutation is disabled by default. A real target-machine mutation run requires:

- exactly one selected broker;
- `--authorize-paper-provider-mutation`;
- exact confirmation text `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credentials, endpoint configuration, environment mode, connected-account availability, prior phase success, Phase 18 code, or passing CI cannot substitute for that gate.

Locked operational order:

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

A fill/partial fill is possible. If it occurs, ATLAS does **not** auto-flatten; it stops for separate cleanup authority. Alpaca is not an automatic failover destination.

## Realtime quote authority

Real Phase 18B certification requires accepted Phase 5/15 market-state evidence:

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

Weekends, holidays, premarket, after-hours, stopped streams, stale data, or delayed data fail closed.

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

Normative phase flow:

`DEFINE -> LOCK -> IMPLEMENT -> FOCUSED TEST -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Normal coherent work package:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status`

Every meaningful change must synchronize, as applicable:

- `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- `docs/phase_flow.md` when process rules change;
- active phase living spec;
- active PR acceptance/evidence ledger;
- configuration docs/templates.

Historical phase/fix READMEs remain frozen provenance unless a factual historical error must be corrected.

## Exact continuation point

Phase 18A is complete. No additional regression is required solely for the closed Windows portability issue.

During a regular U.S. equity session:

1. choose an exact provider-native ticker suitable for the one-share <$1,000 cap;
2. start focused Massive realtime quote state and keep it active;
3. run Phase 18 **plan-only** validation first;
4. verify 0 broker/provider calls/writes in plan-only mode;
5. review the exact one-share plan;
6. only after explicit user authorization may Webull sandbox perform the first real Phase 18 mutation;
7. reconcile the exact deterministic client ID;
8. cancel once if still open and reconcile flat;
9. if filled/partially filled, stop for separate cleanup authorization;
10. never auto-fail over to Alpaca;
11. record sanitized evidence and synchronize living docs/PR;
12. accept and merge Phase 18 only after Phase 18B evidence is complete;
13. verify `main` and delete the merged Phase 18 branch;
14. only then define, lock, and activate Phase 19.

Any later live-money promotion requires a separate numbered phase and separate explicit authorization.