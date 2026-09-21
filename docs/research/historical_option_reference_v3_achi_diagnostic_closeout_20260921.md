# Historical Option Reference V3 underlying-identity diagnostic closeout — 2026-09-21

## Scope

This immutable record closes the read-only diagnostic
`atlas-historical-option-reference-v3-underlying-identity-conflict-diagnostic-v1`.

Diagnostic contract fingerprint:
`aaf0a8e52fdd56521fe000dc1ead04059115d2639b18eb29fad03b8fe76eaec1`.

Parent V3 contract fingerprint:
`7a9dab85c57bbc6cd93dee2472a9244d86e8c1776f986cd97036b9963bc4c48e`.

Target V3 failure:
- partition: `expired-2014-06`
- ticker: `O:ACHI140621C00001000`
- V3 failure class: unversioned same-ticker rows differed in
  `underlying_ticker`, outside V3's `primary_exchange`-only resolver.

No bulk acquisition, source mutation, predictor generation, strategy outcome access,
PAPER authority or LIVE authority was permitted.

## Completed workstation evidence

Evidence fingerprint:
`b655282ff5f1da7bd3c2d7ac931a34b37650ffaa57354c6ac47efdfe746f81d1`.

All repeated option and stock-reference requests were stable.

Current option structural-list view at `as_of=2026-09-19`:
- target rows: 2
- candidate rows under the deliberately broad call/expiration/strike query: 313
- target underlying tickers: `ACHI` and `AH`
- the two target rows differed only in `underlying_ticker`
- exact current Contract Overview: stable HTTP 404 / `NOT_FOUND`

Pre-expiration option structural-list view at `as_of=2014-06-20`:
- target rows: 1
- candidate rows: 258
- target underlying ticker: `ACHI`
- no target-row conflict
- exact historical Contract Overview: stable HTTP 200
- historical Contract Overview exactly matched the historical structural-list row
- that historical payload exactly matched one and only one current conflicting raw row

Supplemental Massive stock-reference context:
- `ACHI`: zero rows at both tested dates under active=true and active=false
- `AH`: one inactive row at both tested dates, zero active rows
- observed stock identity key: CIK `0001472595`

The stock-reference result is not used as option-resolution authority.

## Provider-documentation interpretation

Massive's Options Contract Overview documentation identifies
`/v3/reference/options/contracts/{options_ticker}` as the single-contract structural
reference endpoint and includes underlying ticker among the returned contract
attributes:

https://massive.com/docs/rest/options/overview

Massive documents its stock history coverage separately. Listed U.S. stock history
extends much further back, while OTC stock history begins only on 2021-12-31:

https://massive.com/knowledge-base/article/how-much-historical-stock-data-does-massive-have

Therefore, absence of a 2014 `ACHI` row from the stock-reference/history surface does
not rebut the 2014 option-reference payload. The option source itself supplies a
stable pre-expiration `ACHI` identity.

## Independent identity corroboration

SEC filings for Accretive Health, Inc., CIK `0001472595`, independently explain the
symbol transition. The company's 2014 Form 10-K states that its common stock traded on
the NYSE as `AH` through 2014-03-14, was suspended before the 2014-03-17 open, and
began trading OTC as `ACHI` on 2014-03-17:

https://www.sec.gov/Archives/edgar/data/1472595/000119312514457093/d679613d10k.htm

This corroboration is explanatory only. V4 does not call the SEC, does not stitch stock
symbols, and does not use an external issuer-history rule to choose an option row.

## Frozen successor boundary

Historical Option Reference V4 is separately preregistered. It retains V3's correction
ranking, exact-duplicate handling, structural-reference-only authority, storage guards,
212 monthly partitions, 2032 hard end, bounded scheduling and verified-parent raw reuse.

A same-highest conflicting ticker group remains fail-closed unless every condition
below holds:

1. the reference partition is expired;
2. every highest-rank conflicting row is unversioned (correction rank `-1`);
3. the conflicting current rows differ only in `primary_exchange`,
   `underlying_ticker`, or both;
4. a pre-expiration option structural-list query at
   `expiration_date - 1 calendar day`, with no underlying-ticker filter and with
   contract type / expiration / strike bound from the current group, is repeated twice;
5. each repeated historical list evaluation yields exactly one target-ticker row and
   the target-row hash is stable;
6. exact Contract Overview at the same historical `as_of` is repeated twice and is
   stable;
7. the historical list row and historical overview row are exactly identical; and
8. that historical provider payload exactly matches one and only one current
   conflicting raw payload.

Only then may V4 select that already-preserved current raw payload and record the
full historical list/overview lineage. Any failure remains fatal.

Massive stock-reference rows and SEC corroboration are explicitly non-authoritative
for runtime resolution.

Known AAL and ACHI conflict cases must both pass dedicated pre-acquisition probes before
bulk provider work begins.

V4 contract fingerprint:
`2ddeb58d5f552ff0edb87a2244f130b813cf49600f5f82b1f50d8e1ee047a57d`.

V1, V2 and V3 failure/incomplete evidence remains immutable and is not rewritten.
Historical Option Reference remains structural identity/enrichment only. Historical
availability, dynamic deliverables, prices, predictor validity, strategy promotion,
confluence, PAPER and LIVE authority remain false.
