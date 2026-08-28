# Phase 32 SEC EDGAR Access Incident

## Status

`SOURCE_FEASIBILITY_NOT_ACCEPTED / SECOND 403 CONFIRMED / TRANSPORT_REPAIR_REQUIRED`

Original denied target head:

`1ad589e8dc46566a2af1b0c0afa2664731c08d0f`

First fair-access repair head:

`8b68b5f657b85c0bb7343dea9bc23960fcea1707`

Frozen feasibility fingerprint:

`e8fb25e3b1e8a81bd87761024ac692edcaf29d59c64547ee46f833725c972c10`

Observed target-machine results on 2026-08-28:

1. original transport: `SEC EDGAR request failed with HTTP 403`
2. declared-contact transport: `SEC EDGAR request denied with HTTP 403 under fair-access controls`

The second run used a locally configured contact address that passed ATLAS validation. The first SEC request was still denied. ATLAS did not retry the denial.

## Scientific interpretation

Both results are source-access failures, not alpha results. Neither run granted Phase32 feasibility acceptance, froze an alpha hypothesis, read target/protected market outcomes, consumed the protected holdout, or granted Phase33/trading authority.

The frozen Phase32 probe windows, Massive 8-K discovery contract, official SEC provenance requirement, conservative acceptance-time availability rule, bounded sampling, no-outcome blindness, and downstream authority gates remain unchanged.

## Root-cause refinement

The first repair fixed an incomplete declared User-Agent identity, but the second 403 proves that missing contact identity was not sufficient to explain the target-machine denial.

SEC public guidance allows automated access when a declared User-Agent is used and requests remain below the public rate threshold. SEC also documents that IP addresses can be temporarily limited under fair-access controls. Therefore persistent 403 is treated as a transport/public-IP access state until proven otherwise, never as scientific evidence.

ATLAS must not weaken chronology, substitute Massive filing date for exact SEC acceptance time, or use performance data to route around the denial.

## Second generic transport repair

Phase32 feasibility needs only the official filing submission header fields, not the complete filing body. The dedicated official SEC filing `-index-headers.html` artifact contains the same `<SEC-HEADER>` block with:

- `ACCESSION NUMBER`
- `<ACCEPTANCE-DATETIME>`
- `ITEM INFORMATION`

The second repair is therefore generic and outcome-blind:

- keep `SEC_EDGAR_CONTACT_EMAIL` local and validate it before requests;
- use the SEC sample User-Agent shape: `ATLAS Research <contact>`;
- send `Accept-Encoding: gzip, deflate` and decode those encodings explicitly;
- request only `.../<accession>-index-headers.html`, never the much larger complete-submission `.txt`;
- reduce the feasibility transport to exactly one SEC request per second;
- keep all SEC reads under official `www.sec.gov/Archives/edgar/`;
- fail closed on HTTP 403 and do not automatically retry it;
- never commit or print the real contact address.

No accession-specific, ticker-specific, date-specific, or performance-informed exception is permitted.

The frozen feasibility fingerprint remains unchanged because the official source family, provenance fields, timing rule, probe windows, sample policy, and no-outcome boundaries are unchanged; only the bounded official SEC header transport artifact is narrowed.
