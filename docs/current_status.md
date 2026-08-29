# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28. Phase31 remains closed `ACCEPTED_NEGATIVE`. Phase32 core 8-K source feasibility V2 has passed on the target machine; the active step is now semantic 8-K source qualification with zero market outcomes authorized.**

Read `docs/roadmap.md`, this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_semantic_source_qualification.md`, `docs/phase32_sec_edgar_access_incident.md`, and `docs/phase31_closeout.md` before continuing.

## Authority state

- Accepted foundation: through **Phase31**.
- Phase26–31: all `ACCEPTED_NEGATIVE`.
- Accepted historical alpha support: **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Active gate: **Phase32 — SEC 8-K Material Corporate-Event Alpha**.
- Active internal step: **semantic source qualification only**.
- Current Massive subscription declaration: **Stocks Starter**.
- Phase33 signal-to-trade remains blocked until at least one alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE and automatic broker failover remain disabled.

Root cause before workaround remains mandatory. A failed source/check stops progression until the defect is understood and corrected; validators, chronology, identity, multiplicity, protected rules, and authority are never weakened to force PASS.

## Protected holdout

Master protected outcome window remains `2026-05-12` through `2026-08-11`.

Phases26–31 read zero protected returns. Phase32 V2 and the active semantic source gate read zero target/protected market outcomes. The holdout remains outcome-unopened.

## Phase31 retained closeout

Phase31 closed `ACCEPTED_NEGATIVE` with independent result `PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF` and closeout head `92e61b74d3c6cf95db122b1981ed2b53ab1c7b07`.

Development predictor / usable rows were **5,400 / 5,371**. All four frozen Form-4 candidates failed mandatory gates; survivors, winners, finalists, and supported candidates were all zero. Do not retune or reinterpret Phase31.

Original Phase31 feasibility disposition remains `FEASIBILITY_FAIL`; accepted source-quality fingerprint remains `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`; full acquisition retained **2,993,648** raw / **2,992,608** authoritative rows. Frozen scientific policy fingerprint remains `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`.

## Phase32 V1 source history — retained failure evidence

Six SEC archive/header attempts failed before any market outcome read. The final entity-aware parser showed an exact historical SEC URL normalizing to only **524** characters with required accession fields absent. These failures established that the presentation/archive-header method was unreliable; they did not establish alpha failure.

The source change was formally versioned rather than silently worked around. See `docs/phase32_sec_edgar_access_incident.md`.

## Phase32 V2 core source feasibility — ACCEPTED PASS

Contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine runner `scripts/run_phase32_8k_feasibility.py` returned **PASS** with:

- original 8-K index rows: **6,048**;
- ticker-linked rows: **5,272**;
- sampled official SEC records: **48**;
- sampled SEC item codes: **94**;
- successful Massive pages: **4**;
- SEC filing-date mismatches: **0**;
- target outcome rows: **0**;
- protected candidate rows: **0**;
- protected return rows: **0**;
- provider/broker/order/PAPER/LIVE writes: **0**.

Two samples had SEC acceptance local-calendar dates differing from filing dates. This is not a source mismatch: all 48 exact SEC filing dates matched Massive, and exact SEC `acceptanceDateTime` remains authoritative for timing.

Accepted core source boundary:

- discovery: Massive `/stocks/filings/vX/index?form_type=8-K`;
- authoritative metadata: `data.sec.gov/submissions/CIK##########.json` plus at most two SEC-declared date-matching historical submission shards;
- public-availability rule: `FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`.

## Active Phase32 semantic source qualification

Massive semantic sources being qualified:

- `/stocks/filings/8-K/vX/disclosures`;
- `/stocks/filings/8-K/vX/text`;
- `/stocks/taxonomies/vX/disclosures`.

Massive endpoint docs say Plan History is not applicable; a July 22, 2026 Massive provider article states disclosure coverage starts in January 2022. ATLAS is therefore empirically verifying the source and conservatively freezes semantic study history to begin no earlier than `2022-01-03`.

Contract:

`phase32-semantic-feasibility-v1-massive-8k-disclosures-text-no-market-outcomes`

Frozen semantic fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

The gate verifies taxonomy/versioning, original-8-K accession overlap, provider-native ticker alignment, supporting-text grounding in parsed 8-K Item text, SEC accession/form/filing-date/acceptance reconciliation, immutable evidence, and zero outcome/trading authority.

## Exact next target

Runner:

`scripts/run_phase32_semantic_feasibility.py`

If it passes, freeze the finite Phase32 hypothesis family and complete the full scientific contract **before** any development return read.

If it fails, stop. Diagnose and repair the actual source/provenance defect first; do not weaken the gate or substitute a workaround. Only after the intended method is shown infeasible may a different source method be defined.
