# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-26.**

## Repository state

- **Phases 1–25 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950` through PR #27.
- Phase25 target-tested code head: `302bf6db5d807884f3b74cda049fc95864c5a194`; cumulative CI `32981080421` passed Ubuntu/Windows through Gate11 + full regression.
- Phase25 final docs head: `f2d10465b71446b253b5d73a50845d2ea1e704d3`; CI `33025699177` passed Ubuntu/Windows.
- Phase25 disposition: **NO SUPPORT REPLACEMENT — DEVELOPMENT ROBUSTNESS FAILED**.
- **Next: Phase26 — Materially Different Strategy Architecture Research.**

## Architecture lock

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> deep research/news -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary market/reference; Webull is primary PAPER/sandbox; Alpaca is manual secondary only. LIVE remains disabled and broker failover remains manual only.

## Non-negotiable evidence rules

- Preserve provider-native ticker case and exact PIT identity/populations.
- Ambiguity is quarantined rather than guessed.
- No synthetic pre-2021 intraday history.
- Finalized canonical facts outrank provisional state.
- ML is probability evidence only; AI is independent audit only.
- Unknown provider/broker/run state fails closed; uncertain mutations require reconciliation before retry.
- Zero cases, promotions, selections, and finalists are valid outcomes.
- Never weaken data, strategy, risk, or authority gates merely to create activity.

## Accepted model and strategy authority

- historical daily boundary: Alpaca through 2021-08-13; Massive from 2021-08-16.
- cumulative lineage: `6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`.
- production ML: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`.
- Phase11 support remains authoritative: SUPPORTED 0; MIXED `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`; all other current v1 strategies UNSUPPORTED.

## Phase25 accepted result

Phase25 resolved the population-fidelity question by reconstructing the historical production path without changing incumbent rules.

- exact active-only PIT reference lineage acquired for 1,253 sessions;
- Gate6 replay sessions: 1,260;
- WARM/HOT directional population: 23,177;
- Gate7 fully route-eligible candidates: 15,283;
- eligible route decisions: 61,132;
- total route decisions: 185,416;
- Gate8 legacy-source route coverage: 43,456 / 57,160 = 76.0252%;
- incumbent rule-fired rows: 24,753; candidates with >=1 fire: 10,521;
- every non-empty incumbent had a negative 10 bps production-path mean and worsened vs its broad comparator;
- Gate9 selected 0 strategies and produced 0 internal finalists; all eight failed core chronology, central-tendency, uncertainty, stress-cost, year, and regime robustness;
- Gate10 read zero protected evidence because there were zero finalists;
- Gate11 verdict: `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`;
- Phase11 support map unchanged.

Read `docs/phase25_historical_production_path_route_fidelity.md` and `docs/phase25_remaining_evidence.md` for full accepted evidence.

## Phase26 boundary

Phase26 must be research-only and production-path-native. Do not continue threshold tuning of the failed v1 families and do not use the incomplete legacy Phase11/24 research join as the primary source.

The initial Phase26 batch should:

1. construct an exact research table from accepted Phase25 Gate6/7 identities plus canonical 1d/4h/1h features and the accepted three-session outcome;
2. preregister materially different architectures before target performance is inspected;
3. retain 10 bps primary / 25 bps stress economics, temporal purge, session-level dependence handling, block bootstrap, year/regime robustness, concentration gates, and global multiplicity control;
4. investigate independent architectures such as cross-sectional relative strength, volatility/liquidity-conditioned mean reversion, gap continuation/reversal, volatility-normalized trend structures, multi-timeframe confirmation, and composite feature-block signals;
5. design short-side candidates independently rather than mirroring long rules;
6. keep protected/future prospective evidence separate and leave Phase11 support unchanged unless a later accepted replacement decision earns authority.

Use a cumulative implementation/test/evidence batch rather than serial gate-by-gate operator handoffs.