# Phase 25 Gate 7 — Exact-PIT Market/Ticker Route Context

**Status: ACTIVE / GATE6 TARGET EVIDENCE ACCEPTED / GATE7 IMPLEMENTATION**

## Accepted Gate6 boundary

Gate6 policy fingerprint:

`5ee92c766031fcf02bf8b80d9a1f4366e7bb6faa8c3634236ad438ef11f52da0`

The first target attempt reached 1,250 / 1,260 sessions and blocked at the pre-existing 2026-08-14 discovery-foundation boundary. Review found that the original Gate6 guard called a production builder before proving an existing artifact was current, so the stale 2026-08-14 foundation pair could be recomputed before Gate6 raised. The discovery-score pair was not rebuilt.

Gate6 was repaired to preflight all existing universe/foundation/score artifact sets before any builder call. The one already-bounded 2026-08-14 foundation/score dependency mismatch is permitted to reconcile only when the recomputed foundation is semantically identical across every field consumed by the production scorer. Any semantic mismatch remains blocking.

Exact repaired Gate6 head:

`50df27c71dd698c38c16ff8e9c32c8c6a31a6901`

Exact-head CI run `32909128824`: Ubuntu and Windows both passed every validator through repaired Gate6 and the complete repository regression suite.

Accepted target-machine Gate6 evidence through 2026-08-21:

- replay sessions: **1,260 / 1,260**;
- existing Phase7 universe artifacts preserved: **1,260**;
- existing discovery-foundation artifacts preserved: **1,260**;
- existing discovery-score artifacts preserved: **1,260**;
- newly materialized artifacts on the accepted rerun: **0** (the first run had already materialized the previously missing historical sets);
- Reconciliation events: **1**;
- effective-state rows:
  - HOT: **16,517**;
  - WARM: **16,731**;
  - WATCH: **1,554,664**;
  - NORMAL: **7,331,390**;
- WARM/HOT direction counts:
  - bullish: **16,079**;
  - bearish: **7,098**;
  - neutral: **10,071**;
- accepted WARM/HOT **directional** population: **23,177 rows**;
- provider reads/writes: **0 / 0**;
- operational discovery-state writes: **0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- Phase11 support writes: **0**;
- independent validation: **PASS**;
- Gate6 Pass: **true**.

Interpretation: the historical production-path discovery population is now reconstructed and independently validated from exact PIT reference through production Phase7/discovery scoring and accepted chronological discovery hysteresis.

## Gate7 purpose

Gate7 adds only the regime-routing context that production promotion sees before a strategy rule can fire:

`Gate6 WARM/HOT directional population -> market regime -> ticker regime -> StrategyRouter`

Gate7 does **not** evaluate strategy conditions, read forward returns, reopen protected evidence, or alter Phase11 support.

## Market regime reconstruction

Market state is reconstructed provider-free from the already accepted split-origin production policy:

- history origin: **2016-01-04**;
- accepted point-in-time threshold policy;
- accepted market breadth/proxy population;
- accepted persistence semantics;
- no operational regime-state writes.

Gate7 computes the effective market history in memory/research scope and requires an exact market state for every Gate6 candidate session.

## Exact-PIT ticker continuity

Gate7 must not reuse the old `authoritative_ticker_intervals.parquet` as historical authority. That artifact was derived before the complete Phase25 PIT reference backfill and therefore does not represent the newly accepted daily identity lineage.

Instead Gate7 reconstructs ticker continuity directly from the exact same-session Massive reference snapshots accepted by Gates4/5:

1. only `active=true` rows are considered;
2. candidate `(instrument_id, ticker)` pairs come from the accepted Gate6 population;
3. exact XNYS session ordinals identify contiguous validity;
4. a ticker change, identity-quality change, or missing exact PIT session breaks the interval;
5. ticker feature history is bounded to that exact interval, so old/new ticker series and ticker reuse are never spliced;
6. 1d/4h/1h raw ticker dimensions use the accepted production formulas;
7. missing complete feature sessions break persistence continuity;
8. accepted **2-session dimensional confirmation** is applied independently to daily structure, short alignment, and momentum;
9. the effective ticker composite is recomputed with the accepted production `candidate_ticker_state` function.

Fallback identities are date-scoped by the identity contract, so they naturally remain shallow instead of being given invented continuity.

## Sector behavior

No authoritative point-in-time ticker-to-sector classification has been accepted. Gate7 therefore preserves the production contract:

`sector_state = UNAVAILABLE`

`UNAVAILABLE` is distinct from `MIXED` and is nonblocking in the production `StrategyRouter`. Gate7 has **no sector mapping authority**.

## Strategy routing only

For every one of the **23,177** Gate6 directional candidates, Gate7 runs the accepted production `StrategyRouter` against all eight registered v1 strategies.

Expected cardinality invariant:

- 8 route decisions per candidate;
- 4 direction-matched strategies per bullish/bearish candidate;
- sector fit is `unavailable` for every decision;
- an eligible decision cannot have market fit `blocked` or ticker fit `blocked`.

Gate7 writes only research artifacts under:

`data/derived/strategy_evaluation/phase25/v1/gate7/through=2026-08-21/`

Artifacts:

- `route_context.parquet` — one row per accepted Gate6 candidate with exact market/ticker context and PIT interval evidence;
- `route_decisions.parquet` — one row per candidate × registered strategy using the production router;
- `route_context_report.json` — attribution counts, lineage hashes, policy fingerprint, and authority counters;
- `independent_validation.json` — independent cardinality, lineage, routing, and authority validation.

## Gate7 authority lock

Gate7 has no authority to:

- call Massive or another provider;
- mutate any provider;
- write operational market/sector/ticker regime state;
- fabricate sector mappings;
- use the stale pre-backfill ticker interval artifact as authoritative continuity;
- evaluate any strategy rule or condition;
- read strategy forward returns;
- read protected strategy evidence;
- replace Phase11 support;
- change Phase24 statistical gates;
- read or mutate brokers;
- submit PAPER or LIVE orders;
- invoke browser execution, scheduler authority, or PostgreSQL runtime promotion.

## Gate7 acceptance rule

Gate7 passes only if:

- the exact accepted Gate6 report, independent validation, and WARM/HOT directional population are hash-bound;
- every candidate binds to exactly one exact-PIT ticker interval;
- market state exists for every candidate session;
- ticker persistence never crosses an exact-PIT or feature-session gap;
- `route_context.parquet` contains exactly the Gate6 candidate population once each;
- `route_decisions.parquet` contains exactly 8 unique strategy rows per candidate;
- exactly 4 route rows direction-match each directional candidate;
- sector state remains unavailable and sector fit remains nonblocking/unavailable;
- no eligible route is market-blocked or ticker-blocked;
- provider and operational regime writes are zero;
- strategy-rule evaluation and strategy-return reads are false;
- broker/order/PAPER/LIVE/support/protected-evidence authority remains zero;
- independent validation passes.

## Next boundary

Only after Gate7 target evidence is accepted may Gate8 evaluate the **unchanged incumbent v1 strategy rules** on the route-eligible production-path population.

Gate8 must still hold the accepted three-session outcome definition fixed. Its purpose is attribution, not strategy invention: measure how the historical population changes through the ladder

`Gate6 directional -> market compatible -> ticker compatible -> incumbent rule fired`.

Strategy returns/support replacement remain a later separately preregistered evidence boundary.
