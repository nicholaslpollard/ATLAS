# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-24.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This is the long-term architecture and authority lock. Implementation may evolve when measured evidence requires it, but data-integrity, validation, model, strategy, provider, broker, automation, and LIVE boundaries change only through explicit documented and independently validated replacement decisions.

For exact continuation read [`current_status.md`](current_status.md). For the latest analytical evidence read [`phase24_strategy_evidence_challenger.md`](phase24_strategy_evidence_challenger.md). For accepted current-cycle operations read [`phase23_operational_current_analysis_cycle.md`](phase23_operational_current_analysis_cycle.md). For PAPER authority/operator rules read the Phase21/22 docs. For development cadence read [`phase_flow.md`](phase_flow.md).

## 1. Mission

Build a broad-market system that can:

1. observe a large U.S. market universe;
2. maintain PIT-safe market/reference data, identity, features, and regimes;
3. discover candidates cheaply before expensive research;
4. estimate outcome probabilities with conventional ML;
5. route candidates to deterministic strategies appropriate to context/regime;
6. promote only evidence-supported candidates into deeper research;
7. produce deterministic entry/stop/target/horizon/risk plans;
8. subject deterministic cases to independent AI audit;
9. alert, shadow, paper-trade, and eventually trade LIVE only under separately accepted authority;
10. learn descriptively from outcomes without silently changing authority;
11. expose operational state through a browser control plane without making the browser an execution authority;
12. orchestrate restart-safe runs without silently creating provider/broker/scheduler/database/LIVE authority;
13. operate routinely on current finalized evidence;
14. reach a complete safe end-to-end PAPER/SHADOW system before lower-value infrastructure displaces that objective.

## 2. Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/compute/provider roles:

- **Parquet**: durable analytical/history lake.
- **DuckDB**: analytical/query engine.
- **PostgreSQL**: target persistent operational state; not an accepted runtime prerequisite.
- **Massive**: primary broad-market/reference-data provider.
- **Webull**: primary PAPER/sandbox execution broker; future LIVE only under separate explicit authority.
- **Alpaca**: manually selectable secondary/fallback; never automatic failover.

### 2.1 Strategic anti-drift anchor

The roadmap destination is the operational end-to-end ATLAS system, not an infrastructure milestone. ATLAS must progress from broad discovery through deterministic research/risk and independent AI audit into safe Webull-primary SHADOW/PAPER execution, reconciliation, observability, and outcome learning before any future LIVE transition.

Infrastructure, storage, orchestration, scheduling, and control-plane work are justified only when they improve correctness, safety, evidence quality, recoverability, performance, or operability.

## 3. Mandatory execution contract

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Principles:

- code existence or green tests alone do not establish acceptance;
- credentials/connectivity never silently expand authority;
- coherent batches are preferred over artificial micro-checkpoints;
- Ubuntu/Windows CI belongs at meaningful evidence boundaries;
- target-machine interaction is required only when CI/mocks cannot establish the fact;
- provider mutation, cleanup, broker switching, scheduling, PostgreSQL promotion, strategy-support replacement, and LIVE are separate gates;
- zero-promotion/zero-case/zero-finalist outcomes are legitimate;
- thresholds are never weakened merely to manufacture activity;
- newer files from a failed run are not automatically accepted state;
- protected/final evidence may not be used to retroactively tune preregistered research rules.

Current phase state:

- **Phases 1–23: ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0` through PR #25.
- **Phase24: acceptance evidence complete / NO SUPPORT REPLACEMENT / PR #26 merge pending.**
- Gate1 fingerprint: `9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`.
- Gate2 target head: `f591942413973107d7abc9d21325623e2e7000f1`.
- Phase24 closeout evidence head: `ba0721dd717ae8bdda877a376549cdef69ca00d9`.
- Closeout CI run `32806363124`: Ubuntu/Windows SUCCESS.

## 4. Non-negotiable data rules

- Preserve exact provider-native ticker text/case.
- Ticker text never proves instrument identity or historical continuity.
- Historical populations are PIT/observation-driven; current survivors are not projected backward.
- Current active/delisted state is not retrospective eligibility.
- Ambiguity is quarantined/excluded, never guessed.
- Acquisition/replay is restartable, checkpointed, deterministic, duplicate-safe, and auditable.
- No synthetic pre-2021 intraday bars from daily history.
- Finalized canonical data outranks provisional live observations.
- Data/model/authority transitions require explicit lineage and independent validation.
- Partial-run files do not establish an accepted operational baseline without the applicable handoff.

Accepted historical boundary:

- Alpaca raw SIP daily controlled extension: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- Ticker/intraday regime history origin: **2021-08-16**.
- Pre-2021 1h/4h remains absent rather than fabricated.

Accepted cumulative lineage:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

The cumulative foundation remains frozen at endpoint **2026-08-14**. Later current evidence extends it through explicit handoffs rather than rewriting that audit.

## 5. ML authority rules

Production ML emits raw `p_down`, `p_neutral`, `p_up`. Argmax is diagnostic only and never standalone trade authority. The accepted production model is immutable until a separate challenger/acceptance process replaces it.

Accepted production model:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 PIT predictors;
- holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

ML may inform deterministic evaluation but cannot independently choose trade direction, broker, order, or authority transition.

## 6. Strategy/research/AI rules

- Regime routing lives outside strategy implementations.
- Strategies emit deterministic evidence, not opaque conclusions.
- Expensive analogue/Monte Carlo/scenario/options/news work is promoted-candidate only.
- Zero-promotion/no-op states are valid; thresholds are not weakened after results.
- Phase11 accepted support remains **0 SUPPORTED**, 3 MIXED (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`), 5 UNSUPPORTED.
- Only historically SUPPORTED strategies may promote under current production authority.
- AI is independent audit only; it cannot rewrite accepted evidence, create a trade from a rejected case, create provider/order authority, or promote LIVE.

Phase23 proved the current-data/operator path works: 23 WARM/HOT directional cases were considered on 2026-08-21 and 0 promoted because the supported set is empty.

Phase24 challenged the strategy-evidence problem without weakening authority. Gate0 proved incumbent rules frequently fire on current routed cases. Gate1 locked a stronger v2 methodology. Gate2 evaluated 28 preregistered variants and produced **0 finalists** while protected evidence remained unread. Phase24 therefore has the accepted disposition **NO SUPPORT REPLACEMENT**.

Post-Gate2 forensics show:

- every challenger failed chronological-fold robustness, positive uncertainty LCB, and positive 25 bps stress mean;
- most had abundant observations, so generic sample scarcity is not the explanation;
- the best long trend variant retained only ~+7.37 bps mean after 10 bps cost with negative LCB/stress evidence;
- short trend/momentum/breakdown families were materially negative at the primary cost;
- symmetric mirrored LONG/SHORT architecture is not assumed valid;
- do not continue blind threshold tightening of the v1 rule families.

## 7. Geometry and portfolio-risk rules

Mandatory geometry:

- LONG: `stop < entry < target`;
- SHORT: `stop > entry > target`.

Accepted Phase13 risk envelope includes:

- risk at stop <= 0.5% current equity;
- single-name notional <= 10% current equity;
- liquidity/buying-power/account-state checks;
- exposure/concentration/correlation revalidation where applicable.

Geometry, sizing, and portfolio admission remain deterministic authority. AI cannot override them.

## 8. Provider/broker/execution authority architecture

### 8.1 Webull / Alpaca

Webull is primary PAPER/sandbox and future LIVE only after separate authority. Alpaca is manual secondary/fallback only. Broker switching is explicit; open state is reconciled first. Unknown mutation state fails closed; no blind retry or automatic failover.

### 8.2 Phase20

Policy fingerprint `b4f9bd37c3c425e182e4a0da255e8a903d95101d119c833c38c7fd2c0cd3741a`. Deterministic local orchestration only; no provider/broker mutation, scheduler/PostgreSQL/LIVE authority.

### 8.3 Phase21

Policy fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`. Every new real PAPER submit crosses one default-deny central seam. Exactly one raw `adapter.submit(plan)` remains under `packages/`, in `packages/execution/engine.py`. Merge: `ed9e156437e3924293b90f06620ebbe9534fab15`.

### 8.4 Phase22

Policy fingerprint `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`. PAPER/SANDBOX only; Webull default, Alpaca explicit manual selection; no arbitrary ticker/qty/price/geometry/LIVE inputs; exact Phase21 authority only for nonzero accepted cases. Merge: `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.

### 8.5 Phase23 — accepted current finalized analytical cycle

Policy fingerprint `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`.

- explicit prior finalized `as_of`;
- provider-free prepare;
- chronological advancement from latest accepted baseline;
- only `MASSIVE_MARKET_REFERENCE_READS` may be authorized when missing evidence requires them;
- no broker reads/writes;
- no provider mutations;
- no Phase21 submit / Phase22 execute;
- no scheduler/PostgreSQL/browser/LIVE/failover authority;
- local analytical writes are allowed and distinguished from external mutation;
- post-2026-08-14 Phase15 input requires exact Phase23 handoff.

Accepted target 2026-08-21:

- baseline 2026-08-14;
- sessions advanced 5;
- WARM/HOT directional cases 23;
- promoted 0;
- Phase12/13/14/Phase22-ready cases 0;
- broker/order/PAPER/LIVE writes 0;
- independent validation PASS;
- merge `2004338624766c42b5f4db2bb0976b2047a5c6b0`.

### 8.6 Phase24 — strategy evidence challenger

Authority remained local analytical only: no provider, broker, order, PAPER, LIVE, production-ML, or Phase11-support writes.

Accepted evidence:

- Gate0: 23 current cases, 92 route evaluations, 48 counterfactual incumbent fires, 21/23 cases with >=1 fire, authority zero, PASS.
- Gate1: exact 28-variant preregistration and stronger methodology, fingerprint `9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`.
- Gate2: 28 challengers, 0 basic-pass, 0 selections, 0 finalists, 0 protected reads, independent PASS.
- Exact target head: `f591942413973107d7abc9d21325623e2e7000f1`.
- Closeout head: `ba0721dd717ae8bdda877a376549cdef69ca00d9`.
- Closeout CI `32806363124`: Ubuntu/Windows SUCCESS.
- Disposition: **NO SUPPORT REPLACEMENT**.

### 8.7 LIVE

LIVE remains disabled. PAPER-provider acceptance does not imply LIVE acceptance. Any future LIVE phase must preregister limits, failure handling, reconciliation, explicit authorization, and negative paths independently.

## 9. Phase ledger

1. Phase1 — Foundation.
2. Phase2 — Provider ingestion foundation.
3. Phase3 — Canonical/session-aware data.
4. Phase4 — Instrument identity/history.
5. Phase5 — Live market state.
6. Phase6 — 33-feature engine.
7. Phase7 — PIT universe registry.
8. Phase8 — Broad discovery and hysteresis.
9. Phase9 — Market/sector/ticker regime engine.
10. Phase10 — ML probability/evaluation and production model acceptance.
11. Non-numbered historical extension/audit — controlled Alpaca raw-SIP daily extension to 2016 and cumulative lineage audit.
12. Phase11 — Strategy evaluation/regime routing/support policy.
13. Phase12 — Promoted-only deep candidate research.
14. Phase13 — Context/instrument/geometry/portfolio risk.
15. Phase14 — Independent AI audit/alerting.
16. Phase15 — Broker-neutral SHADOW/PAPER execution + outcome learning.
17. Phase16 — Browser control plane/production operations.
18. Phase17 — Provider-readonly operational readiness.
19. Phase18 — Webull sandbox PAPER mutation lifecycle certification.
20. Phase19 — Operations dashboard/PAPER-SHADOW observability.
21. Phase20 — Deterministic local run orchestration.
22. Phase21 — Unified PAPER execution authority.
23. Phase22 — Operational Webull-primary PAPER runner.
24. Phase23 — Operational current finalized analysis cycle — ACCEPTED/MERGED.
25. Phase24 — Strategy evidence challenger/support replacement research — **acceptance evidence complete; NO SUPPORT REPLACEMENT; merge pending**.

## 10. Key accepted evidence summary

### Phase19
- merge `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`;
- final CI `32739682576`: 932 tests both OS;
- provider/broker writes 0.

### Phase20
- final CI `32766072120`: 945 tests Ubuntu/Windows;
- merge `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.

### Phase21
- validator caught an actual direct-submit bypass before acceptance;
- final CI `32782618589` green;
- exactly one raw submit seam;
- merge `ed9e156437e3924293b90f06620ebbe9534fab15`.

### Phase22
- CI `32787337500`: 974 tests both OS;
- target zero-case prepare accepted;
- merge `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.

### Phase23
- first target execute exposed nullable persisted-state NaN defect and failed closed;
- repair head `803d43e43e8931f03ba836a23b781a7c3d3ee687`;
- repaired without threshold/support/model/risk/authority changes;
- successful 2026-08-21 target advanced 5 sessions, considered 23 current cases, promoted 0, zero downstream/execution activity, independent PASS;
- merge `2004338624766c42b5f4db2bb0976b2047a5c6b0`.

### Phase24
- Gate0 proved 21/23 current cases had incumbent rule activity if support was ignored diagnostically;
- Gate1 preregistered 28 bounded variants and stronger statistical/temporal/cost methodology;
- Gate2 produced 0 basic-pass variants and 0 finalists without touching protected evidence;
- forensics showed broad weak/unstable edge rather than simple sample scarcity;
- no support was replaced;
- closeout CI `32806363124` green on both OS.

## 11. Performance baseline

Post-Phase19 feature evidence:

- 50,000 rows / 7,454 symbols / 7 sessions;
- optimized batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x speedup;
- all 33 features exact parity.

## 12. Next-phase selection boundary

Phase24’s post-evidence audit found that historical support is not currently measured on the same population production promotion uses.

Historical support currently studies broad daily rows with broad market-regime routing. Production promotion requires a narrower chain:

`PIT universe -> broad discovery -> multi-timeframe scoring -> discovery hysteresis -> WARM/HOT directional qualification -> market/sector/ticker strategy route -> historical support -> current rule fire`

Sector is intentionally `UNAVAILABLE` in current production because no authoritative ticker-to-sector mapping is accepted; it must remain unavailable rather than fabricated. Market and ticker route compatibility still matter.

The next phase should therefore be defined as **Phase25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence**.

Initial Phase25 rules:

1. provider/broker/order/PAPER/LIVE/support authority remains zero;
2. replay begins no earlier than legitimate ticker/intraday history origin **2021-08-16**;
3. no synthetic pre-2021 1h/4h/ticker context;
4. reconstruct PIT universe/discovery/state/regime/routing semantics as production-faithfully as accepted evidence allows;
5. hold incumbent rules and three-session outcome fixed initially;
6. compare broad-population, discovery-conditioned, market-routed, ticker-routed, and rule-fired evidence as an attribution ladder;
7. validate the route-fidelity dataset/population independently before any support replacement;
8. do not reuse Phase24 failure metrics to loosen thresholds;
9. if route-fidelity evidence still lacks robust edge, separately preregister materially different signal families instead of more v1 threshold tweaks;
10. keep promoted-only deep research, independent Phase13/14, Phase21/22 PAPER authority, LIVE disablement, and no automatic failover intact.

Candidate later strategy families—only after route-fidelity evidence—include relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, and composite strategies. Existing empty repository scaffolds are not authority or evidence to activate them prematurely.

GUI can consume stable artifacts when scheduled, but the browser remains monitoring/control only. Scheduler and PostgreSQL runtime promotion remain separate future authority decisions.

## 13. Documentation/security/recovery

Every meaningful boundary synchronizes README, roadmap, current status, phase flow when stale, active phase spec, PR evidence, and configuration docs as applicable.

Tracked `.env.example` may contain public/default endpoints and blank secret placeholders. Never commit API secrets, passwords, security codes, raw broker IDs, tokens, or signed request metadata.

Recovery: inspect `main`, open PRs/branches/latest CI; read current status, this roadmap, Phase24, Phase23, Phase22, Phase21, and phase flow; preserve explicit authority boundaries; continue from section 12 rather than reopening accepted work without new evidence.
