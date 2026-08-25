# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-24.**

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
- Phase21 merge: `ed9e156437e3924293b90f06620ebbe9534fab15`.
- Phase22 merge: `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- **Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a` through PR #26.**
- Phase24 disposition: **NO SUPPORT REPLACEMENT**.
- Gate1 fingerprint: `9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`.
- Gate2 target head: `f591942413973107d7abc9d21325623e2e7000f1`.
- Final pre-merge living-doc head: `5ed3311d4ec1ac97cf841e160cf9c0987f731fe5`.
- Final pre-merge CI `32806726958`: Ubuntu/Windows SUCCESS; all validators through Phase24 Gate2 and full regression passed.

LIVE is **DISABLED**. Automatic broker failover is **DISABLED**.

## 3. Architecture lock

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/Monte Carlo/scenarios -> news/events -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

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
- Automatic cross-broker failover is forbidden.
- PAPER does not imply LIVE.
- Zero-promotion, zero-case, and zero-finalist states are valid.
- Never weaken strategy/data/risk/authority gates merely to produce activity.

## 5. Accepted data/model evidence

- Alpaca raw SIP daily controlled authority: **2016-01-04 through 2021-08-13**.
- Massive authority and legitimate ticker/intraday history origin: **2021-08-16**.
- Cumulative lineage: `6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`.
- Production ML: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`; HGB leaf15/iter100; 33 PIT predictors; exact accepted replay.

Accepted Phase11 strategy support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

## 6. Accepted execution/control foundation

### Phase15
Broker-neutral SHADOW/PAPER execution with fresh quote/preflight, reconciliation, current-risk revalidation, protective geometry, deterministic IDs/idempotency, fail-closed uncertainty, Webull primary, Alpaca manual secondary, LIVE disabled. Post-2026-08-14 input requires exact Phase23 handoff.

### Phase16–19
Loopback browser control plane, audit/idempotency/recovery, explicit broker-switch/cleanup planning, dual-broker read-only reconciliation, accepted Phase18 Webull sandbox submit/reconcile/cancel lifecycle, local observability. Do not repeat Phase18 mutation merely to reconfirm it.

### Phase20
Deterministic local orchestration only: immutable DAG/run identity, bounded local retry, atomic manifest/journal, fail-closed leases/resume. No provider/broker/scheduler/PostgreSQL/LIVE authority.

### Phase21
Policy fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`. Every new real PAPER submit crosses `ExecutionEngine.submit_authorized_plan(...)`; exactly one raw `adapter.submit(plan)` exists under `packages/`.

### Phase22
Policy fingerprint `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`. Routine Webull-primary PAPER operator, Alpaca manual only, no arbitrary trade inputs, exact authority only for accepted nonzero cases. Accepted zero-case prepare returned `PREPARED_ZERO_PROVIDER_CALLS`.

### Phase23
Policy fingerprint `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`. Finalized-session analytical operator; provider-free prepare; only `MASSIVE_MARKET_REFERENCE_READS` may be authorized when missing; no broker/PAPER execution.

## 7. Phase23 accepted target result

Finalized 2026-08-21 from baseline 2026-08-14:

- sessions advanced: 5;
- WARM/HOT directional cases: 23;
- promotions: 0;
- Phase12/13/14: 0 / 0 / 0;
- execution cases: 0;
- broker/order/PAPER/LIVE activity: 0;
- independent validation: PASS;
- run scope: `a9f398fcd32e302af125bcf9d81789efadb417da879ff178942880580ab69209`.

## 8. Phase24 accepted result — NO SUPPORT REPLACEMENT

Read `docs/phase24_strategy_evidence_challenger.md` for complete evidence.

### Gate0

- 23 accepted current WARM/HOT directional cases;
- 92 eligible incumbent route evaluations;
- 48 counterfactual incumbent rule fires;
- 21/23 cases with >=1 fire;
- promotions/support/external/execution writes: 0;
- PASS.

This proved the current setup rules are not dormant.

### Gate1

Before challenger results were observed, exactly 28 bounded variants and the stronger methodology were locked: chronological selection/internal validation, purge, session-level dependence handling, block bootstrap, 10/25 bps costs, distribution/uncertainty/year/regime gates, multiplicity control, maximum one finalist per family/direction, and zero protected-read/support-replacement authority.

### Gate2

Target-machine result on `f591942413973107d7abc9d21325623e2e7000f1`:

- challengers 28;
- basic-pass 0;
- multiplicity-pass 0;
- selections/finalists 0;
- protected reads 0;
- provider/broker/order/PAPER/LIVE/support writes 0;
- independent validation PASS;
- overall PASS.

Forensics showed all 28 failed positive chronological folds, positive bootstrap LCB, and positive 25 bps stress mean. Most had abundant samples. Best long trend retained only ~+7.37 bps after 10 bps cost with negative LCB/stress; short trend/momentum/breakdown remained materially negative at 10 bps.

Accepted decision: **Phase11 remains production support authority unchanged. No Gate3 protected evaluation occurred.**

## 9. Exact continuation — Phase25 definition boundary

The Phase24 post-evidence audit found a population-fidelity mismatch:

- historical support studies use broad daily rows with broad market-regime routing;
- production promotion requires PIT universe -> discovery -> WARM/HOT directional qualification -> market/sector/ticker route -> support -> current rule fire.

Historical support is therefore not yet measured on the same population ATLAS tries to trade.

### Define next

**Phase25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence** should be defined and locked next.

Initial contract should:

1. remain provider/broker/order/PAPER/LIVE/support-authority free;
2. begin no earlier than legitimate intraday/ticker-regime origin **2021-08-16**;
3. reconstruct PIT universe, 1d/4h/1h discovery foundation/scoring, hysteresis, WARM/HOT direction, market/ticker strategy routing;
4. keep sector `UNAVAILABLE` unless authoritative historical sector mapping exists;
5. initially hold incumbent strategy rules and the three-session outcome fixed;
6. produce an attribution ladder from broad population to production-route-conditioned population;
7. independently validate the replay population before any support replacement;
8. never use Phase24 failure results to loosen thresholds.

If route-fidelity evidence still lacks robust edge, later strategy research should use a separately preregistered materially different family—relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, or composite—rather than more v1 threshold tweaks.

GUI remains monitoring/control only. Scheduler and PostgreSQL promotion remain separate future decisions.

## 10. Performance baseline

Post-Phase19 retained feature evidence: 50,000 rows / 7,454 symbols / 7 sessions; optimized ~4.00265s vs prior ~594.58s; ~148.5x speedup; all 33 features exact parity.

## 11. Security/recovery

Never commit secrets, raw broker IDs, tokens, signed metadata, passwords, or security codes. Future startup: inspect `main`, open PRs/branches/latest CI; read current status, roadmap, Phase24, Phase23, Phase22/21, and phase flow; continue from section 9 rather than reopening accepted work or weakening evidence gates.
