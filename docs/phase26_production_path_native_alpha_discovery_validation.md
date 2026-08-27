# Phase26 — Production-Path-Native Alpha Discovery & Validation

**Status: ACTIVE / METHODOLOGY LOCKED BEFORE PHASE26 PERFORMANCE INSPECTION**

This is the active Phase26 specification. `docs/roadmap.md` remains the project mission/source of truth; this file freezes the exact Phase26 research question, research population, candidate search space, validation design, and authority boundary before Phase26 target-performance results are inspected.

## Plain-English phase start

### Where we are now

ATLAS has a substantial data, analysis, risk, PAPER-execution, and operational foundation, but no existing strategy has earned `SUPPORTED` authority. Phase24 tested small variations of the old strategy rules and Phase25 checked those rules on the true historical production path. They still did not show a reliable after-cost edge.

### What this phase is trying to accomplish

Phase26 searches for genuinely different ways of identifying good trades using the exact types of candidates ATLAS would have encountered in production. It does not keep adjusting failed thresholds until something looks profitable.

### Why it matters

A reliable trading advantage is the current bottleneck. Better automation, a finished GUI, or flawless broker execution cannot turn a strategy with negative expectancy into a profitable system.

### What will be built

Phase26 will build a production-path-native research table, calculate the accepted three-session outcome directly from canonical history, evaluate a frozen library of 24 materially different long/short strategy candidates, independently validate the research, and confirm only true finalists on protected strategy-return evidence.

### What will be tested at the end

The complete Phase26 gate will test software correctness, data/identity/chronology integrity, realistic after-cost economics, time/regime robustness, concentration/dependence, multiple-testing risk, protected confirmation for finalists, independent validation, full historical regression, Ubuntu/Windows CI, and one target-machine evidence run.

### What success means

A Phase26 candidate can earn historical analytical `SUPPORTED` status only if it survives every predeclared development, internal-validation, multiplicity, robustness, and protected-confirmation requirement. That is enough to enter Phase27 trade construction; it is not PAPER or LIVE authority.

### What happens if nothing passes

A zero-finalist or zero-confirmed result is an accepted scientific outcome if the phase itself passes technically. ATLAS remains blocked on alpha and the next research phase is designed from the documented failure modes. Requirements are not weakened after seeing poor results.

### What is not happening yet

Phase26 does not submit broker orders, does not authorize PAPER or LIVE trading, does not deploy the finished web application, does not invent sector history, and does not change strategy rules after protected results are known.

## 1. Entry evidence

Phase26 depends on accepted Phase25 evidence, including:

- Gate6 production discovery reconstruction and WARM/HOT directional population;
- Gate7 exact point-in-time identity, market state, ticker state, and interval context;
- accepted canonical 1d/4h/1h history and 33-feature contract;
- accepted three-exchange-session endpoint return definition;
- Phase25 conclusion that the legacy broad strategy-research join covered only about 76% of actual route-eligible rows and must not be the Phase26 primary research source.

The Phase25 legacy strategy-specific route decisions are **not** the Phase26 candidate gate. They encode the old strategy catalog that Phase26 is replacing. Phase26 starts from Gate6 candidates bound to Gate7 exact PIT context, then applies its own frozen candidate architectures.

## 2. Primary observation contract

The Phase26 primary research row is one accepted Gate6 candidate on one exchange session, bound one-to-one to its Gate7 exact PIT interval/context.

Required identity/context fields include:

- `as_of_date`;
- `instrument_id`;
- provider-native `ticker`;
- Gate6 effective discovery state and direction;
- discovery setup/priority metadata;
- Gate7 market state;
- Gate7 effective ticker state when available;
- Gate7 identity quality and exact `interval_key` / safe date bounds.

For that exact row, Phase26 joins only observation-time information:

- 1d feature row for the session;
- final regular-session 4h feature row for the session;
- final regular-session 1h feature row for the session;
- canonical daily open/close needed for gap behavior;
- exact prior-session close inside the same safe PIT interval;
- lagged daily closes inside the same safe PIT interval for 5-session and 20-session returns.

No future feature value may enter a candidate predicate.

### 2.1 Frozen research-derived fields

Phase26 may derive these observation-time fields from accepted data:

- `gap_return = daily_open / prior_close - 1`;
- `intraday_return = daily_close / daily_open - 1`;
- `return_5d = daily_close / close_5_sessions_ago - 1`;
- `return_20d = daily_close / close_20_sessions_ago - 1`;
- `vol_scaled_return_20d = return_20d / max(realized_volatility_20, epsilon)`;
- same-session cross-sectional percentiles for `return_20d`, `vol_scaled_return_20d`, `realized_volatility_20`, `bb_width_20`, and `dollar_volume`, calculated only from Phase26 production-path candidate observations available on that session;
- deterministic bullish and bearish five-block composite scores defined in `packages/backtesting/phase26_policy.py`.

Sector-relative fields are forbidden because accepted PIT sector mapping is currently unavailable.

## 3. Outcome contract and protected blindness

The research outcome remains the accepted strategy-neutral **three exchange-session endpoint return**:

`forward_return = close(t+3 exchange sessions) / observation_close - 1`

The endpoint must:

- use exact exchange-session continuity;
- use the same provider-native ticker / exact PIT identity interval;
- remain inside the interval safe bounds;
- censor split-crossing windows using accepted split evidence;
- never splice same text across different identities;
- use endpoint return only, not a path barrier.

For LONG candidates, `directional_return = forward_return`. For SHORT candidates, `directional_return = -forward_return`.

Development/internal returns end before the protected period. Protected strategy returns are not calculated/read until the frozen development process has produced finalists. The protected period is `2026-05-12` through `2026-08-11`, matching the accepted 63-session holdout boundary. It was not read for Phase24/25 strategy finalist confirmation because those phases had zero finalists, but it is not considered globally fresh because the period has existed in prior ML work. Therefore Phase29 prospective SHADOW/PAPER evidence remains mandatory before any LIVE progression.

## 4. Candidate search space — frozen at 24

Phase26 evaluates exactly **24 deterministic candidates**: six materially different architecture families, four candidates per family, with two LONG and two SHORT designs per family. Candidate IDs, feature thresholds, and exact predicates are frozen in `packages/backtesting/phase26_policy.py`.

The six families are:

1. **Cross-sectional relative strength / weakness** — rank current production candidates against peers on observation-time multi-session performance and quality rather than relying on absolute RSI/EMA thresholds alone.
2. **Volatility/liquidity-conditioned mean reversion** — look for oversold reclaims and overextended/failing rallies only when liquidity and volatility context make the setup tradable.
3. **Volatility-normalized breakout / breakdown** — require structure, participation, efficiency, and multi-timeframe confirmation around actual range breaks.
4. **Multi-timeframe state transitions** — use 1d/4h/1h agreement or pullback/bounce failure structures rather than a single-timeframe rule.
5. **Gap continuation / reversal** — test gap holds, gap reclaims, negative-gap continuation, and positive-gap fades from finalized daily data.
6. **Independent feature-block composites** — combine trend, momentum, structure, volume/liquidity, and multi-timeframe blocks; bearish blocks are independently defined rather than being a mechanical sign inversion of bullish blocks.

These families intentionally include concepts common in quantitative research and experienced trading communities, but community popularity is not evidence. Every candidate faces the same validation standard.

No additional candidate, threshold variant, or feature may be added after Phase26 development returns are inspected. A materially new idea discovered later requires a separately declared future research phase.

## 5. Economic assumptions

Frozen stock-signal round-trip cost grid:

- 0 bps — frictionless diagnostic only;
- 5 bps — low-friction diagnostic;
- **10 bps — primary economic test**;
- **25 bps — stress economic test**.

The 10/25 bps levels preserve comparability with Phase24/25. Phase27 must replace these generic signal-level assumptions with actual stock/options instrument-specific spreads, slippage, commissions/fees, borrow/locate constraints, volatility, and execution economics before a trade is constructed.

## 6. Chronology and dependence

- Research begins `2021-08-16`.
- Protected strategy-return period: `2026-05-12` through `2026-08-11`.
- Development period ends `2026-05-11`.
- A 3-session purge is mandatory around chronological boundaries because outcomes overlap for three sessions.
- Development is divided chronologically: 75% selection tranche / 25% internal-validation tranche after applying the purge contract.
- Selection uses 6 chronological folds.
- Internal validation uses 3 chronological folds.
- Protected confirmation uses 3 chronological folds for finalists only.
- Same-session cross-sectional rows are not treated as independent time observations.
- Confidence intervals are based on session-level aggregation plus 6-session moving-block bootstrap with 2,000 preregistered replicates.

Random row splitting is forbidden.

## 7. Candidate acceptance rules

### 7.1 Minimum evidence

Selection:
- at least 1,000 fired rows;
- at least 250 distinct signal sessions.

Internal validation:
- at least 300 fired rows;
- at least 80 distinct signal sessions.

Protected confirmation:
- at least 75 fired rows;
- at least 24 distinct signal sessions.

No single session may supply more than 10% of a candidate's fired rows in selection or internal validation.

### 7.2 Economic / chronological requirements

A candidate must, at minimum:

- have positive aggregate mean net return at 10 bps in selection and internal validation;
- have positive aggregate mean net return at the 25 bps stress cost in selection and internal validation;
- have positive 10 bps mean in at least 5 of 6 selection folds;
- have positive 10 bps mean in at least 2 of 3 internal folds;
- have a positive lower confidence bound for session-level 10 bps mean under the frozen block bootstrap in selection and internal validation;
- meet the frozen year and market/ticker-regime robustness requirements where enough signal sessions exist;
- pass concentration controls.

**Median trade return and win rate remain reported diagnostics, but neither `median > 0` nor `win rate >= 50%` is a universal Phase26 veto.** A strategy can have positive expectancy with fewer than half of trades winning when payoff asymmetry is favorable. Phase26 therefore judges after-cost expectancy and robustness directly.

### 7.3 Multiple-testing / overfitting control

- one-sided candidate evidence is corrected with global Holm-Bonferroni across all 24 frozen candidates at alpha `0.05`;
- at most one candidate per architecture-family/direction can advance to protected confirmation;
- trial-aware/deflated performance diagnostics must be reported for finalist context, but do not replace the preregistered economic and block-bootstrap gates;
- no losing candidate may be revived after protected evidence is opened.

## 8. Protected confirmation

Protected returns remain unread when there are zero finalists.

Each frozen finalist must independently satisfy:

- protected minimum rows/sessions;
- positive aggregate 10 bps mean;
- positive aggregate 25 bps stress mean;
- positive 10 bps mean in at least 2 of 3 protected folds;
- positive 80% block-bootstrap lower confidence bound for session-level 10 bps mean.

A protected failure cannot be repaired by threshold tuning inside Phase26.

## 9. Support semantics

If and only if a candidate survives every frozen requirement and independent validation, Phase26 may produce an accepted support-overlay artifact identifying that exact candidate definition as historically `SUPPORTED`.

This is **analytical strategy authority only**. It permits Phase27 to evaluate how to monetize the signal. It does not authorize provider mutations, broker reads/writes, order submission, PAPER execution, LIVE execution, automatic scheduling, or broker failover.

Existing Phase11 strategy support remains authoritative for incumbent v1 strategies; Phase26 does not silently upgrade any incumbent.

## 10. Provider/broker/GUI authority

Initial Phase26 research is provider-free and broker-free from already accepted local canonical/derived artifacts:

- provider reads: 0;
- provider writes: 0;
- broker reads: 0;
- broker writes: 0;
- order writes: 0;
- PAPER submits: 0;
- LIVE writes: 0.

GUI work is limited to recording stable future data-contract needs if implementation exposes them. Phase26 does not displace alpha research with frontend construction.

## 11. Phase26 deliverables

Phase26 is one project gate and is expected to deliver, as one coherent batch:

- frozen policy and candidate registry;
- production-path-native observation builder;
- development candidate evaluator;
- internal-validation and multiplicity/robustness evaluator;
- finalist-only protected confirmation;
- support-overlay artifact logic for confirmed candidates;
- independent Phase26 validator;
- one cumulative target-machine Phase26 runner;
- focused/unit/integration tests;
- CI integration;
- plain-English and technical closeout documentation.

## 12. Full Phase26 acceptance gate

Phase26 can close only after:

1. all Phase26-focused tests pass;
2. the independent Phase26 validator passes;
3. all retained historical validators still pass;
4. the complete repository regression suite passes;
5. Ubuntu and Windows CI pass on the exact acceptance head;
6. the target-machine cumulative Phase26 evidence command completes successfully;
7. lineage/reproducibility checks pass;
8. forbidden external/broker/PAPER/LIVE activity remains zero;
9. any support change is exactly explained by frozen evidence and is independently validated;
10. living docs are synchronized and the user receives the required plain-English phase-end report.

A technically/scientifically valid zero-finalist result is `ACCEPTED — NEGATIVE`; it is not permission to start Phase27.
