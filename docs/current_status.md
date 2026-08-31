# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-30 (America/New_York). Accepted numbered foundation remains through Phase32. SEC XBRL, SEC Schedule 13D/13G beneficial ownership, and FINRA consolidated short-interest v1 are all scientifically closed accepted-negative research programs. Historical supported alpha remains 0 and Phase33 remains blocked.**

Read `docs/roadmap.md`, this file, `docs/alpha_gate_finra_short_interest_source_only_closeout.md`, retained FINRA scientific/PIT/source records, accepted beneficial-ownership and XBRL closeouts, `docs/phase32_closeout.md`, `docs/phase_flow.md`, and exact-head CI evidence before continuing.

## Authority state

- Accepted numbered foundation: through **Phase32**, merged into `main`.
- Current Massive subscription: **Stocks Starter**.
- Phases26–32: scientifically valid `ACCEPTED_NEGATIVE`.
- Phase32 remains closed `ACCEPTED_NEGATIVE`; its protected-return evidence was never opened.
- Beneficial-ownership final scientific disposition: `ACCEPTED_NEGATIVE`.
- Historical supported alpha remains 0.
- Phase33 remains blocked because accepted historical `SUPPORTED` alpha remains zero.
- Phase33 signal-to-trade entry condition: **not satisfied / blocked**.
- Historical supported alpha: **0**.
- Master protected outcome window `2026-05-12..2026-08-11`: **unconsumed**.
- Provider writes, broker reads/writes, orders, PAPER, LIVE, automation, and automatic broker failover: **disabled** for current alpha research.
- No accepted-negative family grants trading authority.

Root cause before workaround remains mandatory. Failed/negative research evidence must be preserved. No family may be rescued after observation by changing thresholds, horizon, costs, features, direction, sample, multiplicity, winner/finalist rules, or protected policy and calling it the same experiment.

## Accepted modern-alpha lineage

### Phase31 — SEC Form 4 insider transactions

- final disposition: `ACCEPTED_NEGATIVE`;
- merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`;
- original feasibility failure remains preserved;
- owning-layer root cause: Massive beta source-association/data-quality defect;
- source-quality fingerprint: `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`;
- scientific fingerprint: `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`;
- zero survivors/winners/finalists/support; zero protected reads.

### Phase32 — SEC 8-K material corporate events

- final disposition: `ACCEPTED_NEGATIVE`;
- PR #37 / merge: `69f8aa81289934b71f2652482c747391917c15a3`;
- scientific fingerprint: `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`;
- frozen finalist: `solvency_distress_short`;
- protected source-only population: **46 event rows / 33 signal sessions / 40 unique instruments** versus minimum **50 / 20 / 20**;
- protected return rows read: **0**; holdout consumed: **false**.

### Pre-Phase33 — SEC XBRL fundamental quality/accruals

Mechanism: `PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY`.

- merge: `083c0a5742b161cf4b7c04d5bf0246f3057f6c19` via PR #38;
- source feasibility: **200** Company Facts docs, **170** accrual-ready issuers, **92** profitability-ready issuers;
- original PIT audit failure preserved; targeted common-stock identity repair passed;
- scientific fingerprint: `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`;
- development: **0 selection passers / 0 winners / 0 internal finalists**;
- protected return rows read: **0**; holdout consumed: **false**;
- final closeout evidence fingerprint: `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`;
- final disposition: `ACCEPTED_NEGATIVE`.

### Pre-Phase33 — SEC Schedule 13D/13G beneficial ownership

Mechanism: `PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`.

- merge: `208529c5562920cc0b2bcf2bae546e2b9af0a25b` via PR #39;
- targeted source repair passed with **43/43 quarterly indexes**, **200/200 complete submissions**, **195 unique authoritative subject CIKs**, **200 decision sessions**, and **142 unambiguous PIT active common-stock mappings**;
- scientific fingerprint: `4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`;
- repaired predictor reconstruction: **3,652** rows = **2,763 DEVELOPMENT / 889 PROTECTED**;
- usable development outcomes: **2,412** after **306** exact-path-missing and **46** split-censored rows;
- selection passers/winners/internal finalists: **0 / 0 / 0**;
- protected return rows read: **0**; holdout consumed: **false**;
- final closeout evidence fingerprint: `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`;
- final disposition: `ACCEPTED_NEGATIVE`.

## FINRA consolidated short-interest v1 — accepted-negative source closeout

Mechanism: `PIT_FINRA_CONSOLIDATED_SHORT_INTEREST_POSITIONING_AND_CROWDING`.

### Accepted source lineage

Source feasibility contract:

`alpha-gate-finra-short-interest-feasibility-v1-consolidated-position-source-only-no-market-outcomes`

Frozen feasibility fingerprint:

`cc80a87f020a4dece88430d20aa62e13d4dcd898656d60d53dea49b3ef975bc4`

Accepted feasibility result:

- **12/12** frozen source files;
- **244,979** total parsed rows;
- **137,575** exchange-listed rows;
- **20,248** unique exchange-listed symbols;
- years represented: **2021–2026**;
- target/protected market outcome reads: **0**.

PIT audit contract:

`alpha-gate-finra-short-interest-pit-audit-v1-publication-revision-split-active-common-stock-no-market-outcomes`

PIT fingerprint:

`ffdb7389ceae73f31a3781a79a8d825338102b9084cb30dd03bf21f6bf003846`

Accepted PIT result:

- immutable exchange-listed rows: **136,731**;
- PIT-eligible rows: **63,761**;
- unique PIT instruments: **8,054**;
- files with >=2,500 PIT rows: **12/12**;
- target/protected market outcome reads: **0**.

### Frozen science

Scientific contract:

`alpha-gate-finra-short-interest-scientific-v1-four-position-change-crowding-buckets`

Scientific fingerprint:

`0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`

Exactly four hypotheses were frozen before outcomes:

1. `rapid_short_build_crowded_short` — SHORT;
2. `rapid_short_build_non_crowded_short` — SHORT;
3. `rapid_short_cover_crowded_long` — LONG;
4. `rapid_short_cover_non_crowded_long` — LONG.

Multiplicity was frozen globally across all four using `HOLM_BONFERRONI_GLOBAL_4`. The source-only stage required every frozen hypothesis to satisfy both development and protected sample floors before any development return could open.

### Accepted full predictor reconstruction

Accepted source target head:

`d312ec95752ab49a6fcbec18973faacb96d4aa89`

The complete reconstruction processed **116 FINRA source files** and **232 Massive PIT reference snapshots** and produced **19,343** predictor rows:

- DEVELOPMENT: **14,841**;
- PROTECTED: **4,502**.

Candidate totals:

- `rapid_short_build_crowded_short`: **2,036**;
- `rapid_short_build_non_crowded_short`: **8,025**;
- `rapid_short_cover_crowded_long`: **1,257**;
- `rapid_short_cover_non_crowded_long`: **8,025**.

Three hypotheses passed every source-count gate. The only frozen failure was:

`rapid_short_cover_crowded_long -> protected_min_rows`

Exact protected population for that hypothesis:

- event rows: **257** / minimum **300** — FAIL;
- signal sessions: **26** / minimum **16** — PASS;
- unique instruments: **211** / minimum **200** — PASS.

The runner stopped at `SOURCE_ONLY_PREDICTOR_FAIL`. Development market outcomes were never opened.

Accepted artifact hashes:

- predictor report SHA-256: `56479707945a59752aeb2056f3cfbcfd2df1e4a87ada31c9e8e6d3ed93f314cd`;
- predictor rows SHA-256: `21c7dd2e44013ba0f1d290019db70f7b0f23b0603c5e965cbd8b441128190e48`.

Accepted persisted-artifact probe head:

`5ceac74ad67c8f3539b03192cf1946d51d476434`

Accepted probe evidence fingerprint:

`c624da82b45fb8d530c2400262598f266ec6309e614a0dcd135b38d9ba5518ce`

Accepted closeout evidence fingerprint:

`bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565`

Final source disposition:

`ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`

Target/development outcome rows read: **0**. Protected return rows read: **0**. Protected holdout consumed: **false**. Phase33 authority: **false**.

This is a source-capacity negative, not a performance negative. No profitability or return conclusion may be inferred.

### Permanent anti-retuning boundary

FINRA v1 may not be rescued by dropping the sparse fourth hypothesis, reducing the 300-row protected floor, moving the 10% change-tail or 80% crowding thresholds, changing the deterministic sample cap, changing chronology/cost/horizon/multiplicity, substituting another direction/bucket, or opening returns merely to inspect an inadmissible result.

Any future short-interest experiment must be a newly preregistered scientific version before outcome access.

## Immediate next action

1. Complete exact-head focused and full Ubuntu/Windows certification of the FINRA accepted-negative closeout package and synchronized living documents.
2. Merge the FINRA closeout branch and verify post-merge full regression.
3. Define and freeze a **materially different economic/information alpha mechanism**. Do not retune FINRA v1.
4. Phase33 remains blocked until at least one historical alpha earns accepted `SUPPORTED` authority.

## Downstream boundary

The roadmap is conditional rather than schedule-driven. Accepted-negative research improves ATLAS's retained knowledge but cannot substitute for positive alpha support. LIVE, automatic broker failover, and new trading authority remain unavailable until their later separately accepted gates.
