# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-26.**

## 1. Source-of-truth order

1. accepted code/artifacts on `main`;
2. active phase branch + exact-head CI;
3. active phase specification;
4. `docs/roadmap.md`;
5. this file;
6. `docs/phase_flow.md`;
7. README;
8. merged PRs/historical docs as provenance.

Repository: `nicholaslpollard/ATLAS`.

## 2. Exact repository state

- **Phases 1–24 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a` through PR #26.
- **Phase25: VALIDATED / MERGE PENDING through PR #27.**
- Phase25 final target-tested code head: `302bf6db5d807884f3b74cda049fc95864c5a194`.
- Phase25 exact-head CI `32981080421`: Ubuntu/Windows SUCCESS; validators through Gate11 and full regression passed.
- Phase25 disposition: **NO SUPPORT REPLACEMENT — DEVELOPMENT ROBUSTNESS FAILED**.

LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## 3. Architecture lock

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> deep research/news -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary market/reference; Webull is primary PAPER/sandbox; Alpaca is manual secondary only.

## 4. Non-negotiable rules

- Preserve provider-native ticker text/case; ticker text never proves identity continuity.
- Historical populations are PIT; ambiguity is quarantined, never guessed.
- No synthetic pre-2021 intraday history.
- Finalized canonical facts outrank provisional live state.
- ML is probability evidence only; AI is independent audit only.
- LONG `stop < entry < target`; SHORT reverse.
- Unknown provider/broker/run state fails closed.
- Uncertain writes are never retried blindly; reconcile first.
- No automatic broker failover.
- PAPER does not imply LIVE.
- Zero-promotion, zero-case, zero-selection, and zero-finalist states are valid.
- Never weaken data/strategy/risk/authority gates merely to create trades.

## 5. Accepted data/model evidence

- Alpaca raw SIP daily controlled authority: 2016-01-04 through 2021-08-13.
- Massive authority and legitimate ticker/intraday origin: 2021-08-16.
- cumulative lineage: `6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`.
- production ML: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`; HGB leaf15/iter100; 33 PIT predictors; exact accepted replay.

Accepted Phase11 strategy support remains authoritative:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

## 6. Accepted execution/control foundation

Phase15–19: broker-neutral SHADOW/PAPER execution, reconciliation/idempotency, browser control plane, accepted Webull sandbox mutation lifecycle, local observability. Do not repeat accepted provider/broker mutation evidence merely to reconfirm it.

Phase20: deterministic local orchestration only; no provider/broker/scheduler/PostgreSQL/LIVE authority.

Phase21 fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`: centralized default-deny PAPER submit authority; exactly one raw `adapter.submit(plan)` under `packages/`.

Phase22 fingerprint `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`: routine Webull-primary PAPER operator; Alpaca manual only; accepted zero-case/provider-free behavior.

Phase23 fingerprint `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`: finalized-session analytical operator; provider-free prepare; only bounded Massive reads when missing; no broker/PAPER execution.

## 7. Phase23 accepted target result

2026-08-21 from accepted 2026-08-14 baseline:

- sessions advanced: 5;
- WARM/HOT directional cases: 23;
- promotions: 0;
- Phase12/13/14 cases: 0/0/0;
- execution cases: 0;
- broker/order/PAPER/LIVE activity: 0;
- independent validation: PASS.

## 8. Phase24 accepted result

Phase24 tested 28 bounded threshold variants under stronger preregistered methodology. Results: 0 basic-pass, 0 selections/finalists, 0 protected reads. All 28 failed chronological-fold robustness, positive bootstrap LCB, and positive 25 bps stress mean. Decision: **NO SUPPORT REPLACEMENT**.

## 9. Phase25 validated result — route fidelity does not rescue incumbents

Read `docs/phase25_historical_production_path_route_fidelity.md` and `docs/phase25_remaining_evidence.md` for full evidence.

### Data/population reconstruction

- exact active-only PIT reference backfill: 1,253 sessions total, 15,442 provider pages including the 12-page probe;
- Gate6 replay sessions: 1,260;
- WARM/HOT directional population: 23,177;
- Gate7 fully route-eligible candidates: 15,283;
- eligible route decisions: 61,132;
- total route decisions: 185,416;
- all Gate6/7 external/execution/support authority zero;
- independent validation PASS.

### Incumbent strategy evidence

Gate8 development signals:

- legacy research-source route coverage: 43,456 / 57,160 = 76.0252%;
- development rule-fired rows: 24,753;
- candidates with >=1 fire: 10,521.

Every non-empty incumbent had a negative 10 bps production-path mean and was materially worse than its broad comparator. Pullback long/short produced no production-path signals.

Gate9:

- selected after development + global Holm: 0;
- finalists after internal validation: 0;
- all eight failed positive folds, mean, median, positive-rate, bootstrap-LCB, 25 bps stress, year robustness, and regime robustness;
- pullbacks additionally failed sample/session/concentration requirements.

Gate10: `SKIPPED_ZERO_FINALISTS`; protected reads 0.

Gate11 verdict: `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`.

Phase11 support map unchanged: true.

## 10. Exact continuation — Phase26 definition boundary

Phase25 answered the population-fidelity question. Do **not** continue threshold tuning of the v1 trend/momentum/breakout/pullback families and do not relax Phase24/25 gates.

Define next:

**Phase26 — Materially Different Strategy Architecture Research**.

Initial direction:

1. research-only; no provider/broker/order/PAPER/LIVE/support authority;
2. use the accepted PIT production-path lineage as the primary population source rather than the incomplete legacy Phase11/24 research join;
3. preregister all candidate architectures/search dimensions before target performance inspection;
4. retain 10 bps primary and 25 bps stress economics unless a separately justified cost model supersedes them;
5. retain temporal purging, session-level dependence handling, block bootstrap, year/regime robustness, concentration limits, and global multiplicity control;
6. investigate structurally different families such as cross-sectional relative strength, volatility/liquidity-conditioned mean reversion, gap/event continuation/reversal, volatility-normalized trend/breakout, multi-timeframe confirmation, and composite feature-block signals;
7. short-side strategies must not be mechanical mirrors of long-side rules;
8. use development/internal evidence first; protected/future prospective authority remains separate;
9. Phase11 support remains production authority unless a later separately accepted replacement decision occurs.

The Gate8 76% legacy join must be treated as a comparator limitation. Phase26 should construct its own exact production-path research table from accepted PIT canonical features/returns and Gate6/7 identities.

GUI remains monitoring/control only. Scheduler/PostgreSQL promotion remain separate future decisions.

## 11. Security/recovery

Never commit secrets, raw broker IDs, tokens, signed metadata, passwords, or security codes. Future startup: inspect authoritative `main`, open PRs/branches/latest CI; read current status, roadmap, Phase25, Phase24, Phase23, Phase22/21, and phase flow. Continue from Phase26 rather than reopening Phase25 or weakening accepted evidence gates.