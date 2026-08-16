# Phase 04 Historical Lake Acceptance Baseline

Date of acceptance run: 2026-08-16

This document records the first complete fresh-provider historical lake built by ATLAS.
Legacy Chart Monitor market files were not used as inputs.

## Provider entitlement boundary

Massive flat-file read access was probed independently for daily and minute stock
aggregates. Both datasets produced the same observed boundary:

- 2021-08-13: listed remotely but GetObject denied by provider entitlement
- 2021-08-16: readable
- 2026-08-14: requested end of the acceptance build

The observed readable range contained 1,255 XNYS exchange sessions. The 155 earlier
sessions requested from 2021-01-04 were correctly reported as entitlement-skipped,
not as missing-data failures.

## Full historical build result

The resumable historical build completed with:

- requested range: 2021-01-04 through 2026-08-14
- effective range: 2021-08-16 through 2026-08-14
- readable sessions processed: 1,255
- entitlement-skipped sessions: 155
- newly materialized units on the final resume: 2,468
- already-current materialization units: 42
- total expected daily + minute materialization units: 2,510
- failures: 0
- final resume elapsed time: 21,264.69 seconds

The equality `2,468 + 42 = 2,510 = 1,255 * 2` confirms that every readable session
had both daily and minute materialization accounted for.

The build was successfully resumed after a Windows transient file-lock failure in an
advisory checkpoint. Authoritative ingestion/materialization manifests and committed
data remained intact, proving restart/idempotency behavior on real multi-year data.

## Structural lake audit

The completed fast coverage audit reported:

| Layer | Present | Expected | Missing | Bytes |
|---|---:|---:|---:|---:|
| provider 1d | 1,255 | 1,255 | 0 | 276,361,856 |
| provider 1m | 1,255 | 1,255 | 0 | 25,814,441,558 |
| canonical 1d | 1,255 | 1,255 | 0 | 336,541,313 |
| canonical 1m | 1,255 | 1,255 | 0 | 26,974,162,154 |
| derived 15m | 1,255 | 1,255 | 0 | 5,057,024,661 |
| derived 1h | 1,255 | 1,255 | 0 | 2,049,789,306 |
| derived 4h | 1,255 | 1,255 | 0 | 824,763,394 |

Additional audit facts:

- quarantine sessions: 0
- quarantined symbols: 0
- tracked bytes across provider/canonical/derived layers: 61,333,084,242

## Integrity interpretation

Each source file downloaded by the normal ingestion path is size checked, hashed with
SHA-256, fully decompressed for gzip CRC validation, checked for the expected CSV
header, and only then marked COMPLETE in the authoritative ingestion manifest.
Therefore a second full `--deep-validate` pass is not required for this acceptance
baseline; it remains available as an independent later forensic/maintenance check.

Canonical and derived files were independently produced through the Phase 3 quality
gates. The structural audit confirms complete per-session coverage at all retained
historical timeframes.

## Acceptance decision

The fresh ATLAS historical market lake for the provider-readable interval
2021-08-16 through 2026-08-14 is accepted as the Phase 4C baseline.

The next Phase 4 work is explicit instrument continuity: persist provider ticker-change
events/corporate-action identity evidence so historical symbol changes can be modeled
without conflating ticker labels with instrument identity.
