# Successor Practitioner Laboratory — Pre-Outcome Freeze

Status: **PRE-OUTCOME SPECIFICATION / RESEARCH ONLY**  
Date: **2026-09-13 UTC**

This is an immutable specification document once accepted. It is not a fourth living handoff; current project state remains in `README.md`, `docs/roadmap.md`, and `docs/strategy_evidence_register.md`.

## 1. Why this package exists

B35 completed the canonical four-strategy intraday replay, walk-forward condition/selector analysis, retained-artifact robustness, and the final 27-profile exact minute-path perturbation diagnostic. The targeted run completed 482/482 groups and 59,768/59,768 source units with run fingerprint `dd3f6b94f9c669218512ed1eb014b33c0fd35e8ffe38484cc8967dc7a6e29f69` and exact canonical baseline equivalence. No consumed-master or future-blind outcomes were read, and no strategy was promoted.

The perturbation result closes simple neighboring parameter rescue for the four B34/B35 strategies. Gap delay/threshold changes remained deeply negative; ORB 14/15/16-minute and 0/1/2-minute entry variations were economically indistinguishable and negative; premarket relative volume retained only a thin gross signal that was already negative at 10 bps; HVD remained sparse and negative. Successor work therefore changes mechanisms or condition quality rather than selecting the best observed nearby parameter.

## 2. Economic family roster

The successor laboratory contains exactly **21 economic strategy families**. Nearby policy versions remain inside their economic family for multiplicity and confluence accounting.

Retained families: moving-average 50/200 trend cross; EMA20/50 pullback; MACD 12/26/9 shift; RSI14 trend recovery; Donchian20 high-volume breakout; Bollinger20 squeeze breakout; gap continuation; opening range; premarket relative-volume consolidation; Highest-Volume-Day style.

New families: Bollinger mean reversion; ATR volatility expansion; session VWAP reclaim/reject; pivot/support-resistance breakout; objective head-and-shoulders; objective double top/bottom; flag/pennant; triangle breakout; ADX/DMI continuation; relative-strength momentum versus SPY; objective session failed-break/reclaim.

The machine-readable roster and its fingerprint are owned by `packages/strategies/successor_practitioner_lab.py`.

## 3. B35-inspired bounded challengers

Only four mechanism-level B35 challengers are admitted in this cycle:

- `gap_quality_condition_long_v2`: long-side gap continuation with preregistered price/liquidity/volatility/premarket-participation quality. It is not a 1.8/2.0/2.2-percent threshold search.
- `orb_stocks_in_play_5m_v1`: five-minute ORB after an objective same-time opening-activity and executable-liquidity screen.
- `orb_15m_close_retest_v2`: 15-minute ORB requiring an objective close, bounded retest and hold/rejection confirmation.
- `premarket_relvol_quality_v2`: quality/liquidity/participation successor that retains information-safe immediate entry and attempts to increase gross edge rather than weaken costs.

No simple HVD width/delay challenger is admitted. HVD requires a genuine redefinition under a later fingerprint or remains a sparse reference baseline.

These candidates were motivated by DEVELOPMENT evidence and therefore **cannot validate themselves on the same DEVELOPMENT evidence that inspired them**. DEVELOPMENT results are diagnostic/training evidence; later authority requires untouched/prospective evidence.

## 4. Shared PIT context

Every opportunity should carry the same point-in-time context where the source contract can support it: broad-market direction and volatility; short/medium ticker relative strength versus SPY; higher-timeframe ticker trend; ATR-normalized trend maturity/extension; opening same-time and premarket participation; prior dollar-volume/liquidity; overnight gap; price band; signal time; realized volatility; and execution/liquidity quality.

Sector relative strength remains deferred until a PIT-valid sector map exists. Unavailable context remains explicitly unavailable rather than guessed.

## 5. Evaluation contract

Common DEVELOPMENT scope is `2016-01-04..2026-04-30`. The consumed master window `2026-05-12..2026-08-11` may never be reused. The future blind beginning `2026-09-08` remains unread until a separate frozen authority package explicitly opens it.

The default walk-forward structure is 504 training sessions / 63 test sessions / 63-session step / 1-session embargo. Minimum supported condition evidence remains 60 opportunities / 30 sessions / 20 instruments. All strategies preserve standalone outcomes before any condition gate or confluence layer is applied.

The common reporting grid is 0/10/25/50/100 bps. Daily strategies retain 10 bps primary and 25 bps stress interpretation; intraday strategies retain the conservative 50 bps primary and 100 bps stress interpretation. Observed costs are never weakened to rescue a strategy.

Qualification must consider win rate together with payoff, net expectancy/net-R, drawdown/tail behavior, cost decay, MFE/MAE, holding time, sample support, fold/year stability, concentration and abstention. A favorable post-result slice does not validate itself.

## 6. Confluence contract

Strategy firing is immutable and independent of confluence. The confluence layer preserves the primary strategy and direction, exact contributing policies, raw same-direction count, distinct evidence-family count, opposing evidence, costs and context.

Trend, momentum, participation, price structure, volatility, chart pattern, relative strength and context/regime are distinct evidence families. Multiple correlated transforms such as RSI, MACD and EMA are not automatically independent votes.

The preregistered comparison is standalone versus hard-confirmation versus confluence ranking. Begin with transparent stratified outcome tables. Arbitrary subjective point scoring is forbidden. Any later predictive model must be training-only/walk-forward, regularized, calibrated and compared with simpler baselines.

## 7. Runtime and efficiency contract

Long successor workloads are designed for parallel execution from the beginning, not optimized after an avoidable serial run. Independent groups use process-level parallelism, bounded DuckDB threads per worker, atomic outputs, hash-bound completion receipts, restart reuse, machine-readable progress, PID/scope/execution-profile banners and heartbeats no slower than 60 seconds.

Scientific fingerprints exclude worker count, DuckDB thread count, PID, wall-clock throughput and other runtime telemetry. An execution optimization is accepted only when golden-output equivalence proves identical scientific output. Failed or corrupt receipts fail closed; completed validated groups are never rebuilt merely because the execution profile changes.

The B35 targeted replay produced a useful workstation reference on the i7-8700K/24-GiB host: 10x1 was faster but reached thermal throttling; 8 workers x 1 DuckDB thread sustained about 1,702 units/hour without recorded thermal throttling and is therefore the current reference for similar mixed Python/DuckDB workloads. This is not a universal hardcoded optimum. Every materially different long workload should benchmark scientifically equivalent shapes on the actual host and choose the fastest stable configuration that preserves OS and thermal headroom.

## 8. Authority

This package grants no provider call authority, broker read/write authority, PAPER authority, LIVE authority, strategy promotion or selector promotion. All successor policies remain RESEARCH. The consumed master remains permanently consumed and the future blind remains unopened.
