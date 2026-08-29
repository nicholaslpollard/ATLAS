# ATLAS Hardware Benchmark v1

`atlas-hardware-benchmark-v1` is a deterministic local operator utility for measuring how changes to the ATLAS host affect the kinds of local workloads ATLAS uses. It is not a scientific alpha gate and has no trading authority.

## Scope

The benchmark performs only synthetic local work:

- pure-Python scalar compute;
- NumPy vector compute;
- Pandas aggregation;
- DuckDB analytical SQL;
- Parquet ZSTD write/read on the local ATLAS drive;
- fixed-work parallel Python compute using the host's available logical CPU threads.

It performs **no network/provider calls, no market-data reads, no stock/SPY/options outcome reads, no broker reads/writes, no orders, and no PAPER/LIVE actions**. GPU performance is intentionally excluded from v1.

## Run

From the ATLAS repository root:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_atlas_hardware.py
```

The runner measures every stage with `time.perf_counter()`, prints cumulative elapsed time while it runs, prints each stage duration, records total benchmark duration, and writes the complete result to:

```text
data/derived/hardware_benchmarks/atlas_hardware_benchmark_<UTC>_full.json
```

For a clean before/after hardware comparison, close other heavy applications and do not run another ATLAS workload at the same time.

## Automatic before/after comparison

On the first full run, no compatible result exists, so that result becomes the baseline. After a hardware change, run the same command again. The runner automatically finds the latest prior result only when all of these match:

- benchmark contract;
- exact benchmark-script SHA256;
- full versus smoke mode.

It then prints the before time, after time, speedup multiplier, and time change for every benchmark stage and for the complete benchmark.

The exact script hash prevents an accidental comparison when the benchmark workload itself changed. A specific prior result can be selected with:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_atlas_hardware.py --baseline data\derived\hardware_benchmarks\<result>.json
```

## Smoke mode

A reduced workload exists only for fast validation/troubleshooting:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_atlas_hardware.py --smoke
```

Do not compare a smoke run with a full benchmark. The runner rejects that mismatch.

## Interpretation

Lower elapsed time is better. The benchmark deliberately reports stage timings instead of inventing a synthetic score so the effect of a CPU/platform change remains visible by workload type. The most useful comparison for a CPU upgrade is the full before/after run on the same M.2 drive, RAM configuration, operating system, Python environment, and benchmark-script SHA256.
