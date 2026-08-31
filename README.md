# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market and regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read, in order:

1. `docs/roadmap.md`;
2. `docs/current_status.md`;
3. `docs/alpha_gate_finra_short_interest_source_only_closeout.md`, plus the FINRA scientific/PIT/source lineage;
4. `docs/alpha_gate_sec_beneficial_ownership_closeout.md` and retained beneficial-ownership scientific/source records;
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
- Phase32 is `ACCEPTED_NEGATIVE`; frozen protected source-only evidence was **46 event rows / 33 signal sessions / 40 unique instruments**, protected returns remained unread, and the holdout remained unconsumed.
- Phase32 protected return rows read = 0; protected holdout consumed = false.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well.
- Phases26–32 are scientifically valid `ACCEPTED_NEGATIVE`; historical supported modern alpha remains **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Phase32 PR #37 / merge: `69f8aa81289934b71f2652482c747391917c15a3`.
- Pre-Phase33 SEC XBRL fundamental-quality/accrual closed `ACCEPTED_NEGATIVE` and merged through PR #38 at `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`; accepted closeout fingerprint `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`.
- XBRL protected return rows read = **0**; protected holdout consumed = **false**.
- SEC Schedule 13D/13G beneficial ownership closed `ACCEPTED_NEGATIVE` and merged through PR #39 at `208529c5562920cc0b2bcf2bae546e2b9af0a25b`; accepted closeout fingerprint `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`.
- FINRA consolidated short-interest v1 is now closed `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT` before any market outcome read. It reconstructed **19,343** predictor rows across **116 FINRA files** and **232 Massive PIT snapshots**. The sole frozen failure was `rapid_short_cover_crowded_long -> protected_min_rows`: **257** protected rows versus minimum **300**, while **26/16** signal sessions and **211/200** unique instruments passed.
- FINRA predictor report SHA-256: `56479707945a59752aeb2056f3cfbcfd2df1e4a87ada31c9e8e6d3ed93f314cd`.
- FINRA predictor rows SHA-256: `21c7dd2e44013ba0f1d290019db70f7b0f23b0603c5e965cbd8b441128190e48`.
- FINRA accepted probe evidence fingerprint: `c624da82b45fb8d530c2400262598f266ec6309e614a0dcd135b38d9ba5518ce`.
- FINRA accepted closeout evidence fingerprint: `bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565`.
- FINRA target/development outcome rows read = **0**; protected return rows read = **0**; protected holdout consumed = **false**.
- Historical supported modern alpha remains **0**; Phase33 Signal-to-Trade remains blocked.
- Phase33 signal-to-trade remains blocked because accepted historical `SUPPORTED` alpha remains zero.
- Master protected outcome window `2026-05-12..2026-08-11` remains unconsumed.
- LIVE and automatic broker failover remain disabled.

## Retained modern alpha lineage

### Phase32 — SEC 8-K material corporate events

Phase32 closed `ACCEPTED_NEGATIVE` under scientific fingerprint `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`. Its frozen development finalist `solvency_distress_short` had protected source-only evidence **46 event rows / 33 signal sessions / 40 unique instruments** versus frozen minimum **50 / 20 / 20**. Protected stock/SPY returns remained unread; holdout unconsumed.

### Pre-Phase33 SEC XBRL fundamental-quality/accrual

Mechanism: `PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY`.

Source feasibility passed with **200** successful Company Facts documents, **170** accrual-history-ready issuers, and **92** profitability-history-ready issuers. The original PIT audit failure remains preserved; the targeted common-stock active-only identity repair passed without changing source population or numeric gates. Six finite hypotheses were frozen under scientific fingerprint `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`. Development produced zero selection passers, winners, or internal finalists. Protected returns remained unread. Final closeout fingerprint: `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`.

### Pre-Phase33 SEC Schedule 13D/13G beneficial ownership

Scientific mechanism: `PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`.

Targeted source repair passed with **43/43 quarterly indexes**, **200/200 complete submissions**, **195 unique authoritative subject CIKs**, **200 decision sessions**, and **142 unambiguous PIT active common-stock mappings**. Exactly four LONG hypotheses were frozen under scientific fingerprint `4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`. The repaired source-only run produced **3,652 predictors**, and development produced **2,412 usable outcomes**, **0 selection passers**, **0 winners**, and **0 internal finalists**. Protected returns remained unread. Final closeout fingerprint: `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`.

### Pre-Phase33 FINRA consolidated short interest

Scientific mechanism: `PIT_FINRA_CONSOLIDATED_SHORT_INTEREST_POSITIONING_AND_CROWDING`.

Feasibility passed on 12 frozen source anchors; PIT audit passed with **136,731 immutable exchange-listed rows**, **63,761 PIT-eligible rows**, **8,054 unique PIT instruments**, and all **12/12** files above the frozen per-file minimum. Scientific fingerprint: `0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`.

The full 116-settlement predictor reconstruction produced **19,343** source-only rows: **14,841 DEVELOPMENT** and **4,502 PROTECTED**. Three frozen hypotheses passed every source-count gate. `rapid_short_cover_crowded_long` passed all development gates and protected sessions/instruments, but had only **257** protected event rows versus the frozen **300** minimum. Because the family and `HOLM_BONFERRONI_GLOBAL_4` multiplicity were frozen across exactly four hypotheses, the fourth bucket cannot be dropped after observing this result.

Disposition: `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`. Market outcomes were never opened. This result makes no performance claim. The exact v1 thresholds, buckets, sampling, chronology, multiplicity, and protected rules are closed to post-result retuning.

## Remaining roadmap

- **Current pre-Phase33 alpha research:** FINRA short-interest v1 is closed `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`; the next family must use a materially different economic/information mechanism rather than retuning FINRA.
- **Phase33:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on accepted historical `SUPPORTED` alpha.
- **Phase34:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase35:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase36:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase37:** Production Web Application, Operations & Deployment.
- **Phase38:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase39:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
