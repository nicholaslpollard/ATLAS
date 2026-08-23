# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-23.**

This is the fastest source for a future chat or development session to recover the exact ATLAS state and continue without reconstructing the project from conversation history.

## 1. Source-of-truth order

When sources disagree, use this order:

1. accepted code/artifacts on `main` for completed work;
2. active PR/branch code for in-progress work;
3. `docs/roadmap.md` for architecture and authority rules;
4. this file for exact current state/evidence/continuation;
5. `docs/phase_flow.md` for the mandatory phase progression;
6. active phase living specification;
7. root `README.md`;
8. merged PRs for deeper accepted evidence;
9. old phase/fix READMEs as historical provenance only.

## 2. Repository state

Repository: `nicholaslpollard/ATLAS`

Accepted work:

- Phases 1–17 are accepted and merged into `main`.
- Accepted Phase 17 merge: `65d5a7b58c6894eba27722465741c92db9a33aaf`.

Active work:

- Phase 18 — Paper Provider Mutation Lifecycle Validation.
- Branch: `phase-18-paper-provider-mutation-lifecycle-validation`.
- PR: #18, draft, targeting `main`.
- Phase 18 policy: `phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`.
- Phase 18 policy fingerprint: `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.
- Windows transport-hardening code head: `38c09c21d4fc636667921c779fbe59341839e9e8`.
- Final target-machine pre-mutation software acceptance baseline: `94a859fc6d44c22a6f8852c1488215a6677806a0`.
- Phase 18A pre-mutation software package: **ACCEPTED / COMPLETE**.
- Phase 18B real paper-provider certification: **WAITING_EXTERNAL**.
- Real Phase 18 provider mutation performed: **NO**.
- Live execution promoted: **NO**.
- Automatic broker failover allowed: **NO**.

Current provider-authority checkpoint:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

## 3. Mandatory phase flow

ATLAS now has an explicit phase execution contract in `docs/phase_flow.md`.

Every numbered phase follows:

`DEFINE -> LOCK -> IMPLEMENT -> FOCUSED TEST -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

A future numbered phase does not become active merely because useful work can be imagined. The current phase must satisfy its acceptance boundary and merge first unless a deliberate roadmap exception is explicitly documented.

Current Phase 18 subphase status:

- **18A — Pre-mutation software validation: ACCEPTED / COMPLETE**.
- **18B — Real paper-provider operational certification: WAITING_EXTERNAL** for a regular U.S. equity session and explicit mutation authorization after plan review.
- **Phase 19: NOT ACTIVE / NOT YET DEFINED**.

## 4. Architecture snapshot

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/Monte Carlo/scenarios -> news/events -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage roles:

- Parquet: durable analytical/history lake.
- DuckDB: analytical engine.
- PostgreSQL: target operational state.
- Massive: primary accepted market/reference-data provider path.

## 5. Non-negotiable architecture and authority rules

- Preserve exact provider-native ticker text/case.
- Ticker text alone never proves identity continuity.
- Historical populations remain point-in-time/observation-driven.
- Ambiguous identity/continuity is quarantined or excluded, never guessed.
- No synthetic pre-2021 intraday bars from daily data.
- Finalized canonical facts outrank provisional live observations.
- ML emits probability evidence; argmax is diagnostic only and is not a trade signal.
- Production model authority cannot be silently replaced by challenger research.
- AI is independent audit only and cannot create execution authority.
- LONG geometry: `stop < entry < target`.
- SHORT geometry: `stop > entry > target`.
- Unknown broker/provider state fails closed.
- Uncertain writes are not retried blindly.
- Automatic cross-broker failover is forbidden.
- Paper/sandbox authority does not imply live authority.

## 6. Accepted data/model evidence

Historical provider boundary:

- Alpaca raw SIP daily controlled authority: 2016-01-04 through 2021-08-13.
- Massive authority: 2021-08-16 onward.
- No synthetic pre-2021 1h/4h history.

Accepted cumulative data/lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Accepted production ML model:

- ID: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`.
- specification: `hgb_leaf15_iter100`.
- 33 point-in-time quantitative predictors.
- outputs: `p_down`, `p_neutral`, `p_up`.
- protected holdout: 2026-05-12 through 2026-08-11.
- 63 sessions / 454,773 rows.
- log loss 0.948693.
- Brier 0.560422.
- macro OVR AUC 0.570016.
- exact deterministic replay.

Phase 11 accepted strategy support:

- SUPPORTED: 0.
- MIXED: 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`.
- UNSUPPORTED: 5.

Zero supported strategies correctly produced zero accepted promotions on the locked case; thresholds were not weakened.

## 7. Accepted execution/control-plane foundation

### Phase 15

Broker-neutral shadow/paper execution contracts include:

- Webull primary.
- Alpaca manually selectable secondary/fallback.
- no automatic failover.
- fresh quote requirement.
- provider preflight.
- account/order/position reconciliation.
- current risk revalidation.
- protective stop/target geometry.
- deterministic client-order IDs/idempotency.
- uncertainty fail-closed.
- same-ticker add/flip disabled.
- live hard-disabled.

### Phase 16

Accepted browser/control-plane behavior includes:

- loopback-first HTTP surface.
- CSRF/same-origin protection.
- append-only audit/idempotency.
- restart recovery.
- explicit broker switching and cleanup planning.
- browser actions cannot create trading authority.
- provider cleanup writes/live trading were not promoted.

### Phase 17

Real provider read-only readiness is accepted.

Webull sandbox:

- five readable sandbox accounts discovered.
- ambiguity failed closed until explicit selection.
- selected sanitized margin-account ref `3d64d273c694250b`.
- account list/balance/open-order/position reads succeeded.
- accepted closeout: 0 open orders / 0 positions.

Alpaca paper:

- sanitized account ref `4b5b072f7127b4dc`.
- reconciliation succeeded.
- accepted closeout: 0 open orders / 0 positions.

Combined Phase 17 acceptance:

- both brokers AVAILABLE/reconciled.
- provider mutation endpoint invocations 0.
- provider writes 0.
- live writes 0.
- target-machine regression 874 passed in 24.83s.
- Windows/Ubuntu CI passed.

## 8. Phase 18 policy and operational design

Phase 18 proves the first real paper/sandbox provider mutation lifecycle without fabricating strategy/model/AI lineage and without granting live authority.

### 8.1 Authority gate

Provider mutation is disabled by default.

A real target-machine mutation run requires:

- exactly one selected broker.
- `--authorize-paper-provider-mutation`.
- exact confirmation `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

Credentials, endpoints, environment mode, connected accounts, prior acceptance, code existence, or passing tests do not substitute for explicit authorization.

### 8.2 Separate validation paths

1. `packages/execution/phase18_lifecycle.py` validates accepted Phase 15 production semantics against fake providers.
2. `packages/execution/phase18_operational_validation.py` defines a separate validation-only real-provider order.

The operational order is not a strategy signal, model outcome, AI-reviewed production case, performance evidence, or live authority.

### 8.3 Locked certification order

Contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

- PAPER/SANDBOX only.
- EQUITY BUY only.
- quantity exactly 1 share.
- LIMIT / DAY.
- no extended hours.
- entry 5% below fresh realtime bid.
- stop 2% below entry.
- target 2% above entry.
- absolute notional cap $1,000.
- accepted Phase 13 single-name cap 10% of current equity.
- accepted Phase 13 loss-at-stop cap 0.5% of current equity.

Expected normal lifecycle:

`submit once -> exact client-ID reconcile -> cancel once while open -> reconcile zero-open/flat`

If filled or partially filled, ATLAS stops for separate cleanup authority. It does not auto-flatten and does not fail over automatically.

### 8.4 Uncertain mutation handling

If submit or cancel becomes uncertain:

- perform read-only exact reconciliation if possible.
- no blind retry.
- no second mutation.
- no auto-flatten.
- no automatic Alpaca failover.
- stop until exact provider state is established.

## 9. Realtime market-data requirement for Phase 18B

Accepted launcher:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_market_state.py `
  --feed realtime `
  --minute-symbols "" `
  --quote-symbols <TICKER> `
  --no-journal
```

The Phase 15 quote resolver requires:

- connection actively SUBSCRIBED.
- feed REALTIME.
- expected delay 0.
- no open transport gap.
- market session REGULAR.
- exact provider-native ticker exactly once.
- quote FRESH.

Weekends, holidays, stale/delayed data, stopped streams, premarket, and after-hours fail closed. The gate is not weakened simply to perform certification.

## 10. Phase 18A acceptance evidence

Initial pre-mutation target-machine block:

- Phase 18 validator PASS.
- focused Phase 18 tests: 34 passed in 2.23s.
- Webull sandbox read recheck: account list/balance/orders/positions HTTP 200, 0 open orders, 0 positions.
- Alpaca paper recheck: reconciled, 0 open orders, 0 positions.
- mutation gate DENIED correctly before broker initialization.
- provider calls 0.
- provider writes 0.

Windows loopback test investigation produced two test-only hardenings:

- `45a2abeba7a51401ee708ab777d960d2f7fea88f` — disables ambient proxy routing for loopback test traffic.
- `38c09c21d4fc636667921c779fbe59341839e9e8` — directly proves `SAME_ORIGIN_REQUIRED` and accepts only exact Windows `winerror == 10053` as an alternate host-transport manifestation after application rejection is already proven.

Production Phase 16 HTTP code, broker adapters, execution/risk logic, Phase 18 policy, and provider authority were unchanged.

Final repository CI evidence:

- run `32662398274`: all validators through Phase 18 PASS; Ubuntu 908 passed; Windows 908 passed.
- run `32662817172` for baseline `94a859fc6d44c22a6f8852c1488215a6677806a0`: SUCCESS on Ubuntu and Windows with all validators green.

Final target-machine acceptance at baseline `94a859fc6d44c22a6f8852c1488215a6677806a0`:

- isolated CSRF test: 1 passed in 3.30s.
- full regression: **908 passed in 23.50s**.
- working tree clean.
- provider calls 0.
- provider writes 0.

**Disposition: Phase 18A is accepted and complete. There is no remaining software or Windows portability blocker.**

## 11. Current broker authority

### Webull

- primary planned execution broker.
- sandbox reads accepted.
- explicit local selected account established.
- Phase 18B real sandbox mutation not yet authorized/performed.

### Alpaca

- manual secondary/fallback.
- paper reads accepted.
- not an automatic failover destination.
- Phase 18B real paper mutation not yet authorized/performed.

### Live

- live execution disabled.
- configured live placeholders/endpoints do not grant authority.
- any live-money transition requires a later separately defined phase and separate explicit user authorization.

## 12. Exact continuation point

### Phase 18A

**COMPLETE.** Do not repeat the 908-test regression solely for the closed Windows portability issue.

### Phase 18B

**WAITING_EXTERNAL.** During a regular U.S. equity session:

1. choose an exact provider-native ticker suitable for the one-share <$1,000 cap.
2. start focused Massive realtime `Q.<ticker>` state and keep it active.
3. run Phase 18 plan-only operational validation.
4. verify plan-only mode makes 0 broker/provider calls/writes.
5. inspect the exact one-share entry/stop/target/risk plan.
6. obtain explicit paper-provider mutation authorization.
7. certify Webull sandbox first.
8. submit exactly once.
9. reconcile the exact deterministic client ID.
10. cancel exactly once if still open.
11. reconcile zero-open/flat.
12. if filled/partially filled, stop for separate cleanup authorization.
13. never automatically fail over to Alpaca.
14. save only sanitized evidence.
15. update living docs/PR.
16. mark PR #18 ready and merge only after accepted Phase 18B evidence.
17. verify `main` and delete the merged Phase 18 branch.
18. only then define and activate Phase 19.

Until explicit authorization is given, do not submit, cancel, replace, or flatten any provider order for Phase 18 certification.

## 13. Configuration/security status

Tracked `.env.example` is non-secret and may contain public/default endpoints.

It includes:

- application/OpenAI/database placeholders.
- Massive credentials/S3 placeholders and `https://files.massive.com`.
- Webull paper and future live placeholders.
- Alpaca paper endpoint `https://paper-api.alpaca.markets/v2` and live endpoint `https://api.alpaca.markets` with blank credentials.
- optional IBKR localhost defaults (`127.0.0.1`, port 4002, client ID 17).

Secrets, raw account IDs, passwords, security codes, or tokens must never be committed. Commented secrets are still secrets.

## 14. Future-chat startup procedure

A future session should:

1. inspect `main`, branches, open PRs, and latest CI.
2. read this file.
3. read `docs/roadmap.md`.
4. read `docs/phase_flow.md`.
5. read `docs/phase18_operational_validation.md` while Phase 18 is active.
6. read root README.
7. preserve explicit provider/live authority boundaries.
8. continue from section 12 rather than revisiting accepted work unless new evidence requires it.

## 15. Documentation rule

Every meaningful work package synchronizes, as applicable:

- `README.md`.
- `docs/roadmap.md`.
- this file.
- `docs/phase_flow.md` when process rules change.
- active phase specification.
- active PR acceptance/evidence ledger.
- relevant configuration templates/docs.

Historical phase/fix READMEs remain historical provenance.