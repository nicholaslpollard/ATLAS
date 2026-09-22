# Historical Option Reference V5 ACIW historical-gap diagnostic closeout — 2026-09-22

## Status

The read-only `atlas-historical-option-reference-v5-aciw-historical-gap-diagnostic-v1`
completed successfully on the target workstation.

Diagnostic contract fingerprint:

`5be1afdd7cb18cf77f6e0c5b76d2329f4afd1d8c07c37b2c051ec003325688b1`

Evidence fingerprint:

`9c04eba3dd7fce45bbd3e35366e93191acb92493c3e4ed34001e0ad4ef31c777`

Target:

- partition: `expired-2014-08`
- ticker: `O:ACIW140816C00040000`
- contract type: call
- expiration: `2014-08-16`
- strike: 40
- current reference as-of: `2026-09-19`
- V5 required pre-expiration as-of: `2014-08-15`

## Observed provider evidence

The current targeted structural-list request was fully paginated and repeated. Both
repeats were stable and returned **1,604** candidate rows across two pages, including
two target ACIW rows.

The two current target rows:

- share underlying ticker `ACIW`;
- both have missing correction (`null`);
- differ only in `primary_exchange`;
- expose exchanges `GMNI` and `XCBO`.

The historical boundary matrix was stable on every repeated list request:

| as_of | expired | target rows | exact overview present |
| --- | --- | ---: | --- |
| 2014-08-14 | false | 0 | no |
| 2014-08-15 | false | 0 | no |
| 2014-08-15 | true | 0 | no |
| 2014-08-16 | false | 0 | no |
| 2014-08-16 | true | 2 | no |
| 2014-08-17 | false | 0 | no |
| 2014-08-17 | true | 2 | no |
| 2014-08-18 | true | 2 | no |

Exact Contract Overview was absent and repeat-stable on every tested historical
boundary date. No historical structural-list/overview pair produced an exact payload,
and therefore no historical provider payload matched exactly one of the two current
conflicting rows.

The original V5 failure is reproduced: `as_of=2014-08-15, expired=false` returns
zero target rows rather than the one row required by the frozen V5 resolver.

## Interpretation

The provider evidence does not identify whether the historically authoritative row
should be the current `GMNI` payload or the current `XCBO` payload. Selecting
either would be an inference not supported by the provider's point-in-time reference
surface.

The safe successor behavior is therefore **quarantine, not resolution**.

For this evidence class, a successor may:

1. preserve every provider row in immutable raw lineage;
2. select no provider row;
3. write a separate auditable quarantine record containing both raw payloads, hashes,
   differing fields, the failed historical-as-of evidence and request lineage;
4. exclude the unresolved ticker from normalized authoritative option reference; and
5. continue unrelated partition acquisition.

The quarantine must remain narrow. Evidence from ACIW supports expired, unversioned
same-ticker conflicts where the only differing field is `primary_exchange`, the
underlying ticker is identical, and the required pre-expiration structural target is
repeatably absent. Other ambiguity classes remain fail-closed unless separately
qualified.

## Authority boundary

Quarantine does not establish which exchange row was historically correct. It creates
no historical candidate-availability, dynamic-deliverable or market-price authority.
It grants no predictor, strategy, promotion, PAPER or LIVE authority.

The quarantine artifact is source-quality exclusion evidence only. Downstream
historical option research must treat quarantined tickers as unavailable from the
accepted normalized structural-reference corpus unless a later independently accepted
source contract resolves them.
