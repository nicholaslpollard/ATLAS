# ATLAS Data Architecture

ATLAS separates market information according to responsibility. This is a hard architectural boundary.

## 1. Provider archive — `data/provider/`

Original files obtained from a provider. These are retained as reproducibility/source artifacts where practical and are not modified in place.

## 2. Staging — `data/staging/`

Temporary download, normalization, current-session, and reconciliation work. Staging data is recoverable and may be discarded after successful finalization according to retention policy.

## 3. Canonical — `data/canonical/`

Validated provider facts in ATLAS's normalized schema. Canonical data does not contain RSI, EMA, ML predictions, regimes, strategy outputs, or AI decisions.

Initial stock sources:

- canonical 1-minute bars
- canonical daily bars
- reference/instrument metadata
- corporate actions

## 4. Derived — `data/derived/`

Materialized analytical data generated from canonical sources:

- 15-minute bars
- 1-hour bars
- 4-hour bars
- selected historical features
- regimes
- future-outcome labels

Weekly and monthly bars are initially on-demand rather than permanently materialized.

## 5. Live — `data/live/`

Fast current-session state used for discovery and position monitoring. Live state is optimized for latency and can be reconstructed from staging/canonical sources.

## 6. Operational database

PostgreSQL will store operational truth rather than bulk market history: ingestion manifests, instrument registry, candidate state, decisions, orders, fills, positions, jobs, events, and performance.

## 7. DuckDB

DuckDB is the analytical query engine over Parquet/materialized analytical stores. It is not required to own every historical row inside a monolithic database file.

## Core principle

Raw/source facts, derived analytics, operational state, and live state are separate. A new strategy or feature formula must not require rewriting canonical market history.
