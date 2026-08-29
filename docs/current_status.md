# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28. Phase31 remains closed `ACCEPTED_NEGATIVE`. Phase32 core 8-K source feasibility V2 is accepted PASS. Semantic source qualification V1 is NOT ACCEPTED and Phase32 is stopped for root-cause diagnosis; zero market outcomes are authorized.**

Read `docs/roadmap.md`, this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_semantic_source_qualification.md`, `docs/phase32_sec_edgar_access_incident.md`, and `docs/phase31_closeout.md` before continuing.

## Authority state

- Accepted foundation: through **Phase31**.
- Phase26–31: all `ACCEPTED_NEGATIVE`.
- Accepted historical alpha support: **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Active gate: **Phase32 — SEC 8-K Material Corporate-Event Alpha**.
- Active internal step: **diagnose semantic V1 source failure**.
- Current Massive subscription declaration: **Stocks Starter**.
- Phase33 signal-to-trade remains blocked.
- LIVE and automatic broker failover remain disabled.

Root cause before workaround is mandatory. A failed source/check stops progression until the defect is understood and corrected.

## Protected holdout

Master protected outcome window remains `2026-05-12` through `2026-08-11`.

Phases26–31 and all Phase32 source work have read zero protected returns. Semantic V1 also read zero target outcomes, zero protected candidate rows, and zero protected returns. The holdout remains outcome-unopened.

## Phase32 core source feasibility V2 — ACCEPTED PASS

Contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine PASS retained:

- original 8-K index rows: **6,048**;
- ticker-linked rows: **5,272**;
- sampled official SEC records: **48**;
- sampled SEC item codes: **94**;
- SEC filing-date mismatches: **0**;
- target/protected return reads: **0**.

Accepted source boundary remains Massive `/stocks/filings/vX/index?form_type=8-K` plus official `data.sec.gov/submissions`, with public availability `FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`.

## Semantic V1 — NOT ACCEPTED

Semantic V1 fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Target-machine execution failed these checks:

- `all_sampled_tickers_align`;
- `all_sampled_supporting_text_is_grounded`.

No scientific/trading authority was granted.

A separate contract defect was also identified: V1 encoded a January-2022 provider-history expectation and `2022-01-03` safe start that were not established by the supplied Massive endpoint documentation. The supplied docs state Plan History is **not applicable**. That history assumption is therefore rejected and must not propagate into a corrected contract.

V1 is preserved as failed source-only evidence rather than deleted or rewritten.

## Exact next target

Run the local-evidence diagnostic:

`scripts/diagnose_phase32_semantic_failure.py`

It performs no provider calls and reads no market outcomes. It reports the exact sampled ticker mismatches and supporting-text/items-text grounding failures so the root cause can be identified before any correction is designed.

Do not freeze hypotheses, inspect returns, or substitute another semantic method until this failure is diagnosed.
