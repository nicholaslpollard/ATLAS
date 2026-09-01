# ATLAS Current Status and Handoff

**Last synchronized: 2026-09-01 (America/New_York). Accepted numbered foundation remains through Phase32. SEC XBRL, SEC Schedule 13D/13G beneficial ownership, FINRA consolidated short-interest v1, SEC diluted-EPS earnings-innovation v1, and SEC Form 13F institutional-positioning v1 are scientifically closed accepted-negative research programs. Historical supported alpha remains 0, Phase33 remains blocked, and ATLAS is operator-paused after the Form 13F closeout pending explicit direction from the ATLAS Review.**

Read `docs/roadmap.md`, this file, `docs/alpha_gate_sec_13f_source_integrity_closeout.md`, the retained Form 13F feasibility/diagnostic/original-EDGAR reconciliation records, `docs/alpha_gate_sec_earnings_innovation_source_only_closeout.md`, the retained SEC earnings-innovation feasibility/PIT/diagnostic records, `docs/alpha_gate_finra_short_interest_source_only_closeout.md`, retained FINRA scientific/PIT/source records, accepted beneficial-ownership and XBRL closeouts, `docs/phase32_closeout.md`, `docs/phase_flow.md`, and exact-head CI evidence before continuing.

## Authority state

- Accepted numbered foundation: through **Phase32**, merged into `main`.
- Current Massive subscription: **Stocks Starter**.
- Phases26–32: scientifically valid `ACCEPTED_NEGATIVE`.
- Phase32 remains closed `ACCEPTED_NEGATIVE`; its protected-return evidence was never opened.
- Beneficial-ownership final scientific disposition: `ACCEPTED_NEGATIVE`.
- FINRA short-interest v1 final source disposition: `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`.
- SEC diluted-EPS earnings-innovation v1 final source disposition: `ACCEPTED_NEGATIVE_PIT_SOURCE_INTEGRITY_FAILURE`.
- SEC Form 13F institutional-positioning v1 final source disposition: `ACCEPTED_NEGATIVE_SOURCE_INTEGRITY_FAILURE`.
- Historical supported alpha remains 0.
- Phase33 remains blocked because accepted historical `SUPPORTED` alpha remains zero.
- Phase33 signal-to-trade entry condition: **not satisfied / blocked**.
- Historical supported alpha: **0**.
- Master protected outcome window `2026-05-12..2026-08-11`: **unconsumed**.
- Provider writes, broker reads/writes, orders, PAPER, LIVE, automation, and automatic broker failover: **disabled** for current alpha research.
- No accepted-negative family grants trading authority.
- **Operator pause:** after the Form 13F branch is merged and post-merge verification passes, do not start another alpha family, Phase33, or any other new stage until the user explicitly resumes work after the ATLAS Review.

Root cause before workaround remains mandatory. Failed/negative research evidence must be preserved. No family may be rescued after observation by changing thresholds, horizon, costs, features, direction, sample, multiplicity, winner/finalist rules, source-selection/reconciliation rules, or protected policy and calling it the same experiment.

## Accepted modern-alpha lineage

### Phase31 — SEC Form 4 insider transactions

- Phase31 Form-4 alpha closed `ACCEPTED_NEGATIVE`;
- final disposition: `ACCEPTED_NEGATIVE`;
- merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`;
- original feasibility status: `FEASIBILITY_FAIL`;
- original feasibility failure remains preserved;
- owning-layer root cause: Massive beta source-association/data-quality defect;
- source-quality fingerprint: `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`;
- source-quality policy: `RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`;
- scientific fingerprint: `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`;
- Phase31 produced zero survivors/winners/finalists/support and zero protected reads.

### Phase32 — SEC 8-K material corporate events

- final disposition: `ACCEPTED_NEGATIVE`;
- PR #37 / merge: `69f8aa81289934b71f2652482c747391917c15a3`;
- scientific fingerprint: `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`;
- Exactly five hypotheses remained frozen throughout Phase32.
- frozen finalist: `solvency_distress_short`;
- finalist blindness / lineage audit fingerprint: `c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`;
- protected source-only population: **46 event rows / 33 signal sessions / 40 unique instruments** versus minimum **50 / 20 / 20**;
- Protected stock/SPY returns remain unread.
- protected return rows read: **0**; holdout consumed: **false**.

### Pre-Phase33 — SEC XBRL fundamental quality/accruals

XBRL fundamental-quality/accrual mechanism — final `ACCEPTED_NEGATIVE`.

Mechanism: `PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY`.

- Phase32 source merge lineage: `69f8aa81289934b71f2652482c747391917c15a3`;
- source feasibility state: `FEASIBILITY_PASS`;
- feasibility contract: `alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`;
- feasibility fingerprint: `6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`;
- accepted feasibility evidence fingerprint: `33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`;
- retained PIT audit fingerprint: `50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`;
- merge: `083c0a5742b161cf4b7c04d5bf0246f3057f6c19` via PR #38;
- source feasibility: **200** Company Facts docs, **170** accrual-ready issuers, **92** profitability-ready issuers;
- original PIT audit failure preserved; targeted common-stock identity repair passed;
- scientific fingerprint: `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`;
- development: **0 selection passers / 0 winners / 0 internal finalists**;
- protected return rows read: **0**; holdout consumed: **false**;
- final closeout evidence fingerprint: `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`;
- final disposition: `ACCEPTED_NEGATIVE`.

### Pre-Phase33 — SEC Schedule 13D/13G beneficial ownership

Source-only feasibility mechanism: `PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`.

Frozen feasibility fingerprint: `f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`.

Scientific mechanism: `PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`.

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

## SEC diluted-EPS earnings-innovation v1 — accepted-negative source closeout

Mechanism: `PIT_SEC_XBRL_DILUTED_EPS_SEASONAL_EARNINGS_INNOVATION_POST_PERIODIC_FILING_DRIFT`.

- feasibility fingerprint: `c32e4aa83b25cdc23476098ffc30bd48908123d047d75f18f0d45b2acaffcd0d`;
- PIT audit fingerprint: `423528f7518273f91432ee0cfaf0f43fec8cf33fa11a59f40af5523b4f9d6baa`;
- V2 diagnostic fingerprint: `399e7d0bece8088e63c4835566d276b51375a5031d81f4db4781675351a87961`;
- closeout fingerprint: `29e72b427aa63c6ae2e0c25917fad0c9c948f2a2cd97c0d51f390ecd343baacc`;
- accepted failed PIT report SHA-256: `ca5d5494b9c4be0158bd5d89c2f5b70aae0ba3a717a4af60f437bf4eaad37cea`;
- feasibility parent SHA-256: `3c299447e0ed8fd48d10c8cc792cf57396d87378cb21575e219b624c6a50566a`;
- 300/300 Company Facts hashes matched on the source-only diagnostic replay;
- 300/300 SEC submissions roots succeeded;
- 5,896 audited observations survived from 5,902 original-accession candidates;
- exactly **3 ambiguous earliest period contexts** and **6 accession/form/filing-date contradictions** violated frozen zero-tolerance source-integrity gates;
- target/development market outcomes read: **0**;
- protected return rows read: **0**; protected holdout consumed: **false**;
- final source disposition: `ACCEPTED_NEGATIVE_PIT_SOURCE_INTEGRITY_FAILURE`.

This is a source-quality limitation but **not evidence of corrupted local ATLAS data**. The diagnostic re-fetched the official Company Facts documents and reproduced all 300 Gate0 hashes, then re-read SEC submissions metadata and reproduced the same contradictions. Purging/refetching the ATLAS lake or cache is not a repair. The problem is ambiguity/inconsistency in official SEC representations and the frozen v1 contract correctly failed closed rather than inventing a canonical interpretation.

The v1 family may not be rescued after observation by selecting a preferred start date/context, tolerating Company Facts versus Submissions filing-date drift, treating `10-Q/A` as `10-Q`, dropping offending rows, or relaxing the frozen zero-tolerance reconciliation rules.

## SEC Form 13F institutional-positioning v1 — accepted-negative source-integrity closeout

Mechanism: `PIT_SEC_FORM13F_INSTITUTIONAL_POSITIONING_CHANGE_AND_CONSENSUS_ACCUMULATION`.

- Gate0 v2 contract: `alpha-gate-sec-13f-feasibility-v2-official-bulk-probe-only-no-market-outcomes`;
- Gate0 v2 fingerprint: `4f41f7b1ca93bb76d559134d8ef74505ffd6a598e96676011ef515026d491696`;
- Gate0 result: `PROBE_FEASIBILITY_FAIL` because the 2016Q1 valid-nine-character-CUSIP fraction was **0.993405**, below the frozen **0.995** minimum; all other structural probe gates passed;
- 2016Q1 affected population: **10,431 malformed rows across 374 accessions** from **1,581,558** initial 13F-HR holding rows;
- source-only diagnostic found no blanks or long CUSIPs; all malformed values were short, but included heterogeneous values such as `COM`, `ETF`, `0`, and one- through eight-character strings, so mechanical zero-padding was not authorized;
- original-EDGAR reconciliation V1 locator failure is preserved as `IMPLEMENTATION_DEFECT_FIXED`;
- original-EDGAR reconciliation V2 used the authoritative SEC quarterly `master.idx` locator and reconciled the same frozen **374 accessions / 10,431 malformed rows**;
- **374/374** affected accessions matched original-versus-bulk CUSIP row counts;
- **374/374** had exact original-versus-bulk CUSIP multisets;
- all **10,431** malformed bulk rows were reproduced exactly in the original as-filed EDGAR XML;
- exactly one archive CIK differed from the bulk CIK, explaining the repaired V1 locator defect without changing the source-integrity result;
- closeout contract: `alpha-gate-sec-13f-closeout-v1-as-filed-cusip-source-integrity-failure-no-market-outcomes`;
- closeout fingerprint: `0375d5567e0547c151f9fb140309aa568d17528246e611a68fa5984a1c481acd`;
- accepted reconciliation report SHA-256: `e5b0cad238eb13f998c34ca51f659474484ba0ab97e64091a1a73cb604083d47`;
- final disposition: `ACCEPTED_NEGATIVE_SOURCE_INTEGRITY_FAILURE`;
- failure taxonomy: `SOURCE_INTEGRITY_FAIL`;
- provider reads performed by closeout: **0**;
- target/development outcome rows read: **0**;
- protected return rows read: **0**; protected holdout consumed: **false**;
- historical supported alpha remains **0**; Phase33 authority remains **false**.

The exact Form 13F v1 experiment cannot be rescued by lowering the 99.5% CUSIP-validity threshold, zero-padding malformed values, dropping malformed rows or filings, inferring identity from issuer/class, switching source reconciliation rules after observation, or opening outcomes to choose among repairs. Any future institutional-positioning experiment must be prospectively preregistered under a materially different source/identity contract.

## Immediate next action

1. Finish repository closure for the accepted-negative SEC Form 13F source-integrity result: synchronized living documents, PR/merge, and post-merge verification on `main`.
2. **Then STOP. ATLAS is operator-paused.** Do not define, freeze, implement, or run another alpha family; do not advance to Phase33 or another roadmap stage.
3. Await explicit user direction after the separate **ATLAS Review** exploration. Any future path change must be reconciled back into the normative roadmap/status before implementation resumes.
4. Phase33 remains blocked until at least one historical alpha earns accepted `SUPPORTED` authority unless a later explicit roadmap revision changes that architecture under proper governance.

## Downstream boundary

The roadmap is conditional rather than schedule-driven. Accepted-negative research improves ATLAS's retained knowledge but cannot substitute for positive alpha support. LIVE, automatic broker failover, and new trading authority remain unavailable until their later separately accepted gates. The current operator pause is stricter than the ordinary roadmap: no new stage or alpha-development work begins until explicit resume direction is given.