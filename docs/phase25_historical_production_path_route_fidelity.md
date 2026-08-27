# Phase 25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence

**Status: VALIDATED / MERGE PENDING — NO SUPPORT REPLACEMENT**

Upstream authority: Phase24 merge `15b77321d4815f9f52fe74d47ba32fee8127526a`; Phase25 branch `phase-25-historical-production-path-route-fidelity`; final target-tested code head `302bf6db5d807884f3b74cda049fc95864c5a194`.

## Purpose

Phase25 tested whether the poor Phase11/24 incumbent-strategy evidence was mainly an artifact of studying the wrong historical population. The production path is narrower than the old research population:

`PIT universe -> 1d/4h/1h discovery -> hysteresis -> WARM/HOT direction -> market/ticker route -> strategy rule`

The experiment held the eight incumbent v1 rules and the accepted three-session directional-return outcome fixed. Population and routing fidelity were the independent variables. Sector remained `UNAVAILABLE`/nonblocking because no authoritative PIT sector mapping is accepted.

## Final conclusion

**Production-path fidelity does not rescue the incumbent strategies. Phase11 support remains unchanged: SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5.**

On the development interval, every non-empty incumbent had a negative 10 bps production-path mean and every incumbent failed the core preregistered robustness gates. No strategy reached selection, internal validation, or protected confirmation. The accepted protected period was therefore not read in Gate10.

The next research phase must investigate materially different strategy architectures rather than relax evidence thresholds or continue threshold tweaks of the same v1 families.

## Accepted evidence sequence

### Gate0 — local feasibility inventory

- replay origin: 2021-08-16;
- replay sessions: 1,260;
- canonical 1d, derived 4h/1h, feature triplets: 1,260/1,260;
- market daily feature lineage from 2016-01-04: 2,674/2,674;
- exact PIT reference/universe coverage initially only 7/1,260;
- 1,253 sessions blocked by missing PIT reference/universe lineage;
- all provider/broker/execution/support authority zero;
- PASS.

### Gate1 — PIT reference scope proof

- canonical distinct symbols: 20,722;
- canonical symbol-session rows: 13,918,673;
- symbols without exact first-seen reference: 11,329;
- distinct first-seen gap dates: 1,232;
- future-only local reference symbols: 8,449;
- ambiguous local identity symbols: 2,400;
- provider/broker/execution/support authority zero;
- PASS.

Conclusion: the gap was broad; backward-carry of future metadata or tiny first-seen patching was not authoritative.

### Gate2 — active-only PIT equivalence

Across all seven dates with full reference + accepted Phase7 universe evidence:

- full reference rows: 246,631;
- active rows: 89,755;
- inactive rows removable: 156,876;
- row reduction: 63.61%;
- full vs active-only discovery mismatch: 0 on every date;
- active-only vs accepted Phase7 mismatch: 0 on every date;
- PASS.

Conclusion: exact same-session `active=true` PIT reference data are sufficient for this discovery-only replay.

### Gate3 — acquisition preregistration

- frozen acquisition sessions: 1,253;
- earliest entitlement probe: 2021-08-17;
- locked Massive query: `/v3/reference/tickers`, `market=stocks`, `active=true`, exact date, ascending ticker, `limit=1000`;
- projected pages/session: 12–14;
- projected provider page requests: 15,036–17,542;
- provider authority still zero;
- PASS.

### Gate4 — single-session Massive entitlement probe

Accepted target result for 2021-08-17:

- provider probe sessions: 1;
- 12 provider page reads;
- persisted active rows/instruments: 11,027 / 11,027;
- independent validation: PASS;
- broker/order/PAPER/LIVE/support activity: zero.

### Gate5 — resumable exact PIT bulk acquisition

Accepted target result:

- frozen bulk sessions after probe: 1,252;
- newly acquired: 1,252;
- remaining: 0;
- successful provider page reads: 15,430;
- probe re-fetches: 0;
- provider writes: 0;
- broker/order/PAPER/LIVE/support activity: zero;
- independent validation: PASS.

Read-only acquisition used authorization mode `EXPLICIT_CLI_SUBCOMMAND`: the explicit `acquire` command itself authorized the bounded provider-read scope, with no pasted confirmation required. Stronger confirmation rules remain for mutations/trading/destructive actions.

### Gate6 — chronological Phase7 + discovery reconstruction

The first target attempt correctly exposed a late preflight/overwrite hazard at the accepted 2026-08-14 discovery boundary. The repaired Gate6 preflights existing artifacts before any builder and permits reconciliation only when scorer-facing data are semantically identical.

Accepted repaired target result:

- replay sessions: 1,260;
- existing artifacts preserved: universe 1,260; foundation 1,260; score 1,260;
- reconciliation events: 1;
- effective state rows: HOT 16,517; WARM 16,731; WATCH 1,554,664; NORMAL 7,331,390;
- WARM/HOT directional population: 23,177;
- bullish: 16,079; bearish: 7,098;
- provider reads/writes: 0/0;
- operational discovery writes: 0;
- independent validation: PASS.

### Gate7 — exact PIT market/ticker route reconstruction

Accepted target result:

- Gate6 WARM/HOT directional rows: 23,177;
- exact PIT ticker intervals: 9,609;
- ticker raw/persisted history: 5,392,759 / 5,392,759;
- route decisions: 185,416;
- market-compatible candidates: 17,285;
- ticker-compatible / fully route-eligible candidates: 15,283;
- eligible strategy-route decisions: 61,132;
- sector: `UNAVAILABLE` / nonblocking;
- provider/broker/execution/support authority zero;
- independent validation: PASS.

### Gates8–11 — cumulative strategy evidence

Gates8–11 were implemented/preregistered together before target strategy-return evidence was inspected. Exact target-tested head: `302bf6db5d807884f3b74cda049fc95864c5a194`. Exact-head CI run `32981080421`: Ubuntu and Windows SUCCESS; all validators through Gate11 and full regression passed.

#### Gate8 — development-only attribution

- route rows matched to accepted legacy research source: 43,456 / 57,160;
- legacy-source route coverage: 76.0252%;
- development rule-fired signal rows: 24,753;
- candidates with at least one fire: 10,521;
- protected evidence unread.

10 bps broad vs production-path mean:

| Strategy | Broad | Production path | Delta |
|---|---:|---:|---:|
| breakdown_short_v1 | -0.004272 | -0.011314 | -0.007042 |
| breakout_long_v1 | -0.000684 | -0.017605 | -0.016921 |
| momentum_long_v1 | -0.000537 | -0.015455 | -0.014918 |
| momentum_short_v1 | -0.002665 | -0.012069 | -0.009404 |
| pullback_long_v1 | -0.000207 | no production fires | n/a |
| pullback_short_v1 | -0.001467 | no production fires | n/a |
| trend_following_long_v1 | -0.000424 | -0.013482 | -0.013058 |
| trend_following_short_v1 | -0.002891 | -0.011394 | -0.008502 |

All non-empty production-path incumbents worsened materially relative to the broad comparator. The incomplete legacy-source join is retained as a limitation of the comparator, but it does not create positive incumbent evidence.

#### Gate9 — preregistered robustness/internal validation

Selected after development + global Holm: **0**. Finalists after internal validation: **0**.

Failure counts across the eight incumbents:

- positive chronological folds: 8/8 failed;
- primary mean > 0: 8/8 failed;
- primary median > 0: 8/8 failed;
- positive rate >= 50%: 8/8 failed;
- block-bootstrap LCB > 0: 8/8 failed;
- 25 bps stress mean > 0: 8/8 failed;
- year robustness: 8/8 failed;
- regime robustness: 8/8 failed;
- min raw rows: 2/8 failed (pullbacks);
- min signal sessions: 2/8 failed (pullbacks);
- session concentration: 2/8 failed (pullbacks).

Global Holm-Bonferroni across all eight incumbents selected none.

#### Gate10 — protected confirmation

- disposition: `SKIPPED_ZERO_FINALISTS`;
- protected evidence reads: 0;
- confirmed strategies: 0;
- independent validation: PASS.

#### Gate11 — cumulative closeout

- verdict: `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`;
- next boundary: `TARGET_DEVELOPMENT_FAILURE_MODES_OR_NEW_STRATEGY_ARCHITECTURES`;
- Phase11 support map unchanged: true;
- provider reads/writes performed by Gates8–11: 0/0;
- broker/order/PAPER/LIVE writes: 0/0/0/0;
- Phase11 support writes: 0;
- independent validation: PASS;
- cumulative PASS.

## Historical contract statements retained after closeout

These statements remain part of the accepted Gate0–Gate5 evidence contract even though Phase25 is now complete:

- Gate0 permits no provider reads or writes, and pre-2021 1h/4h or ticker-regime context may not be synthesized.
- The original Gate0 inventory had exact PIT reference pairs: 7 / 1,260, with 1,253 blocked sessions.
- Future-only reference observations may be measured but never treated as PIT authority.
- Gate2 does not grant provider-read authority.
- Gate3 does not grant provider-read authority.
- Gate4 was the separate one-session entitlement probe; bulk acquisition remained disabled at that boundary.
- Gate5 subsequently authorized only the frozen read-only acquisition scope under `EXPLICIT_CLI_SUBCOMMAND`, with no pasted confirmation.

## Interpretation

Phase25 resolved the population-fidelity question. The old broad research population was not the main reason incumbents failed. When conditioned on the reconstructed production path, the existing rules were not merely noisy; every non-empty strategy had a materially negative net mean and failed temporal, distributional, uncertainty, cost-stress, year, and regime robustness.

Do not:

- relax Phase24/25 thresholds;
- read protected evidence for losing incumbents;
- promote any incumbent;
- reinterpret no-selection as a software failure;
- continue blind threshold tightening of the same rule families.

The 76% Gate8 join also means future strategy research should avoid depending on the legacy Phase11/24 broad research table as its primary population source. New research should derive observations directly from the accepted PIT production-path lineage and canonical features/returns.

## Next phase boundary

Define **Phase26 — Materially Different Strategy Architecture Research**.

Phase26 should remain research-only and production-path-native. Candidate families should be structurally different from the failed v1 threshold rules, for example:

- cross-sectional / sector-neutral relative strength;
- mean reversion conditioned on volatility/liquidity/regime;
- gap/event continuation or reversal;
- volatility-normalized trend/breakout structures;
- multi-timeframe confirmation/disagreement;
- composite models using independent feature blocks rather than mirrored long/short thresholds.

Short strategies should not be simple mirrors of long rules. Search space, costs, dependence handling, multiplicity, temporal validation, and protected/future evidence boundaries must be preregistered before performance is inspected.

Phase11 support remains authoritative until a later separately accepted replacement decision. LIVE remains disabled; no automatic broker failover.