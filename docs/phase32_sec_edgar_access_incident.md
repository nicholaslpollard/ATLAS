# Phase 32 SEC EDGAR Source Incident

## Status

`SOURCE_FEASIBILITY_NOT_ACCEPTED / SIXTH SOURCE-FORMAT FAILURE / OFFICIAL SUBMISSIONS API V2 CONTRACT`

Observed target heads:

- original denied complete-submission transport: `1ad589e8dc46566a2af1b0c0afa2664731c08d0f`
- fair-access identity repair: `8b68b5f657b85c0bb7343dea9bc23960fcea1707`
- bounded index-header transport: `9d00638a1054fcfa5a2d6ed3fe2ab0bb735242e3`
- raw-header transport attempt: `3b4046de4c2f15ec7e35d2091c9a2a882dce1d38`
- first presentation-tolerant parser: `d18aa3592f5a3718f91aeee1291e98c8dcf535ec`
- entity/markup-normalizing parser: `a88ac62d43bd3a960489c3e0a262cf4609444eb2`

Retained failed V1 feasibility fingerprint:

`e8fb25e3b1e8a81bd87761024ac692edcaf29d59c64547ee46f833725c972c10`

New V2 source-contract fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

## Sixth target result

At `a88ac62d43bd3a960489c3e0a262cf4609444eb2`, the target machine successfully reached the requested SEC archive URL for accession `0000004904-21-000060`, but the bounded response normalized to only **524** characters and contained neither the `ACCESSION` nor `NUMBER` tokens. ATLAS therefore stopped fail-closed with no feasibility acceptance.

The exact accession exists in the official SEC archive. The result shows that continued regex or presentation-normalization changes to `-index-headers.html` are not an evidence-based repair: the target response itself does not contain the required human-readable header fields.

## Scientific interpretation

All six archive/header attempts are source-feasibility failures, not alpha results. None froze a Phase32 hypothesis, read target/protected market outcomes, consumed the protected holdout, satisfied Phase33 entry, or granted broker/order/PAPER/LIVE authority.

The four frozen probe windows, Massive original-8-K discovery, deterministic sample policy, conservative decision timing, no-outcome blindness, and downstream authority gates remain unchanged.

ATLAS must not infer missing metadata from the URL, substitute Massive filing date for SEC acceptance time, make accession-specific exceptions, or use performance evidence to select a source repair.

## V2 source decision

The next feasibility contract uses the official SEC **Submissions API** at `data.sec.gov/submissions` rather than scraping archive presentation pages. The Submissions API is structured filing-history metadata and directly exposes the accession, filing date, acceptance timestamp, form, structured item codes, and primary document needed for this source-only gate.

This is a real source-contract change, so the prior fingerprint is not reused. V2 is explicitly versioned and receives a new frozen feasibility fingerprint before any market outcome read.

V2 safeguards:

- Massive discovery remains `form_type=8-K` and unchanged;
- SEC root source is `https://data.sec.gov/submissions/CIK##########.json`;
- older accessions may use only SEC-declared `filings.files` JSON whose filing-date range contains the requested Massive filing date;
- at most two matching archive shards are allowed per lookup;
- exact SEC `accessionNumber` must equal the requested Massive accession;
- exact SEC form must be original `8-K`, never `8-K/A`;
- SEC `filingDate` must equal Massive `filing_date`;
- SEC `acceptanceDateTime` must be present and is converted to Eastern for the unchanged decision rule;
- SEC `items` are inventoried as structured item codes;
- only an exact canonical sampled filing record is preserved immutably, so unrelated future company filings do not create false drift;
- all SEC requests identify ATLAS with the local contact, advertise gzip/deflate, remain read-only, and are limited to one request per second;
- no ticker/accession/date-specific exception is permitted;
- no market outcomes are authorized.

## Local contact configuration

`.env.example` may and should contain the blank tracked template key:

`SEC_EDGAR_CONTACT_EMAIL=`

The real address belongs only in local `.env`. A local modification to `.env.example` is not itself a secret exposure when it contains only the blank key.
