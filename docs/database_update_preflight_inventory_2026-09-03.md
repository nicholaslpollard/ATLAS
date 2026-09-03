# ATLAS Database Update — Storage Preflight Inventory

**Captured:** 2026-09-03  
**Contract:** `atlas-database-migration-storage-inventory-v1`  
**Status:** COMPLETE / READ-ONLY  
**Parent plan:** `docs/database_update_plan.md`

## Operator disk state

- Total disk: **476.29 GiB** (`511,412,744,192` bytes)
- Used: **251.23 GiB** (`269,752,737,792` bytes)
- Free before V2 build: **225.06 GiB** (`241,660,006,400` bytes)

## Existing ATLAS V1 footprint

The entire existing `data/` tree occupies:

- **148.80 GiB** (`159,776,760,524` bytes)
- **276,305 files**

If the entire current ATLAS `data/` tree were moved off the primary disk without changing other disk contents, theoretical free space would rise to approximately **373.87 GiB**. This is more precise than the earlier rough planning estimate of ~400 GB free.

## V1 footprint by configured data path

| Path | Size |
|---|---:|
| `data/derived` | 66.53 GiB |
| `data/provider` | 32.46 GiB |
| `data/canonical` | 26.88 GiB |
| `data/manifests` | 21.32 MiB |
| `data/live` | 6.49 MiB |
| `data/staging` | 0 B |
| `data/models` | 0 B |
| `data/cache` | 0 B |
| `data/duckdb` | 0 B |
| `data/checkpoints` | 3.47 KiB |

There is also a legacy/unconfigured `data/raw` tree occupying **22.91 GiB**.

## Largest V1 subtrees

| Subtree | Size |
|---|---:|
| `derived/features` | 41.00 GiB |
| `provider/massive` | 29.41 GiB |
| `canonical/stocks` | 25.89 GiB |
| `raw/minute_aggs_v1` | 22.68 GiB |
| `derived/historical_backfill` | 9.40 GiB |
| `derived/bars` | 7.43 GiB |
| `derived/strategy_evaluation` | 4.48 GiB |
| `derived/ml` | 2.16 GiB |
| `provider/pre_phase33_beneficial_ownership` | 1.92 GiB |
| `derived/discovery` | 1.65 GiB |
| `provider/phase32_sec_8k_predictor_acquisition` | 736.89 MiB |
| `canonical/reference` | 716.01 MiB |
| `provider/alpaca` | 359.38 MiB |

## File-type footprint

| Type | Size |
|---|---:|
| Parquet | 83.85 GiB |
| gzip | 52.62 GiB |
| JSONL | 9.74 GiB |
| text | 1,012.86 MiB |
| index | 1,007.48 MiB |
| JSON | 386.24 MiB |
| zip | 239.78 MiB |

## Interpretation

1. V1 is large enough that moving it externally materially changes the V2 feasibility envelope: **225.06 GiB free with V1 local vs ~373.87 GiB if the full ATLAS data tree is moved off-disk**.
2. Existing minute-related evidence is substantial: `raw/minute_aggs_v1` alone is 22.68 GiB and the entire canonical stock lake is 25.89 GiB. This supports, but does not prove, that a complete 2016-present Alpaca 1-minute replacement may fit in the larger ~374 GiB envelope.
3. V2 sizing must not be inferred solely from these V1 bytes because the old minute history covers a different time span/provider and V2 will use Alpaca SIP with a fresh source-built schema.
4. The next required preflight is an empirical Alpaca `1Min` sizing sample using normal ATLAS Parquet/Zstandard storage semantics, combined with current full-history daily symbol-session counts.
5. No V1 files were modified by this inventory.

## Next decision gate

Do **not** start the full V2 historical acquisition yet.

Next:

- run an Alpaca SIP 1-minute sample across a representative cross-section/history;
- measure real returned minute rows, compressed raw-response bytes, and normal Parquet bytes/row;
- extrapolate V2 native `1m` size against ATLAS historical symbol-session counts;
- include native `1d`, derived bars, features, manifests/checkpoints, temporary build overhead, validation outputs, and a free-space reserve;
- compare the resulting peak requirement against both **225.06 GiB** and **~373.87 GiB** scenarios.

Only after that estimate is accepted should ATLAS decide whether V1 can remain local or must be moved to external storage before the one-command V2 rebuild starts.
