# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. The legacy system remains preserved while ATLAS matures into a broad-market quantitative discovery, analysis, decision-support, learning, SHADOW/PAPER, and eventually separately authorized LIVE platform.

## Start here

1. [`docs/current_status.md`](docs/current_status.md)
2. [`docs/roadmap.md`](docs/roadmap.md)
3. [`docs/phase25_historical_production_path_route_fidelity.md`](docs/phase25_historical_production_path_route_fidelity.md)
4. [`docs/phase25_remaining_evidence.md`](docs/phase25_remaining_evidence.md)
5. [`docs/phase24_strategy_evidence_challenger.md`](docs/phase24_strategy_evidence_challenger.md)
6. [`docs/phase23_operational_current_analysis_cycle.md`](docs/phase23_operational_current_analysis_cycle.md)
7. [`docs/phase22_operational_paper_runner.md`](docs/phase22_operational_paper_runner.md)
8. [`docs/phase21_unified_paper_execution_authority.md`](docs/phase21_unified_paper_execution_authority.md)
9. [`docs/phase_flow.md`](docs/phase_flow.md)

Accepted `main` and the living documents control when older material conflicts.

## Architecture

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Massive is primary market/reference. Webull is primary PAPER/sandbox. Alpaca is manual secondary only. ML is probability evidence; AI is independent audit; browser is monitoring/control only.

## Development flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> FOCUSED TEST -> INDEPENDENT VALIDATE -> FULL CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Use cumulative research batches when adjacent gates can be preregistered together. Zero cases, promotions, selections, or finalists are valid outcomes. Never weaken evidence/risk/authority gates merely to create activity.

## Current state — 2026-08-26

- **Phases 1–25: ACCEPTED / MERGED.**
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950` through PR #27.
- Phase25 target code head `302bf6db5d807884f3b74cda049fc95864c5a194`; CI `32981080421` passed Ubuntu/Windows.
- Phase25 final docs head `f2d10465b71446b253b5d73a50845d2ea1e704d3`; CI `33025699177` passed Ubuntu/Windows.
- Phase25 decision: **NO SUPPORT REPLACEMENT — DEVELOPMENT ROBUSTNESS FAILED.**
- **Next: Phase26 — Materially Different Strategy Architecture Research.**

LIVE remains disabled and automatic broker failover remains disabled.

## Phase25 conclusion

Phase25 rebuilt the historical production path while holding the eight incumbent v1 rules and accepted three-session outcome fixed.

- exact active-only PIT historical reference lineage completed;
- 1,260 discovery replay sessions;
- 23,177 WARM/HOT directional rows;
- 15,283 fully route-eligible candidates;
- 61,132 eligible strategy-route decisions;
- 185,416 total route decisions;
- Gate8 legacy research-source route coverage 43,456 / 57,160 = 76.0252%;
- every non-empty incumbent had a negative 10 bps production-path mean and worsened versus broad evidence;
- Gate9 selected 0 strategies and produced 0 internal finalists;
- all eight failed the core chronology, mean/median, positive-rate, bootstrap-LCB, stress-cost, year, and regime robustness gates;
- Gate10 protected reads: 0;
- Gate11: `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`.

The population-fidelity mismatch was not hiding robust incumbent edge. Phase11 support remains authoritative: SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5.

## Phase26 direction

Phase26 will stop threshold-tuning the failed v1 families and investigate materially different architectures on a production-path-native research source.

The initial cumulative batch must:

- build exact research observations from accepted Phase25 PIT identities/context plus canonical 1d/4h/1h features and the accepted outcome;
- avoid the incomplete legacy Phase11/24 research table as primary input;
- preregister architecture families/search dimensions before target performance;
- retain 10 bps primary and 25 bps stress economics, chronological purge, session dependence handling, block bootstrap, year/regime robustness, concentration gates, and global multiplicity control;
- investigate cross-sectional relative strength, volatility/liquidity-conditioned mean reversion, gap continuation/reversal, volatility-normalized trend structures, multi-timeframe confirmation, and composite feature-block signals;
- design short-side candidates independently rather than mirroring long rules;
- keep protected/future prospective evidence separate;
- leave Phase11 support unchanged unless later evidence earns a separate replacement decision.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; no synthetic pre-2021 intraday history; finalized facts outrank provisional state; unknown/uncertain state fails closed; no automatic failover; PAPER does not imply LIVE; browser remains monitoring/control only.