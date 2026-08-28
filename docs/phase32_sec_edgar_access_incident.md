# Phase 32 SEC EDGAR Access Incident

## Status

`SOURCE_FEASIBILITY_NOT_ACCEPTED / SEC REACHABLE / HEADER-PRESENTATION PARSER MISMATCH / RAW SGML REPAIR`

Original denied target head:

`1ad589e8dc46566a2af1b0c0afa2664731c08d0f`

First fair-access repair head:

`8b68b5f657b85c0bb7343dea9bc23960fcea1707`

Header-only HTML transport head:

`9d00638a1054fcfa5a2d6ed3fe2ab0bb735242e3`

Frozen feasibility fingerprint:

`e8fb25e3b1e8a81bd87761024ac692edcaf29d59c64547ee46f833725c972c10`

Observed target-machine results on 2026-08-28:

1. original complete-submission transport: `SEC EDGAR request failed with HTTP 403`
2. declared-contact complete-submission transport: `SEC EDGAR request denied with HTTP 403 under fair-access controls`
3. dedicated `-index-headers.html` transport: SEC access succeeded, then parsing stopped with `SEC submission header is missing ACCESSION NUMBER`

The third result proves the target machine can now reach the official SEC Archives path under the bounded fair-access request. The remaining defect is a source-presentation/parser mismatch, not an IP-access failure.

## Scientific interpretation

All three results are source-feasibility failures, not alpha results. None granted Phase32 feasibility acceptance, froze an alpha hypothesis, read target/protected market outcomes, consumed the protected holdout, or granted Phase33/trading authority.

The frozen Phase32 probe windows, Massive 8-K discovery contract, official SEC provenance requirement, conservative acceptance-time availability rule, bounded sampling, no-outcome blindness, and downstream authority gates remain unchanged.

ATLAS must not weaken chronology, substitute Massive filing date for exact SEC acceptance time, or use performance data to route around source defects.

## Root-cause refinement

The first repair corrected the declared fair-access identity. The second repair narrowed the request and demonstrated that the official SEC path is reachable from the target machine.

The `-index-headers.html` resource is a presentation artifact. Although it renders the filing header fields, its HTML representation is not guaranteed to be byte-identical to the raw SGML payload expected by the parser. The target failure occurred after successful SEC access when the parser could not reconcile the rendered header representation to its strict raw-header grammar.

SEC's EDGAR data documentation provides a dedicated raw filing-header artifact in the accession directory:

`.../<accession>.hdr.sgml`

This is the appropriate provenance source because Phase32 needs only the raw header fields and not an HTML presentation or the complete filing body.

## Third generic transport repair

The repair is source-only and outcome-blind:

- keep `SEC_EDGAR_CONTACT_EMAIL` local and validate it before requests;
- retain the declared `ATLAS Research <contact>` User-Agent;
- retain `Accept-Encoding: gzip, deflate` with explicit decoding;
- retain exactly one SEC request per second;
- request only the official raw `.../<accession>.hdr.sgml` artifact;
- parse the raw SGML header payload directly;
- retain deterministic compatibility with a wrapped `<SEC-HEADER>...</SEC-HEADER>` fixture form;
- reject complete-submission `.txt` and `-index-headers.html` transport targets;
- keep all reads under official `www.sec.gov/Archives/edgar/`;
- fail closed on HTTP 403 and do not automatically retry it;
- never commit or print the real contact address.

No accession-specific, ticker-specific, date-specific, or performance-informed exception is permitted.

The frozen feasibility fingerprint remains unchanged because the official SEC source family, provenance fields, timing rule, probe windows, sample policy, and no-outcome boundaries are unchanged. Only the bounded representation used to read the same official filing header has been corrected.
