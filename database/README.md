# PostgreSQL Operational-State Scaffold

**Current status: PLACEHOLDER / NOT AN ACCEPTED OPERATIONAL DATABASE.**

ATLAS has PostgreSQL locked as the **target persistent operational-state store**, but no numbered phase has yet accepted a PostgreSQL schema, migration lifecycle, deployment topology, or production operational authority.

The files currently present under:

- `database/migrations/`
- `database/seeds/`
- `database/views/`

are historical scaffold placeholders. The existing numbered `.sql` files are zero-byte placeholders and **must not be interpreted as implemented or approved migrations**.

The root `docker-compose.yml` is likewise only historical scaffold at this point and does not define an accepted ATLAS deployment.

Until a future phase explicitly defines and validates PostgreSQL operational state, accepted ATLAS truth remains governed by the storage roles and phase-specific artifacts documented in `docs/roadmap.md` and `docs/current_status.md`.

A future PostgreSQL implementation must, at minimum, explicitly lock and validate:

- authoritative operational-state ownership versus Parquet/DuckDB analytical truth;
- schema and migration ordering;
- forward migration and rollback/recovery behavior;
- migration idempotency and partial-failure handling;
- credential/secret handling;
- backup/restore and corruption recovery;
- concurrency/transaction semantics;
- cross-platform development/test behavior;
- startup/readiness checks;
- data-retention and audit requirements;
- provider/trading authority boundaries;
- independent validation and full regression evidence.

No database scaffold file, environment variable, Docker configuration, or successful connection may silently grant broker, provider-write, or live-trading authority.
