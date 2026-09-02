# ATLAS Phase 03.1 — Circular Import Fix

## Problem

`packages.aggregation.bar_builder` imports `packages.data.atomic`.

Python initializes `packages.data` before loading the `atomic` submodule. The
Phase 03 `packages/data/__init__.py` eagerly imported `materializer`, and
`materializer` imports `SessionBarBuilder`, producing:

aggregation.bar_builder
  -> packages.data.atomic
  -> packages.data.__init__
  -> packages.data.materializer
  -> packages.aggregation.bar_builder

This left `bar_builder` only partially initialized and pytest failed during
collection.

## Fix

`packages.data` now keeps package initialization lightweight and uses PEP 562
lazy exports for:

- MarketDataMaterializer
- MaterializationResult
- DuckDBMarketRepository

`MarketDataPaths` remains an eager lightweight export.

This preserves the convenient public API while preventing low-level data
submodules from importing the higher-level materialization stack.

## Apply

Extract this ZIP directly into the existing ATLAS root and overwrite
`packages/data/__init__.py`.

Then run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

On the user's Phase 03 machine with DuckDB installed, expected result is:

```text
37 passed
```
