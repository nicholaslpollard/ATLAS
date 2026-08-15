# ATLAS Data Architecture

ATLAS separates data by lifecycle and trust level.

1. **Provider archive** — immutable Massive source files.
2. **Staging** — normalized, not-yet-trusted intermediate data.
3. **Canonical** — validated provider facts (1m and 1d).
4. **Derived** — reproducible ATLAS products (15m/1h/4h bars, later features/regimes/outcomes).
5. **Live** — current-session fast state for trading.
6. **PostgreSQL** — operational state/memory, not five years of OHLCV.
7. **DuckDB** — analytical query engine over Parquet and later research metadata.

Phase 03 makes the provider->staging->canonical->derived path operational.
Historical feature persistence and live-state reconciliation arrive in later phases.
