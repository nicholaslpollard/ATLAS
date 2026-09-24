# External Secondary Storage V1 — 2026-09-24

## Status

**IMPLEMENTED / HARDWARE BINDING PENDING**

Contract:

`atlas-external-secondary-storage-v1`

This package makes large secondary ATLAS datasets capable of living on a removable
or external SSD without relocating the core ATLAS installation or the accepted stock
market corpus.

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

Example:

`ATLAS_EXTERNAL_DATA_ROOT=F:/ATLAS_DATA`

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

These limits are intentionally appropriate for the initial approximately 256 GB NVMe
enclosure plan. A future larger SSD can receive a separately reviewed quota increase
without changing the primary stock-storage boundary.

## Portability

The external storage layer deliberately preserves the project-visible namespace.
Replacing the external SSD later therefore requires rebinding the same logical paths
to a new external root rather than rewriting stock paths or scientific identities.

The current 120 GB USB flash drive is not the active database target in this
architecture. It remains suitable for cold archives, backups, frozen evidence copies,
or other low-I/O material.

## Authority

This is product/storage architecture only.

It creates no strategy evidence, historical-price authority, option-price validation,
PAPER authority, LIVE authority, broker/order authority, promotion authority, or
confluence authority. The Strategy Evidence Register is intentionally unchanged.
