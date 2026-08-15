# Recovery and Idempotency

ATLAS ingestion is designed so a crash is an interruption, not a rebuild event.

## Atomic downloads

Provider objects are written to temporary `.part` files. They become visible at
the final provider-archive path only after the complete stream is written, flushed,
fsynced, size-checked, and atomically renamed.

A crash cannot turn a partial transfer into an apparently complete source file.

## Per-source manifests

Every provider object has a deterministic `source_id` and its own atomic JSON
manifest record during the local implementation phases. This avoids repeatedly
rewriting one giant state file and provides simple forensic recovery.

The storage interface can later be backed by PostgreSQL without changing the
planner/downloader contracts.

## Checkpoints

A synchronization checkpoint advances only after a file passes validation. On a
restart, the planner independently reconstructs work from provider inventory plus
manifest state. The checkpoint is therefore operational telemetry rather than the
only source of truth.

## Safe reruns

Rerunning the same range is expected and supported. Completed source objects are
skipped. Failed or invalid objects are scheduled again. No current-year deletion
or derived-data rebuild is required.
