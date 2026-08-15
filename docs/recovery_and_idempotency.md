# Recovery and Idempotency

ATLAS must never require deletion of the current year merely to continue an interrupted update.

## Source identity

Each provider file/unit receives a deterministic source ID from provider + dataset + trading date + remote key.

## Manifest

Every source progresses through states such as:

`PLANNED → DOWNLOADING → DOWNLOADED → VALIDATING → VALIDATED → PROCESSING → COMPLETE`

Failures retain their prior completed work, attempt count, and error information.

## Checkpoints

Long-running transformations checkpoint at deterministic work boundaries. A restart reads the checkpoint and continues rather than starting the full history again.

## Idempotency

The same valid source may be processed repeatedly without duplicating or corrupting canonical history. Canonical bar keys will be deterministic and upsert-safe.

## Atomicity

Later phases should use temporary output + atomic replace/transaction semantics for file/database state changes wherever practical.
