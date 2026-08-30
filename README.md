# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read:

1. `docs/roadmap.md`;
2. `docs/current_status.md`;
3. `docs/phase32_sec_8k_material_event_alpha.md`;
4. `docs/phase32_scientific_contract.md`;
5. `docs/phase32_predictor_independent_acceptance.md`;
6. `docs/phase32_development_evaluation.md`;
7. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
8. accepted code, validators, CI/PR evidence.

Retained Phase32 source-incident history is in `docs/phase32_sec_edgar_access_incident.md`, `docs/phase32_massive_text_multiplicity_incident.md`, `docs/phase32_crash_cache_corruption_incident.md`, and `docs/phase32_sec_submissions_shard_boundary_incident.md`.

## Locked architecture

`market/reference/regulatory -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic alpha evaluation -> candidate promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> SHADOW/PAPER/LIVE execution -> learning -> browser control plane -> production operations`

- Massive = primary market/reference/regulatory provider where entitlement and PIT semantics are proven.
- Current Massive plan = **Stocks Starter**; unrelated paid datasets/plans are never assumed.
- Official SEC EDGAR = read-only authoritative regulatory submission provenance when explicitly phase-gated.
- Parquet = durable analytical lake; DuckDB = analytical engine; PostgreSQL = later operational state.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = manual secondary broker; **no automatic broker failover**.
- ML/AI = evidence/audit layers, never unilateral trading authority.
- Browser GUI = operator surface, never a second trading engine.

## Operating rule

One numbered phase is one acceptance gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

If an error occurs, ATLAS stops progression, identifies the root cause, implements and tests the proper correction, and only then continues. Validators or scientific rules are never weakened to obtain PASS. Failed approaches remain evidence. Zero candidates/trades is legitimate.

Material decisions and completed gates must be synchronized into roadmap/status/phase docs/README before work is complete.

Long-running target-machine runners must provide lightweight terminal progress instead of appearing idle. Prefer a simple `x / total completed` indicator, optionally with percent complete; when a meaningful total is unavailable, report the current date/window/batch plus a completed count. Update at useful intervals without noisy per-record logging. Progress reporting is operational observability only and must never alter scientific logic, source evidence, chronology, acceptance criteria, or authority boundaries.

## Current state — 2026-08-29

- Accepted foundation: **through Phase31**.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; supported modern alpha remains **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Master protected outcome window remains `2026-05-12..2026-08-11` and remains outcome-unopened.
- **Active Phase32: SEC 8-K Material Corporate-Event Alpha.**
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Phase33 signal-to-trade remains blocked.
- LIVE and automatic broker failover remain disabled.

### Phase32 frozen science

Policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Exactly five hypotheses are frozen:

- `equity_issuance_short`;
- `share_repurchase_long`;
- `financial_integrity_adverse_short`;
- `listing_distress_short`;
- `solvency_distress_short`.

The frozen methodology uses SEC acceptance-time public availability, decision-open entry, five-session close exit, SPY-relative primary plus required unhedged profitability, 10-bps primary / 25-bps stress costs, five-session purge/block bootstrap, mandatory sample/concentration/robustness gates, global `HOLM_BONFERRONI_GLOBAL_5`, one winner/finalist per direction, no runner-up substitution, and finalist-only protected returns.

PIT identity is bound to `instrument-identity-v4-no-issuer-level-medium-collapse`: strong = Composite FIGI / Share Class FIGI; medium = CIK + exact provider-native ticker + primary exchange + security type. Only strong/medium is eligible; no fallback ticker+snapshot, current-universe backprojection, or ticker alias backfill.

### Phase32 source/predictor gates — ACCEPTED PASS

Accepted source fingerprints:

- core V2: `978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`;
- semantic V2: `eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`.

The accepted full-history source/predictor acquisition completed **36,309** filing entities with **19,792** eligible predictors: **18,819 development** and **973 protected-predictor-only**. It read zero stock/SPY/options/protected returns.

Filing-entity evidence SHA-256:

`18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`

Predictor SHA-256:

`c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`

The independent local source/predictor audit reprocessed all 36,309 filing entities, reproduced those hashes with zero network/market-outcome reads, and froze acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

### Exact active target — development-only performance evaluation

The next authorized gate is `scripts/run_phase32_development.py` after its focused unit tests and `scripts/validate_phase32_development.py` pass.

This is the **first Phase32 step authorized to read development stock/SPY outcomes**. Before doing so it revalidates the accepted source/predictor fingerprint and hashes, exact stage partition, source-derived execution ticker for every development predictor, and accepted split/corporate-action evidence. Any missing or ambiguous execution-ticker lineage fails before outcomes; ATLAS never chooses a ticker because market data happens to exist.

The development study uses exact decision-open / t+5-close stock and SPY bars, previous-session accepted regimes, the frozen 75% selection + five-session purge + internal chronology, all fixed folds/sample/robustness/concentration gates, Holm-5, and no runner-up substitution.

Protected stock/SPY returns remain forbidden. If development produces zero finalists, Phase32 goes to independent negative closeout with the holdout unread. If finalists exist, a separate blindness/lineage audit and immutable finalist-only protected plan must pass before protected returns may be opened.

## Remaining roadmap

- **Phase32:** SEC 8-K Material Corporate-Event Alpha — active; development-only performance gate next.
- **Phase33:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on supported alpha.
- **Phase34:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase35:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase36:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase37:** Production Web Application, Operations & Deployment.
- **Phase38:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase39:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
