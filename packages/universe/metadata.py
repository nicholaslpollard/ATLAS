from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths


REFERENCE_UNIVERSE_INVENTORY_VERSION = "universe-reference-inventory-v1"


def _safe(path: Path | str) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _value_counts(con: Any, source: str, column: str) -> list[dict[str, object]]:
    rows = con.execute(
        f"""
        SELECT {column}, count(*) AS row_count
        FROM read_parquet('{source}')
        GROUP BY {column}
        ORDER BY row_count DESC, {column} NULLS LAST
        """
    ).fetchall()
    return [
        {"value": _json_value(value), "row_count": int(row_count)}
        for value, row_count in rows
    ]


def _duplicate_examples(con: Any, source: str, *, limit: int) -> list[dict[str, object]]:
    rows = con.execute(
        f"""
        WITH grouped AS (
            SELECT
                instrument_id,
                count(*) AS row_count,
                count(DISTINCT ticker) AS ticker_count,
                count(DISTINCT market) AS market_count,
                count(DISTINCT locale) AS locale_count,
                count(DISTINCT primary_exchange) AS exchange_count,
                count(DISTINCT security_type) AS security_type_count,
                count(DISTINCT active) AS active_count,
                list_sort(list(DISTINCT ticker)) AS tickers,
                list_sort(list(DISTINCT market) FILTER (WHERE market IS NOT NULL)) AS markets,
                list_sort(list(DISTINCT locale) FILTER (WHERE locale IS NOT NULL)) AS locales,
                list_sort(list(DISTINCT primary_exchange) FILTER (WHERE primary_exchange IS NOT NULL)) AS exchanges,
                list_sort(list(DISTINCT security_type) FILTER (WHERE security_type IS NOT NULL)) AS security_types,
                list_sort(list(DISTINCT active)) AS active_values
            FROM read_parquet('{source}')
            GROUP BY instrument_id
            HAVING count(*) > 1
        )
        SELECT *
        FROM grouped
        ORDER BY ticker_count DESC, row_count DESC, instrument_id
        LIMIT ?
        """,
        [int(limit)],
    ).fetchall()
    columns = [
        "instrument_id",
        "row_count",
        "ticker_count",
        "market_count",
        "locale_count",
        "exchange_count",
        "security_type_count",
        "active_count",
        "tickers",
        "markets",
        "locales",
        "exchanges",
        "security_types",
        "active_values",
    ]
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _security_type_examples(
    con: Any,
    source: str,
    *,
    samples_per_type: int,
) -> list[dict[str, object]]:
    rows = con.execute(
        f"""
        WITH ranked AS (
            SELECT
                security_type,
                ticker,
                name,
                market,
                locale,
                primary_exchange,
                active,
                row_number() OVER (
                    PARTITION BY security_type
                    ORDER BY ticker, instrument_id
                ) AS rn
            FROM read_parquet('{source}')
        )
        SELECT security_type, ticker, name, market, locale, primary_exchange, active
        FROM ranked
        WHERE rn <= ?
        ORDER BY security_type NULLS LAST, ticker
        """,
        [int(samples_per_type)],
    ).fetchall()
    columns = [
        "security_type",
        "ticker",
        "name",
        "market",
        "locale",
        "primary_exchange",
        "active",
    ]
    return [dict(zip(columns, row, strict=True)) for row in rows]


class UniverseReferenceInventory:
    """Inspect real Phase 4 reference metadata before Phase 7 eligibility is locked."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)

    def inspect(
        self,
        as_of_date: date,
        *,
        duplicate_example_limit: int = 25,
        samples_per_security_type: int = 3,
        persist: bool = True,
    ) -> dict[str, Any]:
        source_path = self.paths.reference_snapshot_file(as_of_date)
        if not source_path.exists():
            raise FileNotFoundError(
                f"Phase 4 reference snapshot is not available for {as_of_date}: {source_path}"
            )
        source = _safe(source_path)
        source_sha256 = _sha256_file(source_path)

        con = connect_utc(":memory:")
        try:
            totals = con.execute(
                f"""
                SELECT
                    count(*) AS row_count,
                    count(DISTINCT instrument_id) AS instrument_count,
                    count(*) - count(DISTINCT instrument_id) AS repeated_identity_rows,
                    count(*) FILTER (WHERE instrument_id IS NULL OR trim(instrument_id)='') AS missing_instrument_id,
                    count(*) FILTER (WHERE ticker IS NULL OR trim(ticker)='') AS missing_ticker,
                    count(*) FILTER (WHERE market IS NULL OR trim(market)='') AS missing_market,
                    count(*) FILTER (WHERE locale IS NULL OR trim(locale)='') AS missing_locale,
                    count(*) FILTER (WHERE security_type IS NULL OR trim(security_type)='') AS missing_security_type,
                    count(*) FILTER (WHERE primary_exchange IS NULL OR trim(primary_exchange)='') AS missing_primary_exchange,
                    count(*) FILTER (WHERE NOT active) AS inactive_rows,
                    count(*) FILTER (WHERE delisted_utc IS NOT NULL) AS rows_with_delisted_timestamp
                FROM read_parquet('{source}')
                """
            ).fetchone()

            duplicate_stats = con.execute(
                f"""
                WITH grouped AS (
                    SELECT
                        instrument_id,
                        count(*) AS row_count,
                        count(DISTINCT ticker) AS ticker_count,
                        count(DISTINCT market) AS market_count,
                        count(DISTINCT locale) AS locale_count,
                        count(DISTINCT primary_exchange) AS exchange_count,
                        count(DISTINCT security_type) AS security_type_count,
                        count(DISTINCT active) AS active_count
                    FROM read_parquet('{source}')
                    GROUP BY instrument_id
                    HAVING count(*) > 1
                )
                SELECT
                    count(*) AS duplicate_identity_groups,
                    coalesce(sum(row_count), 0) AS rows_in_duplicate_groups,
                    count(*) FILTER (WHERE ticker_count > 1) AS multi_ticker_groups,
                    count(*) FILTER (WHERE market_count > 1) AS conflicting_market_groups,
                    count(*) FILTER (WHERE locale_count > 1) AS conflicting_locale_groups,
                    count(*) FILTER (WHERE exchange_count > 1) AS conflicting_exchange_groups,
                    count(*) FILTER (WHERE security_type_count > 1) AS conflicting_security_type_groups,
                    count(*) FILTER (WHERE active_count > 1) AS conflicting_active_groups
                FROM grouped
                """
            ).fetchone()

            report: dict[str, Any] = {
                "inventory_version": REFERENCE_UNIVERSE_INVENTORY_VERSION,
                "as_of_date": as_of_date.isoformat(),
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "source_path": str(source_path),
                "source_sha256": source_sha256,
                "row_count": int(totals[0]),
                "instrument_count": int(totals[1]),
                "repeated_identity_rows": int(totals[2]),
                "missing": {
                    "instrument_id": int(totals[3]),
                    "ticker": int(totals[4]),
                    "market": int(totals[5]),
                    "locale": int(totals[6]),
                    "security_type": int(totals[7]),
                    "primary_exchange": int(totals[8]),
                },
                "inactive_rows": int(totals[9]),
                "rows_with_delisted_timestamp": int(totals[10]),
                "duplicate_identity": {
                    "groups": int(duplicate_stats[0]),
                    "rows": int(duplicate_stats[1]),
                    "multi_ticker_groups": int(duplicate_stats[2]),
                    "conflicting_market_groups": int(duplicate_stats[3]),
                    "conflicting_locale_groups": int(duplicate_stats[4]),
                    "conflicting_exchange_groups": int(duplicate_stats[5]),
                    "conflicting_security_type_groups": int(duplicate_stats[6]),
                    "conflicting_active_groups": int(duplicate_stats[7]),
                    "examples": _duplicate_examples(
                        con,
                        source,
                        limit=duplicate_example_limit,
                    ),
                },
                "distributions": {
                    "market": _value_counts(con, source, "market"),
                    "locale": _value_counts(con, source, "locale"),
                    "security_type": _value_counts(con, source, "security_type"),
                    "primary_exchange": _value_counts(con, source, "primary_exchange"),
                    "identity_quality": _value_counts(con, source, "identity_quality"),
                    "active": _value_counts(con, source, "active"),
                },
                "security_type_examples": _security_type_examples(
                    con,
                    source,
                    samples_per_type=samples_per_security_type,
                ),
            }
        finally:
            con.close()

        if persist:
            target = self.paths.universe_reference_inventory_report(as_of_date)
            atomic_write_text(target, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
            report["report_path"] = str(target)
        return report
