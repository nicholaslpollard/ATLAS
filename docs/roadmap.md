# ATLAS Master Roadmap

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This document is the project-level direction lock: implementation may evolve when evidence requires it, but changes must preserve the architectural boundaries below unless an explicit design decision replaces them.

## 1. Mission

Build a broad-market discovery, quantitative analysis, decision-support, learning, and eventually automated-trading platform that can:

1. observe a large U.S. market universe;
2. maintain point-in-time-safe market data, instrument identity, features, and regimes;
3. discover promising candidates cheaply and quickly;
4. estimate outcome probabilities with conventional ML;
5. route candidates to strategies appropriate to current regime/context;
6. spend expensive research only on promoted candidates;
7. combine quantitative, historical-analogue, simulation, news/event/sentiment, instrument, and risk evidence into one case;
8. subject that case to an independent AI review rather than letting AI replace the deterministic engine;
9. construct an executable trade plan only after risk and geometry checks;
10. operate paper/shadow before live execution;
11. record outcomes so models, strategies, routing, and risk policies can be evaluated and improved;
12. expose the system through a browser control plane with clear reasoning, broker/mode controls, candidates, alerts, positions, and operational health.

The legacy Chart Monitor is preserved. ATLAS is the redesign/rebuild path; legacy components are not deleted merely because equivalent ATLAS functionality is introduced.

## 2. Target architecture

Primary flow:

`market/reference data -> Parquet data lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> strategy routing/evaluation -> candidate promotion -> historical analogue + Monte Carlo/simulation -> news/events/sentiment -> instrument selection -> entry/stop/target/horizon -> portfolio/risk -> consolidated case -> independent AI audit -> alert/paper/shadow/live execution -> outcome/performance learning -> browser control plane`

Target persistent operational state that does not belong in the analytical lake is PostgreSQL-backed. Parquet remains the durable analytical/historical format and DuckDB remains the local analytical query engine unless a later measured requirement justifies a change.

## 3. Non-negotiable boundaries

### Data and identity

- Preserve exact provider-native ticker text/case.
- Literal ticker text alone never proves identity continuity.
- Historical populations are observation-driven and point-in-time safe; current survivor state is not projected backward.
- Unresolved identity/structural evidence is quarantined or excluded rather than guessed.
- Long-running acquisition/replay jobs must be resumable, idempotent, and duplicate-safe.
- Provider/canonical/derived promotions require lineage and independent validation.
- Do not fabricate unavailable intraday history from daily bars.

### Discovery, regimes, and strategies

- Broad discovery is intentionally cheap and instrument-agnostic.
- Regime classification is context and routing evidence.
- Strategy-to-regime routing belongs in the router/orchestration layer, not hidden inside individual strategy implementations.
- Expensive analogue, Monte Carlo, options-chain, and deep contextual work runs only after candidate promotion.

### Machine learning

- The accepted conventional ML layer produces `p_down`, `p_neutral`, and `p_up` probability evidence.
- ML argmax is diagnostic only; it is **not** a trade signal.
- Chronological walk-forward evaluation, purge/embargo where required, leakage controls, immutable OOS predictions, and reproducibility remain mandatory.
- A new dataset/model never silently replaces an accepted production model. Challengers require separately versioned evidence and acceptance.
- The LLM/AI layer is not the predictive model.

### AI review

- AI receives the consolidated quantitative case and independently returns an approve/cautious/reject-style audit with grounded reasons, risks, and plan observations.
- AI may challenge engine conclusions, but it does not rewrite historical facts, probability outputs, or validation evidence.
- Engine evidence and AI review remain separately visible for auditability.

### Execution

- Webull is the planned primary execution broker for paper/sandbox and live operation.
- Alpaca is the manually selectable secondary/fallback broker, including low-capital fallback if Webull live API eligibility becomes unavailable.
- Broker adapters must be replaceable without changing strategy logic.
- Browser broker switching must first inspect open orders/positions, warn, optionally cancel/close only with explicit user action, reconcile exposure, and only then activate the selected broker.
- Live money is never the first validation environment: paper -> shadow/observation -> controlled live.

## 4. Accepted foundation through Phase 10

Phases 1-10 established the foundation required before strategy/execution work: project foundation, provider/canonical storage, instrument identity/history, live market state, feature engine, point-in-time universe registry, broad discovery, market/sector/ticker regime hierarchy, and conventional ML probability/evaluation.

Phase 10 is accepted. The accepted HGB model uses 33 point-in-time quantitative predictors and raw three-class probabilities. The protected final holdout passed all locked checks. The model remains a probability surface, not a strategy or execution signal.

## 5. Accepted historical extension

The post-Phase-10 historical-data work is a **foundation extension**, not a replacement roadmap phase.

Accepted source boundary:

- Alpaca raw SIP daily history: 2016-01-04 through the pre-Massive seam in August 2021.
- Massive production history: 2021-08-16 onward.
- No pre-2021 4h/1h data is synthesized from the Alpaca daily backfill.

The historical extension preserved the accepted Phase 10 production model while validating canonical history, feature state, regime replay, and longer-history challenger evidence independently. The longer-history C result remains separately versioned challenger/research evidence rather than silently replacing production authority. Its primary value is deeper regime/strategy/backtest/analogue evidence.

## 6. Accepted roadmap phases after the historical extension

Phases 11-16 have been implemented, independently validated at their authority boundaries, and merged. Their architectural responsibilities remain locked as follows.

### Phase 11 — Strategy Evaluation and Regime Routing

Build the strategy interface/catalog, deterministic regime router, historical strategy evaluation/backtesting, and candidate-promotion policy as one coherent phase. Consume the ML probability surface as evidence; never convert argmax directly into a trade.

Deliverable: promoted candidates with auditable strategy/regime/ML evidence, not broker orders.

### Phase 12 — Deep Candidate Research

For promoted candidates only, run historical analogue retrieval and Monte Carlo/scenario simulation. Preserve source windows, assumptions, comparable-state definitions, distributions, and failure modes.

Deliverable: expensive historical/scenario evidence attached to each promoted candidate.

### Phase 13 — Context, Instrument, Trade Geometry, and Portfolio Risk

Add richer news/events/sentiment, equities/options instrument selection, entry/stop/target/horizon construction, option alignment where applicable, portfolio exposure, sizing, concentration, liquidity, and risk controls.

Geometry must be valid before a case can advance (`LONG: stop < entry < target`; `SHORT: stop > entry > target`).

Deliverable: a complete deterministic case and proposed trade plan.

### Phase 14 — Independent AI Audit and Alerting

Create the structured AI reviewer and final case presentation. Show engine evidence versus AI audit, reasons, risk flags, and any plan disagreement. Produce alert artifacts/reporting only after deterministic validation.

Deliverable: auditable approved/cautious/rejected cases and alerts.

### Phase 15 — Broker Execution and Outcome Learning

Implement broker-neutral order/execution contracts, Webull primary and Alpaca fallback adapters, paper execution, shadow validation, controlled live mode, reconciliation, order/position lifecycle, performance/outcome storage, and post-trade attribution.

Deliverable: safe execution plus a learning/performance record that can evaluate probabilities, strategies, routing, risk, and realized outcomes.

### Phase 16 — Browser Control Plane and Production Operations

Expose system state through the browser: scan/run control, broker and paper/live mode, candidate funnel, complete case reasoning, AI review, alerts, orders/positions, performance, model/strategy versions, data freshness, failures, resumable jobs, and operational health.

Deliverable: production-operable ATLAS with transparent control and monitoring.

Phase 15/16 acceptance did **not** promote live money. Provider mutation, actual paper-provider order lifecycle testing, and live promotion remain separate operational authority checkpoints.

## 7. Accelerated delivery protocol

Quality gates remain; **micro-step ceremony does not**.

### Batch by evidence boundary

A normal implementation batch should include, where applicable:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status update`

These should usually land as one coherent work package rather than a separate conversational approval and commit for every small sub-step.

### Validation cadence

During a batch:

- run focused tests while changing code;
- run the full regression suite and cross-platform CI at the batch boundary;
- run independent validators for data promotion, model selection/registration, broker-state transitions, or other authority-changing operations;
- keep read-only diagnostics and preregistration checks automated inside the batch rather than turning each into a separate user stop point.

Independent validation is retained because it has already caught real semantic defects. The acceleration comes from automating and grouping the checks, not removing them.

### User interaction / local target-machine work

When local data or hardware evidence is required, provide one PowerShell block containing the smallest complete safe sequence for the batch, including the expected test count or other output landmarks. The user runs it locally and returns the complete output.

Stop for user input only when one of these is true:

1. required local/external evidence is unavailable to the repository/CI environment;
2. a validation fails and the result changes the technical decision;
3. an irreversible or production-authority write needs explicit operational approval;
4. a broker/live-money transition is involved;
5. a genuine product/design choice cannot be resolved from the locked architecture or measured evidence.

Otherwise continue autonomously through the batch.

### Evidence policy

- Do not invent thresholds to force acceptance; measure first or preregister the threshold before viewing decision data.
- Do not advance merely because code ran. Advance on test/validator/real-data evidence appropriate to the risk.
- Fail closed on ambiguous identity, lineage, missing data, broker state, or trade geometry.
- Preserve rollback artifacts for production data/state promotions.
- Keep PR descriptions or phase acceptance records as the concise evidence ledger; avoid duplicating the same status across dozens of documents.

## 8. Immediate priority

Complete **Phase 17 — Provider-Readonly Operational Readiness** as a bounded operational extension after accepted Phase 16.

Required acceptance boundary:

- reconcile real Webull sandbox and Alpaca paper accounts through read-only provider calls;
- keep credential/account values out of reports and logs;
- preserve the accepted Phase 16 artifacts unchanged and hash-bound;
- keep provider mutation disabled;
- keep live execution disabled;
- keep automatic cross-broker failover disabled;
- report open orders/positions without requiring a flat account merely to accept read-only readiness;
- fail closed if broker/account selection or reconciliation is ambiguous.

Webull sandbox account selection may be resolved locally and persisted only as local configuration; selecting an account is not trading authority.

After Phase 17 is accepted, the next authority boundary is a **separate explicitly authorized paper-provider mutation checkpoint**. That checkpoint may validate real paper/sandbox order lifecycle behavior under the already accepted Phase 15/16 safety contracts, but it must not silently enable live trading, automatic broker failover, or bypass reconciliation/risk/idempotency controls.