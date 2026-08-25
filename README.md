# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. The legacy system remains preserved while ATLAS matures into a broad-market quantitative discovery, analysis, decision-support, learning, SHADOW/PAPER, and eventually separately authorized LIVE platform.

## Start here

Read in this order for future continuation:

1. [`docs/current_status.md`](docs/current_status.md)
2. [`docs/roadmap.md`](docs/roadmap.md)
3. [`docs/phase24_strategy_evidence_challenger.md`](docs/phase24_strategy_evidence_challenger.md)
4. [`docs/phase23_operational_current_analysis_cycle.md`](docs/phase23_operational_current_analysis_cycle.md)
5. [`docs/phase22_operational_paper_runner.md`](docs/phase22_operational_paper_runner.md)
6. [`docs/phase21_unified_paper_execution_authority.md`](docs/phase21_unified_paper_execution_authority.md)
7. [`docs/phase_flow.md`](docs/phase_flow.md)
8. Older phase documents for provenance only.

Accepted `main` and the living documents control when older material conflicts.

## Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

- Parquet: durable analytical/history lake.
- DuckDB: analytical/query engine.
- PostgreSQL: future operational state; not an accepted runtime prerequisite.
- Massive: primary broad-market/reference provider.
- Webull: primary PAPER/sandbox broker; future LIVE only after separate authority.
- Alpaca: manually selectable secondary/fallback; never automatic failover.
- ML: PIT probability evidence only.
- Strategies/router: deterministic setup semantics and external regime routing.
- AI: independent audit only.
- Browser: monitoring/control plane only.

## Mandatory development flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Credentials, endpoints, connected accounts, passing tests, locally present artifacts, or registered jobs never silently expand provider, broker, strategy-support, automation, or LIVE authority.

## Current state — 2026-08-24

- **Phases 1–24: ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- **Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a` through PR #26.**
- Phase24 disposition: **NO SUPPORT REPLACEMENT**.
- Gate1 policy fingerprint: `9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`.
- Gate2 target head: `f591942413973107d7abc9d21325623e2e7000f1`.
- Final pre-merge living-doc head: `5ed3311d4ec1ac97cf841e160cf9c0987f731fe5`.
- Final pre-merge exact-head CI `32806726958`: Ubuntu/Windows SUCCESS; every validator through Phase24 Gate2 and full regression passed.

LIVE execution remains **DISABLED**. Automatic cross-broker failover remains **DISABLED**.

## Accepted analytical evidence

### Phase23

Finalized 2026-08-21 cycle from accepted 2026-08-14 baseline:

- sessions advanced: 5;
- WARM/HOT directional cases: 23;
- promoted candidates: 0;
- Phase12/13/14 cases: 0 / 0 / 0;
- Phase22-ready execution cases: 0;
- broker/order/PAPER/LIVE activity: 0;
- independent validation: PASS.

### Phase24

Gate0 showed the current rules are not dormant:

- 23 current WARM/HOT directional cases;
- 92 route-eligible incumbent evaluations;
- 48 counterfactual incumbent rule fires;
- 21/23 cases with at least one fire;
- authoritative promotions 0;
- all provider/broker/order/PAPER/LIVE/support writes 0.

Gate1 then preregistered exactly 28 bounded challengers and a stronger evidence framework before observing challenger performance: chronological selection/internal validation, purge, session-level dependence handling, six-session block bootstrap, 10 bps primary and 25 bps stress costs, uncertainty/year/regime gates, multiplicity control, and zero protected-read/support-replacement authority.

Gate2 result:

- challengers: 28;
- basic-pass: 0;
- selections/finalists: 0;
- protected reads: 0;
- provider/broker/order/PAPER/LIVE/support writes: 0;
- independent validation: PASS.

Post-run forensics showed every challenger failed chronological-fold robustness, positive block-bootstrap LCB, and positive 25 bps stress mean. Most had abundant observations. The best long trend variant retained only about +7.37 bps mean after the 10 bps primary cost but still had a negative LCB and negative stress mean. Short trend/momentum/breakdown rules were materially negative even at the primary cost.

**Accepted conclusion: no Phase24 strategy replaces Phase11 support.** Phase11 remains SUPPORTED 0; MIXED 3 (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`); UNSUPPORTED 5.

## Next analytical boundary

The post-Phase24 audit found a population-fidelity mismatch: historical Phase11/24 support studies use broad daily rows plus broad market-regime routing, while production promotion occurs only after WARM/HOT discovery qualification, discovery direction, and fuller market/ticker strategy routing.

The next numbered phase should therefore be **Phase25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence**. Initial work must:

- remain provider/broker/order/PAPER/LIVE/support-authority free;
- begin no earlier than the legitimate intraday/ticker-regime origin **2021-08-16**;
- never fabricate pre-2021 intraday context;
- reconstruct PIT universe -> discovery foundation -> multi-timeframe scoring -> hysteresis -> WARM/HOT direction -> market/ticker routing;
- keep sector `UNAVAILABLE` unless authoritative historical sector mapping exists;
- initially hold incumbent rules and the three-session outcome fixed;
- independently validate the reconstructed population before any support replacement.

If route-fidelity conditioning still produces no robust edge, later separately preregistered research should investigate materially different strategy architectures such as relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, or composite signals rather than further v1 threshold tightening.

## Accepted data/model foundation

- Alpaca raw SIP daily controlled authority: 2016-01-04 through 2021-08-13.
- Massive authority: 2021-08-16 onward.
- No synthetic pre-2021 1h/4h history.
- Cumulative lineage: `6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`.
- Production ML: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`; HGB leaf15/iter100; 33 predictors; exact accepted replay.

## Non-negotiable rules

Preserve provider-native ticker case; PIT populations only; quarantine ambiguity; no fabricated intraday history; finalized facts outrank provisional live state; ML/AI never create trade authority; LONG `stop < entry < target`, SHORT reverse; uncertain mutation state requires reconciliation; no automatic failover; PAPER does not imply LIVE; zero-case/no-promotion/no-finalist outcomes are valid; never lower evidence/risk/authority gates merely to create trades.

## Security

Tracked `.env.example` is non-secret. Never commit or expose API secrets, passwords, security codes, raw broker IDs, tokens, or signed request metadata. Real `.env` remains local/ignored.
