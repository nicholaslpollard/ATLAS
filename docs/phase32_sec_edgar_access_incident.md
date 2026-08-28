# Phase 32 SEC EDGAR Access Incident

## Status

`SOURCE_FEASIBILITY_NOT_ACCEPTED / SEC REACHABLE / FOURTH SOURCE-FORMAT FAILURE / PRESENTATION-TOLERANT PARSER REPAIR`

Observed target heads:

- original denied transport: `1ad589e8dc46566a2af1b0c0afa2664731c08d0f`
- fair-access identity repair: `8b68b5f657b85c0bb7343dea9bc23960fcea1707`
- bounded index-header transport: `9d00638a1054fcfa5a2d6ed3fe2ab0bb735242e3`
- raw-header transport attempt: `3b4046de4c2f15ec7e35d2091c9a2a882dce1d38`

Frozen feasibility fingerprint:

`e8fb25e3b1e8a81bd87761024ac692edcaf29d59c64547ee46f833725c972c10`

Observed target-machine results on 2026-08-28:

1. complete-submission transport: `SEC EDGAR request failed with HTTP 403`
2. declared-contact complete-submission transport: HTTP 403 again
3. listed `-index-headers.html` transport: SEC access succeeded, then strict parsing stopped with `SEC submission header is missing ACCESSION NUMBER`
4. `.hdr.sgml` transport attempt: SEC access again succeeded far enough to recover `ACCEPTANCE-DATETIME`, but strict accession parsing again stopped with `SEC submission header is missing ACCESSION NUMBER`

## Scientific interpretation

All four results are source-feasibility failures, not alpha results. None granted Phase32 feasibility acceptance, froze an alpha hypothesis, read target/protected market outcomes, consumed the protected holdout, or granted Phase33/trading authority.

The frozen Phase32 probe windows, Massive 8-K discovery contract, official SEC provenance requirement, conservative acceptance-time availability rule, bounded sampling, no-outcome blindness, and downstream authority gates remain unchanged.

ATLAS must not weaken chronology, substitute Massive filing date for exact SEC acceptance time, or use performance data to route around source defects.

## Root-cause refinement

The HTTP 403 issue is resolved: the target machine can reach SEC Archives using the declared local contact identity and conservative one-request-per-second transport.

The remaining issue is representation parsing. Official SEC accession directories publicly enumerate the `-index-headers.html` artifact and it exposes the exact fields Phase32 needs: `<ACCEPTANCE-DATETIME>`, `ACCESSION NUMBER`, `ITEM INFORMATION`, and filing CIK metadata. The `.hdr.sgml` name appears inside the filing-header presentation but is not consistently enumerated as a standalone archive file, so ATLAS will not rely on it as the transport target.

The original index-header parser was too strict because it required human-readable fields to occupy an entire physical line. SEC presentation markup can trail those fields on the same line, so exact line-end anchors are not a safe representation assumption.

## Fourth generic repair

The repair is source-only, presentation-tolerant, and outcome-blind:

- return to the official listed `.../<accession>-index-headers.html` artifact;
- keep `SEC_EDGAR_CONTACT_EMAIL` local and validate it before requests;
- retain the declared `ATLAS Research <contact>` User-Agent;
- retain `Accept-Encoding: gzip, deflate` with explicit decoding;
- retain exactly one SEC request per second;
- extract `<ACCEPTANCE-DATETIME>` without requiring a line-end boundary;
- extract `ACCESSION NUMBER`, `CENTRAL INDEX KEY`, and `ITEM INFORMATION` while allowing trailing HTML presentation markup;
- keep the accession value itself strictly validated as `##########-##-######`;
- independently require the parsed SEC accession to equal the requested Massive accession before returning the header;
- reject complete-submission `.txt` and standalone `.hdr.sgml` transport targets;
- keep all reads under official `www.sec.gov/Archives/edgar/`;
- fail closed on HTTP 403 and do not automatically retry it;
- never commit or print the real contact address.

No accession-specific, ticker-specific, date-specific, or performance-informed exception is permitted.

The frozen feasibility fingerprint remains unchanged because the SEC authority, provenance fields, timing rule, probe windows, sample policy, and no-outcome boundaries are unchanged. The repair only corrects parsing of the same official filing-header metadata representation.
