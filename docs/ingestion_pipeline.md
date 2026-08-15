# ATLAS Incremental Ingestion Pipeline

## Phase 2 contract

ATLAS treats Massive Flat Files as immutable provider source objects. The provider
inventory is queried from Massive's S3-compatible storage; ATLAS does not assume
that every calendar date or even every requested exchange session has already
been published.

Flow:

1. List remote objects for the requested dataset/date range.
2. Parse trading dates from provider object keys.
3. Compare remote objects to the XNYS session calendar and the local manifest.
4. Plan only remote objects that are absent, untracked, failed, or invalid locally.
5. Stream each object to a `.part` file while computing SHA-256.
6. Verify provider-reported byte size.
7. Atomically rename the completed `.part` file into the provider archive.
8. Validate gzip integrity and the CSV header without loading the dataset into RAM.
9. Persist one atomic manifest record per source object.
10. Advance a restart checkpoint only after validation succeeds.

The source archive is not the canonical market database. Canonical normalization
and session-aware aggregation begin in the next phase.

## Provider datasets

ATLAS Phase 2 supports:

- `stock_minute_aggregates`
- `stock_daily_aggregates`

The Massive dataset prefixes are configuration, not hard-coded throughout the
application.

## Idempotency

A file is complete only when:

- the manifest says VALIDATED or COMPLETE;
- validation status is VALID or WARNING;
- the local file exists;
- local byte size agrees with manifest/provider metadata;
- provider ETag has not changed when both sides have one;
- optionally, SHA-256 can be rechecked during planning.

A second sync over a complete range therefore plans zero downloads.
