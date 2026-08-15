# ATLAS Ingestion Pipeline

ATLAS ingestion is incremental, idempotent, restartable, and provider-agnostic.

```text
Provider inventory
      ↓
Ingestion planner
      ↓
Missing/unverified units only
      ↓
Download
      ↓
Checksum / file validation
      ↓
Normalize into staging
      ↓
Data-quality validation
      ↓
Canonical upsert/finalization
      ↓
Affected derived bars only
      ↓
Affected feature state only
      ↓
Checkpoint + manifest COMPLETE
```

## Required behaviors

1. Reprocessing the same source must not duplicate canonical rows.
2. A crash must resume from the first incomplete unit rather than rebuild a year.
3. The manifest records source identity, dataset, trading date, local path, status, checksum, attempts, errors, and completion timestamps.
4. Provider credentials are read from environment/secret management only.
5. URLs containing credentials must never be logged.
6. Validation failure blocks promotion into canonical history until resolved or explicitly quarantined.
