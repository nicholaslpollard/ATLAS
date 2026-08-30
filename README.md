# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read:

1. `docs/roadmap.md`;
2. `docs/current_status.md`;
3. `docs/phase32_closeout.md`;
4. `docs/phase32_sec_8k_material_event_alpha.md`;
5. `docs/phase32_scientific_contract.md`;
6. `docs/phase32_predictor_independent_acceptance.md`;
7. `docs/phase32_development_evaluation.md`;
8. `docs/phase32_finalist_blindness_audit.md`;
9. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
10. accepted code, validators, CI/PR evidence.

Retained Phase32 source-incident history remains in `docs/phase32_sec_edgar_access_incident.md`, `docs/phase32_massive_text_multiplicity_incident.md`, `docs/phase32_crash_cache_corruption_incident.md`, and `docs/phase32_sec_submissions_shard_boundary_incident.md`.

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

Use the largest safe coherent work package. Do not create conversational micro-gates for implementation steps that do not change scientific/provider/broker/destructive/LIVE authority. Target-machine checks remain mandatory when repository CI cannot prove local data/provider/artifact facts.

If an error occurs, ATLAS identifies the root cause, implements and tests the proper correction, and only then continues. Validators or scientific rules are never weakened to obtain PASS. Failed approaches remain evidence. Zero candidates/trades is legitimate.

Material decisions and completed gates must be synchronized into roadmap/status/phase docs/README before work is complete.

## Current state — 2026-08-30

- Accepted foundation: **through Phase32**, pending Phase32 branch merge into `main`.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well.
- Historical supported modern alpha remains **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Current closeout branch: `phase-32-sec-8k-material-event-alpha`.
- Master protected outcome window `2026-05-12..2026-08-11` remains **protected-return unopened**.
- Phase32 development finalist `solvency_distress_short` did not earn `SUPPORTED` authority.
- Phase33 signal-to-trade remains blocked.
- LIVE and automatic broker failover remain disabled.

### Phase32 frozen science

Policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Exactly five hypotheses were frozen before performance:

- `equity_issuance_short`;
- `share_repurchase_long`;
- `financial_integrity_adverse_short`;
- `listing_distress_short`;
- `solvency_distress_short`.

The frozen methodology used SEC acceptance-time public availability, decision-open entry, five-session close exit, SPY-relative primary plus required unhedged profitability, 10-bps primary / 25-bps stress costs, five-session purge/block bootstrap, mandatory sample/concentration/robustness gates, global `HOLM_BONFERRONI_GLOBAL_5`, one winner/finalist per direction, no runner-up substitution, and finalist-only protected returns.

PIT identity remained bound to `instrument-identity-v4-no-issuer-level-medium-collapse`.

### Phase32 source/predictor gates — ACCEPTED PASS

Accepted source fingerprints:

- core V2: `978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`;
- semantic V2: `eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`;
- independent source/predictor acceptance: `531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`.

Full-history acquisition completed 36,309 filing entities with 19,792 eligible predictors: 18,819 development and 973 protected-predictor-only. Acquisition read zero stock/SPY/options/protected outcomes.

### Phase32 development + finalist audit

The development study produced one frozen finalist, `solvency_distress_short`, after `share_repurchase_long` failed internal validation on its required LCB.

The independent finalist blindness / lineage audit then reproduced the accepted development result without importing the development implementation and built a source-only protected plan.

Finalist audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

Protected plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Protected plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

Frozen protected source-only population:

- **46 event rows**;
- **33 signal sessions**;
- **40 unique instruments**.

Frozen minimums were **50 / 20 / 20**. The 46-row population fails the mandatory 50-row gate before protected performance is opened. Audit status: `AUDIT_PASS_PROTECTED_SAMPLE_GATE_IMPOSSIBLE`.

**Protected stock/SPY returns remain unread.** Protected return rows read = 0 and protected holdout consumed = false.

### Phase32 closeout

Phase32 is `ACCEPTED_NEGATIVE`. The result is scientifically valid: the development finalist cannot satisfy a preregistered protected source-only sample requirement, so looking at protected returns would be both unnecessary and inadmissible.

No threshold may be relaxed, no runner-up may replace the finalist, and the same 8-K family may not be retuned after results. Historical supported alpha remains **0**.

The next alpha research mechanism, if pursued, must be materially different. Phase33 Signal-to-Trade Construction remains blocked until at least one later alpha gate earns accepted historical `SUPPORTED` authority.

## Remaining roadmap

- **Next alpha research gate:** must be a materially different mechanism; not yet frozen/opened.
- **Phase33:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on supported alpha.
- **Phase34:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase35:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase36:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase37:** Production Web Application, Operations & Deployment.
- **Phase38:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase39:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
