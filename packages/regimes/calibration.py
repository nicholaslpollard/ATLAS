from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.discovery.filter_policy import ACTIVE_DISCOVERY_FILTER_POLICY
from packages.features.feature_registry import (
    CORE_FEATURE_CONTRACT_VERSION,
    CORE_FEATURE_REGISTRY,
)

from .input_inventory import MARKET_PROXY_TICKERS, SECTOR_PROXY_TICKERS


REGIME_CALIBRATION_CONTRACT_VERSION = (
    "regime-calibration-v1-historical-activity-floor-proxy-distributions"
)
REGIME_CALIBRATION_QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)

BREADTH_METRICS = (
    "close_above_ema_20",
    "close_above_ema_50",
    "close_above_ema_200",
    "ema_20_above_ema_50",
    "ema_50_above_ema_200",
    "positive_return_1",
    "rsi_above_50",
    "macd_hist_positive",
)

PROXY_METRICS = (
    "return_1",
    "rsi_14",
    "natr_14",
    "realized_volatility_20",
    "directional_efficiency_20",
)

BASKET_METRICS = (
    "fraction_above_ema_20",
    "fraction_above_ema_50",
    "fraction_above_ema_200",
    "fraction_ema_20_above_ema_50",
    "fraction_ema_50_above_ema_200",
    "fraction_positive_return_1",
    "fraction_rsi_above_50",
    "fraction_macd_hist_positive",
    "median_rsi_14",
    "median_natr_14",
    "median_realized_volatility_20",
    "median_directional_efficiency_20",
)


@dataclass(frozen=True, slots=True)
class RegimeCalibrationReport:
    contract_version: str
    generated_at_utc: str
    start_date: str
    end_date: str
    wall_seconds: float
    requested_session_count: int
    feature_manifest_count: int
    feature_lineage_fingerprint: str
    feature_contract_version: str
    feature_registry_fingerprint: str
    discovery_filter_policy_version: str
    minimum_dollar_volume: float
    breadth_population_note: str
    usable_breadth_session_count: int
    first_usable_breadth_date: str | None
    last_usable_breadth_date: str | None
    breadth_participant_count_quantiles: dict[str, float | None]
    breadth_metric_quantiles: dict[str, dict[str, float | None]]
    end_date_breadth: dict[str, float | int | None]
    market_proxy_observation_counts: dict[str, int]
    market_proxy_quantiles: dict[str, dict[str, dict[str, float | None]]]
    market_basket_metric_quantiles: dict[str, dict[str, float | None]]
    sector_proxy_observation_counts: dict[str, int]
    sector_proxy_quantiles: dict[str, dict[str, dict[str, float | None]]]
    sector_basket_metric_quantiles: dict[str, dict[str, float | None]]
    source_daily_bar_glob: str
    source_feature_glob: str
    report_path: str


def quantile_label(value: float) -> str:
    return f"p{int(round(value * 100)):02d}"


def quantile_summary(series: pd.Series) -> dict[str, float | None]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        result: dict[str, float | None] = {"min": None}
        result.update({quantile_label(q): None for q in REGIME_CALIBRATION_QUANTILES})
        result["max"] = None
        return result
    result = {"min": float(numeric.min())}
    for q in REGIME_CALIBRATION_QUANTILES:
        result[quantile_label(q)] = float(numeric.quantile(q))
    result["max"] = float(numeric.max())
    return result


def metric_quantiles(frame: pd.DataFrame, metrics: tuple[str, ...]) -> dict[str, dict[str, float | None]]:
    return {metric: quantile_summary(frame[metric]) for metric in metrics}


def basket_daily(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=("trading_date",) + BASKET_METRICS)
    data = frame.copy()
    data["trading_date"] = pd.to_datetime(data["trading_date"]).dt.date
    data["above_ema_20"] = (data["close"] > data["ema_20"]).astype("float64")
    data["above_ema_50"] = (data["close"] > data["ema_50"]).astype("float64")
    data["above_ema_200"] = (data["close"] > data["ema_200"]).astype("float64")
    data["ema_20_above_ema_50"] = (data["ema_20"] > data["ema_50"]).astype("float64")
    data["ema_50_above_ema_200"] = (data["ema_50"] > data["ema_200"]).astype("float64")
    data["positive_return_1"] = (data["return_1"] > 0.0).astype("float64")
    data["rsi_above_50"] = (data["rsi_14"] > 50.0).astype("float64")
    data["macd_hist_positive"] = (data["macd_hist_12_26_9"] > 0.0).astype("float64")
    grouped = data.groupby("trading_date", sort=True, observed=True)
    return grouped.agg(
        fraction_above_ema_20=("above_ema_20", "mean"),
        fraction_above_ema_50=("above_ema_50", "mean"),
        fraction_above_ema_200=("above_ema_200", "mean"),
        fraction_ema_20_above_ema_50=("ema_20_above_ema_50", "mean"),
        fraction_ema_50_above_ema_200=("ema_50_above_ema_200", "mean"),
        fraction_positive_return_1=("positive_return_1", "mean"),
        fraction_rsi_above_50=("rsi_above_50", "mean"),
        fraction_macd_hist_positive=("macd_hist_positive", "mean"),
        median_rsi_14=("rsi_14", "median"),
        median_natr_14=("natr_14", "median"),
        median_realized_volatility_20=("realized_volatility_20", "median"),
        median_directional_efficiency_20=("directional_efficiency_20", "median"),
    ).reset_index()


class RegimeCalibration:
    """Measure historical distributions before Phase 9 regime thresholds are locked.

    The broad calibration population intentionally uses the already-accepted Phase 8
    dollar-volume floor, but it is not called the production universe because ATLAS
    does not have a daily Phase 7 reference snapshot for every historical session.
    Proxy calibration is exact for the named market/sector ETF baskets.

    Phase 6 deliberately separates canonical OHLCV facts from derived features.
    Calibration therefore joins canonical 1d close to the 1d feature lake on the exact
    ``(symbol, timestamp_utc)`` market key rather than assuming source OHLCV is stored
    inside feature Parquet.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)

    def _lineage(self, sessions: list[date]) -> tuple[int, str]:
        entries: list[str] = []
        missing: list[Path] = []
        for session in sessions:
            path = self.paths.feature_manifest_file(Timeframe.DAY_1, session)
            if not path.is_file():
                missing.append(path)
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid feature manifest JSON: {path}") from exc
            feature_sha = payload.get("feature_sha256")
            if not feature_sha:
                raise ValueError(f"Feature manifest is missing feature_sha256: {path}")
            entries.append(f"{session.isoformat()}:{feature_sha}")
        if missing:
            preview = "\n  ".join(str(path) for path in missing[:20])
            suffix = "" if len(missing) <= 20 else f"\n  ... and {len(missing) - 20} more"
            raise FileNotFoundError(
                "Phase 9 calibration requires complete 1d feature manifests:\n  " + preview + suffix
            )
        raw = "\n".join(entries).encode("utf-8")
        return len(entries), hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _date_sql(value: date) -> str:
        return f"DATE '{value.isoformat()}'"

    def _breadth_daily(self, start_date: date, end_date: date) -> pd.DataFrame:
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        floor = float(ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume)
        con = connect_utc(":memory:")
        try:
            return con.execute(
                f"""
                WITH feat AS (
                    SELECT
                        symbol, timestamp_utc, return_1, ema_20, ema_50, ema_200,
                        rsi_14, macd_hist_12_26_9, dollar_volume
                    FROM read_parquet({sql_string(feature_glob)}, union_by_name=true)
                    WHERE CAST(timestamp_utc AS DATE) BETWEEN {self._date_sql(start_date)} AND {self._date_sql(end_date)}
                      AND dollar_volume >= {floor}
                      AND ema_20 IS NOT NULL
                      AND ema_50 IS NOT NULL
                      AND ema_200 IS NOT NULL
                      AND return_1 IS NOT NULL
                      AND rsi_14 IS NOT NULL
                      AND macd_hist_12_26_9 IS NOT NULL
                ), bars AS (
                    SELECT symbol, timestamp_utc, close
                    FROM read_parquet({sql_string(bar_glob)}, union_by_name=true)
                    WHERE CAST(timestamp_utc AS DATE) BETWEEN {self._date_sql(start_date)} AND {self._date_sql(end_date)}
                      AND close > 0
                ), eligible AS (
                    SELECT
                        CAST(f.timestamp_utc AS DATE) AS trading_date,
                        b.close, f.return_1, f.ema_20, f.ema_50, f.ema_200,
                        f.rsi_14, f.macd_hist_12_26_9, f.dollar_volume
                    FROM feat AS f
                    INNER JOIN bars AS b
                      ON b.symbol = f.symbol
                     AND b.timestamp_utc = f.timestamp_utc
                )
                SELECT
                    trading_date,
                    count(*) AS participant_count,
                    avg(CASE WHEN close > ema_20 THEN 1.0 ELSE 0.0 END) AS close_above_ema_20,
                    avg(CASE WHEN close > ema_50 THEN 1.0 ELSE 0.0 END) AS close_above_ema_50,
                    avg(CASE WHEN close > ema_200 THEN 1.0 ELSE 0.0 END) AS close_above_ema_200,
                    avg(CASE WHEN ema_20 > ema_50 THEN 1.0 ELSE 0.0 END) AS ema_20_above_ema_50,
                    avg(CASE WHEN ema_50 > ema_200 THEN 1.0 ELSE 0.0 END) AS ema_50_above_ema_200,
                    avg(CASE WHEN return_1 > 0 THEN 1.0 ELSE 0.0 END) AS positive_return_1,
                    avg(CASE WHEN rsi_14 > 50 THEN 1.0 ELSE 0.0 END) AS rsi_above_50,
                    avg(CASE WHEN macd_hist_12_26_9 > 0 THEN 1.0 ELSE 0.0 END) AS macd_hist_positive
                FROM eligible
                GROUP BY trading_date
                ORDER BY trading_date
                """
            ).fetchdf()
        finally:
            con.close()

    def _proxy_frame(self, start_date: date, end_date: date) -> pd.DataFrame:
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        tickers = MARKET_PROXY_TICKERS + SECTOR_PROXY_TICKERS
        placeholders = ", ".join("?" for _ in tickers)
        con = connect_utc(":memory:")
        try:
            return con.execute(
                f"""
                WITH feat AS (
                    SELECT
                        symbol, timestamp_utc, return_1, ema_20, ema_50, ema_200,
                        rsi_14, macd_hist_12_26_9, natr_14,
                        realized_volatility_20, directional_efficiency_20
                    FROM read_parquet({sql_string(feature_glob)}, union_by_name=true)
                    WHERE CAST(timestamp_utc AS DATE) BETWEEN {self._date_sql(start_date)} AND {self._date_sql(end_date)}
                      AND symbol IN ({placeholders})
                      AND return_1 IS NOT NULL
                      AND ema_20 IS NOT NULL
                      AND ema_50 IS NOT NULL
                      AND ema_200 IS NOT NULL
                      AND rsi_14 IS NOT NULL
                      AND macd_hist_12_26_9 IS NOT NULL
                      AND natr_14 IS NOT NULL
                      AND realized_volatility_20 IS NOT NULL
                      AND directional_efficiency_20 IS NOT NULL
                ), bars AS (
                    SELECT symbol, timestamp_utc, close
                    FROM read_parquet({sql_string(bar_glob)}, union_by_name=true)
                    WHERE CAST(timestamp_utc AS DATE) BETWEEN {self._date_sql(start_date)} AND {self._date_sql(end_date)}
                      AND symbol IN ({placeholders})
                      AND close > 0
                )
                SELECT
                    CAST(f.timestamp_utc AS DATE) AS trading_date,
                    f.symbol,
                    b.close, f.return_1, f.ema_20, f.ema_50, f.ema_200, f.rsi_14,
                    f.macd_hist_12_26_9, f.natr_14, f.realized_volatility_20,
                    f.directional_efficiency_20
                FROM feat AS f
                INNER JOIN bars AS b
                  ON b.symbol = f.symbol
                 AND b.timestamp_utc = f.timestamp_utc
                ORDER BY trading_date, f.symbol
                """,
                list(tickers) + list(tickers),
            ).fetchdf()
        finally:
            con.close()

    @staticmethod
    def _proxy_summaries(
        frame: pd.DataFrame,
        tickers: tuple[str, ...],
    ) -> tuple[dict[str, int], dict[str, dict[str, dict[str, float | None]]]]:
        counts: dict[str, int] = {}
        summaries: dict[str, dict[str, dict[str, float | None]]] = {}
        for ticker in tickers:
            subset = frame.loc[frame["symbol"] == ticker]
            counts[ticker] = int(len(subset))
            summaries[ticker] = metric_quantiles(subset, PROXY_METRICS)
        return counts, summaries

    @staticmethod
    def _end_date_breadth(frame: pd.DataFrame, end_date: date) -> dict[str, float | int | None]:
        if frame.empty:
            return {"trading_date": None, "participant_count": None, **{metric: None for metric in BREADTH_METRICS}}
        dates = pd.to_datetime(frame["trading_date"]).dt.date
        exact = frame.loc[dates == end_date]
        row = exact.iloc[-1] if not exact.empty else frame.iloc[-1]
        result: dict[str, float | int | None] = {
            "trading_date": str(pd.Timestamp(row["trading_date"]).date()),
            "participant_count": int(row["participant_count"]),
        }
        for metric in BREADTH_METRICS:
            result[metric] = float(row[metric])
        return result

    def build(self, start_date: date, end_date: date) -> RegimeCalibrationReport:
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        started = perf_counter()
        sessions = get_market_calendar().sessions_in_range(start_date, end_date)
        if not sessions:
            raise ValueError("requested calibration range contains no XNYS sessions")
        manifest_count, lineage_fingerprint = self._lineage(sessions)
        breadth = self._breadth_daily(start_date, end_date)
        proxies = self._proxy_frame(start_date, end_date)

        market_frame = proxies.loc[proxies["symbol"].isin(MARKET_PROXY_TICKERS)].copy()
        sector_frame = proxies.loc[proxies["symbol"].isin(SECTOR_PROXY_TICKERS)].copy()
        market_counts, market_quantiles = self._proxy_summaries(market_frame, MARKET_PROXY_TICKERS)
        sector_counts, sector_quantiles = self._proxy_summaries(sector_frame, SECTOR_PROXY_TICKERS)
        market_basket = basket_daily(market_frame)
        sector_basket = basket_daily(sector_frame)

        target = self.paths.regime_calibration_report(end_date)
        first_date = None if breadth.empty else str(pd.Timestamp(breadth.iloc[0]["trading_date"]).date())
        last_date = None if breadth.empty else str(pd.Timestamp(breadth.iloc[-1]["trading_date"]).date())
        report = RegimeCalibrationReport(
            contract_version=REGIME_CALIBRATION_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            requested_session_count=len(sessions),
            feature_manifest_count=manifest_count,
            feature_lineage_fingerprint=lineage_fingerprint,
            feature_contract_version=CORE_FEATURE_CONTRACT_VERSION,
            feature_registry_fingerprint=CORE_FEATURE_REGISTRY.fingerprint(),
            discovery_filter_policy_version="discovery-filter-v1-250k-dollar-volume-no-price-floor",
            minimum_dollar_volume=float(ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume),
            breadth_population_note=(
                "Historical calibration population uses complete 1d feature rows at or above the accepted "
                "Phase 8 dollar-volume floor and exact-key canonical 1d closes. It is calibration evidence, "
                "not a reconstructed daily Phase 7 universe."
            ),
            usable_breadth_session_count=int(len(breadth)),
            first_usable_breadth_date=first_date,
            last_usable_breadth_date=last_date,
            breadth_participant_count_quantiles=quantile_summary(breadth["participant_count"]),
            breadth_metric_quantiles=metric_quantiles(breadth, BREADTH_METRICS),
            end_date_breadth=self._end_date_breadth(breadth, end_date),
            market_proxy_observation_counts=market_counts,
            market_proxy_quantiles=market_quantiles,
            market_basket_metric_quantiles=metric_quantiles(market_basket, BASKET_METRICS),
            sector_proxy_observation_counts=sector_counts,
            sector_proxy_quantiles=sector_quantiles,
            sector_basket_metric_quantiles=metric_quantiles(sector_basket, BASKET_METRICS),
            source_daily_bar_glob=self.paths.glob_for_timeframe(Timeframe.DAY_1),
            source_feature_glob=self.paths.feature_glob(Timeframe.DAY_1),
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
