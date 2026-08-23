# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-23.**

This is the fastest source for a future chat or development session to recover the exact ATLAS state and continue without reconstructing the project from conversation history.

## 1. Source-of-truth order

When sources disagree, use this order:

1. accepted code/artifacts on `main` for completed work;
2. active PR/branch code for in-progress work;
3. `docs/roadmap.md` for architecture and authority rules;
4. this file for current operational state/evidence/continuation;
5. active phase living spec;
6. root `README.md`;
7. merged PRs for deeper accepted evidence;
8. old phase/fix READMEs as historical provenance only.

## 2. Repository state

Repository: `nicholaslpollard/ATLAS`

Accepted work:

- Phases 1–17 merged into `main`.
- Accepted Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.

Active work:

- Phase 18 — Paper Provider Mutation Lifecycle Validation.
- Branch: `phase-18-paper-provider-mutation-lifecycle-validation`.
- PR: #18, draft, targeting `main`.
- Phase 18 policy: `phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`.
- Phase 18 policy fingerprint: `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.
- Current code/test portability head before this documentation commit: `45a2abeba7a51401ee708ab777d960d2f7fea88f`.
- Real Phase 18 provider mutation performed: **NO**.
- Live execution promoted: **NO**.
- Automatic broker failover allowed: **NO**.

Current authority checkpoint:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

## 3. Architecture snapshot

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/Monte Carlo/scenarios -> news/events -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage roles:

- Parquet durable lake;
- DuckDB analytical engine;
- PostgreSQL target operational state.

## 4. Accepted phase ledger

### Phases 1–5

Foundation, provider acquisition/canonicalization, point-in-time instrument identity/history, and Massive live market state. Live state explicitly tracks delayed vs realtime feed, freshness, session, reconnect/gap state, and finalized-data authority.

### Phase 6

33 deterministic point-in-time core features with explicit warmup and replay/incremental consistency.

### Phase 7

Point-in-time universe registry. Current survivor state is not projected backward; identity ambiguity fails closed.

### Phase 8

Broad-market discovery. Accepted routed universe at locked 2026-08-14 state: 12,066 instruments; broad-ready population 8,034. Cheap-first state/ranking is instrument-agnostic.

### Phase 9

Market/sector/ticker regimes with prior-only calibration/persistence and no guessed sector mapping. Optional authoritative SIC only.

### Phase 10

Conventional ML probability/evaluation layer.

Accepted production model:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- 33 point-in-time quantitative predictors;
- raw `p_down/p_neutral/p_up`;
- holdout 2026-05-12 to 2026-08-11;
- 63 sessions / 454,773 rows;
- logloss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

Argmax is diagnostic only.

### Historical extension/cumulative audit

Accepted history:

- Alpaca raw SIP daily controlled authority: 2016-01-04 through 2021-08-13;
- Massive authority: 2021-08-16 onward;
- no synthetic pre-2021 intraday;
- exact provider-native ticker text/case;
- observation-driven historical populations;
- accepted cumulative fingerprint `6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`.

### Phase 11

Eight deterministic strategy variants evaluated. Accepted historical support: 0 supported, 3 mixed, 5 unsupported. Zero supported strategies correctly produced no accepted promotion on the locked case.

### Phase 12

Promoted-only historical analogue and empirical scenario/Monte Carlo research. No candidates means valid no-op closeout.

### Phase 13

Context/instrument/geometry/portfolio risk. Equity-primary current path, valid entry/stop/target geometry, liquidity and portfolio-risk controls.

### Phase 14

Independent AI audit and Engine-vs-AI artifact alerting. AI cannot create execution authority or rewrite deterministic evidence.

### Phase 15

Broker-neutral shadow/paper execution and outcome-learning contracts. Webull primary; Alpaca manual secondary. Fresh quote, reconciliation, preflight, current risk, protective geometry, deterministic IDs/idempotency, uncertainty fail-closed, live disabled, no automatic failover.

### Phase 16

Browser control plane and production operations. Loopback-first HTTP surface, same-origin/CSRF, append-only audit/idempotency, restart recovery, explicit broker switching/cleanup planning. Browser is not execution authority; provider cleanup writes/live trading not promoted.

### Phase 17

Real provider read-only operational readiness accepted.

Target-machine evidence:

- Webull sandbox explicit selected sanitized account ref `3d64d273c694250b` after five readable accounts;
- Webull account list/balance/open-order/position reads passed;
- Webull 0 open orders / 0 positions;
- Alpaca paper sanitized ref `4b5b072f7127b4dc`, reconciled, 0 open orders / 0 positions;
- both brokers AVAILABLE/reconciled;
- provider mutation endpoint invocations 0;
- provider writes 0;
- live writes 0;
- local regression 874 passed in 24.83s;
- Windows/Ubuntu CI passed.

## 5. Phase 18 implementation state

Phase 18 is designed to prove the first real **paper/sandbox provider mutation lifecycle** without contaminating strategy/model/AI lineage and without granting live authority.

### 5.1 Authority gate

Provider mutation defaults to disabled.

A real run requires:

- one explicit broker;
- `--authorize-paper-provider-mutation`;
- exact confirmation `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credentials, endpoints, environment mode, connected accounts, prior phase acceptance, code existence, and passing tests do not substitute for authorization.

### 5.2 Production semantic path

`packages/execution/phase18_lifecycle.py` exercises accepted Phase 15 execution semantics against fake providers:

- fresh quote;
- current risk;
- provider preflight;
- broker/account/order/position reconciliation;
- protective geometry;
- deterministic client IDs;
- uncertain-write blocking;
- no automatic failover;
- no automatic flatten after fill.

### 5.3 Operational certification path

`packages/execution/phase18_operational_validation.py` defines a separate validation-only order so real broker plumbing can be certified without inventing a fake Phase 13/14 production trade.

It is not strategy/model/AI/performance evidence.

Contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

Locked order:

- PAPER/SANDBOX only;
- equity BUY;
- exactly 1 share;
- LIMIT / DAY;
- no extended hours;
- entry 5% below realtime bid;
- stop 2% below entry;
- target 2% above entry;
- absolute notional <= $1,000;
- single-name notional <= 10% equity;
- loss at stop <= 0.5% equity.

Expected lifecycle is submit/reconcile/cancel/reconcile flat, but fills are possible. If filled or partially filled, no auto-flatten occurs; separate cleanup authority is required.

### 5.4 Uncertainty handling

Uncertain submit/cancel:

- read-only reconcile if possible;
- no retry;
- no second mutation;
- no flatten;
- no failover;
- stop until exact state is known.

### 5.5 Target runner

`scripts/run_phase18_operational_validation.py`

Requires `--broker webull|alpaca` and exact `--ticker`. No default ticker and no quantity argument.

Without mutation authorization it is plan-only and must initialize no broker adapter / make 0 provider calls / make 0 provider writes.

Mutation-gate diagnostic:

`scripts/diagnose_phase18_mutation_gate.py --broker webull`

Correct default result is authorization DENIED with no adapter/calls/writes.

## 6. Realtime market-data requirement for real certification

Accepted launcher:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_market_state.py `
  --feed realtime `
  --minute-symbols "" `
  --quote-symbols <TICKER> `
  --no-journal
```

The Phase 15 resolver accepts execution evidence only when:

- connection is actively SUBSCRIBED;
- feed is REALTIME;
- expected delay is 0;
- no transport gap is open;
- market session is REGULAR;
- exact provider-native ticker exists exactly once;
- quote is FRESH.

Stopped streams, weekends, holidays, stale/delayed feeds, premarket, and after-hours fail closed. Since today is Sunday 2026-08-23, real Phase 18 provider certification is intentionally unavailable today.

## 7. Latest target-machine evidence

User pulled Phase 18 branch head `e1631e741a547c78eb6c3c9b943ba1473c805cf6` and ran the complete pre-mutation block.

Results:

- Phase 18 validator: PASS.
- Focused Phase 18 tests: **34 passed in 2.23s**.
- Webull read-only recheck:
  - credentials present;
  - explicit selected account configured;
  - account list HTTP 200;
  - balance HTTP 200;
  - open orders HTTP 200, count 0;
  - positions HTTP 200, count 0.
- Alpaca paper read-only recheck:
  - reconciled true;
  - open orders 0;
  - positions 0;
  - safe-to-switch true.
- Phase 18 mutation gate:
  - provider adapter initialized NO;
  - provider calls 0;
  - provider writes 0;
  - live disabled;
  - automatic failover disabled;
  - authorization DENIED exactly as intended.
- Working tree: clean.

Full local regression was **907 passed / 1 failed in 31.73s**. Sole failure:

`tests/unit/test_phase16_action_api.py::test_csrf_failure_creates_no_action_event`

Error:

`ConnectionAbortedError: [WinError 10053] An established connection was aborted by the software in your host machine`

This happened on the loopback CSRF-rejection request and was isolated from Phase 18 broker/provider logic.

## 8. Windows loopback test portability hardening

Investigation showed the unit-test HTTP opener inherited ambient proxy settings. That is inappropriate for a deterministic test of the accepted Phase 16 loopback-only `127.0.0.1` server and can expose the test to local Windows proxy/security interception.

Commit:

`45a2abeba7a51401ee708ab777d960d2f7fea88f`

Change:

- test harness `_session_opener()` now explicitly adds `urllib.request.ProxyHandler({})` before the cookie handler.

Scope:

- test client only;
- no production Phase 16 server change;
- no broker-adapter change;
- no execution/risk/authority change;
- no provider mutation.

Validation CI run:

`32657554236`

Results:

- all validators through Phase 18 PASS;
- Ubuntu full suite: **908 passed in 13.57s**;
- Windows full suite: **908 passed in 20.98s**;
- both jobs SUCCESS.

Therefore the next target-machine action is only to pull the hardening and rerun the formerly failing isolated test plus full regression. The broker/provider diagnostics do not need repetition solely because this code change is test-harness-only.

## 9. Current broker authority

### Webull

- primary planned execution broker;
- sandbox reads accepted;
- explicit local selected account established;
- real Phase 18 mutation not yet authorized/performed.

### Alpaca

- manual secondary/fallback;
- paper reads accepted;
- not an automatic failover target;
- real Phase 18 mutation not yet authorized/performed.

### Live

- live execution disabled;
- live credentials/endpoints, if configured as placeholders, do not grant authority;
- any later live-money transition requires a separate preregistered phase and explicit user authorization.

## 10. Configuration status

Tracked `.env.example` is non-secret and may contain public/default endpoints.

Current structure includes:

- application/OpenAI/database placeholders;
- Massive API/S3 placeholders and `https://files.massive.com` endpoint;
- Webull paper and future live credential placeholders;
- Alpaca paper endpoint `https://paper-api.alpaca.markets/v2` and live endpoint `https://api.alpaca.markets` with blank credentials;
- optional IBKR `127.0.0.1:4002`, client ID 17.

Secrets, raw account IDs, passwords, security codes, or tokens must never be committed. Commented secrets are still secrets. Generated `webull_trade_sdk.log*` is ignored.

## 11. Exact next steps

### Immediate local recheck

Pull latest Phase 18 branch, run:

1. isolated `test_csrf_failure_creates_no_action_event`;
2. full `pytest -q`;
3. confirm clean `git status`.

Expected: isolated test passes and full suite reports **908 passed**.

### Later regular-session Phase 18 certification

After local recheck is clean, wait until a regular U.S. equity session, then:

1. start focused Massive realtime `Q.<ticker>` stream;
2. keep stream active;
3. run Phase 18 plan-only validation first;
4. verify 0 broker/provider calls/writes in plan-only mode;
5. review exact one-share plan;
6. obtain explicit paper-provider mutation authorization;
7. certify Webull sandbox first;
8. reconcile exact client ID;
9. cancel once if still open;
10. prove flat/zero-open state;
11. if fill/partial fill, stop for separate cleanup authorization;
12. never auto-fail over to Alpaca;
13. record sanitized evidence in PR/docs;
14. merge Phase 18 only after accepted real paper-provider lifecycle evidence.

## 12. Future-chat startup procedure

A future session should:

1. inspect `main`, branches, open PRs;
2. read this file;
3. read `docs/roadmap.md`;
4. read `docs/phase18_operational_validation.md` while Phase 18 is active;
5. read root README;
6. inspect PR #18 and latest CI;
7. preserve explicit provider/live authority boundaries;
8. continue from section 11 rather than revisiting already accepted phases unless validation evidence requires it.

## 13. Documentation rule

Every meaningful work package synchronizes:

- `README.md`;
- `docs/roadmap.md`;
- this file;
- active phase spec;
- active PR evidence ledger;
- relevant configuration templates/docs.

Historical phase/fix READMEs remain historical provenance.
