# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-26.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. Implementation may evolve with evidence, but data integrity, model, strategy, provider, broker, automation, and LIVE boundaries change only through explicit documented and independently validated replacement decisions.

## 1. Mission and architecture

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> deep research/news -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary broad-market/reference; Webull is primary PAPER/sandbox; Alpaca is manual secondary only; ML is probability evidence; AI is audit only; browser is monitoring/control only.

## 2. Development contract

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Use the largest safe coherent batch. Zero-promotion/zero-case/zero-selection/zero-finalist results are valid. Protected/final evidence cannot be used to retroactively tune a preregistered study.

## 3. Current phase state

- **Phases 1–24 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- **Phase25 VALIDATED / MERGE PENDING through PR #27.**
- Phase25 final target-tested code head: `302bf6db5d807884f3b74cda049fc95864c5a194`.
- Phase25 exact-head CI `32981080421`: Ubuntu/Windows SUCCESS; all validators through Gate11 and full regression passed.
- Phase25 disposition: **NO SUPPORT REPLACEMENT — DEVELOPMENT ROBUSTNESS FAILED**.

## 4. Non-negotiable data rules

- Preserve provider-native ticker text/case; ticker text never proves identity continuity.
- Historical populations are PIT; do not project current survivors backward.
- Ambiguity is quarantined/excluded, never guessed.
- No synthetic pre-2021 intraday bars from daily history.
- Finalized canonical data outranks provisional live observations.
- Partial-run files are not accepted baselines without the applicable handoff.
- Data/model/authority transitions require explicit lineage and independent validation.

Historical boundary:

- Alpaca raw SIP daily: 2016-01-04 through 2021-08-13 under controlled historical authority.
- Massive and legitimate intraday/ticker-regime history: 2021-08-16 onward.
- cumulative lineage: `6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`.

## 5. ML and strategy authority

Accepted production ML:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB leaf15/iter100;
- 33 PIT predictors;
- protected holdout 2026-05-12 through 2026-08-11;
- exact deterministic replay.

Accepted Phase11 strategy support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Only accepted SUPPORTED strategies may promote under current production authority. Regime routing stays outside strategy implementations. Expensive research remains promoted-only. AI cannot override deterministic evidence, geometry, risk, provider, or execution authority.

## 6. Geometry/risk and execution authority

LONG: `stop < entry < target`; SHORT: `stop > entry > target`.

Accepted Phase13 envelope includes risk-at-stop <=0.5% equity, single-name notional <=10% equity, liquidity/buying-power/account-state checks, and exposure/concentration/correlation revalidation where applicable.

- Webull: primary PAPER/sandbox; future LIVE only after separate authority.
- Alpaca: manual secondary/fallback only.
- no automatic failover.
- unknown/uncertain mutation state fails closed and requires reconciliation.
- LIVE remains disabled.

Phase20: deterministic local orchestration only; no provider/broker/scheduler/PostgreSQL/LIVE authority.

Phase21 fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`: centralized PAPER submit authority; exactly one raw `adapter.submit(plan)` under `packages/`.

Phase22 fingerprint `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`: routine Webull-primary PAPER operator; Alpaca manual; no arbitrary trade inputs.

Phase23 fingerprint `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`: finalized-session analytical operator; provider-free prepare; only bounded Massive reads when missing; no broker/PAPER execution.

## 7. Phase24 evidence — accepted no replacement

Phase24 preregistered 28 bounded v2 threshold variants under stronger chronology/uncertainty/cost/multiplicity rules. Target result: 0 basic-pass, 0 selections/finalists, 0 protected reads. All 28 failed chronological folds, positive block-bootstrap LCB, and positive 25 bps stress mean. **NO SUPPORT REPLACEMENT.**

## 8. Phase25 evidence — validated no replacement

Phase25 rebuilt historical population/routing fidelity instead of changing incumbent rules.

### PIT production-path reconstruction

- exact PIT active-only reference acquisition: 1,253 sessions total;
- provider page reads: 15,442 total including Gate4 probe;
- Gate6 replay sessions: 1,260;
- WARM/HOT directional population: 23,177;
- Gate7 market-compatible candidates: 17,285;
- fully route-eligible candidates: 15,283;
- eligible route decisions: 61,132;
- total route decisions: 185,416;
- exact PIT ticker intervals: 9,609;
- independent validation PASS.

### Incumbent evidence on production path

Gate8 development-only result:

- legacy research-source route coverage: 43,456 / 57,160 = 76.0252%;
- rule-fired signal rows: 24,753;
- candidates with >=1 incumbent fire: 10,521;
- every non-empty incumbent had a negative 10 bps production-path mean and worsened vs its broad comparator;
- pullback long/short had no production-path fires.

Gate9:

- 0 selected after development + global Holm;
- 0 internal finalists;
- all eight failed positive folds, mean, median, positive-rate, bootstrap LCB, 25 bps stress, year robustness, and regime robustness.

Gate10: zero finalists -> protected evidence reads 0.

Gate11 verdict: `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`.

**Decision: Phase11 support remains authoritative unchanged. Population fidelity was not the hidden missing edge.**

The 76% legacy research-source join is retained as a comparator limitation. Future strategy research should build directly from accepted PIT production-path features/returns rather than depend on the legacy broad research table as primary source.

## 9. Phase ledger

1. Phase1 — Foundation.
2. Phase2 — Provider ingestion foundation.
3. Phase3 — Canonical/session-aware data.
4. Phase4 — Instrument identity/history.
5. Phase5 — Live market state.
6. Phase6 — 33-feature engine.
7. Phase7 — PIT universe registry.
8. Phase8 — Broad discovery/hysteresis.
9. Phase9 — Market/sector/ticker regimes.
10. Phase10 — ML probability/evaluation and production model.
11. historical extension/audit — controlled Alpaca daily extension to 2016 and cumulative lineage audit.
12. Phase11 — Strategy evaluation/routing/support.
13. Phase12 — Promoted-only deep research.
14. Phase13 — Context/instrument/geometry/portfolio risk.
15. Phase14 — Independent AI audit/alerting.
16. Phase15 — Broker-neutral SHADOW/PAPER + outcome learning.
17. Phase16 — Browser control plane/production operations.
18. Phase17 — Provider-readonly operational readiness.
19. Phase18 — Webull sandbox mutation lifecycle certification.
20. Phase19 — Operations dashboard/PAPER-SHADOW observability.
21. Phase20 — Deterministic local orchestration.
22. Phase21 — Unified PAPER submit authority.
23. Phase22 — Operational Webull-primary PAPER runner.
24. Phase23 — Operational current finalized analytical cycle — ACCEPTED/MERGED.
25. Phase24 — Strategy evidence challenger — ACCEPTED/MERGED, NO SUPPORT REPLACEMENT.
26. Phase25 — Historical production-path replay / route fidelity — VALIDATED, NO SUPPORT REPLACEMENT.

## 10. Next phase — materially different strategy architectures

Define and lock **Phase26 — Materially Different Strategy Architecture Research** after Phase25 merge.

Phase26 requirements:

1. research-only; no provider/broker/order/PAPER/LIVE/support authority;
2. accepted Phase25 production-path lineage is the primary research population;
3. do not use the incomplete legacy Phase11/24 research join as primary source;
4. candidate search space and architecture families frozen before target performance inspection;
5. retain realistic transaction costs, 10 bps primary and 25 bps stress unless separately justified otherwise;
6. retain chronological selection/internal validation, purge, session-level dependence handling, block bootstrap, year/regime robustness, concentration gates, and multiplicity control;
7. candidate families must be materially different, such as cross-sectional relative strength, volatility/liquidity-conditioned mean reversion, gap/event continuation/reversal, volatility-normalized trend/breakout, multi-timeframe confirmation, and composite feature-block signals;
8. short strategies must not be mechanical long-rule mirrors;
9. protected/future prospective evidence remains separate and cannot retroactively tune development selection;
10. Phase11 support remains production authority until a separately accepted replacement decision.

GUI remains monitoring/control only. Scheduler/PostgreSQL promotion remain separate future authority decisions.

## 11. Performance/security/recovery

Retained feature benchmark: 50k rows / 7,454 symbols / 7 sessions; optimized ~4.00s vs ~594.58s prior baseline; ~148.5x; all 33 features exact parity.

Never commit secrets, raw broker IDs, tokens, passwords, security codes, or signed request metadata. Recovery: inspect authoritative `main`, current status, roadmap, Phase25, Phase24, Phase23, Phase22/21, and phase flow; continue from Phase26 rather than reopening accepted Phase25 work.