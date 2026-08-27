# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. The legacy system remains preserved while ATLAS matures into a broad-market quantitative discovery, analysis, decision-support, learning, SHADOW/PAPER, and eventually separately authorized LIVE platform.

## Start here

Read in this order for future continuation:

1. [`docs/current_status.md`](docs/current_status.md)
2. [`docs/roadmap.md`](docs/roadmap.md)
3. [`docs/phase25_historical_production_path_route_fidelity.md`](docs/phase25_historical_production_path_route_fidelity.md)
4. [`docs/phase25_remaining_evidence.md`](docs/phase25_remaining_evidence.md)
5. [`docs/phase24_strategy_evidence_challenger.md`](docs/phase24_strategy_evidence_challenger.md)
6. [`docs/phase23_operational_current_analysis_cycle.md`](docs/phase23_operational_current_analysis_cycle.md)
7. [`docs/phase22_operational_paper_runner.md`](docs/phase22_operational_paper_runner.md)
8. [`docs/phase21_unified_paper_execution_authority.md`](docs/phase21_unified_paper_execution_authority.md)
9. [`docs/phase_flow.md`](docs/phase_flow.md)
10. Older phase documents for provenance only.

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

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Use the largest safe coherent batch. Adjacent research gates may be implemented and run cumulatively when thresholds/authority are frozen in advance. Credentials, endpoints, connected accounts, passing tests, locally present artifacts, or registered jobs never silently expand provider, broker, strategy-support, automation, or LIVE authority.

## Current state — 2026-08-26

- **Phases 1–24: ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a` through PR #26.
- **Phase25: VALIDATED / MERGE PENDING through PR #27.**
- Phase25 final target-tested code head: `302bf6db5d807884f3b74cda049fc95864c5a194`.
- Phase25 exact-head CI `32981080421`: Ubuntu/Windows SUCCESS; every validator through Gate11 and full regression passed.
- Phase25 disposition: **NO SUPPORT REPLACEMENT — DEVELOPMENT ROBUSTNESS FAILED**.

LIVE execution remains **DISABLED**. Automatic cross-broker failover remains **DISABLED**.

## Phase25 result

Phase25 rebuilt the historical production path instead of changing the incumbent rules.

Accepted reconstruction evidence:

- exact active-only PIT reference lineage acquired for all missing sessions;
- Gate6 replay sessions: 1,260;
- WARM/HOT directional population: 23,177;
- Gate7 fully route-eligible candidates: 15,283;
- eligible strategy-route decisions: 61,132;
- total route decisions: 185,416;
- exact PIT ticker intervals: 9,609;
- independent validation PASS.

Cumulative Gates8–11 then held the eight incumbent v1 rules and accepted three-session outcome fixed:

- legacy research-source route coverage: 43,456 / 57,160 = 76.0252%;
- development incumbent signal rows: 24,753;
- candidates with >=1 incumbent fire: 10,521;
- every non-empty incumbent had a negative 10 bps production-path mean and worsened vs its broad comparator;
- Gate9 selections: 0;
- internal finalists: 0;
- every incumbent failed positive folds, mean, median, positive-rate, bootstrap-LCB, 25 bps stress, year robustness, and regime robustness;
- Gate10 protected evidence reads: 0 because there were zero finalists;
- Gate11 verdict: `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`;
- Phase11 support unchanged.

The route-fidelity hypothesis is therefore resolved: **the old research-population mismatch was not hiding robust edge in the incumbent strategies.**

## Strategy authority

Accepted Phase11 support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Do not lower Phase24/25 thresholds or keep tightening the same v1 families merely to create activity.

## Next analytical boundary

After Phase25 merge, define **Phase26 — Materially Different Strategy Architecture Research**.

Phase26 should:

- remain research-only with zero provider/broker/order/PAPER/LIVE/support authority;
- use the accepted Phase25 PIT production-path lineage as the primary research population;
- avoid the incomplete legacy Phase11/24 research join as primary input;
- preregister materially different architecture families/search dimensions before target performance inspection;
- retain realistic costs, temporal purge, session-level dependence handling, block bootstrap, year/regime robustness, concentration gates, and multiplicity control;
- investigate cross-sectional relative strength, volatility/liquidity-conditioned mean reversion, gap/event continuation/reversal, volatility-normalized trend/breakout, multi-timeframe confirmation, and composite feature-block signals;
- design short strategies independently rather than mirroring long rules;
- preserve separate protected/future prospective evidence boundaries;
- leave Phase11 support authoritative unless a later phase earns replacement.

## Accepted data/model foundation

- Alpaca raw SIP daily controlled authority: 2016-01-04 through 2021-08-13.
- Massive authority: 2021-08-16 onward.
- no synthetic pre-2021 1h/4h history.
- cumulative lineage: `6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`.
- production ML: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`; HGB leaf15/iter100; 33 predictors; exact accepted replay.

## Non-negotiable rules

Preserve provider-native ticker case; PIT populations only; quarantine ambiguity; no fabricated intraday history; finalized facts outrank provisional live state; ML/AI never create trade authority; LONG `stop < entry < target`, SHORT reverse; uncertain mutation state requires reconciliation; no automatic failover; PAPER does not imply LIVE; zero-case/no-promotion/no-selection/no-finalist outcomes are valid; never lower evidence/risk/authority gates merely to create trades.

## Security

Tracked `.env.example` is non-secret. Never commit or expose API secrets, passwords, security codes, raw broker IDs, tokens, or signed request metadata. Real `.env` remains local/ignored.