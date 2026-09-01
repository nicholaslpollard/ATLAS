# SEC Form 13F original-EDGAR CUSIP reconciliation

The audit-aligned Form 13F Gate0 bounded probe preserved a real 2016Q1 source failure: 10,431 of 1,581,558 original 13F-HR bulk information-table rows had CUSIPs whose raw length was not nine characters, producing a 99.3405% nine-character rate versus the frozen 99.5% minimum.

The preserved source-only diagnostic then showed that the defect is not safely reducible to leading-zero loss. All 10,431 malformed rows were short and nonblank, but they included values such as `COM`, `ETF`, and `0`; they were spread across 374 accessions; only 2,841 rows had a left-zero-pad candidate already seen as valid elsewhere in the archive; only 2,768 rows had a unique same-issuer/class valid candidate; and only 896 rows satisfied both signals simultaneously.

This gate therefore reconciles the **entire frozen affected population** against the original SEC EDGAR complete submissions before any decision is made about source repair or family closeout.

Contract:

`alpha-gate-sec-13f-original-edgar-reconciliation-v1-all-malformed-accessions-source-only-no-market-outcomes`

Fingerprint:

`6b28e6e7eac599d1f795fed2de200c0886f49b91af29a699faa98a043521c91c`

Frozen scope:

- anchor: `2016Q1`
- malformed accessions: `374`
- malformed bulk rows: `10,431`
- source: original SEC EDGAR complete submissions under `/Archives/edgar/data/...`
- maximum complete-submission response: `256,000,000` bytes
- source population: every accession containing at least one malformed CUSIP in the preserved Gate0 2016Q1 archive

The run reconstructs the affected accession list from the hash-validated preserved Gate0 ZIP, derives each filer CIK from `SUBMISSION.tsv`, and reads the corresponding original complete submission. Original submissions are persisted immutably and reused on restart, making the gate resumable without deleting or rewriting evidence.

For each accession ATLAS extracts `cusip` elements only from XML blocks in the original complete submission and compares the complete CUSIP multiset with the SEC flattened bulk information-table rows. It records whether the malformed bulk values are exactly present in the original filing, whether the original contains only valid nine-character CUSIPs, whether row counts differ, whether XML parsing fails, or whether the filing contains a mixed/unresolved pattern.

Interpretation is intentionally fail-closed:

- `AS_FILED_MALFORMED_CUSIP_CONFIRMED` means the malformed value is present in the original filing and is therefore not a bulk-only extraction defect.
- `BULK_FLATTENING_DIFFERS_FROM_VALID_ORIGINAL` means the original filing has the same number of CUSIP rows and all original CUSIPs are nine characters, but the flattened bulk CUSIP multiset differs.
- row-count mismatch, XML parse failure, mixed evidence, and other differences remain unresolved source defects until separately governed.

This reconciliation does **not** retroactively change the Gate0 `PROBE_FEASIBILITY_FAIL`, lower the 99.5% threshold, left-pad any CUSIP, map CUSIPs to ATLAS instruments, freeze economic hypotheses, open market prices or returns, consume protected data, authorize Phase33, or perform any broker/order/PAPER/LIVE action.

SEC documentation states that the Form 13F bulk data sets are extracted from the XML portion of EDGAR submissions, are presented from the as-filed data in flattened form, and are not a substitute for the original filing. The original EDGAR submission is therefore the correct authority for determining whether the 2016 defect originated in the filer submission or in the flattened dataset representation.
