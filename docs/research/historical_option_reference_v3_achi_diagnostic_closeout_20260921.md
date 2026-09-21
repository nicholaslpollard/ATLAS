# Historical Option Reference V3 ACHI underlying-identity diagnostic closeout — 2026-09-21

## Scope

This immutable record closes the read-only diagnostic
`atlas-historical-option-reference-v3-underlying-identity-conflict-diagnostic-v1`.

Contract fingerprint:
`aaf0a8e52fdd56521fe000dc1ead04059115d2639b18eb29fad03b8fe76eaec1`.

Parent V3 contract fingerprint:
`7a9dab85c57bbc6cd93dee2472a9244d86e8c1776f986cd97036b9963bc4c48e`.

Target:
- partition: `expired-2014-06`
- ticker: `O:ACHI140621C00001000`
- V3 failure: unversioned same-ticker provider rows differed in `underlying_ticker`

The diagnostic granted no bulk acquisition, source mutation, conflict-resolution,
predictor, strategy, PAPER or LIVE authority.

## Completed workstation evidence

Evidence fingerprint:
`b655282ff5f1da7bd3c2d7ac931a34b37650ffaa57354c6ac47efdfe746f81d1`.

All repeated option and stock-reference requests were stable.

Current option structural-list view at `as_of=2026-09-19`:
- target ticker rows: 2
- structural candidates: 313
- target underlying tickers: `ACHI`, `AH`
- conflicting field: `underlying_ticker` only
- exact current Contract Overview: stable HTTP 404 / `NOT_FOUND`

Pre-expiration option structural-list view at `as_of=2014-06-20`:
- target ticker rows: 1
- structural candidates: 258
- target underlying ticker: `ACHI`
- conflicting fields: none
- exact historical Contract Overview: stable HTTP 200
- historical Contract Overview exactly matched the historical structural-list row
- that historical payload exactly matched one and only one current conflicting raw row

Supplemental Massive stock-reference context:
- `ACHI`: zero rows at both 2014-06-20 and 2026-09-19 for active=true/false
- `AH`: one inactive row at both dates, no active row
- observed stock identity key: CIK `0001472595`

The stock-reference result is supplemental only and does not override the option
reference. Massive documents OTC stock history as beginning on 2021-12-31, so the
absence of a 2014 OTC `ACHI` stock row is a coverage limitation rather than evidence
that the 2014 option underlying field is invalid.

## External corroboration

SEC EDGAR filings for CIK `0001472595` identify Accretive Health, Inc. and state:
- NYSE ticker `AH` traded through 2014-03-14;
- NYSE trading was suspended before the open on 2014-03-17 and the shares were
  subsequently delisted;
- OTC trading under ticker `ACHI` began on 2014-03-17.

The target option expired on 2014-06-21, so the pre-expiration option-reference row
using `underlying_ticker=ACHI` is consistent with the issuer's documented symbol at
that time.

This SEC evidence is corroboration only. Runtime resolution remains provider-native
and does not query SEC or infer symbol equivalence.

## Source interpretation

The diagnostic demonstrates a stable current-reference conflict caused by later
reference-state coexistence, while Massive's own pre-expiration option reference is
internally consistent and uniquely identifies one of the current raw payloads.

This does not justify stitching `AH` and `ACHI`, globally preferring newer or older
symbols, or trusting stock-reference coverage outside its archive. It supports a
narrow point-in-time option-reference resolution rule.

## Frozen successor boundary

Historical Option Reference V4 is separately preregistered under contract fingerprint:
`2ddeb58d5f552ff0edb87a2244f130b813cf49600f5f82b1f50d8e1ee047a57d`.

V4 retains V3 correction ranking and exact-duplicate handling. A conflicting
same-highest group may use the successor fallback only when every condition below
holds:

1. the partition is expired;
2. every conflicting row is unversioned at correction rank `-1`;
3. the rows differ only in `primary_exchange`, `underlying_ticker`, or both;
4. the resolver derives contract type, expiration and strike from the current raw rows
   and queries the provider's pre-expiration option structural list at
   `expiration_date - 1 calendar day` without an underlying filter;
5. repeated historical list requests produce exactly one stable target-ticker row;
6. repeated exact Contract Overview requests return one stable HTTP-200 row;
7. historical list and historical Contract Overview payloads are identical; and
8. that historical payload exactly matches one and only one current conflicting raw
   payload.

Any failure remains fatal.

Both known AAL and ACHI conflicts must pass dedicated pre-acquisition probes before
bulk provider work begins. Stock-reference data and SEC corroboration are not runtime
resolution authorities.

Verified V4/V3/V2/V1 receipts and raw lineage remain reusable without raw-byte
duplication. Historical option reference remains structural identity/enrichment only;
historical availability, dynamic deliverables, market price, predictor, strategy,
promotion, PAPER and LIVE authority remain false.
