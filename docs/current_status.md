# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28 after Phase31 closed `ACCEPTED_NEGATIVE` and PR #35 merged. Phase32 SEC 8-K source feasibility remains the active gate; the target machine has proven SEC Archives reachability but five source-format attempts have not yet completed feasibility, and no Phase32 market outcomes have been read.**

Read `docs/roadmap.md` first, then this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_sec_edgar_access_incident.md`, `docs/phase31_closeout.md`, and retained Phase31 provenance records.

## Authority state

- Accepted foundation: **through Phase31**.
- Phase26–31: all `ACCEPTED_NEGATIVE`; accepted historical alpha support remains **0**.
- Phase31 PR #35 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Historical Phase31 branch: `phase-31-sec-insider-transaction-alpha`.
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Active gate: **Phase32 — SEC 8-K Material Corporate-Event Alpha**.
- Active internal step: **source feasibility/provenance only**.
- Phase33 signal-to-trade remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains disabled. Automatic broker failover remains disabled.

Never weaken a chronology, identity, statistical, multiplicity, protected, or authority gate to obtain PASS. Zero finalists/trades is valid. Provider-native ticker strings/case and PIT identity remain authoritative.

## Protected holdout

Master protected outcome window remains:

`2026-05-12` through `2026-08-11`

Phases26–31 read zero protected returns. Phase31 closeout explicitly confirmed:

- protected candidate rows read **0**
- protected return rows read **0**
- protected holdout consumed **False**.

Phase32 feasibility is forbidden from reading any target or protected market outcomes. A later Phase32 scientific contract must be frozen before governed performance and protected evidence remains finalist-only.

## Phase31 final closeout — ACCEPTED_NEGATIVE

Accepted independent result:

`PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF`

Closeout implementation head:

`92e61b74d3c6cf95db122b1981ed2b53ab1c7b07`

Final merge:

`ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`

Development predictor / usable outcome rows: **5,400 / 5,371**. Independent selection reconstruction:

- `open_market_purchase_long`: 1,516 rows / 641 sessions / 230 tickers — mandatory sample gate FAIL
- `clustered_open_market_purchase_long`: 638 / 376 / 136 — mandatory sample gate FAIL
- `open_market_sale_short`: 2,355 / 785 / 216 — mandatory sample gate FAIL
- `clustered_open_market_sale_short`: 1,281 / 645 / 131 — mandatory sample gate FAIL.

Selection survivors **0**; winners **0**; finalists **0**; supported candidates **0**. The two positive-looking selection LCB diagnostics remain non-authoritative because frozen mandatory gates and global multiplicity were not satisfied.

Complete final record: `docs/phase31_closeout.md`.

### Retained Phase31 source/provenance facts

Original Form-4 feasibility `FEASIBILITY_FAIL` and its repair history remain permanent provenance. Root cause remains a **Massive beta source-association/data-quality defect**, not an ATLAS parser bug.

Original failed feasibility target head:

`b59a64938eb84c0c1e7df3aaea390cc437326f94`

Original failed feasibility fingerprint:

`edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`

Historical chronology diagnostic implementation head:

`80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`

Historical chronology violation artifact SHA:

`3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`

Source-quality policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Source-quality fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Historical source-quality target retained **45,915** authoritative rows. Historical repair runner retained:

`scripts/run_phase31_form4_source_quality_repair.py`

Full historical acquisition retained:

- raw rows **2,993,648**
- authoritative rows **2,992,608**
- quarantined rows **1,040**
- contaminated accessions **187**
- chronology seeds **233**
- missing transaction-code seeds **15**
- month shards **62**.

Historical acquisition runner retained:

`scripts/run_phase31_form4_acquisition.py`

Frozen Phase31 scientific policy fingerprint:

`e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`

The predictor-only Form-4 event construction produced 5,400 development and 343 protected predictor rows before performance. Do not retune or reinterpret Phase31.

## Phase32 source boundary

Current Massive plan: **Stocks Starter**.

Discovery source:

`MassiveRESTClient -> GET /stocks/filings/vX/index?form_type=8-K`

Authoritative timestamp/item source:

`official SEC EDGAR -> www.sec.gov/Archives/edgar/data/.../<accession>-index-headers.html`

Feasibility public-availability rule:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

Phase32 feasibility must prove actual credential access and historical 8-K population at four frozen windows, provider-native ticker linkage, deterministic pagination, SEC accession reconciliation, exact `<ACCEPTANCE-DATETIME>`, `ITEM INFORMATION`, immutable evidence, and conservative SEC request behavior.

Target-machine source history on 2026-08-28:

- original complete-submission transport: HTTP 403;
- declared-contact complete-submission transport: HTTP 403;
- bounded `-index-headers.html` transport: SEC request succeeded, then strict parsing failed with `SEC submission header is missing ACCESSION NUMBER`;
- `.hdr.sgml` transport attempt: SEC request again reached filing-header content far enough to recover acceptance time, but strict accession parsing again failed with the same message;
- presentation-tolerant `-index-headers.html` parser at `d18aa3592f5a3718f91aeee1291e98c8dcf535ec`: SEC request succeeded, but accession extraction still failed with the same message.

The HTTP 403 problem is resolved. Official SEC 8-K index-header examples from the frozen-era history visibly contain the required fields, so the source remains appropriate. The current repair therefore keeps the same bounded `-index-headers.html` artifact but HTML-unescapes and removes browser presentation markup in a separate parser view before extracting human-readable fields. The original bounded SEC text remains unchanged for evidence hashing, parsed accession format remains strict, and the parsed accession must still equal the requested Massive accession exactly.

If another parse failure occurs, the error now returns only safe structural diagnostics: source URL, header SHA-256, normalized character count, and boolean presence of the `ACCESSION` and `NUMBER` tokens. It does not print credentials or infer an accession from the URL.

The declared contact identity, gzip/deflate support, one-request-per-second rate, fail-closed 403 behavior, frozen feasibility fingerprint, four probe windows, no-outcome blindness, and all downstream authority gates remain unchanged.

The SEC header path is derived generically from CIK + accession; no accession-specific exceptions are allowed. No market outcomes or protected returns have been read.

## Local SEC contact configuration

`.env.example` intentionally contains only the blank template:

`SEC_EDGAR_CONTACT_EMAIL=`

The real contact address belongs only in local `.env`, which is gitignored. `load_settings()` loads `.env` before the Phase32 SEC client is constructed, so a local `.env` value persists across PowerShell sessions without being committed.

## Exact next target — Phase32 8-K feasibility

Runner:

`scripts/run_phase32_8k_feasibility.py`

This step may perform bounded read-only Massive and official SEC requests. It may **not** read stock/SPY outcomes, protected returns, broker/account state, or submit any order/PAPER/LIVE action. Alpha hypotheses remain **NOT YET FROZEN**.

If source feasibility passes, the next internal action is to use only the non-performance source evidence to freeze a finite item-defined scientific contract before any return read. If feasibility fails, repair the source/provenance defect generically or select a genuinely different source; do not inspect outcomes to rescue it.
