# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-baselined: 2026-08-26. Updated for GUI/web/deployment and plain-English phase communication.**

This document controls the long-term destination, anti-drift rules, remaining phase sequence, GUI/web/deployment path, and phase acceptance model for ATLAS. Accepted code/evidence on `main` controls what already exists; this roadmap controls what the project is trying to become and what must happen next.

Future continuation order:

1. this roadmap — mission, architecture, anti-drift rules, GUI/web/deployment path, remaining phases;
2. `docs/current_status.md` — exact repository/current-phase handoff;
3. the active phase specification — frozen scope and acceptance criteria;
4. `docs/phase_flow.md` — how a phase is developed and accepted;
5. `docs/phase_plain_english_contract.md` — required operator-facing phase-start/phase-end explanation;
6. accepted code, validators, CI/PR evidence, and older phase documents for implementation detail/provenance.

When older documents conflict with accepted `main` or this roadmap, accepted `main` controls historical fact and this roadmap controls future direction.

## 1. Mission and end goal

ATLAS is the **Autonomous Trading, Learning, and Analysis System** and the greenfield successor to Chart Monitor.

The practical end goal is:

> **Use trustworthy market evidence, validated quantitative edge, disciplined risk management, appropriate stock/options trade construction, reliable execution, and outcome learning to make educated trades with the objective of growing account equity and producing profit over time after realistic costs.**

Profit is never guaranteed. ATLAS is not judged by trade count, alert count, or impressive-looking backtests. It is judged by whether its decisions have defensible positive expected value after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

Capital growth is the objective. Capital preservation and controlled risk are constraints required for compounding.

## 2. Original intent preserved

The earliest Chart Monitor 2.0 concept was already a browser-operated stock/options research system: refresh trustworthy data, determine market/ticker context, evaluate appropriate strategies, form a directional thesis, incorporate events/news, evaluate option structures, simulate likely outcomes, show transparent scoring/reasoning, independently review the deterministic case with AI, and archive predictions/outcomes for later calibration.

That correctly evolved into ATLAS: broad-market discovery, point-in-time historical evidence, conventional ML probability estimates, deterministic regime routing, promoted-only expensive research, portfolio-aware trade construction, broker execution, outcome learning, and an operational browser/web control plane.

The destination has not changed: **find defensible opportunities, decide whether and how to trade them, control risk, execute safely, present the system clearly to the operator, and learn whether the decisions actually made money.**

## 3. Locked architecture

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> candidate promotion -> analogue/scenario/news research -> stock/options instrument selection -> entry/exit/geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome/performance learning -> browser/web control plane -> production deployment/operations`

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
- **Browser/web GUI**: the intended operator experience for monitoring, understanding, configuring, and invoking accepted operations. It is not a second trading engine.
- **Deployment/runtime**: packages the accepted engine, API, web application, persistence, scheduler, logging, recovery, and security into a routine operating system only after the appropriate phase earns that capability.

## 4. Anti-drift rules

Every phase and implementation decision must answer: **does this materially improve ATLAS's ability to identify, construct, execute, control, understand, measure, or learn from profitable-risk-adjusted trades?**

The following are mandatory:

1. **Alpha before unnecessary plumbing.** Once required safety/foundation capability exists, the current trading bottleneck takes priority over lower-value infrastructure work.
2. **No activity target.** Zero candidates/trades can be correct. Thresholds are never weakened merely to create trades.
3. **No backtest theater.** Point-in-time data, realistic costs, leakage controls, chronological evaluation, dependence-aware statistics, multiplicity/selection-bias controls, protected evidence, and reproducibility are required.
4. **No silent self-modification.** Models, strategies, thresholds, and support states change only through explicit versioned evidence and a later accepted phase.
5. **No community idea receives special treatment.** Ideas from traders/options communities are hypothesis sources, not evidence. They must survive the same validation as internally generated ideas.
6. **Reuse accepted components.** Later phases integrate/strengthen accepted capabilities rather than rebuilding parallel pipelines without measured cause.
7. **Plain-English operator visibility.** Every phase starts and ends with an understandable explanation before technical evidence.
8. **GUI is a first-class product surface, not a separate authority.** Web development is planned and tested, but frontend code cannot duplicate/bypass trading, risk, broker, or LIVE controls.
9. **Deployment is engineered, not improvised.** Service startup, persistence, configuration, security, logging, backup/recovery, restart behavior, and rollback must be tested when introduced.
10. **Fail closed on uncertainty.** Ambiguous identity, stale/missing data, unknown broker/order state, invalid geometry, or uncertain mutation state blocks advancement until reconciled.
11. **PAPER does not imply LIVE.** LIVE remains a separate final authority decision.
12. **No automatic cross-broker failover.** Broker switching remains explicit and reconciled.

## 5. Data, research, execution, GUI, and deployment standards

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

A profitable-looking mean alone is insufficient. A useful edge also does not have to win every trade; acceptance is based on preregistered economic and robustness criteria appropriate to the strategy.

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

### 5.5 GUI/web-development standards

The GUI/browser application is part of the intended finished product and is developed progressively as backend outputs stabilize.

Mandatory principles:

- frontend pages consume versioned backend/API contracts rather than reimplementing analytical logic;
- trade direction, support status, geometry, sizing, risk admission, broker mutations, and LIVE authority remain backend-controlled;
- the UI must distinguish read-only information from action-capable controls;
- Engine evidence and AI audit remain separately visible;
- candidate funnel, trade plan, risk, broker/order/position state, failures, and outcome/performance evidence must be understandable to the operator;
- safe configuration controls may exist only inside explicit backend-enforced limits;
- web security, permissions, CSRF/same-origin/session handling as applicable, input validation, audit logging, and idempotency are tested before action-capable deployment;
- development/test/PAPER/LIVE deployment mode must be visible and difficult to confuse.

### 5.6 Deployment/operations standards

Deployment is part of the roadmap and must eventually cover:

- reproducible environment/setup and dependency locking;
- service/process management and automatic restart behavior;
- persistent operational state and migrations;
- scheduler/recurring-run integration;
- secure configuration/secret handling;
- browser/API exposure and network/security boundaries;
- structured logging, health checks, metrics, audit logs, and failure visibility;
- backups/recovery/rollback and restart-safe behavior;
- host installation/update/upgrade procedure;
- version visibility so the operator can identify the exact deployed engine/UI/model/strategy versions;
- SHADOW/PAPER/LIVE mode isolation and emergency disable controls.

The production deployment must run the accepted Python engine; it must not create a separate web-only implementation of trading logic.

## 6. Audit of work completed through Phase25

The project has built substantial useful foundation; this work is not discarded.

### Phases 1–10 — data/discovery/model foundation

Accepted capabilities include project/config/session foundations, restartable provider ingestion, canonical Parquet/DuckDB market data, point-in-time instrument identity/history, live market state, 33 deterministic features, point-in-time universe eligibility, broad discovery with hysteresis, market/sector/ticker regimes, and conventional ML probability/evaluation.

### Historical extension

Accepted controlled Alpaca raw-SIP daily history extends the daily analytical foundation to 2016 without fabricating unavailable historical intraday bars.

### Phases 11–14 — decision/research stack

Accepted capabilities include strategy catalog/evaluation and regime routing, promoted-only analogue/scenario research, context/news/options/instrument/geometry/portfolio-risk planning, and independent AI audit/alert artifacts.

### Phases 15–22 — execution, browser, and operations foundation

Accepted capabilities include broker-neutral SHADOW/PAPER execution, Webull-primary/Alpaca-manual-secondary architecture, browser/API operational primitives, provider read readiness, real Webull sandbox submit/cancel lifecycle evidence, paper/shadow observability, restart-safe orchestration, one centralized default-deny PAPER submit authority seam, and the routine Webull-primary PAPER runner.

### Phase23 — current analytical production binding

ATLAS gained a routine finalized-session analytical path from current Massive/reference data through canonical/features/discovery/regimes/ML/current strategy evaluation into the existing downstream stack. The accepted run produced legitimate zero promotions because no strategy had SUPPORTED authority.

### Phase24 — bounded strategy challenger

Twenty-eight variants were tested under stronger methodology. Zero earned selection/support. The result was negative evidence, not a software failure.

### Phase25 — historical production-path route fidelity

ATLAS reconstructed the actual production candidate/routing population and tested whether the old broad research population had hidden incumbent edge. It did not: all incumbent strategies still failed core economic/robustness tests. Phase11 remains SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5.

### Audit conclusion

**The architecture and end goal remain on track, but the project did drift in presentation and phase mechanics.** Phases23–25 were a justified analytical detour caused by a real bottleneck—no validated strategy edge—but internal research sub-gates became too visible as project progress.

The primary bottleneck is now **validated alpha**. GUI/web/deployment remain required end-product work, but they progress in parallel only where doing so does not displace the current alpha critical path.

## 7. Phase = gate execution and communication model

**Starting with Phase26, the numbered phase itself is the project gate.**

A phase may contain work packages, checkpoints, preregistration steps, development tests, research splits, UI prototypes, deployment experiments, or protected-evidence steps. These are **not separate project gates**.

Normal flow:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK PHASE -> IMPLEMENT ALL COHERENT WORK -> DEVELOPMENT/FOCUSED TESTING -> COMPLETE PHASE-END ACCEPTANCE SUITE -> PLAIN-ENGLISH PHASE END -> DOCUMENT RESULT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

A phase is accepted only after its full end-of-phase gate passes. Research phases may end ACCEPTED-NEGATIVE if the frozen scientific question was answered correctly. Negative evidence grants no downstream authority.

The required communication format is defined in `docs/phase_plain_english_contract.md`.

## 8. Progressive GUI/web/deployment track

GUI/web/deployment work is deliberately spread across the remaining roadmap instead of being deferred entirely to the end:

- **Phase26:** alpha remains the critical path; identify only the data/API/view contracts needed for future operator visibility where useful. No major frontend build should slow the research bottleneck.
- **Phase27:** stabilize case/trade/risk outputs into web-facing contracts and build read-only interface prototypes for candidate/trade-plan/risk inspection.
- **Phase28:** build historical replay/stress dashboard views so account behavior, drawdowns, regimes, trade decisions, and stress results are visually inspectable.
- **Phase29:** run a SHADOW/PAPER operator web beta showing runs, candidates, complete cases, AI review, paper orders/positions, alerts, failures, health, and reconciliation. Only already-accepted PAPER actions may be exposed.
- **Phase30:** add outcome/performance/learning dashboards for P&L, MAE/MFE, slippage, calibration, strategy/regime performance, drift, and degradation.
- **Phase31:** consolidate the complete production web application and perform real deployment engineering: persistent operational state, scheduler, services, secure configuration, logging, recovery, backup, host setup, updates, and operator documentation.
- **Phase32:** harden the deployed stack under outages, restarts, stale data, broker/provider failures, reconciliation faults, and emergency procedures.
- **Phase33:** expose controlled LIVE activation/disable, risk-envelope visibility, reconciliation/health, and evidence-based scaling through the production control plane without allowing the frontend to bypass backend authority.

## 9. Remaining master roadmap

### Phase26 — Production-Path-Native Alpha Discovery & Validation

**Purpose:** solve the current bottleneck: ATLAS has no SUPPORTED strategy.

Build an exact research population directly from accepted Phase25 production-path identities/context and canonical features/outcomes. Research materially different architectures rather than another threshold sweep of failed v1/v2 families. Long and short designs are independent.

Phase26 may evaluate the hypothesis backlog above plus other preregistered evidence-based designs. Deterministic rules, statistical/composite models, and conventional ML may be compared where appropriate, but complexity must earn its keep against simpler baselines.

Before protected performance inspection, freeze search space, outcomes, economic assumptions, chronology, dependence handling, robustness requirements, and multiplicity/selection-bias handling. Legacy 10 bps/25 bps cost assumptions remain useful comparators for equity research where applicable, but final candidate economics must use realistic instrument/strategy-specific costs.

Web work in Phase26 is limited to documenting/stabilizing research output contracts needed later; it must not displace alpha discovery.

**Phase-end gate:** full software/regression/CI validation plus independent research validation and protected out-of-sample confirmation for any finalist.

**Authority on success:** Phase26 may replace the Phase11 support map only for strategies that satisfy its predeclared acceptance standard. It creates no broker/PAPER/LIVE authority.

**If no strategy earns support:** accept the negative result, do not move toward LIVE, and define the next alpha-research phase from the documented failure modes rather than weakening thresholds.

### Phase27 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** at least one strategy has accepted SUPPORTED authority.

Convert validated signal evidence into the best executable account decision using existing Phase12/13/14 capabilities rather than rebuilding them.

For each candidate determine PASS versus trade, stock versus option/defined-risk structure where applicable, direction, entry method, stop/invalidation, target/exit logic, holding horizon/DTE, quantity, and portfolio admission. Explicitly model liquidity, expected slippage/cost, IV/realized volatility, skew/term structure, Greeks, earnings/events, assignment/dividend risk, correlation, concentration, buying power, total portfolio heat, and drawdown controls.

The optimizer must be allowed to choose **no trade** when the available instrument does not preserve the underlying edge after cost/risk.

Stabilize the backend/API/view-model contract for candidate evidence, deterministic trade plan, AI audit, risk decision, and PASS/no-trade reason. Build a read-only web prototype against those real contracts so the operator can inspect a complete case without giving the GUI new trading authority.

**Phase-end gate:** deterministic and independent tests for geometry, sizing, options/risk handling, portfolio constraints, reproducible plans, API/view contracts, and read-only UI correctness. No LIVE authority.

### Phase28 — End-to-End Historical Replay & Stress Certification + Replay Dashboard

Run the full trading decision pipeline historically as one account-level system using frozen supported strategies and Phase27 construction/risk rules.

Evaluate realistic execution/cost assumptions and declared benchmarks. Measure account-equity behavior and trade-level economics, including net expectancy, drawdown/tail loss, risk-adjusted return, turnover/cost drag, concentration, regime/year behavior, and capacity/liquidity. Stress high-volatility, crash, gap, low-liquidity, stale/missing-data, and execution-degradation scenarios. Options paths must include spread/slippage and expiration/assignment-specific risk where relevant.

Build replay/stress dashboard views backed by the same accepted results so the operator can visually inspect equity curve, drawdowns, trades, regime changes, candidate decisions, rejected trades, and stress outcomes.

**Phase-end gate:** predeclared portfolio/economic robustness requirements plus full software/regression/CI/reproducibility and replay-dashboard data-integrity/UI tests. Historical success alone still does not authorize LIVE.

### Phase29 — Prospective SHADOW/PAPER Certification + Operator Web Beta

Operate the accepted end-to-end system on genuinely new, previously unseen market sessions using SHADOW and Webull-primary PAPER execution. Alpaca remains manual secondary.

The prospective evidence window and minimum evidence requirements are frozen before results are known. The system is not allowed to lower thresholds or force trades to reach a trade-count target.

Validate decision timing, data freshness, signal generation, instrument selection, risk sizing, order creation, fills/reconciliation, idempotency, latency, expected-versus-observed execution cost, failures/restarts, and prospective economics.

Run an operator web beta that displays current runs, candidate funnel, complete deterministic case, Engine-vs-AI review, risk/sizing, PAPER orders/positions, alerts, failures, health, and reconciliation. The beta may invoke only explicitly accepted SHADOW/PAPER operations through backend authority seams; LIVE remains unavailable.

**Phase-end gate:** full cross-platform/target-machine certification, prospective evidence review, UI/API permission tests, PAPER action/idempotency tests, and web beta stability/recovery testing. PAPER success still does not authorize LIVE.

### Phase30 — Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI

Complete the original learning objective: every decision, rejected candidate, trade plan, order, fill, position, exit, and realized outcome must be traceable to exact data/model/strategy/risk versions.

Measure MAE/MFE, slippage, realized P&L, forecast calibration, strategy/regime performance, options/instrument-selection quality, drift, and degradation. Define retraining/research/revalidation triggers.

Add operator dashboards for account performance, trade outcomes, expected-versus-realized behavior, strategy/regime performance, calibration, drift, degradation alerts, and version lineage.

Learning is **governed**, not self-authorizing: ATLAS may detect that a model/strategy needs review, but it may not silently alter production thresholds, support, sizing, or model versions.

**Phase-end gate:** complete lineage/outcome reconciliation, monitoring tests, drift-trigger validation, rollback/versioning tests, dashboard correctness, and full regression/CI.

### Phase31 — Production Web Application, Operations & Deployment

Turn the accepted trading system and accumulated web prototypes into the intended routine product without changing its analytical authority.

Build/consolidate the complete web application: operator dashboard, market/system health, candidate funnel, full case reasoning, Engine-vs-AI review, alerts, positions/orders/outcomes, broker selection, SHADOW/PAPER/LIVE mode visibility, risk/configuration controls, run controls, audit history, failures/recovery, learning/performance views, and deployment/version status.

Promote PostgreSQL operational state and autonomous scheduling only here and only if behavioral parity, restart/recovery safety, idempotency, and auditability are proven.

Perform production deployment engineering for the intended ATLAS host/environment: environment/bootstrap process, service/process management, API/web serving, secure configuration/secrets, persistence/migrations, scheduler, logs/health/metrics, backups/recovery, startup/shutdown/restart, update/rollback procedure, and operator documentation.

The deployed browser remains a control surface over the Python engine rather than a second trading engine. User-adjustable settings remain inside backend-enforced safe bounds.

**Phase-end gate:** complete GUI/web/API, security, permission, restart/recovery, scheduler, state-store, migration, logging, backup/restore, deployment, cross-platform and target-host validation.

### Phase32 — LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification

**No LIVE trading authority yet.**

Harden the exact deployed production stack under the failures that matter before real capital is exposed: pre-open/continuous/end-of-day reconciliation, open-order/position consistency, partial fills, cancel/replace races, stale quotes/data, broker/provider outages, network/API/UI failures, service/process restarts, database/persistence issues, duplicate prevention, account/buying-power drift, corporate-action/event handling where relevant, daily/portfolio loss limits, emergency disable/flatten procedures, and manual broker fallback.

Verify that the GUI accurately reports degraded/unsafe state and cannot hide, override, or work around backend fail-closed decisions.

Define the initial LIVE capital/risk envelope and rollback criteria before any real-money activation.

**Phase-end gate:** adversarial/failure-injection tests across engine/API/UI/deployment, full regression/CI, target host/provider/broker readiness evidence, backup/recovery validation, and explicit independent reconciliation certification. LIVE remains disabled after this phase until Phase33 authority is granted.

### Phase33 — Controlled LIVE Activation & Evidence-Based Scaling through the Production Control Plane

This is the final planned build/authority phase.

Enable LIVE only through explicit authorization using a deliberately small initial capital/risk envelope, hard per-trade/portfolio/daily-loss limits, real-time health/reconciliation monitoring, kill/disable capability, manual fallback, and no automatic broker failover.

Expose LIVE state, authority, risk envelope, positions/orders, reconciliation, health, emergency disable, and scaling evidence through the production GUI. The frontend can request only backend-authorized operations and cannot expand its own authority.

Compare actual LIVE decisions, fills, slippage, costs, P&L distribution, and operational behavior with Phase28/29 expectations. Any material mismatch can pause/disable LIVE without waiting for further losses.

Capital scaling is gradual and evidence-based. Increasing capital does not permit strategy/model/risk logic to change silently; such changes require a separately accepted future phase.

**Phase-end gate:** controlled LIVE evidence demonstrates that the accepted deployed engine + API + GUI behave within predeclared operational/risk tolerances. After acceptance, ATLAS enters governed production/maintenance rather than endless feature-building.

## 10. Progression rule

The roadmap is **conditional, not schedule-driven**.

- Phase26 is the current phase.
- Phases27–33 describe the intended route to production, including the progressive GUI/web/deployment track.
- If a required entry condition fails—especially validated alpha—downstream trading phases pause.
- UI work may proceed only to the extent that it does not falsely imply unavailable trading authority or displace the active critical-path requirement.
- A new numbered research/repair phase may be inserted only when evidence identifies a real blocker. The roadmap must be updated explicitly at that time; future chats must not silently redefine the sequence.
- Accepted negative research is valuable, but it does not justify skipping the missing requirement.

## 11. Plain-English phase start and end contract

Every phase must begin with an operator-facing explanation covering:

1. where ATLAS is now;
2. what the phase is trying to accomplish;
3. why it matters to account growth/profit;
4. what will be built/changed;
5. what will be tested at the end;
6. what success means;
7. what happens if the phase fails/returns a negative result;
8. what is explicitly not happening yet.

Every phase closeout must begin with:

1. **Goal**;
2. **What we built**;
3. **Did the full phase gate pass?**;
4. **What the results mean**;
5. **What ATLAS can do now**;
6. **What is still missing/risky**;
7. **Where this leaves the project**;
8. **What happens next**.

When GUI/web/deployment is involved, both explanations must also state what the operator can see/control, whether the interface is read-only or action-capable, the deployment maturity/environment, and the authority/security boundaries still in force.

Raw hashes, row counts, fingerprints, p-values, CI IDs, validator outputs, and deployment logs remain available underneath for auditability but never replace the plain-English explanation.

## 12. Persistent safety boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never synthesize unavailable history; finalized facts outrank provisional state; unknown/uncertain state fails closed; uncertain mutations require reconciliation before retry; valid geometry and portfolio risk are mandatory; AI never creates authority; frontend/UI controls never create or bypass authority; automatic broker failover remains disabled; PAPER never implies LIVE; and LIVE authority exists only after Phase33 acceptance.