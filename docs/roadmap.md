# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-24.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This is the long-term architecture and authority lock. Implementation may evolve with measured evidence, but data-integrity, model, strategy, provider, broker, automation, and LIVE boundaries change only through explicit documented and independently validated replacement decisions.

## 1. Mission and architecture

Build the operational chain:

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> deep research/news -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary broad-market/reference; Webull is primary PAPER/sandbox; Alpaca is manual secondary only; ML is probability evidence; AI is audit only; browser is monitoring/control only.

The strategic destination is a complete safe Webull-primary SHADOW/PAPER system with reconciliation, observability, and outcome learning before any separately authorized LIVE transition. Infrastructure must support that destination rather than displace it.

## 2. Development contract

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Code existence, credentials, connectivity, locally present files, registered jobs, or green tests never silently expand authority. Zero-promotion/zero-case/zero-finalist results are valid. Protected/final evidence cannot be used to retroactively tune a preregistered study.

## 3. Current phase state

- **Phases 1–24 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- **Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a` through PR #26.**
- Phase24 disposition: **NO SUPPORT REPLACEMENT**.
- Gate1 fingerprint: `9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`.
- Gate2 target head: `f591942413973107d7abc9d21325623e2e7000f1`.
- Final pre-merge living-doc head: `5ed3311d4ec1ac97cf841e160cf9c0987f731fe5`.
- Final pre-merge CI `32806726958`: Ubuntu/Windows SUCCESS; every validator through Phase24 Gate2 and full regression passed.

## 4. Non-negotiable data rules

- Preserve provider-native ticker text/case; ticker text never proves identity continuity.
- Historical populations are PIT; do not project current survivors backward.
- Ambiguity is quarantined/excluded, never guessed.
- No synthetic pre-2021 intraday bars from daily history.
- Finalized canonical data outranks provisional live observations.
- Partial-run files are not an accepted baseline without the applicable handoff.
- Data/model/authority transitions require explicit lineage and independent validation.

Historical boundary:

- Alpaca raw SIP daily: 2016-01-04 through 2021-08-13 under controlled historical authority.
- Massive and legitimate intraday/ticker-regime history: **2021-08-16 onward**.
- Cumulative lineage: `6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`.

## 5. ML and strategy authority

Accepted production ML:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB leaf15/iter100;
- 33 PIT predictors;
- accepted protected holdout 2026-05-12 through 2026-08-11;
- exact deterministic replay.

ML cannot independently choose a trade, broker, order, or authority transition.

Accepted Phase11 strategy support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Only accepted SUPPORTED strategies may promote under current production authority. Regime routing stays outside strategy implementations. Expensive research remains promoted-only. AI cannot override deterministic evidence, geometry, risk, provider, or execution authority.

## 6. Geometry/risk

LONG: `stop < entry < target`; SHORT: `stop > entry > target`.

Accepted Phase13 envelope includes risk-at-stop <=0.5% equity, single-name notional <=10% equity, liquidity/buying-power/account-state checks, and exposure/concentration/correlation revalidation where applicable.

## 7. Execution/control authority

- Webull: primary PAPER/sandbox; future LIVE only after separate authority.
- Alpaca: manual secondary/fallback only.
- No automatic failover.
- Unknown/uncertain mutation state fails closed and requires reconciliation.

Phase20: deterministic local orchestration only; no provider/broker/scheduler/PostgreSQL/LIVE authority.

Phase21 fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`: centralized default-deny PAPER submit authority; exactly one raw `adapter.submit(plan)` under `packages/`.

Phase22 fingerprint `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`: routine Webull-primary PAPER operator; Alpaca manual; no arbitrary trade inputs; accepted zero-case/no-provider behavior.

Phase23 fingerprint `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`: routine explicit-finalized-session analytical operator; provider-free prepare; only Massive market/reference reads when missing; no broker/PAPER execution.

LIVE remains disabled.

## 8. Phase23 evidence

Accepted finalized 2026-08-21 cycle:

- baseline 2026-08-14;
- sessions advanced 5;
- WARM/HOT directional cases 23;
- promotions 0;
- Phase12/13/14/execution cases 0;
- broker/order/PAPER/LIVE activity 0;
- independent validation PASS.

The first attempt exposed a persisted nullable-state NaN defect and failed closed; the repair did not change discovery thresholds, support, model, risk, or authority.

## 9. Phase24 evidence — accepted no replacement

Gate0 provider-free current diagnostic:

- 23 current WARM/HOT cases;
- 92 eligible incumbent route evaluations;
- 48 counterfactual incumbent fires;
- 21/23 current cases with >=1 fire;
- promotions and all external/execution/support writes 0;
- PASS.

Gate1 preregistered exactly 28 bounded challengers and stronger methodology before performance was observed: chronological selection/internal validation, purge, session-level dependence handling, block bootstrap, 10/25 bps costs, mean/median/positive-rate/LCB, year/regime robustness, Holm multiplicity, maximum one finalist per family/direction, zero protected-read/support-replacement authority.

Gate2 target on `f591942413973107d7abc9d21325623e2e7000f1`:

- 28 challengers;
- 0 basic-pass;
- 0 selections/finalists;
- protected reads 0;
- provider/broker/order/PAPER/LIVE/support writes 0;
- independent PASS.

Forensics:

- positive chronological folds failed 28/28;
- positive block-bootstrap LCB failed 28/28;
- positive 25 bps stress mean failed 28/28;
- sample scarcity affected only a small minority;
- best long trend variant retained ~+7.37 bps after 10 bps cost but had negative LCB/stress;
- short trend/momentum/breakdown families were materially negative at the primary cost.

**Decision: NO SUPPORT REPLACEMENT.** No Gate3 protected evaluation occurred. Do not relax Phase24 gates or continue blind threshold tightening of the same rule families.

## 10. Phase ledger

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
11. Non-numbered historical extension/audit — controlled Alpaca daily extension to 2016 and cumulative lineage audit.
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
25. Phase24 — Strategy evidence challenger/support replacement research — ACCEPTED/MERGED, **NO SUPPORT REPLACEMENT**.

## 11. Next phase — route-fidelity boundary

The Phase24 post-evidence audit found that historical support is not measured on the same population production promotion uses.

Historical study population: broad daily rows + broad market-regime routing.

Production path:

`PIT universe -> broad discovery -> 1d/4h/1h scoring -> discovery hysteresis -> WARM/HOT directional qualification -> market/sector/ticker strategy route -> historical support -> current rule fire`

Current sector context is intentionally `UNAVAILABLE` because no authoritative ticker-to-sector mapping is accepted; it must not be fabricated. Market/ticker routing still matter.

Define next:

**Phase25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence**.

Initial Phase25 requirements:

1. zero provider/broker/order/PAPER/LIVE/support authority;
2. replay begins no earlier than **2021-08-16**;
3. no synthetic pre-2021 intraday/ticker context;
4. reconstruct PIT universe, multi-timeframe discovery, state hysteresis, WARM/HOT direction, market/ticker route semantics;
5. hold incumbent rules and the three-session outcome fixed initially;
6. build an attribution ladder: broad -> discovery-qualified -> market-routed -> ticker-routed -> rule-fired;
7. independently validate replay population/lineage before any support replacement;
8. do not use Phase24 failures to loosen thresholds.

If route-fidelity evidence still lacks robust edge, a later separately preregistered strategy phase may investigate materially different architectures: relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, or composite signals. Existing empty scaffolds are not authority to activate them prematurely.

GUI remains monitoring/control only. Scheduler/PostgreSQL promotion remain separate future authority decisions.

## 12. Performance/security/recovery

Retained feature benchmark: 50k rows/7,454 symbols/7 sessions; optimized ~4.00s vs ~594.58s prior baseline; ~148.5x; all 33 features exact parity.

Never commit secrets, raw broker IDs, tokens, passwords, security codes, or signed request metadata. Recovery: inspect `main`, current status, this roadmap, Phase24, Phase23, Phase22/21, and phase flow; continue from section 11 rather than reopening accepted work without new evidence.
