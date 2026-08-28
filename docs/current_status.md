# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28. Phase31 remains closed `ACCEPTED_NEGATIVE`. Phase32 SEC 8-K source feasibility is active; six archive/header source attempts failed without reading any market outcomes, and the active repair is a separately fingerprinted V2 feasibility contract using the official SEC Submissions API.**

Read `docs/roadmap.md`, this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_sec_edgar_access_incident.md`, and `docs/phase31_closeout.md` before continuing.

## Authority state

- Accepted foundation: through **Phase31**.
- Phase26–31: all `ACCEPTED_NEGATIVE`.
- Accepted historical alpha support: **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Active gate: **Phase32 — SEC 8-K Material Corporate-Event Alpha**.
- Active internal step: **V2 source feasibility/provenance only**.
- Phase33 signal-to-trade remains blocked until at least one alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE and automatic broker failover remain disabled.

Never weaken chronology, identity, statistical, multiplicity, protected, or authority gates to obtain PASS. Zero finalists/trades remains a valid result.

## Protected holdout

Master protected outcome window remains `2026-05-12` through `2026-08-11`.

Phases26–31 read zero protected returns. Phase31 closeout confirmed protected candidate rows **0**, protected return rows **0**, and holdout consumed **False**. Phase32 feasibility remains forbidden from reading any target or protected market outcomes.

## Phase31 closeout retained

Phase31 closed `ACCEPTED_NEGATIVE` with independent result `PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF` and closeout head `92e61b74d3c6cf95db122b1981ed2b53ab1c7b07`.

Development predictor / usable rows were **5,400 / 5,371**. All four frozen Form-4 candidates failed mandatory gates; survivors, winners, finalists, and supported candidates were all zero. Do not retune or reinterpret Phase31.

Retained source facts include 2,992,608 authoritative full-history rows and 45,915 authoritative source-quality target rows. Full detail remains in `docs/phase31_closeout.md` and retained Phase31 provenance documents.

## Phase32 V1 source history — not accepted

The failed V1 feasibility fingerprint remains:

`e8fb25e3b1e8a81bd87761024ac692edcaf29d59c64547ee46f833725c972c10`

Six target attempts established:

1. complete-submission transport: HTTP 403;
2. declared-contact complete-submission transport: HTTP 403;
3. `-index-headers.html`: SEC reachable, required accession field not recovered;
4. `.hdr.sgml` attempt: required accession field not recovered;
5. first presentation-tolerant index-header parser: required accession field not recovered;
6. entity/markup-normalizing parser at `a88ac62d43bd3a960489c3e0a262cf4609444eb2`: exact historical SEC URL returned only **524** normalized characters with `ACCESSION=False` and `NUMBER=False`.

All six were source failures only. No Phase32 hypothesis was frozen and no market/protected outcome was read.

## Phase32 V2 source contract

V2 contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Frozen V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Massive discovery remains:

`MassiveRESTClient -> GET /stocks/filings/vX/index?form_type=8-K`

Official SEC metadata source is now:

`https://data.sec.gov/submissions/CIK##########.json`

For older history, ATLAS may follow only SEC-declared `filings.files` JSON shards whose `filingFrom..filingTo` range contains the requested Massive filing date, with at most two candidate shards per lookup.

Every sampled filing must independently reconcile exact SEC accession, exact original `8-K` form, SEC filing date equal to Massive filing date, nonempty acceptance timestamp, and structured SEC item codes. SEC acceptance time is converted to `America/New_York` for the unchanged rule:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

The four probe windows and max-12 deterministic sample remain unchanged. V2 evidence/report paths use separate `/v2/` namespaces, so the failed V1 evidence remains intact.

## Local SEC contact configuration

The tracked `.env.example` template should contain the blank key:

`SEC_EDGAR_CONTACT_EMAIL=`

The real value belongs only in the gitignored local `.env`. A local `M .env.example` is expected when adding only that blank template key and is not, by itself, secret exposure.

## Exact next target

Runner:

`scripts/run_phase32_8k_feasibility.py`

The V2 target may perform bounded read-only Massive and `data.sec.gov/submissions` calls and write immutable source evidence/report artifacts. It may not read stock/SPY/options outcomes, protected returns, broker/account state, or submit orders/PAPER/LIVE actions.

If V2 feasibility passes, use only its non-performance SEC item-code coverage to freeze a finite scientific hypothesis family before any governed return read. If it fails, diagnose the source/provenance issue generically; do not inspect outcomes to rescue it.
