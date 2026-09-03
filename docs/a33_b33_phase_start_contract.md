# A33/B33 Phase-Start Contract — Practitioner Strategy Laboratory and Product Rebaseline

**Status:** frozen pre-outcome implementation contract. This is an immutable package specification, not a living handoff. The root `README.md` and `docs/roadmap.md` remain the only living project documents.

## Purpose

A33/B33 starts the post-Review-Chat-3 two-track implementation without reopening the closed alpha gates. This package builds the first finite practitioner reference library and the shared historical/product opportunity architecture while preserving the distinction between evidence, authority, ranking, and execution.

No historical strategy performance, protected returns, qualifying PAPER, or LIVE authority may be used to choose or repair these starting rules.

## Locked boundaries

- Existing accepted Phase11 strategy/runtime contracts remain backward compatible while A33 introduces a broader research taxonomy.
- Evidence source for all six starting strategies is `PRACTITIONER_BASELINE`.
- Starting authority for every strategy is `RESEARCH`.
- Operational PAPER is a product-debug mode and cannot promote strategy authority.
- Qualifying PAPER requires at least `HISTORICALLY_VALIDATED` authority.
- LIVE requires `LIVE_ELIGIBLE` authority plus the later system/operator gates; A33/B33 grants neither.
- The existing master protected window `2026-05-12..2026-08-11` remains unconsumed and is not part of A33/B33 practitioner selection.
- Signals formed at a finalized daily close enter no earlier than the next executable regular-session event.
- Signal-level cost diagnostics are `0/5/10/25/50` bps round trip, with 10 bps primary and 25 bps stress; executable replay must later use order/liquidity/volatility-aware economics.
- Every eligible, fired, routed-out, authority-blocked, risk-rejected, not-selected, counterfactual, planned, submitted, filled, canceled, exited, and unreconciled opportunity must remain observable through the shared append-only opportunity contract.

## Six frozen starting research specifications

The source-of-truth code definitions are in `packages/strategies/research_catalog.py`.

1. `ma_trend_cross_50_200_long_v1`
   - 50/200 moving-average transition, LONG.
   - Next-session entry; 2 ATR initial stop; reverse cross / 3 ATR trail / 126-session exit.
2. `ema_pullback_20_50_long_v1`
   - 20/50 EMA pullback continuation, LONG.
   - Outcome access remains blocked until the exact pullback-low versus 1.5 ATR stop-price algorithm and risk-cap behavior are frozen.
3. `macd_shift_12_26_9_v1`
   - MACD momentum-shift seed specification.
   - LONG and SHORT executable policies must be split into distinct versions before outcome access; SHORT also requires explicit borrow/locate and asymmetric-cost treatment.
4. `rsi_recovery_14_trend_long_v1`
   - RSI14 recovery above 30 inside a close-above-EMA200 trend, LONG.
   - RSI below 30 alone is not a signal or an undervaluation claim.
5. `donchian_breakout_20_volume_v1`
   - Prior-20-session range escape with relative-volume and EMA50-slope confirmation.
   - Directional versions, exact channel/ATR stop logic, and SHORT economics must be frozen before outcome access.
6. `bollinger_squeeze_breakout_20_v1`
   - Trailing-126-session low-width compression followed by an outer-band break and relative-volume confirmation.
   - Compression alone supplies no direction; directional versions, stop selection, and SHORT economics must be frozen before outcome access.

## Shared authority model

Strategy evidence source:

`PRACTITIONER_BASELINE | LITERATURE_ANCHORED | INTERNAL_CHALLENGER`

Strategy authority:

`RESEARCH -> CANDIDATE -> HISTORICALLY_VALIDATED -> PAPER_VALIDATED -> LIVE_ELIGIBLE`

Authority promotions must advance one stage at a time and carry an explicit evidence identifier. Ranking or AI opinion cannot promote authority.

Execution modes:

- `HISTORICAL_REPLAY`: permitted for research specifications after their pre-outcome blockers are resolved and outcome access is explicitly opened by a later frozen package step.
- `OPERATIONAL_PAPER`: permitted as a product-test mode but does not qualify or promote a baseline.
- `QUALIFYING_PAPER`: prohibited below `HISTORICALLY_VALIDATED`.
- `LIVE`: prohibited below `LIVE_ELIGIBLE` and remains globally disabled by later gates.

## Immediate implementation sequence

1. Resolve every declared pre-outcome blocker and split directional policies where required.
2. Implement the exact missing daily features and transition semantics for the six policies.
3. Freeze code/data/feature/cost/risk/evaluation versions before historical performance access.
4. Build the reusable PIT historical trade simulator and append-only trials/opportunity/outcome persistence around these same contracts.
5. Connect the same versioned records to discovery/regime/risk routing and API read models.
6. Run focused tests, then exact-head full acceptance before opening or merging historical reports.

Negative, zero-trade, and underpowered strategy results remain valid outcomes. No post-result threshold or policy repair may be used to manufacture support.
