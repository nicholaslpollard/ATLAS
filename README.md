# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its end goal is to use trustworthy market evidence, validated quantitative edge, disciplined risk management, appropriate stock/options trade construction, reliable execution, and outcome learning to make educated trades with the objective of growing account equity and producing profit over time after realistic costs. Profit is never guaranteed; the system is designed to maximize decision quality and risk-adjusted expected account growth rather than trade frequency.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after separate acceptance, controlled LIVE operation.

## Start here — anti-drift order

Future ATLAS chats/work should read these in order before changing the system:

1. [`docs/roadmap.md`](docs/roadmap.md) — **normative mission, anti-drift rules, GUI/web/deployment path, and complete remaining roadmap**;
2. [`docs/current_status.md`](docs/current_status.md) — exact repository/current-phase handoff;
3. active phase specification — frozen scope/evidence/authority for the current phase;
4. [`docs/phase_flow.md`](docs/phase_flow.md) — **phase = acceptance gate** development contract;
5. [`docs/phase_plain_english_contract.md`](docs/phase_plain_english_contract.md) — required plain-English phase-start and phase-end explanation;
6. accepted code, validators, CI/PR evidence, and older phase documents for detailed provenance.

Accepted `main` controls what already exists. The master roadmap controls the intended destination and future sequence. Older phase documents never silently redefine either.

For the active Phase30, `docs/phase30_event_driven_public_information_alpha.md` preserves the original pre-performance feasibility contract and `docs/phase30_scientific_contract.md` contains the subsequently frozen scientific policy. The feasibility document intentionally remains historically unchanged after its target-machine PASS.

## Architecture

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> candidate promotion -> analogue/scenario/news research -> stock/options instrument selection -> entry/exit/geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome/performance learning -> browser/web control plane -> production deployment/operations`

Massive is primary market/reference. Webull is primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance. Alpaca is manual secondary only. ML is predictive/probability evidence, AI is an independent audit, and the browser/web application is the operator control surface rather than a parallel trading engine.

## Phase execution model

Starting with Phase26, **the numbered phase itself is the project gate**.

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK PHASE -> IMPLEMENT COHERENT WORK -> FOCUSED DEVELOPMENT TESTING -> FULL PHASE-END ACCEPTANCE GATE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT/REPAIR -> MERGE -> NEXT PHASE`

Internal research splits, checkpoints, development tests, feasibility steps, or protected-evidence steps are not separate project gates. Full regression, retained validators, Ubuntu/Windows CI, negative/recovery testing, independent validation, and target-machine/provider/broker evidence where required happen at the phase-end acceptance boundary.

## Required plain-English communication

At the start of every phase, explain where ATLAS is, what the phase is trying to accomplish, why it matters to the profit/account-growth goal, what will change, what will be tested, what success means, what a legitimate negative means, and what is explicitly not happening yet.

At the end of every phase, explain the goal, what was built, whether the full gate passed, practical meaning, actual new authority/capability or `NONE`, remaining risk/blockers, roadmap position, and exact next objective. Technical hashes/statistics follow as audit evidence; they never replace the operator explanation.

See [`docs/phase_plain_english_contract.md`](docs/phase_plain_english_contract.md).

## GUI, web development, and deployment are part of the product

The ATLAS browser/GUI is the intended day-to-day operator experience, but it remains a client of accepted backend authority rather than a second trading engine.

Four consecutive modern price/market-data alpha phases (26–29) closed as scientifically valid negatives, so the downstream product path remains gated on finding validated alpha. The rebaselined sequence is:

- **Phase30:** event-driven public-information alpha; no major frontend build.
- **Phase31:** signal-to-trade/risk contracts + read-only complete-case web prototype.
- **Phase32:** historical replay/stress dashboard.
- **Phase33:** prospective SHADOW/PAPER operator web beta.
- **Phase34:** outcome/performance/learning/drift dashboards and governance.
- **Phase35:** complete production web application + PostgreSQL operational state + scheduler + deployment engineering.
- **Phase36:** failure/security/reconciliation/deployment hardening; LIVE still disabled.
- **Phase37:** controlled LIVE activation/disable and evidence-based scaling.

Frontend controls call accepted backend/API contracts. The Python trading engine remains the source of analytical, risk, broker, and execution authority.

## Current state — 2026-08-27

- **Accepted foundation through Phase29.**
- Phase29 PR #33 merged at `87c9450e1b21606b83489f16ff326235ae92eb2b`; disposition **`ACCEPTED_NEGATIVE`**.
- Phase29 result: **14,523** development relative-value rows, **745** protected predictors, zero selection survivors, zero winners, zero finalists, zero supported candidates, zero protected candidate/return reads, inherited holdout unconsumed, independent validation PASS, anti-workaround audit PASS.
- Phase29 post-merge workflow `33124971664` passed Ubuntu and Windows completely.
- **Phase30 — Event-Driven Public-Information Alpha is active.**
- Phase30 historical-news feasibility fingerprint: `04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312`.
- Target-machine feasibility: **PASS** — 1,219 articles across the four frozen boundary windows, all 1,219 ticker-linked, zero target outcomes and zero protected returns read.
- Phase30 scientific policy fingerprint: `341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8`.
- Exactly four hypotheses are frozen: aligned news-shock continuation LONG/SHORT and counterreaction reversal LONG/SHORT.
- Only historical news `id`, `published_utc`, and exact provider-native `tickers` have alpha authority. Provider article text/content and provider-generated `insights` remain provenance only because historical revision/model-vintage semantics were not proven by the feasibility gate.
- The next internal Phase30 action is full resumable immutable historical-news acquisition from `2021-07-16` through `2026-08-11`; it remains non-performance-bearing.
- Phase11 strategy authority remains **SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5**.
- The inherited protected predictor window remains `2026-05-12` through `2026-08-11` and is still genuinely outcome-unopened.
- Signal-to-trade construction is Phase31 and remains blocked until at least one alpha candidate earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains disabled; automatic broker failover remains disabled.

## Phase30 frozen mechanism

Phase26 rejected deterministic/composite focal self-feature alpha. Phase27 rejected bounded cross-sectional expected-return/ranking models. Phase28 rejected cross-stock residual/lead-lag predictive relationships. Phase29 rejected PCA/nearest-pair relative-value mean-reversion confirmation. Phase30 therefore changes the **information source** rather than retuning those failures.

The feasibility gate proved historical Massive news coverage, chronology, pagination, ticker linkage, and deterministic evidence at the required boundaries without inspecting market outcomes. The scientific contract was then frozen before any Phase30 performance read.

For each exact ticker, Phase30 assigns an article to the first XNYS session whose official close is at least 30 minutes after publication. It measures unusual news arrival against the previous 20 zero-filled XNYS sessions using:

`news_surprise = log1p(current_unique_article_count) - mean(log1p(previous_20_session_counts_with_zeros))`

That news shock is combined only with the already-PIT-safe finalized Phase26 `d1_return_1` reaction to test the four frozen continuation/reversal hypotheses. The fixed research design retains the 2021-08-16 research start, 2026-05-06 development end, three-session purge, 2026-05-12 through 2026-08-11 protected window, `t+3` directional outcome, realistic costs, dependence-aware bootstrap, global four-hypothesis Holm correction, robustness/concentration gates, finalist-only protected confirmation, and no runner-up substitution.

No retrospective NLP, provider sentiment, alternate news lookback, alternate event timing, fifth hypothesis, or post-result threshold change is authorized.

A positive Phase30 result may grant historical analytical support only and unlock Phase31. A negative result is accepted rather than tuned away.

## Remaining planned phases

- **Phase30:** Event-Driven Public-Information Alpha.
- **Phase31:** Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype.
- **Phase32:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase33:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase34:** Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI.
- **Phase35:** Production Web Application, Operations & Deployment.
- **Phase36:** LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification.
- **Phase37:** Controlled LIVE Activation & Evidence-Based Scaling through the production control plane.

The full purpose, entry conditions, acceptance boundaries, web/deployment responsibilities, and conditional progression rules are defined in [`docs/roadmap.md`](docs/roadmap.md).

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate unavailable history; finalized facts outrank provisional state; unknown/uncertain mutation state fails closed and requires reconciliation; valid trade geometry and portfolio risk are mandatory; community trading ideas are hypotheses that must be tested rather than assumed; the frontend never duplicates or bypasses engine authority; no automatic broker failover; PAPER does not imply LIVE; AI cannot create authority; negative research cannot satisfy a positive downstream gate; protected performance is finalist-only; and LIVE exists only after the final separately accepted Phase37 authority gate.
