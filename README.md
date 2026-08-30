# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read:

1. `docs/roadmap.md`;
2. `docs/current_status.md`;
3. `docs/alpha_gate_sec_xbrl_closeout.md`;
4. `docs/alpha_gate_sec_xbrl_fundamental_quality.md`;
5. `docs/alpha_gate_sec_xbrl_scientific_contract.md`;
6. `docs/alpha_gate_sec_xbrl_development.md`;
7. `docs/alpha_gate_sec_xbrl_pit_audit.md` and `docs/alpha_gate_sec_xbrl_pit_identity_repair.md`;
8. `docs/phase32_closeout.md` and retained Phase32 scientific/source records;
9. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
10. accepted code, validators, CI/PR evidence.

Retained Phase32 source-incident history remains in `docs/phase32_sec_edgar_access_incident.md`, `docs/phase32_massive_text_multiplicity_incident.md`, `docs/phase32_crash_cache_corruption_incident.md`, and `docs/phase32_sec_submissions_shard_boundary_incident.md`.

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

## Operating rule

One numbered phase is one acceptance gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Use the largest safe coherent work package. Do not create conversational micro-gates for implementation steps that do not change scientific/provider/broker/destructive/LIVE authority. Target-machine checks remain mandatory when repository CI cannot prove local data/provider/artifact facts.

If an error occurs, ATLAS identifies the root cause, implements and tests the proper correction, and only then continues. Validators or scientific rules are never weakened to obtain PASS. Failed approaches remain evidence. Zero candidates/trades is legitimate.

Material decisions and completed gates must be synchronized into roadmap/status/phase docs/README before work is complete.

## Current state — 2026-08-30 (America/New_York)

- Accepted numbered foundation: **through Phase32**, merged into `main`.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well.
- Phase32 is `ACCEPTED_NEGATIVE`; protected return rows read = 0 and the holdout remains unconsumed.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Phase32 PR #37 / merge: `69f8aa81289934b71f2652482c747391917c15a3`.
- The materially different pre-Phase33 SEC XBRL fundamental-quality/accrual mechanism has completed and is also **`ACCEPTED_NEGATIVE`**.
- XBRL source feasibility: `FEASIBILITY_PASS` with 200 successful Company Facts documents, 170 accrual-history-ready issuers, and 92 profitability-history-ready issuers.
- XBRL PIT audit v1 is preserved `AUDIT_FAIL`; targeted common-stock active-only identity repair v2 passed with 171 unambiguous mappings and 38 issuers with >=3 mappings.
- Frozen XBRL scientific fingerprint: `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`.
- Accepted XBRL development target head: `58e7c9b60ba59d250a7c91e282daefa4aef3c2b9`.
- XBRL development result: `ACCEPTED_NEGATIVE_DEVELOPMENT` with 5,536 predictors, 3,963 usable development outcomes, **0 selection passers, 0 winners, and 0 internal finalists**.
- XBRL protected return rows read = **0**; protected holdout consumed = **false**.
- Accepted XBRL closeout evidence fingerprint: `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`.
- Historical supported modern alpha remains **0**.
- Phase33 signal-to-trade remains blocked.
- Master protected outcome window `2026-05-12..2026-08-11` remains unconsumed.
- LIVE and automatic broker failover remain disabled.

### Phase32 closeout

Phase32 policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

The independent finalist blindness / lineage audit reproduced `solvency_distress_short` and froze a protected source-only population of **46 event rows / 33 signal sessions / 40 unique instruments** against frozen minimums of **50 / 20 / 20**.

Finalist audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

Protected plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Protected plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

The 46-row population failed the mandatory 50-row gate before protected performance was opened. No threshold relaxation, alternate finalist, or post-result 8-K retune is authorized.

### SEC XBRL fundamental-quality/accrual closeout

Source feasibility contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Feasibility fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

Accepted feasibility evidence fingerprint:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

Frozen PIT audit fingerprint:

`50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`

Targeted identity-repair fingerprint:

`e17cf5539fbd5d3d0c31514d5fbed97332f046eb98af05dfaa0039a8c127304f`

Scientific fingerprint:

`2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`

Development implementation fingerprint:

`3b5a02113ceab0065ea9a03020cc5266222e67ba39abe36311a6959e7e2d488f`

Closeout contract:

`alpha-gate-xbrl-closeout-v1-development-negative-protected-unread`

Accepted closeout evidence fingerprint:

`291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`

Artifact SHA-256 evidence:

- development report: `50bf99956ca95d725764b16bc5ae622b5ffe9dbfbadb4e63afa591a4aef998c6`;
- predictor report: `246bc1df65ce923b83167ea65f7e25b266657dec30fdcfd841e4bae260fbdb16`;
- predictor rows: `9b3526527d2d45433f5970d768155c9763c16bc8d0772fdc526659ec1aabd14a`;
- development outcomes: `17be9dd103902ea0e9f39c172b7dfb0cf3d552b6f743bd8101c7f836b8500b55`;
- finalists: `c5cfddbe30b597d115560a9611e8bf3bef5bcb76f7c59f5d5f5a071db458945f`.

No XBRL candidate survived the frozen selection gates plus global Holm correction. This family is closed. It may not be retuned or rescued with the protected holdout.

## Remaining roadmap

- **Next pre-Phase33 alpha research:** must use a materially different economic/information mechanism from the closed XBRL family; exact mechanism not yet accepted/frozen.
- **Phase33:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on supported alpha.
- **Phase34:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase35:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase36:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase37:** Production Web Application, Operations & Deployment.
- **Phase38:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase39:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
