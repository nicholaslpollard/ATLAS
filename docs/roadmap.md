# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-baselined: 2026-08-26.**

This document controls the long-term destination, anti-drift rules, remaining phase sequence, and phase acceptance model for ATLAS. Accepted code/evidence on `main` controls what already exists; this roadmap controls what the project is trying to become and what must happen next.

Future continuation order:

1. this roadmap — mission, architecture, anti-drift rules, remaining phases;
2. `docs/current_status.md` — exact repository/current-phase handoff;
3. the active phase specification — frozen scope and acceptance criteria;
4. `docs/phase_flow.md` — how a phase is developed and accepted;
5. accepted code, validators, CI, PR evidence, and older phase documents for implementation detail/provenance.

When older documents conflict with accepted `main` or this re-baselined roadmap, accepted `main` controls historical fact and this roadmap controls future direction.

## 1. Mission and end goal

ATLAS is the **Autonomous Trading, Learning, and Analysis System** and the greenfield successor to Chart Monitor.

The practical end goal is simple:

> **Use trustworthy market evidence, validated quantitative edge, disciplined risk management, appropriate stock/options trade construction, reliable execution, and outcome learning to make educated trades with the objective of growing account equity and producing profit over time after realistic costs.**

Profit is never guaranteed. ATLAS is not judged by how many trades it creates, how often it is active, or whether a backtest looks impressive. It is judged by whether its decisions have defensible positive expected value after costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

Capital growth is the objective. Capital preservation and controlled risk are constraints required for compounding.

## 2. Original intent preserved

The earliest Chart Monitor 2.0 concept began as a browser-operated stock/options research system: refresh trustworthy data, determine market/ticker context, evaluate appropriate strategies, form a directional thesis, incorporate events/news, evaluate option structures, simulate likely outcomes, show transparent scoring/reasoning, independently review the deterministic case with AI, and archive predictions/outcomes for later calibration.

That concept correctly evolved into the broader ATLAS architecture: broad-market discovery rather than requiring the operator to supply every ticker, point-in-time historical evidence, conventional ML probability estimates, deterministic regime routing, promoted-only expensive research, portfolio-aware trade construction, broker execution, outcome learning, and an operational browser control plane.

The destination has not changed: **find defensible opportunities, determine whether and how to trade them, control risk, execute safely, and learn whether the decisions actually made money.**

## 3. Locked architecture

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> candidate promotion -> analogue/scenario/news research -> stock/options instrument selection -> entry/exit/geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alert/shadow/paper/live execution -> outcome/performance learning -> browser control plane`

Roles remain separated:

- **Parquet**: durable analytical/history lake.
- **DuckDB**: analytical/query engine.
- **PostgreSQL**: target persistent operational state when its production phase earns promotion.
- **Massive**: primary broad-market/reference provider.
- **Webull**: primary PAPER/sandbox broker and intended primary LIVE broker only after separate LIVE acceptance.
- **Alpaca**: explicit/manual secondary broker; no automatic failover.
- **ML**: probability/predictive evidence, never automatic trade authority by argmax alone.
- **Strategies/alpha models**: must earn support from historical and out-of-sample evidence.
- **AI**: independent audit/challenge layer, not the source of historical facts or unilateral trade authority.
- **Browser**: monitoring/control/configuration surface, not a parallel business-logic engine.

## 4. Anti-drift rules

Every phase and implementation decision must answer: **does this materially improve ATLAS's ability to identify, construct, execute, control, measure, or learn from profitable-risk-adjusted trades?**

The following are mandatory:

1. **Alpha before unnecessary plumbing.** Once required safety/foundation capability exists, the current trading bottleneck takes priority over lower-value infrastructure work.
2. **No activity target.** Zero candidates/trades can be correct. Thresholds are never weakened merely to create trades.
3. **No backtest theater.** Point-in-time data, realistic costs, leakage controls, chronological evaluation, dependence-aware statistics, multiplicity/selection-bias controls, protected evidence, and reproducibility are required.
4. **No silent self-modification.** Models, strategies, thresholds, and support states change only through explicit versioned evidence and a later accepted phase.
5. **No community idea receives special treatment.** Ideas from traders/options communities are useful hypothesis sources, not evidence. They must survive the same validation as internally generated ideas.
6. **Reuse accepted components.** Later phases integrate/strengthen existing Phase1–25 capabilities rather than rebuilding parallel pipelines without measured cause.
7. **Simple operator outputs.** Raw evidence may be detailed, but every phase closeout must explain in plain English what was built, whether it worked, what changed, what remains risky, and what happens next.
8. **Fail closed on uncertainty.** Ambiguous identity, stale/missing data, unknown broker/order state, invalid geometry, or uncertain mutation state blocks advancement until reconciled.
9. **PAPER does not imply LIVE.** LIVE remains a separate final authority decision.
10. **No automatic cross-broker failover.** Broker switching remains explicit and reconciled.

## 5. Data, research, and execution standards

### 5.1 Data integrity

- preserve provider-native ticker text/case and stable point-in-time identity;
- do not project current survivors backward;
- quarantine ambiguity rather than guess;
- finalized canonical facts outrank provisional/live observations;
- no fabricated pre-2021 intraday history;
- resumable/idempotent acquisition, deterministic lineage, duplicate protection, and independent validation remain mandatory.

Accepted historical boundary remains Alpaca daily through `2021-08-13` and Massive from `2021-08-16` onward.

### 5.2 Strategy/alpha research

New strategy research should use production-path-native observations and evaluate **economic edge**, not just classification accuracy or win rate.

As applicable, methodology must include:

- chronological walk-forward/development/internal/protected separation;
- purge/embargo for overlapping outcomes;
- session/cross-sectional dependence handling and block bootstrap where appropriate;
- realistic spread, slippage, commissions/fees, borrow/locate, and option execution costs;
- sample-size and concentration controls;
- year, market-regime, volatility/liquidity-regime, and direction robustness;
- multiple-testing/selection-bias control and explicit backtest-overfitting diagnostics where useful;
- comparison with simple benchmarks/baselines;
- fully reproducible frozen definitions before protected evidence is inspected.

A profitable-looking mean alone is insufficient. Conversely, a useful edge does not have to win every trade or every short interval; acceptance must be based on preregistered economic and robustness criteria appropriate to the strategy.

### 5.3 Community/market hypothesis backlog

ATLAS may deliberately research ideas widely used or discussed by quantitative, stock, and options traders, including:

- cross-sectional and sector-relative strength;
- momentum/trend and volatility-normalized trend;
- volatility/liquidity-conditioned mean reversion;
- gaps, opening-range behavior, VWAP relationship, RVOL/volume expansion, and continuation/reversal structures when authoritative intraday data support them;
- market breadth and multi-timeframe agreement/disagreement;
- event/earnings continuation or reversal when point-in-time event data are authoritative;
- stock-versus-options selection using expected move, realized versus implied volatility, IV level/rank, skew, term structure, Greeks, liquidity, bid/ask spread, volume/open interest, DTE, and event/assignment/dividend risk;
- defined-risk option structures where they improve expected utility/risk efficiency versus a single option or stock position.

These are hypotheses to test, not assumptions to encode as profitable facts.

### 5.4 Risk and execution

The system must optimize for **after-cost risk-adjusted account growth**, not isolated trade return.

Trade/portfolio evaluation should measure as appropriate: net expectancy, return distribution, drawdown, tail loss, volatility-adjusted return, profit factor, payoff ratio, hit rate, turnover/cost drag, exposure, concentration/correlation, liquidity/capacity, and risk of ruin. Options require explicit Greek/volatility/expiration/assignment and execution-risk treatment.

Execution must preserve deterministic IDs, pre-trade risk limits, quote/data freshness, idempotency, reconciliation, duplicate-submit prevention, partial-fill/cancel handling, kill/disable capability, and auditable state transitions.

## 6. Audit of work completed through Phase25

The project has built a substantial amount of useful foundation; this work is not discarded.

### Phases 1–10 — data/discovery/model foundation

Accepted capabilities include project/config/session foundations, restartable provider ingestion, canonical Parquet/DuckDB market data, point-in-time instrument identity/history, live market state, 33 deterministic features, point-in-time universe eligibility, broad discovery with hysteresis, market/sector/ticker regimes, and conventional ML probability/evaluation.

### Historical extension

Accepted controlled Alpaca raw-SIP daily history extends the daily analytical foundation to 2016 without fabricating unavailable historical intraday bars.

### Phases 11–14 — decision/research stack

Accepted capabilities include strategy catalog/evaluation and regime routing, promoted-only analogue/scenario research, context/news/options/instrument/geometry/portfolio-risk planning, and independent AI audit/alert artifacts.

### Phases 15–22 — execution and operations foundation

Accepted capabilities include broker-neutral SHADOW/PAPER execution, Webull-primary/Alpaca-manual-secondary architecture, browser/API operational primitives, provider read readiness, real Webull sandbox submit/cancel lifecycle evidence, paper/shadow observability, restart-safe orchestration, one centralized default-deny PAPER submit authority seam, and the routine Webull-primary PAPER runner.

### Phase23 — current analytical production binding

ATLAS gained a routine finalized-session analytical path from current Massive/reference data through canonical/features/discovery/regimes/ML/current strategy evaluation into the existing downstream stack. The accepted run produced legitimate zero promotions because no strategy had SUPPORTED authority.

### Phase24 — bounded strategy challenger

Twenty-eight variants were tested under stronger methodology. Zero earned selection/support. The result was negative evidence, not a software failure.

### Phase25 — historical production-path route fidelity

ATLAS reconstructed the actual production candidate/routing population and tested whether the old broad research population had hidden incumbent edge. It did not: all incumbent strategies still failed core economic/robustness tests. Phase11 remains SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5.

### Audit conclusion

**The architecture and end goal remain on track, but the project did drift in presentation and phase mechanics.** Phases 23–25 were a justified analytical detour caused by a real bottleneck—no validated strategy edge—but the master roadmap was not re-baselined clearly, and internal research sub-gates became too visible as project progress.

The primary bottleneck is now **validated alpha**, not missing execution plumbing. The remaining roadmap is therefore re-centered on proving edge first and then proving the whole system can turn that edge into safe, profitable-after-cost operation.

## 7. Phase = gate execution model

**Starting with Phase26, the numbered phase itself is the project gate.**

A phase may contain work packages, checkpoints, preregistration steps, development tests, research splits, or protected-evidence steps. These are **not separate project gates** and should not be presented to the operator as if they were independent phases.

Normal flow:

`DEFINE/LOCK PHASE -> IMPLEMENT ALL COHERENT WORK -> DEVELOPMENT/FOCUSED TESTING -> COMPLETE PHASE-END ACCEPTANCE SUITE -> DOCUMENT RESULT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

A phase is accepted only after its **full end-of-phase gate** passes. See `docs/phase_flow.md` for the exact validation contract.

Research phases can finish with a scientifically negative result and still be accepted if the frozen question was answered correctly. Negative evidence never grants trading authority.

## 8. Remaining master roadmap

### Phase26 — Production-Path-Native Alpha Discovery & Validation

**Purpose:** solve the current bottleneck: ATLAS has no SUPPORTED strategy.

Build an exact research population directly from accepted Phase25 production-path identities/context and canonical features/outcomes. Research materially different architectures rather than another threshold sweep of failed v1/v2 families. Long and short designs are independent.

Phase26 may evaluate the hypothesis backlog above plus other preregistered evidence-based designs. Deterministic rules, statistical/composite models, and conventional ML may be compared where appropriate, but complexity must earn its keep against simpler baselines.

Before protected performance inspection, freeze search space, outcomes, economic assumptions, chronology, dependence handling, robustness requirements, and multiplicity/selection-bias handling. Legacy 10 bps/25 bps cost assumptions remain useful comparators for equity research where applicable, but final candidate economics must use realistic instrument/strategy-specific costs.

**Phase-end gate:** full software/regression/CI validation plus independent research validation and protected out-of-sample confirmation for any finalist.

**Authority on success:** Phase26 may replace the Phase11 support map only for strategies that satisfy its predeclared acceptance standard. It creates no broker/PAPER/LIVE authority.

**If no strategy earns support:** accept the negative result, do not move toward LIVE, and define the next alpha-research phase from the documented failure modes rather than weakening thresholds.

### Phase27 — Signal-to-Trade Construction & Portfolio Optimization

**Entry condition:** at least one strategy has accepted SUPPORTED authority.

Convert validated signal evidence into the best executable account decision using existing Phase12/13/14 capabilities rather than rebuilding them.

For each candidate determine PASS versus trade, stock versus option/defined-risk structure where applicable, direction, entry method, stop/invalidation, target/exit logic, holding horizon/DTE, quantity, and portfolio admission. Explicitly model liquidity, expected slippage/cost, IV/realized volatility, skew/term structure, Greeks, earnings/events, assignment/dividend risk, correlation, concentration, buying power, total portfolio heat, and drawdown controls.

The optimizer must be allowed to choose **no trade** when the available instrument does not preserve the underlying edge after cost/risk.

**Phase-end gate:** complete deterministic and independent tests demonstrating valid geometry, sizing, options/risk handling, portfolio constraints, and reproducible trade plans across normal and adverse cases. No LIVE authority.

### Phase28 — End-to-End Historical Replay & Stress Certification

Run the full trading decision pipeline historically as one account-level system using frozen supported strategies and Phase27 construction/risk rules.

Evaluate realistic execution/cost assumptions and compare against declared benchmarks. Measure account-equity behavior and trade-level economics, including net expectancy, drawdown/tail loss, risk-adjusted return, turnover/cost drag, concentration, regime/year behavior, and capacity/liquidity. Stress high-volatility, crash, gap, low-liquidity, stale/missing-data, and execution-degradation scenarios. Options paths must include spread/slippage and expiration/assignment-specific risk where relevant.

**Phase-end gate:** predeclared portfolio/economic robustness requirements plus full software/regression/CI/reproducibility evidence. Historical success alone still does not authorize LIVE.

### Phase29 — Prospective SHADOW/PAPER Certification

Operate the accepted end-to-end system on genuinely new, previously unseen market sessions using SHADOW and Webull-primary PAPER execution. Alpaca remains manual secondary.

The prospective evidence window and minimum evidence requirements are frozen before results are known. The system is not allowed to lower thresholds or force trades to reach a trade-count target.

Validate decision timing, data freshness, signal generation, instrument selection, risk sizing, order creation, fills/reconciliation, idempotency, latency, expected-versus-observed execution cost, failures/restarts, and the prospective economic behavior of the strategy set.

**Phase-end gate:** full cross-platform/target-machine certification and prospective evidence review. PAPER success still does not authorize LIVE.

### Phase30 — Outcomes, Learning, Drift Monitoring & Governance

Complete the original learning objective: every decision, rejected candidate, trade plan, order, fill, position, exit, and realized outcome must be traceable to exact data/model/strategy/risk versions.

Measure MAE/MFE, slippage, realized P&L, forecast calibration, strategy/regime performance, options/instrument-selection quality, drift, and degradation. Define retraining/research/revalidation triggers.

Learning is **governed**, not self-authorizing: ATLAS may detect that a model/strategy needs review, but it may not silently alter production thresholds, support, sizing, or model versions.

**Phase-end gate:** complete lineage/outcome reconciliation, monitoring tests, drift-trigger validation, rollback/versioning tests, and full regression/CI.

### Phase31 — Production Operations & Browser Control Plane

Turn the accepted trading system into the intended routine product without changing its analytical authority.

Consolidate the browser control plane, operational health, candidate/case reasoning, Engine-vs-AI review, alerts, positions/orders/outcomes, broker selection, paper/live mode controls, risk/deployment settings, run controls, audit history, and failure/recovery surfaces. Existing accepted browser components are reused.

Promote PostgreSQL operational state and autonomous scheduling only here and only if behavioral parity, restart/recovery safety, idempotency, and auditability are proven. The dedicated ATLAS host/browser deployment remains a control surface over the Python engine rather than a second trading engine.

User-adjustable settings must remain inside explicitly safe bounds; changing a UI setting cannot bypass evidence, geometry, broker, portfolio-risk, or LIVE-authority rules.

**Phase-end gate:** complete system, security, restart/recovery, scheduler, state-store, browser, cross-platform and target-deployment validation.

### Phase32 — LIVE Readiness, Reconciliation & Failure Certification

**No LIVE trading authority yet.**

Prove the exact production failure controls needed before real capital is exposed: pre-open/continuous/end-of-day reconciliation, open-order/position consistency, partial fills, cancel/replace races, stale quotes/data, broker/provider outages, process restarts, duplicate prevention, account/buying-power drift, corporate-action/event handling where relevant, daily/portfolio loss limits, emergency disable/flatten procedures, and manual broker fallback.

Define the initial LIVE capital/risk envelope and rollback criteria before any real-money activation.

**Phase-end gate:** adversarial/failure-injection tests, full regression/CI, target provider/broker readiness evidence, and explicit independent reconciliation certification. LIVE remains disabled after this phase until Phase33 authority is granted.

### Phase33 — Controlled LIVE Activation & Evidence-Based Scaling

This is the final planned build/authority phase.

Enable LIVE only through explicit external authorization using a deliberately small initial capital/risk envelope, hard per-trade/portfolio/daily-loss limits, real-time health/reconciliation monitoring, kill/disable capability, manual fallback, and no automatic broker failover.

Compare actual LIVE decisions, fills, slippage, costs, P&L distribution, and operational behavior with Phase28/29 expectations. Any material mismatch can pause/disable LIVE without waiting for further losses.

Capital scaling is gradual and evidence-based. Increasing capital does not permit strategy/model/risk logic to change silently; such changes require a separately accepted future phase.

**Phase-end gate:** controlled LIVE evidence demonstrates that the accepted system behaves within its predeclared operational/risk tolerances. After acceptance, ATLAS enters governed production/maintenance rather than endless feature-building.

## 9. Progression rule

The roadmap is **conditional, not schedule-driven**.

- Phase26 is the current phase.
- Phases27–33 describe the intended route to production.
- If a required entry condition fails—especially validated alpha—downstream trading phases pause.
- A new numbered research/repair phase may be inserted only when evidence identifies a real blocker. The roadmap must be updated explicitly at that time; future chats must not silently redefine the sequence.
- Accepted negative research is valuable, but it does not justify skipping the missing requirement.

## 10. Plain-English phase closeout contract

Every phase closeout delivered to the operator must begin with these seven items before detailed metrics:

1. **Goal:** what question/capability this phase was responsible for.
2. **Built:** what materially changed.
3. **Full gate:** PASS or FAIL, including full regression and CI status.
4. **Evidence meaning:** what the results mean in ordinary language.
5. **Trading/authority change:** exactly what ATLAS can do now that it could not do before, or `NONE`.
6. **Limitations/risks:** what is still unproven or blocked.
7. **Next phase:** exact next objective and why it follows.

Raw hashes, row counts, fingerprints, p-values, CI IDs, and validator details remain available underneath for auditability, but they are not a substitute for the seven-item explanation.

## 11. Persistent safety boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never synthesize unavailable history; finalized facts outrank provisional state; unknown/uncertain state fails closed; uncertain mutations require reconciliation before retry; valid geometry and portfolio risk are mandatory; AI never creates authority; automatic broker failover remains disabled; PAPER never implies LIVE; and LIVE authority exists only after Phase33 acceptance.
