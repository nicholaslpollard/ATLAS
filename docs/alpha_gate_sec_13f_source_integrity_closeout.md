# SEC Form 13F source-integrity closeout

The audit-aligned Form 13F experiment is closed from source-only evidence before any market outcome is opened.

Mechanism:

`PIT_SEC_FORM13F_INSTITUTIONAL_POSITIONING_CHANGE_AND_CONSENSUS_ACCUMULATION`

Closeout contract:

`alpha-gate-sec-13f-closeout-v1-as-filed-cusip-source-integrity-failure-no-market-outcomes`

Closeout fingerprint:

`0375d5567e0547c151f9fb140309aa568d17528246e611a68fa5984a1c481acd`

Final source disposition:

`ACCEPTED_NEGATIVE_SOURCE_INTEGRITY_FAILURE`

Failure taxonomy:

`SOURCE_INTEGRITY_FAIL`

## Accepted source lineage

Gate0 v2 was a bounded four-anchor source probe. Three anchors had a 100% nine-character CUSIP rate, while 2016Q1 contained 1,581,558 initial 13F-HR information-table rows and only 99.3405% had raw nine-character CUSIPs, failing the frozen 99.5% minimum. All other structural gates passed. Gate0 therefore preserved `PROBE_FEASIBILITY_FAIL` with zero market or protected outcome reads.

The source diagnostic showed 10,431 malformed rows across 374 accessions. The values were not safely reducible to leading-zero loss: malformed values included alphabetic and extremely short strings, and the diagnostic did not authorize any repair.

Original-EDGAR reconciliation V1 preserved more than 330 original filings before an HTTP 404 exposed a locator implementation defect. V1 had derived the archive CIK from the bulk submission record. The scientific population and source result were not changed. The locator failure is retained as `IMPLEMENTATION_DEFECT_FIXED`.

Reconciliation V2 used official SEC 2016 Q1 `master.idx` filenames as the archive-location authority while retaining the exact same frozen 374-accession / 10,431-row population. The accepted V2 source result is decisive:

- 374/374 affected accessions resolved by the official master index;
- exactly one archive CIK differed from the bulk submission CIK;
- 374/374 original filings had the same CUSIP row count as the bulk representation;
- 374/374 had an exact CUSIP multiset match;
- all 10,431 malformed bulk CUSIP rows were reproduced exactly in the authoritative original as-filed EDGAR XML;
- classification was `AS_FILED_MALFORMED_CUSIP_CONFIRMED` for all 374 accessions and all 10,431 malformed rows;
- no CUSIP repair or ATLAS identity was granted;
- target outcome rows read = 0;
- protected return rows read = 0;
- protected holdout consumed = false;
- scientific freeze remained false;
- Phase33 authority remained false.

Therefore the 2016 source defect is not a SEC bulk-flattening artifact that can be corrected by switching to original filing XML. It is present in the original as-filed source itself.

## Permanent anti-retuning boundary

This exact 13F experiment may not be rescued after observing the source result by:

- lowering the frozen 99.5% raw nine-character-CUSIP gate;
- left-zero-padding malformed CUSIPs;
- dropping malformed rows or entire malformed filings;
- inferring CUSIPs from issuer name, security class, nearby rows, or later observations;
- redefining CUSIP validity;
- keeping only rows that appear repairable;
- opening market outcomes to decide whether a source repair is profitable.

Those changes would alter the source-selection/identity contract after observing the failure.

A future Form 13F experiment is not prohibited, but it must be a new preregistered version with an authoritative identity/canonicalization policy for malformed as-filed holdings frozen before any market outcome is opened.

The closeout runner is provider-free. It reads only the persisted V2 reconciliation report, validates the exact accepted source result and zero-outcome governance boundary, hashes the parent report, and writes an immutable closeout report.
