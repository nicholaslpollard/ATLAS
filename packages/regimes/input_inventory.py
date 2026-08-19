from __future__ import annotations

import json
from collections import Counter
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
from packages.data.sql import sql_string
from packages.discovery.persistence import DISCOVERY_STATE_MANIFEST_VERSION
from packages.features.partition_store import sha256_file


REGIME_INPUT_INVENTORY_CONTRACT_VERSION = (
    "regime-input-inventory-v1-local-breadth-benchmark-sector-proxy-audit"
)

MARKET_PROXY_TICKERS = ("SPY", "QQQ", "IWM", "DIA")
SECTOR_PROXY_TICKERS = (
    "XLB",
    "XLC",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLRE",
    "XLU",
    "XLV",
    "XLY",
)

CLASSIFICATION_FIELD_CANDIDATES = frozenset(
    {
        "sector",
        "sector_code",
        "sector_name",
        "industry",
        "industry_code",
        "industry_name",
        "sic_code",
        "sic_description",
        "naics",
        "gics_sector",
        "gics_industry",
    }
)


@dataclass(frozen=True, slots=True)
class BreadthEvidence:
    population_count: int
    daily_join_count: int
    close_above_ema_20: int
    close_above_ema_50: int
    close_above_ema_200: int
    ema_20_above_ema_50: int
    ema_50_above_ema_200: int
    positive_return_1: int
    negative_return_1: int
    rsi_above_50: int
    rsi_below_50: int
    macd_hist_positive: int
    macd_hist_negative: int
    percentages: dict[str, float]


@dataclass(frozen=True, slots=True)
class ProxyEvidence:
    ticker: str
    has_daily_bar: bool
    has_daily_feature: bool
    has_regular_4h_feature: bool
    has_regular_1h_feature: bool
    close: float | None
    return_1: float | None
    ema_20: float | None
    ema_50: float | None
    ema_200: float | None
    rsi_14: float | None
    macd_hist_12_26_9: float | None
    natr_14: float | None
    realized_volatility_20: float | None
    directional_efficiency_20: float | None


@dataclass(frozen=True, slots=True)
class RegimeInputInventoryReport:
    contract_version: str
    as_of_date: str
    generated_at_utc: str
    wall_seconds: float
    state_record_count: int
    source_sha256: dict[str, str]
    raw_state_counts: dict[str, int]
    effective_state_counts: dict[str, int]
    direction_counts: dict[str, int]
    top_setup_counts: dict[str, int]
    breadth: BreadthEvidence
    market_proxies: dict[str, ProxyEvidence]
    sector_proxies: dict[str, ProxyEvidence]
    classification_columns: dict[str, tuple[str, ...]]
    local_sector_mapping_ready: bool
    report_path: str


class RegimeInputInventory:
    """Audit the local evidence available before Phase 9 regime policy is locked.

    This diagnostic intentionally does not label market, sector, or ticker regimes.
    It measures broad-market breadth, confirms benchmark/sector-proxy coverage, and
    checks whether a point-in-time sector/industry classification already exists in
    ATLAS's local canonical/reference artifacts. Missing classification is reported
    explicitly rather than guessed from ticker names or security descriptions.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)

    def _required_paths(self, as_of_date: date) -> dict[str, Path]:
        paths = {
            "discovery_state": self.paths.discovery_state_file(as_of_date),
            "discovery_state_manifest": self.paths.discovery_state_manifest(as_of_date),
            "discovery_foundation": self.paths.discovery_snapshot_file(as_of_date),
            "universe": self.paths.universe_snapshot_file(as_of_date),
            "reference": self.paths.reference_snapshot_file(as_of_date),
            "bars_1d": self.paths.canonical_file(Timeframe.DAY_1, as_of_date),
            "features_1d": self.paths.feature_file(Timeframe.DAY_1, as_of_date),
            "features_4h": self.paths.feature_file(Timeframe.HOUR_4, as_of_date),
            "features_1h": self.paths.feature_file(Timeframe.HOUR_1, as_of_date),
        }
        missing = [f"{name}: {path}" for name, path in paths.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError("Phase 9 regime inventory inputs are missing:\n  " + "\n  ".join(missing))
        return paths

    @staticmethod
    def _manifest(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON manifest: {path}") from exc

    @staticmethod
    def _number(value: object) -> float | None:
        return None if value is None else float(value)

    @staticmethod
    def _percentage(count: int, denominator: int) -> float:
        return 0.0 if denominator <= 0 else float(count) / float(denominator)

    @staticmethod
    def _classification_columns(con: Any, path: Path) -> tuple[str, ...]:
        rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet({sql_string(path)})").fetchall()
        names = {str(row[0]) for row in rows}
        return tuple(sorted(name for name in names if name.lower() in CLASSIFICATION_FIELD_CANDIDATES))

    def _validate_state_lineage(self, paths: dict[str, Path]) -> None:
        manifest = self._manifest(paths["discovery_state_manifest"])
        if manifest.get("manifest_version") != DISCOVERY_STATE_MANIFEST_VERSION:
            raise ValueError("Discovery state manifest contract is stale for Phase 9 inventory")
        actual_sha = sha256_file(paths["discovery_state"])
        if manifest.get("snapshot_sha256") != actual_sha:
            raise ValueError("Discovery state snapshot hash does not match its manifest")

    @staticmethod
    def _counts(con: Any, state_path: Path, column: str) -> dict[str, int]:
        rows = con.execute(
            f"SELECT CAST({column} AS VARCHAR), count(*) "
            f"FROM read_parquet({sql_string(state_path)}) GROUP BY 1 ORDER BY 1"
        ).fetchall()
        return {str(key): int(value) for key, value in rows}

    def _breadth(self, con: Any, paths: dict[str, Path]) -> BreadthEvidence:
        row = con.execute(
            f"""
            WITH state AS (
                SELECT instrument_id, ticker
                FROM read_parquet({sql_string(paths['discovery_state'])})
            ), bars AS (
                SELECT symbol, close
                FROM (
                    SELECT symbol, close, timestamp_utc,
                           row_number() OVER (PARTITION BY symbol ORDER BY timestamp_utc DESC) AS rn
                    FROM read_parquet({sql_string(paths['bars_1d'])})
                )
                WHERE rn = 1
            ), feat AS (
                SELECT symbol, return_1, ema_20, ema_50, ema_200, rsi_14,
                       macd_hist_12_26_9
                FROM (
                    SELECT symbol, timestamp_utc, return_1, ema_20, ema_50, ema_200,
                           rsi_14, macd_hist_12_26_9,
                           row_number() OVER (PARTITION BY symbol ORDER BY timestamp_utc DESC) AS rn
                    FROM read_parquet({sql_string(paths['features_1d'])})
                )
                WHERE rn = 1
            ), joined AS (
                SELECT s.instrument_id, s.ticker, b.close,
                       f.return_1, f.ema_20, f.ema_50, f.ema_200, f.rsi_14,
                       f.macd_hist_12_26_9,
                       b.symbol IS NOT NULL AND f.symbol IS NOT NULL AS daily_joined
                FROM state s
                LEFT JOIN bars b ON b.symbol = s.ticker
                LEFT JOIN feat f ON f.symbol = s.ticker
            )
            SELECT
                count(*),
                count(*) FILTER (WHERE daily_joined),
                count(*) FILTER (WHERE daily_joined AND close > ema_20),
                count(*) FILTER (WHERE daily_joined AND close > ema_50),
                count(*) FILTER (WHERE daily_joined AND close > ema_200),
                count(*) FILTER (WHERE daily_joined AND ema_20 > ema_50),
                count(*) FILTER (WHERE daily_joined AND ema_50 > ema_200),
                count(*) FILTER (WHERE daily_joined AND return_1 > 0),
                count(*) FILTER (WHERE daily_joined AND return_1 < 0),
                count(*) FILTER (WHERE daily_joined AND rsi_14 > 50),
                count(*) FILTER (WHERE daily_joined AND rsi_14 < 50),
                count(*) FILTER (WHERE daily_joined AND macd_hist_12_26_9 > 0),
                count(*) FILTER (WHERE daily_joined AND macd_hist_12_26_9 < 0)
            FROM joined
            """
        ).fetchone()
        values = [int(value) for value in row]
        population, joined = values[0], values[1]
        labels = (
            "close_above_ema_20",
            "close_above_ema_50",
            "close_above_ema_200",
            "ema_20_above_ema_50",
            "ema_50_above_ema_200",
            "positive_return_1",
            "negative_return_1",
            "rsi_above_50",
            "rsi_below_50",
            "macd_hist_positive",
            "macd_hist_negative",
        )
        percentages = {
            label: self._percentage(value, joined)
            for label, value in zip(labels, values[2:], strict=True)
        }
        return BreadthEvidence(
            population_count=population,
            daily_join_count=joined,
            close_above_ema_20=values[2],
            close_above_ema_50=values[3],
            close_above_ema_200=values[4],
            ema_20_above_ema_50=values[5],
            ema_50_above_ema_200=values[6],
            positive_return_1=values[7],
            negative_return_1=values[8],
            rsi_above_50=values[9],
            rsi_below_50=values[10],
            macd_hist_positive=values[11],
            macd_hist_negative=values[12],
            percentages=percentages,
        )

    def _proxy(self, con: Any, ticker: str, paths: dict[str, Path]) -> ProxyEvidence:
        row = con.execute(
            f"""
            WITH b AS (
                SELECT close
                FROM read_parquet({sql_string(paths['bars_1d'])})
                WHERE symbol = ?
                ORDER BY timestamp_utc DESC
                LIMIT 1
            ), d AS (
                SELECT return_1, ema_20, ema_50, ema_200, rsi_14,
                       macd_hist_12_26_9, natr_14, realized_volatility_20,
                       directional_efficiency_20
                FROM read_parquet({sql_string(paths['features_1d'])})
                WHERE symbol = ?
                ORDER BY timestamp_utc DESC
                LIMIT 1
            ), h4 AS (
                SELECT count(*) > 0 AS available
                FROM read_parquet({sql_string(paths['features_4h'])})
                WHERE symbol = ? AND session_segment = 'regular'
            ), h1 AS (
                SELECT count(*) > 0 AS available
                FROM read_parquet({sql_string(paths['features_1h'])})
                WHERE symbol = ? AND session_segment = 'regular'
            )
            SELECT
                EXISTS(SELECT 1 FROM b),
                EXISTS(SELECT 1 FROM d),
                (SELECT available FROM h4),
                (SELECT available FROM h1),
                (SELECT close FROM b),
                (SELECT return_1 FROM d),
                (SELECT ema_20 FROM d),
                (SELECT ema_50 FROM d),
                (SELECT ema_200 FROM d),
                (SELECT rsi_14 FROM d),
                (SELECT macd_hist_12_26_9 FROM d),
                (SELECT natr_14 FROM d),
                (SELECT realized_volatility_20 FROM d),
                (SELECT directional_efficiency_20 FROM d)
            """,
            [ticker, ticker, ticker, ticker],
        ).fetchone()
        return ProxyEvidence(
            ticker=ticker,
            has_daily_bar=bool(row[0]),
            has_daily_feature=bool(row[1]),
            has_regular_4h_feature=bool(row[2]),
            has_regular_1h_feature=bool(row[3]),
            close=self._number(row[4]),
            return_1=self._number(row[5]),
            ema_20=self._number(row[6]),
            ema_50=self._number(row[7]),
            ema_200=self._number(row[8]),
            rsi_14=self._number(row[9]),
            macd_hist_12_26_9=self._number(row[10]),
            natr_14=self._number(row[11]),
            realized_volatility_20=self._number(row[12]),
            directional_efficiency_20=self._number(row[13]),
        )

    def build(self, as_of_date: date) -> RegimeInputInventoryReport:
        started = perf_counter()
        paths = self._required_paths(as_of_date)
        self._validate_state_lineage(paths)

        con = connect_utc(":memory:")
        try:
            raw_state_counts = self._counts(con, paths["discovery_state"], "raw_state")
            effective_state_counts = self._counts(con, paths["discovery_state"], "effective_state")
            direction_counts = self._counts(con, paths["discovery_state"], "direction")
            top_setup_counts = self._counts(con, paths["discovery_state"], "top_setup")
            breadth = self._breadth(con, paths)
            market_proxies = {
                ticker: self._proxy(con, ticker, paths) for ticker in MARKET_PROXY_TICKERS
            }
            sector_proxies = {
                ticker: self._proxy(con, ticker, paths) for ticker in SECTOR_PROXY_TICKERS
            }
            classification_columns = {
                "universe": self._classification_columns(con, paths["universe"]),
                "reference": self._classification_columns(con, paths["reference"]),
            }
        finally:
            con.close()

        source_sha256 = {
            name: sha256_file(path)
            for name, path in paths.items()
            if path.suffix.lower() == ".parquet" or name == "discovery_state_manifest"
        }
        local_sector_mapping_ready = any(classification_columns.values())
        report_path = self.paths.regime_input_inventory_report(as_of_date)
        report = RegimeInputInventoryReport(
            contract_version=REGIME_INPUT_INVENTORY_CONTRACT_VERSION,
            as_of_date=as_of_date.isoformat(),
            generated_at_utc=datetime.now(UTC).isoformat(),
            wall_seconds=perf_counter() - started,
            state_record_count=breadth.population_count,
            source_sha256=source_sha256,
            raw_state_counts=raw_state_counts,
            effective_state_counts=effective_state_counts,
            direction_counts=direction_counts,
            top_setup_counts=top_setup_counts,
            breadth=breadth,
            market_proxies=market_proxies,
            sector_proxies=sector_proxies,
            classification_columns=classification_columns,
            local_sector_mapping_ready=local_sector_mapping_ready,
            report_path=str(report_path),
        )
        atomic_write_text(
            report_path,
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report


def complete_proxy_count(proxies: dict[str, ProxyEvidence]) -> int:
    return sum(
        proxy.has_daily_bar
        and proxy.has_daily_feature
        and proxy.has_regular_4h_feature
        and proxy.has_regular_1h_feature
        for proxy in proxies.values()
    )


def state_population(counts: dict[str, int]) -> int:
    return sum(Counter(counts).values())
