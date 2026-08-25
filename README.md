# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield redesign/successor path for Chart Monitor. The legacy system remains preserved while ATLAS matures into a broad-market quantitative discovery, analysis, decision-support, learning, SHADOW/PAPER, and eventually separately authorized LIVE platform.

## Start here

For a future development session, read in this order:

1. [`docs/current_status.md`](docs/current_status.md) — exact continuation and current authority boundary.
2. [`docs/roadmap.md`](docs/roadmap.md) — long-term architecture, phase ledger, and non-negotiable rules.
3. [`docs/phase24_strategy_evidence_challenger.md`](docs/phase24_strategy_evidence_challenger.md) — Phase24 evidence, no-replacement decision, and next analytical finding.
4. [`docs/phase23_operational_current_analysis_cycle.md`](docs/phase23_operational_current_analysis_cycle.md) — accepted current finalized-session analytical operator.
5. [`docs/phase22_operational_paper_runner.md`](docs/phase22_operational_paper_runner.md) — accepted routine Webull-primary PAPER operator.
6. [`docs/phase21_unified_paper_execution_authority.md`](docs/phase21_unified_paper_execution_authority.md) — accepted centralized PAPER-submit authority.
7. [`docs/phase_flow.md`](docs/phase_flow.md) — mandatory development/acceptance flow.
8. Older phase documents for provenance only.

Accepted `main` and the living documents control when older documents conflict.

## Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Core roles:

- **Parquet** — durable analytical/history lake.
- **DuckDB** — analytical/query engine.
- **PostgreSQL** — future persistent operational state; not an accepted runtime prerequisite.
- **Massive** — primary broad-market/reference provider.
- **Webull** — primary PAPER/sandbox execution broker; future LIVE only after separate authority.
- **Alpaca** — manually selectable secondary/fallback; never automatic failover.
- **ML** — point-in-time `p_down/p_neutral/p_up` evidence, never standalone trade authority.
- **Strategies/router** — deterministic setup semantics and external regime routing.
- **Deep research** — promoted-candidate-only analogue/scenario/options/news work.
- **AI** — independent audit/reviewer only.
- **Browser** — monitoring/control plane only; never execution authority.
- **Phase20** — deterministic local orchestration only; no provider/broker/scheduler/LIVE authority.
- **Phase21** — centralized default-deny authority for every new real PAPER provider submit.
- **Phase22** — routine Webull-primary PAPER operator over accepted Phase15 + Phase21 authority.
- **Phase23** — accepted finalized-session analytical cycle with provider-free prepare and narrowly scoped Massive market/reference reads only when missing.
- **Phase24** — preregistered strategy-evidence challenger research; accepted evidence currently supports **NO SUPPORT REPLACEMENT**.

## Strategic anti-drift anchor

The destination remains the complete operational evidence chain: **broad-market discovery -> deterministic analysis/risk -> independent AI review -> safe Webull-primary SHADOW/PAPER execution -> exact reconciliation -> observability -> outcome learning**, before any separately authorized LIVE transition.

Infrastructure is a means to that system. Scheduler, PostgreSQL, browser, or other infrastructure work must not silently displace the end-to-end PAPER/SHADOW objective.

## Mandatory development flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Credentials, endpoints, connected accounts, passing tests, locally present artifacts, or registered jobs never silently expand provider, broker, automation, support, or LIVE authority.

## Current state — 2026-08-24

- **Phases 1–23: ACCEPTED / MERGED.**
- Phase23 PR #25 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- **Phase24: acceptance evidence complete / NO SUPPORT REPLACEMENT / PR #26 merge pending.**
- Phase24 Gate1 policy fingerprint: `9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`.
- Phase24 Gate2 target head: `f591942413973107d7abc9d21325623e2e7000f1`.
- Phase24 closeout evidence head: `ba0721dd717ae8bdda877a376549cdef69ca00d9`.
- Closeout CI run `32806363124`: Ubuntu/Windows SUCCESS; every validator through Phase24 Gate2 and the full regression suite passed.

LIVE execution remains **DISABLED**. Automatic cross-broker failover remains **DISABLED**.

## Phase23 accepted current-cycle evidence

ATLAS successfully advanced finalized market evidence through **2026-08-21** from the accepted **2026-08-14** baseline:

- sessions advanced: **5** — Aug 17–21;
- WARM/HOT directional cases: **23**;
- promoted candidates: **0**;
- Phase12 research / Phase13 cases / Phase14 AI reviews: **0 / 0 / 0**;
- Phase22-ready execution cases: **0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- independent persisted validation: **PASS**.

Zero promotion was correct because accepted Phase11 contained no SUPPORTED strategy.

## Phase24 accepted evidence — no support replacement

### Gate0 current-case diagnostic

Provider-free target evidence on the accepted 2026-08-21 population showed:

- current WARM/HOT directional cases: **23**;
- route-eligible incumbent evaluations: **92**;
- counterfactual incumbent rule fires: **48**;
- candidates with at least one incumbent rule fire: **21 / 23**;
- authoritative promotions: **0**;
- provider/broker/order/PAPER/LIVE/support writes: **0**;
- PASS.

Therefore the incumbent setup logic is not dormant. Historical support is the blocking authority.

### Gate1 preregistration

Before challenger performance was observed, Phase24 locked exactly **28** bounded v2 variants and a stronger evidence framework: chronological selection/internal validation, three-session purge, session-level dependence handling, six-session block bootstrap, 10 bps primary / 25 bps stress costs, mean/median/positive-rate/LCB requirements, year/regime robustness, and Holm-Bonferroni multiplicity control. Protected evidence was unavailable to Gate1/2.

### Gate2 development-only result

Target run on exact head `f591942413973107d7abc9d21325623e2e7000f1`:

- challengers: **28**;
- basic-pass: **0**;
- multiplicity-pass: **0**;
- frozen selections: **0**;
- fresh finalists: **0**;
- protected evidence reads: **0**;
- provider/broker/order/PAPER/LIVE/support writes: **0**;
- independent validation: **PASS**;
- overall: **PASS**.

No Gate3 protected evaluation is authorized because no finalist earned access.

Post-run forensic analysis showed the dominant failures were not lack of observations: all 28 challengers failed chronological-fold, positive block-bootstrap LCB, and positive 25 bps stress gates. The best long trend variants retained only about +7 bps mean after the 10 bps primary cost but still had negative uncertainty lower bounds and negative 25 bps stress means. Short trend/momentum/breakdown rules were materially negative even at the 10 bps primary cost.

**Phase24 disposition: NO SUPPORT REPLACEMENT.** Phase11 remains authoritative: SUPPORTED 0; MIXED 3 (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`); UNSUPPORTED 5.

## Next analytical boundary

The Phase24 post-evidence audit found a more fundamental methodological issue to investigate before generating more indicator thresholds: historical support studies evaluate rules over a broad market-regime-routed daily population, while production promotion is reached only after WARM/HOT discovery qualification, discovery direction, and fuller market/ticker route compatibility.

The next numbered phase should therefore be defined around **historical production-path replay / route-fidelity strategy evidence**, beginning no earlier than the legitimate intraday/ticker-regime origin **2021-08-16**. It should initially keep incumbent rules and the three-session outcome fixed and change only the historical population/routing. No pre-2021 intraday context may be fabricated.

If route-fidelity conditioning still yields no robust edge, later strategy research should move to materially different families—relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, or composite—rather than further threshold tightening of v1.

## Accepted data/model foundation

Historical provider boundary:

- Alpaca raw SIP daily controlled authority: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- No synthetic pre-2021 1h/4h history.

Accepted cumulative lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Accepted production ML:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 PIT predictors;
- protected holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

## Non-negotiable rules

- Preserve exact provider-native ticker text/case; ticker text never proves identity continuity.
- Historical populations remain point-in-time; ambiguity is quarantined, never guessed.
- No synthetic unavailable intraday history.
- Finalized canonical facts outrank provisional live observations.
- ML is evidence, not trade authority; AI is independent audit only.
- LONG: `stop < entry < target`; SHORT: reverse.
- Unknown broker/provider/run state fails closed; uncertain writes are never retried blindly.
- Automatic broker failover is forbidden.
- PAPER does not imply LIVE.
- Zero-case/no-promotion/no-finalist results are valid and must not be bypassed.
- Never lower data, strategy, risk, provider, or authority thresholds simply to create trades.

## Environment/security

Tracked `.env.example` is non-secret. Never commit or expose API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata. Real `.env` remains local/ignored.
