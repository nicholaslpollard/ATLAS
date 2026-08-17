from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.historical_materializer import HistoricalFeatureMaterializer
from packages.features.incremental import feature_stream_key
from packages.features.partition_store import FeaturePartitionStore
from packages.features.verification import market_key_series_equal


@dataclass(frozen=True, slots=True)
class FeatureContinuityResult:
    timeframe: Timeframe
    symbol: str
    anchor_date: date
    target_date: date
    replay_sessions: int
    replay_source_rows: int
    target_rows: int
    features_compared: int
    maximum_abs_diff: float
    failed_features: tuple[str, ...]
    key_match: bool

    @property
    def passed(self) -> bool:
        return self.key_match and not self.failed_features and self.target_rows > 0


class FeatureContinuityVerifier:
    """Prove persisted historical state can hydrate and continue incrementally.

    A monthly exact-state checkpoint is loaded, later source bars are fed through the
    same IncrementalFeatureEngine.update API intended for live/current processing,
    and the target session is compared with the already persisted historical feature
    partition. This tests the state handoff rather than recomputing from genesis.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.store = FeaturePartitionStore(settings)
        self.materializer = HistoricalFeatureMaterializer(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        self.feature_names = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]

    def _load_symbol_source(
        self,
        timeframe: Timeframe,
        trading_date: date,
        symbol: str,
    ) -> pd.DataFrame:
        source = self.store.source_path(timeframe, trading_date)
        if not source.is_file():
            raise FileNotFoundError(f"feature source partition is missing: {source}")
        con = connect_utc(":memory:")
        try:
            if timeframe == Timeframe.DAY_1:
                columns = "symbol, timestamp_utc, high, low, close, volume"
                order_by = "timestamp_utc"
            else:
                columns = "symbol, timestamp_utc, session_segment, high, low, close, volume"
                order_by = "session_segment, timestamp_utc"
            return con.execute(
                f"""
                SELECT {columns}
                FROM read_parquet({sql_string(source)})
                WHERE symbol = ?
                ORDER BY {order_by}
                """,
                [symbol],
            ).fetch_df()
        finally:
            con.close()

    def _load_persisted_target(
        self,
        timeframe: Timeframe,
        target_date: date,
        symbol: str,
    ) -> pd.DataFrame:
        feature_path = self.store.paths.feature_file(timeframe, target_date)
        if not feature_path.is_file():
            raise FileNotFoundError(f"feature partition is missing: {feature_path}")
        con = connect_utc(":memory:")
        try:
            order_by = "timestamp_utc"
            if timeframe != Timeframe.DAY_1:
                order_by = "session_segment, timestamp_utc"
            return con.execute(
                f"""
                SELECT *
                FROM read_parquet({sql_string(feature_path)})
                WHERE symbol = ?
                ORDER BY {order_by}
                """,
                [symbol],
            ).fetch_df()
        finally:
            con.close()

    def verify(
        self,
        *,
        timeframe: Timeframe,
        target_date: date,
        symbol: str,
        atol: float = 1e-10,
        rtol: float = 1e-10,
    ) -> FeatureContinuityResult:
        clean_symbol = str(symbol).strip()
        if not clean_symbol:
            raise ValueError("symbol cannot be blank")

        anchor = self.materializer.latest_anchor_before(timeframe, target_date)
        if anchor is None:
            raise ValueError(
                f"no monthly {timeframe.value} feature-state anchor exists before {target_date}"
            )
        anchor_date, anchor_path = anchor
        engine, payload = self.materializer.checkpoints.read(
            anchor_path,
            expected_timeframe=timeframe,
        )
        if date.fromisoformat(str(payload["as_of_date"])) != anchor_date:
            raise ValueError("feature-state anchor date mismatch")

        sessions = self.calendar.sessions_in_range(anchor_date + timedelta(days=1), target_date)
        target_records: list[dict[str, object]] = []
        replay_source_rows = 0
        for trading_date in sessions:
            bars = self._load_symbol_source(timeframe, trading_date, clean_symbol)
            replay_source_rows += len(bars)
            has_segment = "session_segment" in bars.columns
            for row in bars.itertuples(index=False):
                segment = str(row.session_segment) if has_segment else None
                values = engine.update(
                    symbol=clean_symbol,
                    state_key=feature_stream_key(clean_symbol, segment),
                    timestamp_utc=row.timestamp_utc,
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=float(row.volume),
                )
                if trading_date != target_date:
                    continue
                record: dict[str, object] = {
                    "symbol": clean_symbol,
                    "timestamp_utc": row.timestamp_utc,
                }
                if has_segment:
                    record["session_segment"] = segment
                record.update({name: values[name] for name in self.feature_names})
                target_records.append(record)

        key_columns = ["symbol", "timestamp_utc"]
        if timeframe != Timeframe.DAY_1:
            key_columns.append("session_segment")
        expected = pd.DataFrame.from_records(target_records)
        persisted = self._load_persisted_target(timeframe, target_date, clean_symbol)
        if expected.empty or persisted.empty:
            return FeatureContinuityResult(
                timeframe=timeframe,
                symbol=clean_symbol,
                anchor_date=anchor_date,
                target_date=target_date,
                replay_sessions=len(sessions),
                replay_source_rows=replay_source_rows,
                target_rows=0,
                features_compared=len(self.feature_names),
                maximum_abs_diff=0.0,
                failed_features=tuple(self.feature_names),
                key_match=False,
            )

        expected = expected.sort_values(key_columns, kind="stable").reset_index(drop=True)
        persisted = persisted.sort_values(key_columns, kind="stable").reset_index(drop=True)
        key_match = len(expected) == len(persisted)
        if key_match:
            key_match = all(
                market_key_series_equal(expected[column], persisted[column], column)
                for column in key_columns
            )

        failed: list[str] = []
        maximum_abs_diff = 0.0
        if len(expected) == len(persisted):
            for name in self.feature_names:
                expected_values = expected[name].to_numpy(dtype="float64")
                actual_values = persisted[name].to_numpy(dtype="float64")
                finite = np.isfinite(expected_values) & np.isfinite(actual_values)
                if finite.any():
                    maximum_abs_diff = max(
                        maximum_abs_diff,
                        float(np.max(np.abs(expected_values[finite] - actual_values[finite]))),
                    )
                if not np.allclose(
                    expected_values,
                    actual_values,
                    atol=atol,
                    rtol=rtol,
                    equal_nan=True,
                ):
                    failed.append(name)
        else:
            failed.extend(self.feature_names)

        return FeatureContinuityResult(
            timeframe=timeframe,
            symbol=clean_symbol,
            anchor_date=anchor_date,
            target_date=target_date,
            replay_sessions=len(sessions),
            replay_source_rows=replay_source_rows,
            target_rows=len(expected),
            features_compared=len(self.feature_names),
            maximum_abs_diff=maximum_abs_diff,
            failed_features=tuple(failed),
            key_match=key_match,
        )
