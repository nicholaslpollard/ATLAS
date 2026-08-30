# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-30 (America/New_York). Phase32 remains closed and merged `ACCEPTED_NEGATIVE`. The SEC XBRL fundamental-quality/accrual research program has completed, merged, and closed `ACCEPTED_NEGATIVE`; its post-merge full regression is green on Ubuntu and Windows. The current pre-Phase33 gate is a frozen source-only SEC Schedule 13D/13G beneficial-ownership feasibility audit. Protected stock/SPY returns remain unread and the master holdout remains unconsumed. Historical supported alpha remains 0 and Phase33 remains blocked.**

Read `docs/roadmap.md`, this file, `docs/alpha_gate_sec_beneficial_ownership_feasibility.md`, `docs/alpha_gate_sec_xbrl_closeout.md`, retained XBRL scientific/source records, retained Phase32 records, `docs/phase_flow.md`, and accepted code/CI evidence before continuing.

## Authority state

- Accepted numbered foundation: through **Phase32**, merged into `main`.
- Phase26–32: all scientifically valid `ACCEPTED_NEGATIVE`.
- Completed pre-Phase33 SEC XBRL fundamental-quality/accrual mechanism: **`ACCEPTED_NEGATIVE`**.
- XBRL PR #38 / merge: `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`; post-merge full ATLAS Ubuntu/Windows regression passed.
- Current pre-Phase33 research branch: `alpha-gate-sec-beneficial-ownership-feasibility`.
- Current mechanism: `PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`.
- Frozen beneficial-ownership feasibility fingerprint: `f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`.
- Beneficial-ownership alpha hypotheses: **not frozen**; target/protected market outcomes remain forbidden/unread.
- Accepted historical modern alpha support: **0**.
- Phase33 signal-to-trade entry condition: **not satisfied / blocked**.
- Master protected outcome window `2026-05-12..2026-08-11`: **unconsumed**.
- LIVE and automatic broker failover remain disabled.
- Current Massive subscription: **Stocks Starter**; no broader entitlement is assumed.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Phase32 PR #37 / merge: `69f8aa81289934b71f2652482c747391917c15a3`.

Root cause before workaround remains mandatory. Failed research evidence must be preserved. No failed family may be rescued by changing thresholds, horizon, costs, feature definitions, direction, multiplicity, winner rules, or protected policy after results.

## Current SEC Schedule 13D/13G beneficial-ownership source gate

Mechanism:

`PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`

Feasibility contract:

`alpha-gate-sec-beneficial-ownership-feasibility-v1-schedule13d13g-source-only-no-market-outcomes`

Frozen feasibility fingerprint:

`f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`

Source lineage begins after accepted XBRL merge `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`.

The frozen source window is `2016-01-01..2026-08-11`. ATLAS reads official SEC quarterly master indexes, then exact complete-submission `.txt` archives for a deterministic 200-filing sample stratified across legacy/structured × initial/amended 13D/13G forms. The SEC structured compliance boundary is `2024-12-18`.

The gate reconciles exact accession, form, filing date, `SUBJECT COMPANY` CIK, SEC acceptance time, the first XNYS session open strictly after acceptance, and exact PIT active common-stock identity through the accepted Massive CIK/date reference seam. Multiple eligible share classes fail closed; no arbitrary ticker/share-class selection is permitted.

Alpha hypotheses remain **not frozen**. The source gate reads zero market outcomes, zero protected returns, and grants zero broker/order/PAPER/LIVE authority. `FEASIBILITY_PASS` may authorize only a later complete scientific freeze; it does not unblock Phase33.

## Phase32 final evidence

Phase32 scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Exactly five hypotheses remained frozen throughout Phase32: `equity_issuance_short`, `share_repurchase_long`, `financial_integrity_adverse_short`, `listing_distress_short`, and `solvency_distress_short`.

Accepted source/predictor fingerprints:

- core V2: `978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`;
- semantic V2: `eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`;
- independent source/predictor acceptance: `531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`.

Phase32 development produced one frozen finalist, `solvency_distress_short`. The independent finalist blindness/lineage audit froze a protected source-only population of **46 event rows / 33 signal sessions / 40 unique instruments** against frozen minimums **50 / 20 / 20**.

Accepted finalist-audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

Accepted protected-plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Accepted protected-plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

The 46-row population failed the frozen 50-row event minimum before protected performance. Protected return rows read = **0**; protected holdout consumed = **false**. Phase32 closed `ACCEPTED_NEGATIVE`, historical supported alpha remained 0, and Phase33 remained blocked.

## SEC XBRL fundamental-quality/accrual mechanism — final `ACCEPTED_NEGATIVE`

This research program materially changed the information mechanism from Phase32 by using PIT standardized quarterly fundamentals from original SEC 10-Q/10-K filings.

### Accepted source feasibility

Feasibility contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Feasibility fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

Accepted feasibility evidence fingerprint:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

Target result on head `5a8c15f95417390d0d64ff240977adfb38a20c45`: **`FEASIBILITY_PASS`** with 200 successful Company Facts documents, 170 accrual-history-ready issuers, 92 profitability-history-ready issuers, zero target outcomes, zero protected returns, and zero trading/mutation authority.

### PIT audit and targeted repair

Frozen v1 audit fingerprint:

`50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`

The first v1 target audit is permanently preserved as **`AUDIT_FAIL`**: 139 unambiguous PIT mappings and 28 issuers with >=3 mappings versus frozen minimum 30.

Root-cause diagnosis identified incorrect identity-universe semantics in the Massive historical query: `active=false` plus non-common-stock types expanded the candidate set with preferreds, warrants, units, rights, and legacy securities.

Targeted repair fingerprint:

`e17cf5539fbd5d3d0c31514d5fbed97332f046eb98af05dfaa0039a8c127304f`

The proper owning-layer correction used exact historical CIK/date with `active=true` and `type=CS`, retained the same 40 issuers/accessions/SEC chronology/numeric gates, and replayed existing source-only caches with zero provider calls. Corrected v2 result: **`AUDIT_PASS`**, 171 unambiguous common-stock mappings and 38 issuers with >=3 mappings. The v1 failure remains preserved.

### Frozen science

Scientific contract:

`alpha-gate-xbrl-scientific-v1-six-yoy-quality-change-hypotheses`

Scientific fingerprint:

`2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`

The six frozen hypotheses covered year-over-year improvement/deterioration in gross profitability, cash profitability, and accrual quality. The contract froze PIT quarter semantics, exact chronology, 63-session primary horizon, SPY-relative plus unhedged outcomes, direction-specific costs, 70/30 chronological development partition, 63-session purge, dependence-aware bootstrap, global `HOLM_BONFERRONI_GLOBAL_6`, robustness/concentration gates, selection-only winner choice, no runner-up substitution, and finalist-only protected returns.

Development implementation fingerprint:

`3b5a02113ceab0065ea9a03020cc5266222e67ba39abe36311a6959e7e2d488f`

### Accepted development-negative evidence

Accepted target development head:

`58e7c9b60ba59d250a7c91e282daefa4aef3c2b9`

Result: **`ACCEPTED_NEGATIVE_DEVELOPMENT`**.

- predictor rows: **5,536**;
- development predictor rows: **4,157**;
- protected predictor rows: **1,379**;
- usable development outcomes: **3,963**;
- selection passers after all hard gates + Holm: **0**;
- selection winners: **0**;
- internal finalists: **0**;
- protected-return eligible finalists: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- Phase33 authority: **false**.

No candidate survived selection, so protected performance was never authorized.

### Accepted negative closeout

Closeout contract:

`alpha-gate-xbrl-closeout-v1-development-negative-protected-unread`

Target-machine closeout: **PASS / `ACCEPTED_NEGATIVE`**.

Accepted closeout evidence fingerprint:

`291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`

Accepted artifact SHA-256 values:

- development report: `50bf99956ca95d725764b16bc5ae622b5ffe9dbfbadb4e63afa591a4aef998c6`;
- predictor report: `246bc1df65ce923b83167ea65f7e25b266657dec30fdcfd841e4bae260fbdb16`;
- predictor rows: `9b3526527d2d45433f5970d768155c9763c16bc8d0772fdc526659ec1aabd14a`;
- development outcomes: `17be9dd103902ea0e9f39c172b7dfb0cf3d552b6f743bd8101c7f836b8500b55`;
- finalists: `c5cfddbe30b597d115560a9611e8bf3bef5bcb76f7c59f5d5f5a071db458945f`.

The closeout reads only persisted artifacts and performs zero provider calls, zero new market reads, and zero provider/broker/order/PAPER/LIVE/automation mutations.

## Protected boundary

Master protected outcome window remains `2026-05-12..2026-08-11`.

Neither Phase32 nor the XBRL mechanism opened protected stock/SPY returns. The current beneficial-ownership feasibility gate also forbids all target/protected market outcomes. The holdout remains unconsumed. It is not available for post-hoc rescue of failed families and may be used only under a later materially different preregistered mechanism that independently satisfies its frozen source/scientific entry conditions.

## Retained Phase31 provenance

Phase31 Form-4 alpha closed `ACCEPTED_NEGATIVE` under scientific fingerprint `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`.

The original Phase31 target result remains `FEASIBILITY_FAIL`; it is preserved rather than rewritten. The diagnosed root cause was a Massive beta source-association/data-quality defect, not a chronology-rule defect and not a performance result.

Accepted source-quality repair fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Retained source-quality policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Phase31 produced zero survivors/winners/finalists/support and zero protected reads.

## Immediate repository action

Complete exact-head focused beneficial-ownership plus full ATLAS Ubuntu/Windows CI for the frozen source gate. Once repository certification is green, run the source-only feasibility runner on the target machine to establish real SEC/Massive coverage and PIT identity evidence. Do not enter market-outcome science before that source result is accepted and a complete scientific contract is frozen.

Do not enter Phase33 unless a later mechanism earns accepted historical `SUPPORTED` authority.
