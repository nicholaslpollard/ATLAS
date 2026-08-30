# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market and regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read, in order:

1. `docs/roadmap.md`;
2. `docs/current_status.md`;
3. `docs/alpha_gate_sec_beneficial_ownership_closeout.md` and `docs/alpha_gate_sec_beneficial_ownership_development.md`;
4. `docs/alpha_gate_sec_beneficial_ownership_scientific_contract.md`, source-repair, feasibility, and preserved transport-failure records;
5. `docs/alpha_gate_sec_xbrl_closeout.md` and retained XBRL scientific/source records;
6. `docs/phase32_closeout.md` and retained Phase32 scientific/source records;
7. `docs/phase_flow.md`, `docs/phase_plain_english_contract.md`, and accepted code/CI evidence.

Historical failure/incident documents remain evidence and must not be rewritten to make a later repair look like an original pass.

## Locked architecture

`market/reference/regulatory -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic alpha evaluation -> candidate promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> SHADOW/PAPER/LIVE execution -> learning -> browser control plane -> production operations`

- Massive = primary market/reference/regulatory provider where entitlement and PIT semantics are proven.
- Current Massive plan = **Stocks Starter**; unrelated paid datasets/plans are never assumed.
- Official SEC EDGAR/XBRL = read-only authoritative regulatory provenance when explicitly phase-gated.
- Parquet = durable analytical lake; DuckDB = analytical engine; PostgreSQL = later operational state.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = manual secondary broker; **no automatic broker failover**.
- ML/AI = evidence/audit layers, never unilateral trading authority.
- Browser GUI = operator surface, never a second trading engine.

## Required operating cadence

One numbered phase is one acceptance gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT LARGEST SAFE COHERENT PACKAGE -> FOCUSED TESTS -> ROOT-CAUSE REPAIR IF NEEDED -> EXACT-HEAD FULL ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> POST-MERGE VERIFY -> NEXT`

Do not create conversational micro-gates for implementation work that does not change scientific, provider, broker, destructive, or LIVE authority. When an error occurs, preserve the failed evidence, identify the owning-layer root cause, implement the narrow correction, add regression coverage, and rerun certification. Validators or scientific rules are never weakened to obtain PASS. Zero candidates/trades and accepted-negative research are legitimate outcomes.

Target-machine checks remain mandatory where repository CI cannot prove local data/provider/artifact facts. Expensive target execution starts only after the exact repository head is certified.

## Current state — 2026-08-30 (America/New_York)

- Accepted numbered foundation: **through Phase32**, merged into `main`.
- **Phase32 is `ACCEPTED_NEGATIVE`.** Frozen scientific policy fingerprint `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`; frozen development finalist `solvency_distress_short`; frozen protected source-only evidence **46 event rows / 33 signal sessions / 40 unique instruments**. The preregistered 50-row minimum failed before protected performance access. Protected stock/SPY returns remain unread; protected return rows read = 0 and the holdout remains unconsumed.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Phase32 PR #37 / merge: `69f8aa81289934b71f2652482c747391917c15a3`.
- The pre-Phase33 SEC XBRL fundamental-quality/accrual family also closed `ACCEPTED_NEGATIVE` and merged through PR #38 at `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`; accepted XBRL closeout evidence fingerprint `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`; XBRL protected return rows read = **0**; post-merge Ubuntu/Windows regression passed.
- The SEC Schedule 13D/13G beneficial-ownership family is now scientifically closed `ACCEPTED_NEGATIVE` on the active branch: source-only reconstruction passed with **3,652 predictors**, development used **2,412** usable outcomes, and the frozen four-hypothesis screen produced **0 selection passers / 0 winners / 0 internal finalists**. Accepted target evidence fingerprint: `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`. Beneficial-ownership protected return rows read = **0**; holdout consumed = **false**.
- Historical supported modern alpha remains **0**; Phase33 signal-to-trade remains blocked.
- Master protected outcome window `2026-05-12..2026-08-11` remains unconsumed.
- LIVE and automatic broker failover remain disabled.

## Retained pre-Phase33 SEC XBRL lineage

The XBRL family entered from accepted Phase32 merge `69f8aa81289934b71f2652482c747391917c15a3` and used the materially different mechanism `PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY`.

Source-only feasibility contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Frozen feasibility fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

The source gate was `FEASIBILITY_PASS`: **200** successful Company Facts documents, **170** accrual-history-ready issuers, and **92** profitability-history-ready issuers. Accepted feasibility-evidence fingerprint:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

The first frozen PIT source/identity audit remains preserved as `AUDIT_FAIL` under fingerprint `50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`. The targeted active-common-stock identity repair retained the same source population and numeric gates and passed under contract `alpha-gate-xbrl-pit-audit-v2-targeted-common-stock-active-only-identity-repair-no-market-outcomes` and fingerprint `e17cf5539fbd5d3d0c31514d5fbed97332f046eb98af05dfaa0039a8c127304f`.

Six finite XBRL hypotheses were frozen before outcomes under scientific fingerprint `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`. Development produced zero selection passers, zero winners, and zero internal finalists. XBRL protected return rows read = **0** and the holdout remained unconsumed. The final `ACCEPTED_NEGATIVE` closeout evidence fingerprint is `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`. Phase33 remained blocked.

## Completed pre-Phase33 SEC Schedule 13D/13G beneficial-ownership lineage

Retained original source-feasibility mechanism identifier:

`PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`

Retained frozen source-feasibility fingerprint:

`f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`

Frozen scientific mechanism:

`PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`

The original beneficial-ownership source-only v1 target failure is preserved. Targeted source repair v2 subsequently passed without opening market outcomes: **43/43 quarterly indexes**, **200/200 complete submissions parsed**, **195 unique authoritative SEC-header `SUBJECT COMPANY` CIKs**, **200 acceptance/decision sessions**, and **142 unambiguous PIT active common-stock mappings**.

Source-repair fingerprint:

`78bf3f18368114a5a6073e8a4d66a0c13ee29a5da78b8adeb1d71b1f10c6f78c`

Exactly four non-overlapping LONG hypotheses were frozen before outcomes: initial 13D 5–10%, initial 13D 10%+, initial 13G 5–10%, and initial 13G 10%+.

Scientific fingerprint:

`4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`

Development implementation fingerprint:

`0e90a65e6e2f6a7d7206296901054de3a2c97aaa204c80927a963c298c81060d`

The earlier target-machine source-only predictor reconstruction stopped at roughly **3500/5200** before predictor reconstruction PASS because one legitimate official SEC complete submission exceeded the historical/default 20 MB archive ceiling. That failed run remains preserved as **pre-outcome**: development stock/SPY return rows read = **0**, protected return rows read = **0**, protected holdout consumed = **false**.

Development transport-repair fingerprint:

`a4db8419364895c6861c4becbe3abf9b32ec044ceb4aff5cf14a7c9244368bdb`

The narrow repair retained the historical/default 20 MB submission ceiling and 64 MB quarterly-index ceiling, retained SEC pacing at 5 calls/second, and allowed only the scientific runner to opt into a bounded 256 MB complete-submission ceiling. It did not change the frozen science.

The repaired target run then completed `Source-only predictor reconstruction: PASS` with **3,652** predictors: **2,763 development** and **889 protected-source-only** rows. Only after that PASS did development outcomes open. The development study obtained **2,412** usable outcome rows after **306** exact-path-missing rows and **46** split-crossing censored rows.

Final development status: `ACCEPTED_NEGATIVE_DEVELOPMENT`.

- selection passers: **0**;
- selection winners: **0**;
- internal finalists: **0**;
- protected-return eligible finalists: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- Phase33 authority: **false**.

Accepted evidence fingerprint:

`c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`

The family is closed to post-result rescue. Its ownership thresholds, form/amendment eligibility, direction, purpose-text/reporting-person/filer filters, horizon, costs, sample, chronology, multiplicity, winner/finalist rules, and protected policy may not be retuned from the observed negative result.

## Remaining roadmap

- **Current pre-Phase33 alpha research:** the beneficial-ownership family is closed `ACCEPTED_NEGATIVE`; after its exact-head closeout certification/merge, define and preregister a materially different information/economic mechanism without reusing its observed performance to retune it.
- **Phase33:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on accepted historical `SUPPORTED` alpha.
- **Phase34:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase35:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase36:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase37:** Production Web Application, Operations & Deployment.
- **Phase38:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase39:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
