from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths


DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION = "discovery-input-inventory-v1-measured-market-activity"


@dataclass(frozen=True, slots=True)
class QuantileSummary:
    finite_count: int
    missing_or_nonfinite_count: int
    minimum: float | None
    p05: float | None
    p10: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p90: float | None
    p95: float | None
    p99: float | None
    maximum: float | None


@dataclass(frozen=True, slots=True)
class TimeframeCoverage:
    timeframe: str
    total_feature_rows: int
    distinct_feature_symbols: int
    matched_universe_symbols: int
    missing_universe_symbols: int
    regular_session_symbols: int | None
    premarket_symbols: int | None
    after_hours_symbols: int | None


@dataclass(frozen=True, slots=True)
class DiscoveryInputInventoryReport:
    contract_version: str
    as_of_date: str
    generated_at_utc: str
    wall_seconds: float
    universe_count: int
    duplicate_universe_tickers: int
    source_sha256: dict[str, str]
    coverage: dict[str, TimeframeCoverage]
    daily_quality: dict[str, int]
    quantiles: dict[str, QuantileSummary]
    threshold_counts: dict[str, dict[str, int]]
    combined_activity_counts: dict[str, int]
    report_path: str


class DiscoveryInputInventory:
    """Measure the real Phase 8 discovery input population before locking filters.

    This class intentionally does not decide which securities survive discovery.
    It measures point-in-time universe/feature coverage and activity distributions so
    the Phase 8 policy can be chosen from observed data rather than arbitrary guesses.
    """

    DAILY_METRICS = (
        "close",
        "volume",
        "dollar_volume",
        "relative_volume_20",
        "relative_dollar_volume_20",
        "natr_14",
        "realized_volatility_20",
    )

    CLOSE_THRESHOLDS = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
    VOLUME_THRESHOLDS = (
        1_000.0,
        10_000.0,
        50_000.0,
        100_000.0,
        250_000.0,
        500_000.0,
        1_000_000.0,
    )
    DOLLAR_VOLUME_THRESHOLDS = (
        100_000.0,
        250_000.0,
        500_000.0,
        1_000_000.0,
        2_000_000.0,
        5_000_000.0,
        10_000_000.0,
        25_000_000.0,
        50_000_000.0,
    )
    RELATIVE_VOLUME_THRESHOLDS = (0.5, 1.0, 1.5, 2.0, 3.0)

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)

    @staticmethod
    def _safe(path: Path | str) -> str:
        return str(path).replace("\\", "/").replace("'", "''")

    @staticmethod
    def _sha256(path: Path, *, chunk_size: int = 4 * 1024 * 1024) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _number(value: object) -> float | None:
        return None if value is None else float(value)

    def _required_paths(self, as_of_date: date) -> dict[str, Path]:
        paths = {
            "universe": self.paths.universe_snapshot_file(as_of_date),
            "features_1d": self.paths.feature_file(Timeframe.DAY_1, as_of_date),
            "features_4h": self.paths.feature_file(Timeframe.HOUR_4, as_of_date),
            "features_1h": self.paths.feature_file(Timeframe.HOUR_1, as_of_date),
        }
        missing = [f"{name}: {path}" for name, path in paths.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError("Phase 8 inventory inputs are missing:\n  " + "\n  ".join(missing))
        return paths

    def _quantiles(self, con: Any, metric: str) -> QuantileSummary:
        row = con.execute(
            f"""
            SELECT
                count(*) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                count(*) FILTER (WHERE {metric} IS NULL OR NOT isfinite({metric})),
                min({metric}) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                quantile_cont({metric}, 0.05) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                quantile_cont({metric}, 0.10) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                quantile_cont({metric}, 0.25) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                quantile_cont({metric}, 0.50) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                quantile_cont({metric}, 0.75) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                quantile_cont({metric}, 0.90) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                quantile_cont({metric}, 0.95) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                quantile_cont({metric}, 0.99) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric})),
                max({metric}) FILTER (WHERE {metric} IS NOT NULL AND isfinite({metric}))
            FROM atlas_daily_join
            """
        ).fetchone()
        return QuantileSummary(
            finite_count=int(row[0]),
            missing_or_nonfinite_count=int(row[1]),
            minimum=self._number(row[2]),
            p05=self._number(row[3]),
            p10=self._number(row[4]),
            p25=self._number(row[5]),
            p50=self._number(row[6]),
            p75=self._number(row[7]),
            p90=self._number(row[8]),
            p95=self._number(row[9]),
            p99=self._number(row[10]),
            maximum=self._number(row[11]),
        )

    @staticmethod
    def _threshold_label(value: float) -> str:
        if value >= 1_000_000:
            return f">={value / 1_000_000:g}m"
        if value >= 1_000:
            return f">={value / 1_000:g}k"
        return f">={value:g}"

    def _threshold_counts(
        self,
        con: Any,
        metric: str,
        thresholds: tuple[float, ...],
    ) -> dict[str, int]:
        result: dict[str, int] = {}
        for threshold in thresholds:
            value = con.execute(
                f"""
                SELECT count(*)
                FROM atlas_daily_join
                WHERE {metric} IS NOT NULL
                  AND isfinite({metric})
                  AND {metric} >= ?
                """,
                [threshold],
            ).fetchone()[0]
            result[self._threshold_label(threshold)] = int(value)
        return result

    def _coverage(
        self,
        con: Any,
        timeframe: Timeframe,
        feature_path: Path,
        universe_count: int,
    ) -> TimeframeCoverage:
        safe = self._safe(feature_path)
        if timeframe == Timeframe.DAY_1:
            row = con.execute(
                f"""
                WITH f AS (
                    SELECT symbol FROM read_parquet('{safe}')
                ), stats AS (
                    SELECT count(*) AS feature_rows, count(DISTINCT symbol) AS feature_symbols FROM f
                ), matched AS (
                    SELECT count(DISTINCT u.ticker) AS matched
                    FROM atlas_universe u
                    INNER JOIN f ON f.symbol = u.ticker
                )
                SELECT stats.feature_rows, stats.feature_symbols, matched.matched
                FROM stats CROSS JOIN matched
                """
            ).fetchone()
            matched = int(row[2])
            return TimeframeCoverage(
                timeframe=timeframe.value,
                total_feature_rows=int(row[0]),
                distinct_feature_symbols=int(row[1]),
                matched_universe_symbols=matched,
                missing_universe_symbols=universe_count - matched,
                regular_session_symbols=None,
                premarket_symbols=None,
                after_hours_symbols=None,
            )

        row = con.execute(
            f"""
            WITH f AS (
                SELECT symbol, session_segment
                FROM read_parquet('{safe}')
            ), stats AS (
                SELECT
                    count(*) AS feature_rows,
                    count(DISTINCT symbol) AS feature_symbols,
                    count(DISTINCT symbol) FILTER (WHERE session_segment='regular') AS regular_symbols,
                    count(DISTINCT symbol) FILTER (WHERE session_segment='premarket') AS premarket_symbols,
                    count(DISTINCT symbol) FILTER (WHERE session_segment='after_hours') AS after_hours_symbols
                FROM f
            ), matched AS (
                SELECT count(DISTINCT u.ticker) AS matched
                FROM atlas_universe u
                INNER JOIN f ON f.symbol = u.ticker
            )
            SELECT stats.*, matched.matched FROM stats CROSS JOIN matched
            """
        ).fetchone()
        matched = int(row[5])
        return TimeframeCoverage(
            timeframe=timeframe.value,
            total_feature_rows=int(row[0]),
            distinct_feature_symbols=int(row[1]),
            matched_universe_symbols=matched,
            missing_universe_symbols=universe_count - matched,
            regular_session_symbols=int(row[2]),
            premarket_symbols=int(row[3]),
            after_hours_symbols=int(row[4]),
        )

    def run(self, as_of_date: date) -> DiscoveryInputInventoryReport:
        started = perf_counter()
        paths = self._required_paths(as_of_date)
        report_path = self.paths.discovery_input_inventory_report(as_of_date)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        con = connect_utc(":memory:")
        try:
            universe = self._safe(paths["universe"])
            daily = self._safe(paths["features_1d"])
            con.execute(
                f"""
                CREATE TEMP VIEW atlas_universe AS
                SELECT instrument_id, ticker, security_type
                FROM read_parquet('{universe}')
                WHERE discovery_eligible = TRUE
                """
            )
            universe_count = int(con.execute("SELECT count(*) FROM atlas_universe").fetchone()[0])
            duplicate_tickers = int(
                con.execute(
                    """
                    SELECT count(*) FROM (
                        SELECT ticker FROM atlas_universe GROUP BY ticker HAVING count(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
            if duplicate_tickers:
                raise ValueError(
                    f"Phase 7 discovery universe contains {duplicate_tickers} duplicate routing tickers"
                )

            con.execute(
                f"""
                CREATE TEMP VIEW atlas_daily_latest AS
                SELECT * EXCLUDE (rn)
                FROM (
                    SELECT *, row_number() OVER (PARTITION BY symbol ORDER BY timestamp_utc DESC) AS rn
                    FROM read_parquet('{daily}')
                )
                WHERE rn = 1
                """
            )
            con.execute(
                """
                CREATE TEMP VIEW atlas_daily_join AS
                SELECT
                    u.instrument_id,
                    u.ticker,
                    u.security_type,
                    d.symbol AS feature_symbol,
                    d.timestamp_utc,
                    d.close,
                    d.volume,
                    d.dollar_volume,
                    d.relative_volume_20,
                    d.relative_dollar_volume_20,
                    d.natr_14,
                    d.realized_volatility_20
                FROM atlas_universe u
                LEFT JOIN atlas_daily_latest d ON d.symbol = u.ticker
                """
            )

            quality_row = con.execute(
                """
                SELECT
                    count(*) FILTER (WHERE feature_symbol IS NOT NULL) AS matched,
                    count(*) FILTER (WHERE feature_symbol IS NULL) AS missing,
                    count(*) FILTER (WHERE close IS NULL OR NOT isfinite(close) OR close <= 0) AS invalid_close,
                    count(*) FILTER (WHERE feature_symbol IS NOT NULL AND volume = 0) AS zero_volume,
                    count(*) FILTER (
                        WHERE feature_symbol IS NOT NULL
                          AND (dollar_volume IS NULL OR NOT isfinite(dollar_volume) OR dollar_volume <= 0)
                    ) AS nonpositive_dollar_volume,
                    count(*) FILTER (
                        WHERE feature_symbol IS NOT NULL AND relative_volume_20 IS NULL
                    ) AS relative_volume_warmup,
                    count(*) FILTER (
                        WHERE feature_symbol IS NOT NULL AND natr_14 IS NULL
                    ) AS natr_warmup,
                    count(*) FILTER (
                        WHERE feature_symbol IS NOT NULL AND realized_volatility_20 IS NULL
                    ) AS realized_volatility_warmup
                FROM atlas_daily_join
                """
            ).fetchone()
            daily_quality = {
                "matched_universe": int(quality_row[0]),
                "missing_universe": int(quality_row[1]),
                "invalid_or_nonpositive_close": int(quality_row[2]),
                "zero_volume": int(quality_row[3]),
                "nonpositive_or_missing_dollar_volume": int(quality_row[4]),
                "relative_volume_warmup": int(quality_row[5]),
                "natr_warmup": int(quality_row[6]),
                "realized_volatility_warmup": int(quality_row[7]),
            }

            quantiles = {metric: self._quantiles(con, metric) for metric in self.DAILY_METRICS}
            threshold_counts = {
                "close": self._threshold_counts(con, "close", self.CLOSE_THRESHOLDS),
                "volume": self._threshold_counts(con, "volume", self.VOLUME_THRESHOLDS),
                "dollar_volume": self._threshold_counts(
                    con,
                    "dollar_volume",
                    self.DOLLAR_VOLUME_THRESHOLDS,
                ),
                "relative_volume_20": self._threshold_counts(
                    con,
                    "relative_volume_20",
                    self.RELATIVE_VOLUME_THRESHOLDS,
                ),
            }

            combined: dict[str, int] = {}
            for minimum_close in (0.5, 1.0, 2.0, 5.0):
                for minimum_dollar_volume in (
                    250_000.0,
                    500_000.0,
                    1_000_000.0,
                    2_000_000.0,
                    5_000_000.0,
                    10_000_000.0,
                ):
                    count = con.execute(
                        """
                        SELECT count(*)
                        FROM atlas_daily_join
                        WHERE feature_symbol IS NOT NULL
                          AND close IS NOT NULL AND isfinite(close) AND close >= ?
                          AND dollar_volume IS NOT NULL
                          AND isfinite(dollar_volume)
                          AND dollar_volume >= ?
                        """,
                        [minimum_close, minimum_dollar_volume],
                    ).fetchone()[0]
                    label = (
                        f"close>={minimum_close:g}|dollar_volume>="
                        f"{minimum_dollar_volume / 1_000_000:g}m"
                    )
                    combined[label] = int(count)

            coverage = {
                "1d": self._coverage(
                    con,
                    Timeframe.DAY_1,
                    paths["features_1d"],
                    universe_count,
                ),
                "4h": self._coverage(
                    con,
                    Timeframe.HOUR_4,
                    paths["features_4h"],
                    universe_count,
                ),
                "1h": self._coverage(
                    con,
                    Timeframe.HOUR_1,
                    paths["features_1h"],
                    universe_count,
                ),
            }
        finally:
            con.close()

        report = DiscoveryInputInventoryReport(
            contract_version=DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION,
            as_of_date=as_of_date.isoformat(),
            generated_at_utc=datetime.now(UTC).isoformat(),
            wall_seconds=perf_counter() - started,
            universe_count=universe_count,
            duplicate_universe_tickers=duplicate_tickers,
            source_sha256={name: self._sha256(path) for name, path in paths.items()},
            coverage=coverage,
            daily_quality=daily_quality,
            quantiles=quantiles,
            threshold_counts=threshold_counts,
            combined_activity_counts=dict(sorted(combined.items())),
            report_path=str(report_path),
        )
        atomic_write_text(
            report_path,
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
