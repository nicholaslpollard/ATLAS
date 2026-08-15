# ATLAS Phase 03 — Canonical Storage and Session-Aware Aggregation

## Purpose

Phase 03 converts validated Massive stock aggregate flat files into ATLAS-owned,
query-efficient Parquet history. Provider files remain immutable source evidence;
canonical Parquet is the trusted normalized fact layer; derived Parquet contains
only deterministic bars built from canonical 1-minute facts.

## Storage lifecycle

```text
Massive CSV.gz
    -> normalized staging Parquet
    -> data-quality gate
    -> canonical session Parquet
    -> derived 15m / 1h / 4h session Parquet
    -> DuckDB analytical queries/views
```

A provider **trading session** is the atomic replacement unit. ATLAS never needs
to delete and rebuild an entire year because one source day changed.

## Layout

Canonical minute:

```text
data/canonical/stocks/1m/year=YYYY/month=MM/date=YYYY-MM-DD/part-000.parquet
```

Canonical daily:

```text
data/canonical/stocks/1d/year=YYYY/date=YYYY-MM-DD/part-000.parquet
```

Derived bars:

```text
data/derived/bars/{15m|1h|4h}/year=YYYY/month=MM/date=YYYY-MM-DD/part-000.parquet
```

Quality reports:

```text
data/derived/quality/<timeframe>/YYYY/YYYY-MM-DD.json
```

## Canonical rules

Canonical rows preserve provider/source facts and provenance. They do not
contain indicators, regimes, strategy output, predictions, or AI decisions.

Minute `timestamp_utc` is the provider minute-window start in UTC.
Daily `timestamp_utc` is the official regular-session open for that session;
the provider's original daily `window_start` is retained separately as
`provider_timestamp_utc`.

`source_id` deterministically identifies the Massive remote object and links
canonical rows back to the ingestion/materialization manifests.

## Session anchoring

ATLAS does not floor exchange data to arbitrary wall-clock boundaries.

Each segment has its own anchor:

- premarket: configured 04:00 America/New_York
- regular: official XNYS session open (normally 09:30 America/New_York)
- after-hours: official regular close (normally 16:00 America/New_York)

Therefore a regular-session 1-hour sequence begins at 09:30, 10:30, 11:30,
12:30, 13:30, 14:30, and 15:30 (the final bar is partial through the close).
A regular 4-hour sequence begins at 09:30 and 13:30.

Premarket and after-hours bars are never mixed with regular-session bars.

## Why aggregation is chunk-safe

Phase 03 never aggregates arbitrary source chunks independently. The complete
canonical session partition is the relational input to one GROUP BY operation.
Input row order does not determine OHLC because first/last are explicitly
ordered by `timestamp_utc`.

## Incremental/idempotent behavior

The materialization manifest records:

- source ID
- source SHA-256
- source date/dataset
- staging/canonical/derived paths
- row counts
- quality status
- processing status
- last error

If the manifest says COMPLETE, the source hash is unchanged, and all expected
outputs exist, the session is skipped.

If Massive later corrects a source object and its hash changes, only that
session is normalized, validated, and replaced again.

An interrupted session may be recomputed from its source file on restart. All
previously complete sessions remain untouched.

## Quality gate

Before staging becomes canonical, Phase 03 checks at minimum:

- blank symbols
- null timestamps
- null OHLC
- invalid OHLC geometry
- negative/null volume
- negative transaction counts
- duplicate bar keys
- rows outside the configured market-session envelope

Blocking errors prevent canonical promotion. Quality reports are persisted as
JSON for auditability.

Derived 15m/1h/4h outputs pass the same structural quality gate after creation.

## Daily/minute reconciliation

`scripts/reconcile_daily_minute.py` compares an official Massive daily session
to a daily OHLCV reconstructed from canonical **regular-session** minute bars.
Differences are reported rather than automatically treated as corruption,
because provider daily definitions/corrections can legitimately differ.

## Query model

`DuckDBMarketRepository` queries Parquet directly. ATLAS does not maintain a
second duplicate OHLCV database merely for SQL access. `data/duckdb/atlas.duckdb`
is reserved for analytical views/metadata and later derived operational state.

## Provider symbol conflicts and quarantine

Massive aggregate flat files identify observations by ticker text. A session can
therefore contain provider anomalies in which the same ticker/date key has
materially different OHLCV rows. ATLAS must not choose an arbitrary winner.

Phase 03 policy:

- exact duplicate rows are removed deterministically and logged as a warning;
- materially conflicting daily rows quarantine the entire symbol for that
  trading session;
- the daily quarantine is propagated to the same session's minute data so
  contaminated intraday bars cannot enter canonical or derived history;
- quarantined rows remain preserved under `data/derived/quality/quarantine/`;
- a session-level registry is written under
  `data/derived/quality/symbol_quarantine/`;
- clean symbols continue materializing, so a handful of ambiguous symbols do
  not block an otherwise valid 12k-symbol market session;
- quarantined symbols are ineligible for downstream trading/research until a
  later reconciliation process resolves identity/data provenance.

Ticker text is treated as a point-in-time provider symbol, not the final stable
ATLAS instrument identity. Point-in-time reference ingestion and FIGI-backed
instrument identity are intentionally moved earlier in the roadmap so later
phases can reconcile symbol changes/collisions without rewriting historical
bars.

Minute materialization also fingerprints the session quarantine registry as an
input dependency. If the daily source is later corrected and the quarantine set
changes, the minute session is rebuilt even when the minute provider file hash
did not change. This prevents stale quarantines (or stale contaminated minute
history) from surviving a provider correction.
