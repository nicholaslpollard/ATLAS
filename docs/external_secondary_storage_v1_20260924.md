# External Secondary Storage V1 — 2026-09-24

## Status

**IMPLEMENTED / WORKSTATION SSD BINDING READY (2026-09-26)**

Contract:

`atlas-external-secondary-storage-v1`

This package makes large secondary ATLAS datasets capable of living on a
separate storage volume (internal SATA SSD or an eligible external SSD) without
relocating the core ATLAS installation or the accepted stock market corpus.

## Non-negotiable primary-storage boundary

The following remain in their existing project/internal-drive locations:

- ATLAS source code and Python environment;
- `data/provider`;
- `data/canonical`, including the accepted Alpaca SIP V2 stock corpus;
- `data/duckdb`;
- `data/checkpoints`;
- core runtime/live state and the existing primary stock-data layout unless a future
  separately versioned package explicitly changes it.

External Secondary Storage V1 does not move or reinterpret any stock evidence.

## External-eligible bindings

When configured, these project-visible paths are bound to the external data root:

| Logical binding | Project-visible path | External target |
| --- | --- | --- |
| options | `data/options` | `options` |
| news | `data/news` | `news` |
| provider qualification | `data/research/provider_qualification` | `research/provider_qualification` |
| research evidence | `data/research/evidence` | `research/evidence` |
| fundamentals | `data/fundamentals` | `fundamentals` |
| archives | `data/archives` | `archives` |

On Windows the bootstrap creates directory junctions. ATLAS therefore retains stable
project-relative paths such as `data/options/...` even though the bytes reside on
another volume. This keeps receipts and manifests independent of the external drive
letter.

## Configuration

The external root is selected with:

`ATLAS_EXTERNAL_DATA_ROOT`

Current workstation root:

`ATLAS_EXTERNAL_DATA_ROOT=D:/ATLAS_DATA`

The `external` setting name denotes a secondary data root distinct from the
project storage; the active workstation volume is an internal SATA SSD.

The variable should be persisted only after the binding setup reaches `READY`.

## Bootstrap

Dry inspection:

~~~powershell
.\.venv\Scripts\python.exe scripts\configure_external_storage.py --root "F:/ATLAS_DATA"
~~~

Create bindings when the project-side secondary directories are empty:

~~~powershell
.\.venv\Scripts\python.exe scripts\configure_external_storage.py --root "F:/ATLAS_DATA" --apply --persist-env
~~~

If existing secondary files must be moved first:

~~~powershell
.\.venv\Scripts\python.exe scripts\configure_external_storage.py --root "F:/ATLAS_DATA" --apply --migrate-existing --persist-env
~~~

Migration is limited to the configured secondary bindings. The bootstrap does not
move the primary stock paths.

## Fail-closed behavior

Once `ATLAS_EXTERNAL_DATA_ROOT` is configured:

- explicit secondary-path resolution validates that the project binding points to its
  expected external target;
- research acquisition refuses to proceed when the root/bindings are unavailable;
- a configured-but-missing external drive is not treated as permission to spill large
  options/news acquisitions onto the internal drive;
- a project path already linked to a different target fails;
- existing local secondary data is not moved unless `--migrate-existing` is supplied;
- destination collisions fail rather than overwrite data.

The external root receives a marker file
`.atlas_external_storage_v1.json` after successful setup.

## Storage budgets

The original internal-drive research policy remains unchanged when no external root
is configured:

- total acquisition budget: 40 GiB;
- minimum free space: 50 GiB;
- warning free space: 65 GiB;
- candidate-options cache quota: 20 GiB.

When the external root is configured and READY, the external-volume profile becomes:

- total secondary acquisition budget: 190 GiB;
- minimum free space: 25 GiB;
- warning free space: 40 GiB;
- news quota: 15 GiB;
- options reference quota: 15 GiB;
- options daily quota: 30 GiB;
- candidate-options cache quota: 120 GiB;
- options derived quota: 10 GiB.

These limits also fit the activated 250 GB Samsung 860 EVO SATA SSD.
A future larger SSD can receive a separately reviewed quota increase without
changing the primary stock-storage boundary.

## Portability

The external storage layer deliberately preserves the project-visible namespace.
Replacing the secondary SSD later therefore requires rebinding the same logical
paths to a new secondary root rather than rewriting stock paths or scientific identities.

The current 120 GB USB flash drive is not the active database target in this
architecture. It remains suitable for cold archives, backups, frozen evidence copies,
or other low-I/O material.

## 2026-09-26 workstation activation evidence

The operator installed and quick-formatted a Samsung 860 EVO 250 GB SATA SSD as
`D:` (`ATLAS_SECONDARY`, NTFS). Initial Windows volume inspection reported
232.28 GiB capacity and 232.18 GiB free. The dry inspection identified four
populated secondary project directories and two unbound destinations. All six
target directories were empty before migration.

The pre-migration SHA-256 inventory is retained on C: at
`data/manifests/secondary_migration_20260926_132952_before.csv`. It covered
2,122 files / 2.521 GiB across `data/options`, `data/news`,
`data/research/provider_qualification`, and `data/research/evidence`;
`data/fundamentals` and `data/archives` had no source files.

The operator ran `scripts/configure_external_storage.py --root
D:/ATLAS_DATA --apply --migrate-existing --persist-env`; the resulting
inspection reported all six bindings `READY`, and a subsequent SHA-256
verification through the original project-visible paths passed for all
2,122 inventoried files. `ATLAS_EXTERNAL_DATA_ROOT` was persisted in `.env`.
The stock database and primary data paths were not moved. These are
operator-reported workstation results, not GitHub CI observations.

The subsequent news/options storage preflight (no provider probes) returned
fingerprint `38560d038795e7994a253a1d2c191e0dfb403c0f17bd1a07e17b048eaf0d7f88`,
227.07 GiB free, status SAFE, 190.00 GiB total / 187.62 GiB remaining budget,
and 25/40 GiB minimum/warning free-space thresholds. Existing source usage
remained news 1.931 GiB and options reference 0.446 GiB, with zero bulk downloads.
The exact saved candidate-chain preview returned EXTERNAL_SECONDARY, 12 planned
opportunities and distinct requests, 12 pending, zero provider calls, zero
credits consumed and no new receipts; report fingerprint:
`c83f7464dbdccd5dc7c1242e926cc5598d16a79f1e38bf5130bee714befc9538`.
These are operator-reported workstation results. They do not independently
verify provider entitlement or authorize acquisition, trading or strategy changes.

## Authority

This is product/storage architecture only.

It creates no strategy evidence, historical-price authority, option-price validation,
PAPER authority, LIVE authority, broker/order authority, promotion authority, or
confluence authority. The Strategy Evidence Register is intentionally unchanged.
