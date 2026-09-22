# Historical Option Reference V5 ACIW historical-gap incident — 2026-09-21

## Status

Historical Option Reference V5 remains incomplete and fail-closed.

The first target-workstation V5 acquisition used five workers. The frozen 2032
active-hard-end probe passed, and all three mandatory source-conflict probes passed:

- AAL primary-exchange identity;
- ACHI underlying identity; and
- ACT2 explicit-correction additional-underlyings deliverable identity.

The run inventoried 212 monthly partitions as 0 verified V5 reusable, 63 verified V4
raw reusable and 149 provider-pending at startup. All 63 verified V4 raw partitions
were then re-normalized successfully under V5. The displayed option-reference usage
reached about 0.322 GiB with about 135.45 GiB free.

Provider-side work subsequently failed closed in `expired-2014-08` on
`O:ACIW140816C00040000`:

```
HistoricalOptionReferenceV5Error:
O:ACIW140816C00040000:
pre-expiration structural-list expected exactly 1 target row, received 0
```

The exception arose inside V5's frozen **unversioned** conflict resolver after it
requested the provider-native pre-expiration structural view for
`as_of=2014-08-15`. Therefore this is not ACT2's explicit-correction branch and no
existing conflict rule is broadened.

Because bounded worker tasks persist atomically, a later V5/successor inventory must
verify any receipts that may have completed before cancellation rather than assuming
that every provider-pending partition remains unpersisted.

## Frozen diagnostic

Before any V6/successor behavior is considered, run the read-only diagnostic contract:

`atlas-historical-option-reference-v5-aciw-historical-gap-diagnostic-v1`

Contract fingerprint:

`5be1afdd7cb18cf77f6e0c5b76d2329f4afd1d8c07c37b2c051ec003325688b1`

Target:

- partition: `expired-2014-08`
- ticker: `O:ACIW140816C00040000`
- contract type: call
- expiration: `2014-08-16`
- strike: 40
- current reference as-of: `2026-09-19`
- V5 failed pre-expiration as-of: `2014-08-15`

The diagnostic repeats and fully paginates the current targeted structural-list view.
It then probes the immediate historical boundary from 2014-08-14 through 2014-08-18,
including both `expired=false` and `expired=true` around expiration where useful.
Exact Contract Overview is repeated on each historical date.

It records:

- the current conflicting rows and exact field differences;
- current underlying tickers, primary exchanges and correction values;
- whether the V5 zero-target failure reproduces stably;
- whether the target appears on any neighboring point-in-time date;
- whether `expired` filter choice changes visibility;
- whether list and Contract Overview agree exactly; and
- whether any historical exact payload matches exactly one current conflicting row.

The diagnostic is evidence collection only. It creates neither a conflict-resolution
rule nor a quarantine rule and grants no bulk acquisition, predictor, strategy,
PAPER or LIVE authority.

## Successor decision boundary

If a stable provider-native historical payload exists and exactly identifies one
current conflicting row, a narrowly frozen successor resolver may be considered.

If no such point-in-time payload exists, ATLAS must not guess. A separately frozen
successor quarantine contract may instead preserve the raw conflicting rows, mark the
ticker unresolved/ambiguous and keep it out of normalized authoritative reference
use while allowing unrelated source acquisition to continue. That behavior is not
authorized by this diagnostic itself.
