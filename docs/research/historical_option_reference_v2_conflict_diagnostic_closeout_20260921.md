# Historical Option Reference V2 conflict diagnostic closeout — 2026-09-21

## Scope

This immutable record closes the bounded read-only diagnostic
`atlas-historical-option-reference-v2-unversioned-conflict-diagnostic-v1`.

Contract fingerprint:
`f544bb78cb6d61cbd69aa5fd266ee20349b3a977b39cb85e79a0a6a5ec0f9678`.

Target V2 failure:
- partition: `expired-2014-06`
- ticker: `O:AAL140621C00020000`
- V2 failure: conflicting provider payloads shared highest correction rank `-1`

No bulk acquisition, source mutation, predictor generation, strategy outcome access,
PAPER authority or LIVE authority was permitted.

## Completed workstation evidence

Evidence fingerprint:
`20f255cab7b19e1d27902a76ed386e94156393c019434fbff4623b6d269a1722`.

All repeated requests were stable.

Current structural-list view at `as_of=2026-09-19`:
- target ticker rows: 2
- structural candidates: 3
- candidate tickers:
  - `O:AAL140621C00020000`
  - `O:AAL2140621C00020000`
- the two target-ticker payloads differed only in `primary_exchange`:
  `BATO` versus `XMIO`
- exact current Contract Overview for `O:AAL140621C00020000` returned
  HTTP 404 / `NOT_FOUND` / `Option Ticker not found.` twice

Historical structural-list view at pre-expiration `as_of=2014-06-20`:
- target ticker rows: 1
- structural candidates: 1
- candidate ticker: `O:AAL140621C00020000`
- exact historical Contract Overview returned one row twice
- the historical Contract Overview row exactly matched the historical structural-list
  row

Current and historical structural-list fingerprints were different. Current and
historical Contract Overview results were different. The current same-rank conflict
was therefore reproduced; the historical pre-expiration conflict was not.

## Source interpretation

Massive documents adjusted option series as separate series that may coexist with
standard contracts rather than being merged. The current structural query visibly
contains an adjusted AAL series alongside the target ticker. The current provider view
also exposes two unversioned payloads for the target ticker while the supported exact
Contract Overview cannot resolve that old ticker.

The pre-expiration provider view is materially cleaner: one target structural row and
one stable exact Contract Overview row that agree. This supports a narrowly versioned
resolution rule for expired unversioned conflicts; it does not justify globally
discarding duplicates, choosing an exchange arbitrarily, merging adjusted series, or
granting historical availability/deliverable/market-price authority.

## Frozen successor boundary

Historical Option Reference V3 is separately preregistered. It retains V2 correction
ranking and exact-duplicate handling. A same-highest conflicting group remains
fail-closed except when every condition below holds:

1. the partition is expired;
2. the highest correction rank is `-1` for every conflicting row;
3. the current conflicting payloads differ only in `primary_exchange`;
4. two exact Contract Overview requests at
   `expiration_date - 1 calendar day` both return HTTP 200;
5. the two overview payloads are byte-canonical/hash identical;
6. the overview ticker exactly matches the conflicted ticker; and
7. that stable historical overview payload exactly matches one of the current
   conflicting payloads.

Only then may V3 select that already-present current raw payload and record the
historical resolution lineage. Any other conflict remains fatal.

The known AAL conflict must pass this resolver as a dedicated pre-acquisition probe
before any bulk provider acquisition starts.

V3 contract fingerprint:
`7a9dab85c57bbc6cd93dee2472a9244d86e8c1776f986cd97036b9963bc4c48e`.

V1 and V2 remain failed/incomplete source-contract evidence and are not rewritten.
Historical option reference remains structural identity/enrichment only. Predictor,
strategy, promotion, confluence, PAPER and LIVE authority remain false.
