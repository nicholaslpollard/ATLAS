# Phase26 — Production-Path-Native Alpha Discovery & Validation

**Status: ACTIVE / METHODOLOGY LOCKED BEFORE PHASE26 PERFORMANCE INSPECTION**

This is the active Phase26 specification. `docs/roadmap.md` controls the ATLAS mission and long-term sequence; this document freezes the exact Phase26 research question, population, candidate search space, validation design, and authority boundary before Phase26 target-performance results are inspected.

## Plain-English phase start

### Where we are now
ATLAS has a substantial data, analysis, risk, PAPER-execution, and operational foundation, but no existing strategy has earned `SUPPORTED` authority. Phase24 tested bounded variants of the old strategy rules and Phase25 replayed those rules on the true historical production path. They still did not show reliable after-cost edge.

### What this phase is trying to accomplish
Phase26 searches for genuinely different ways of identifying good trades using the exact types of candidates ATLAS would have encountered in production. It does not keep adjusting failed thresholds until something looks profitable.

### Why it matters
Validated trading edge is the current bottleneck. Better automation, a finished GUI, or flawless broker execution cannot turn negative expectancy into a profitable system.

### What will be built
Phase26 builds a production-path-native research table, calculates the accepted three-session outcome from canonical history, evaluates a frozen library of 24 materially different long/short strategy candidates, independently validates the research, and opens protected strategy returns only for finalists that survive frozen development/internal requirements.

### What will be tested at the end
The complete Phase26 gate tests software correctness, identity/chronology integrity, realistic after-cost economics, time/regime robustness, concentration/dependence, multiple-testing risk, protected confirmation, independent persisted-artifact reconciliation, all retained historical validators, full regression, Ubuntu/Windows CI, one target-machine cumulative evidence run, and a bounded end-to-end architectural/integrity audit for workaround debt or duplicate authority paths.

### What success means
A Phase26 candidate can earn historical analytical `SUPPORTED` status only if it survives every predeclared development, internal-validation, multiplicity, robustness, and protected-confirmation requirement. This permits Phase27 trade construction; it does not grant PAPER or LIVE authority.

### What happens if nothing passes
Zero finalists or zero protected-confirmed candidates is valid negative evidence if the phase itself passes technically/scientifically. ATLAS remains blocked on alpha and the next research phase is designed from the documented failure modes. Requirements are not weakened after seeing disappointing results.

### What is not happening yet
Phase26 does not submit broker orders, authorize PAPER/LIVE, deploy the finished web application, invent sector history, or change candidate rules after results are known.

## 1. Entry evidence

Phase26 depends on accepted Phase25 evidence:

- Gate6 production discovery reconstruction and WARM/HOT directional population;
- Gate7 exact point-in-time identity, market state, ticker state, and interval context;
- canonical 1d/4h/1h history and the accepted 33-feature contract;
- the accepted three-exchange-session endpoint-return definition;
- the Phase25 finding that the legacy broad strategy-research join covered only about 76% of the real production route population.

The legacy Phase11/24 research join is not the Phase26 primary population. Phase25 Gate7 strategy-specific route decisions are also not the Phase26 candidate gate because they encode the failed incumbent catalog. Phase26 begins with Gate6 candidates bound to Gate7 exact PIT context, then applies its own frozen architectures.

## 2. Primary observation contract

One Phase26 research row is one accepted Gate6 candidate on one exchange session, bound one-to-one to its Gate7 exact PIT context.

Identity/context includes:
- `as_of_date`;
- `instrument_id`;
- provider-native `ticker`;
- effective discovery state/direction/setup/priority;
- market state;
- effective ticker state when available;
- identity quality;
- exact `interval_key`, `safe_start_date`, and `safe_end_date` for observation-time historical joins.

Observation-time research inputs include:
- same-session finalized 1d features;
- final regular-session 4h features;
- final regular-session 1h features;
- canonical same-session daily open/close;
- exact prior-session close within the same PIT interval;
- 5-session and 20-session lag closes within the same PIT interval.

No future feature value may enter a candidate predicate.

### 2.1 Frozen research-derived fields

Phase26 derives only preregistered observation-time fields:
- `gap_return = daily_open / prior_close - 1`;
- `intraday_return = daily_close / daily_open - 1`;
- `return_5d`;
- `return_20d`;
- `vol_scaled_return_20d = return_20d / realized_volatility_20` when volatility is positive;
- same-session production-candidate percentiles for 20-session return, volatility-scaled return, realized volatility, Bollinger width, and dollar volume;
- independent bullish/bearish five-block composite scores defined in `packages/backtesting/phase26_policy.py`.

Sector-relative research is forbidden because accepted PIT sector mapping is unavailable.

## 3. Outcome identity, chronology, and protected blindness

The strategy-neutral outcome remains:

`forward_return = close(t+3 exchange sessions) / observation_close - 1`

Outcome identity rules are:
- observation identity must be the accepted exact PIT Gate7 identity/interval;
- the endpoint is the exact third later exchange session;
- the endpoint uses the same provider-native ticker text as the observation;
- same ticker text is never used to splice or infer identity continuity across an observation-time identity ambiguity;
- if the exact t+3 ticker close is unavailable, the row is censored rather than guessed;
- any accepted split execution date after the observation and through the t+3 endpoint censors the row;
- endpoint return is used; there is no hidden intraperiod barrier/path label.

The endpoint is **not required to remain before the Gate7 observation interval's stored `safe_end_date`**. `safe_end_date` protects observation-time historical joins. A valid observation on `2026-08-11` needs its third later exchange-session close on `2026-08-14`; the accepted same-ticker endpoint plus split censor provides the outcome contract. This clarification was made before Phase26 target-performance inspection.

LONG uses `directional_return = forward_return`; SHORT uses `directional_return = -forward_return`.

### 3.1 Development/protected boundary

The accepted protected observation period remains `2026-05-12` through `2026-08-11`.

Because each observation needs three later exchange sessions, the last **labelable development observation** is `2026-05-06`. The three exchange sessions `2026-05-07`, `2026-05-08`, and `2026-05-11` form the mandatory outer purge before protected observations begin on `2026-05-12`.

Inside the labelable development period, Phase26 then makes its own chronological 75% selection / 25% internal-validation split with another exact 3-session purge between those tranches.

Protected predictors are built without any future-return columns. Protected strategy returns are calculated/read only after the development process has frozen finalists. If there are zero finalists, protected strategy returns remain unread.

The protected period was not opened for Phase24/25 strategy finalists because those phases had none, but it is not globally fresh because it existed in prior ML work. Therefore Phase29 genuinely prospective SHADOW/PAPER evidence remains mandatory before LIVE progression even if Phase26 succeeds.

## 4. Candidate search space — exactly 24

Phase26 evaluates exactly 24 deterministic candidates: six architecture families, four candidates per family, with two independently designed LONG and two SHORT candidates per family. Exact IDs, thresholds, and predicates are frozen in `packages/backtesting/phase26_policy.py`.

Families:
1. cross-sectional relative strength / weakness;
2. volatility/liquidity-conditioned mean reversion;
3. volatility-normalized breakout / breakdown;
4. multi-timeframe state transitions;
5. gap continuation / reversal;
6. independent feature-block composites.

The families deliberately include concepts used in quantitative research and experienced stock/options communities, but popularity is not evidence. Every candidate faces the same frozen validation standard.

No candidate, threshold, feature, or family may be added after Phase26 development returns are inspected. A materially new idea found later belongs in a separately declared future research phase.

## 5. Economic assumptions

Frozen signal-level round-trip cost grid:
- 0 bps: frictionless diagnostic only;
- 5 bps: low-friction diagnostic;
- **10 bps: primary economic test**;
- **25 bps: stress economic test**.

The 10/25 bps levels preserve comparability with Phase24/25. Phase27 must replace generic signal costs with actual stock/options instrument-specific spread, slippage, commission/fee, borrow/locate, volatility, liquidity, expiration, and execution economics before constructing a trade.

## 6. Development dependence and validation design

Within the labelable development observation set:
- 75% chronological selection tranche;
- exact 3-session purge;
- remaining chronological internal-validation tranche;
- 6 selection folds;
- 3 internal-validation folds;
- 3 protected-confirmation folds for finalists only;
- no random row splitting;
- same-session cross-sectional rows are not treated as independent time observations;
- confidence uses session aggregation plus 6-session moving-block bootstrap with 2,000 frozen replicates.

## 7. Candidate acceptance rules

### Selection minimums
- at least 1,000 fired rows;
- at least 250 signal sessions;
- positive 10 bps mean;
- positive 25 bps stress mean;
- positive 10 bps mean in at least 5 of 6 folds;
- positive frozen block-bootstrap lower confidence bound;
- year, market-state, and ticker-state robustness when enough sessions exist;
- no single session supplies more than 10% of fired rows.

### Internal-validation minimums
- at least 300 fired rows;
- at least 80 signal sessions;
- positive 10 bps mean;
- positive 25 bps stress mean;
- positive 10 bps mean in at least 2 of 3 folds;
- positive frozen block-bootstrap lower confidence bound;
- frozen year/regime/concentration requirements.

**Median trade return and trade win rate remain diagnostics, not universal hard vetoes.** Positive expectancy can exist with fewer than half of trades winning when payoff asymmetry is favorable. Phase26 therefore tests after-cost expectancy and robustness directly.

## 8. Multiple testing / selection bias

- one-sided candidate evidence is globally corrected with Holm-Bonferroni across all 24 candidates at alpha `0.05`;
- at most one candidate per architecture-family/direction can advance;
- family/direction winner selection uses the selection tranche only;
- internal validation may confirm or reject that frozen winner but may not substitute a runner-up after seeing internal results;
- trial-aware/deflated performance diagnostics are reported for context but do not replace the frozen economic/bootstrap gates;
- losing candidates are not revived after protected evidence is opened.

## 9. Protected confirmation

For each frozen finalist only:
- at least 75 usable fired rows;
- at least 24 signal sessions;
- positive aggregate 10 bps mean;
- positive aggregate 25 bps mean;
- positive 10 bps mean in at least 2 of 3 protected folds;
- positive 80% moving-block-bootstrap lower confidence bound.

A protected failure cannot be repaired by tuning within Phase26.

## 10. Support semantics and authority

Only a candidate surviving all frozen requirements plus independent validation may enter the Phase26 support overlay as historically `SUPPORTED`.

That authority is **HISTORICAL ANALYTICAL STRATEGY SUPPORT ONLY**. It permits Phase27 to evaluate trade construction. It does not authorize provider mutation, broker reads/writes, orders, PAPER, LIVE, scheduling, or broker failover.

Existing Phase11 incumbent support remains unchanged; Phase26 does not silently upgrade incumbent v1 strategies.

Phase26 external activity authority:
- provider reads/writes: 0 / 0;
- broker reads/writes: 0 / 0;
- order writes: 0;
- PAPER submits: 0;
- LIVE writes: 0;
- automation writes: 0.

GUI work is limited to noting future stable data-contract needs. Alpha research remains the critical path.

## 11. Deliverables

Phase26 is one project gate and delivers one coherent batch:
- frozen policy/candidate registry;
- production-path-native observation builder;
- development/selection evaluator;
- internal validation + multiplicity/robustness evaluator;
- finalist-only protected confirmation;
- historical analytical support-overlay logic;
- independent persisted-evidence validator;
- one cumulative target-machine runner;
- focused tests and CI integration;
- bounded end-to-end architectural/integrity audit of the critical data-to-execution authority path;
- plain-English + technical closeout documentation.

## 12. Full Phase26 acceptance gate

Phase26 closes only after:
1. all Phase26-focused tests pass;
2. independent persisted-artifact validation passes;
3. all retained historical validators pass;
4. complete repository regression passes;
5. Ubuntu and Windows CI pass on the exact acceptance head;
6. one target-machine cumulative Phase26 command completes successfully;
7. lineage/reproducibility checks pass;
8. forbidden external/broker/PAPER/LIVE activity remains zero;
9. any support change is exactly explained by frozen evidence and independently reconciled;
10. a bounded end-to-end architectural/integrity audit reviews the critical `provider data -> canonical data -> identity/universe -> features -> discovery -> regimes -> ML -> strategies -> promotion -> downstream case -> risk -> execution authority` chain for workaround-like fallbacks, duplicate implementations/validators, stale compatibility shims, wrapper proliferation, circular provenance/recovery logic, or alternate authority paths. Each finding must be classified as legitimate resilience/provenance, simplification debt, root-cause defect, or obsolete bypass. Anything compensating for an unresolved defect must be corrected at the owning layer; temporary containment cannot earn acceptance; material corrections require the full applicable acceptance suite again;
11. living docs synchronize and the user receives the required plain-English phase-end report.

A technically/scientifically valid zero-finalist or zero-confirmed result is `ACCEPTED — NEGATIVE`. It does not permit Phase27 to begin because Phase27's entry condition is at least one accepted supported strategy.
