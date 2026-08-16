from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.incremental import IncrementalFeatureEngine, feature_stream_key
from packages.features.materialization import ACTIVE_FEATURE_PERSISTENCE_POLICY
from packages.features.partition_store import (
    FeaturePartitionManifest,
    FeaturePartitionStore,
    sha256_file,
)
from packages.features.state_checkpoint import (
    FeatureStateCheckpointStore,
    feature_state_fingerprint,
)


class FeatureBootstrapRequired(RuntimeError):
    pass


class FeatureReplayRequired(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FeatureSessionMaterializationResult:
    timeframe: Timeframe
    trading_date: date
    row_count: int
    symbol_count: int
    feature_path: Path
    input_state_fingerprint: str
    output_state_fingerprint: str


FeatureProgressCallback = Callable[[FeatureSessionMaterializationResult, int, int], None]


@dataclass(frozen=True, slots=True)
class FeatureRangeMaterializationResult:
    timeframe: Timeframe
    requested_start: date
    requested_end: date
    effective_start: date | None
    effective_end: date | None
    sessions_processed: int
    rows_processed: int
    checkpoint_as_of: date | None


class HistoricalFeatureMaterializer:
    """Exact chronological feature persistence using the live-compatible state engine.

    A first historical build bootstraps explicitly from the ATLAS history origin.
    Intraday recursive state is isolated by exact provider symbol + Phase 3 session
    segment. Durable state is checkpointed at month-end replay anchors and at the end
    of each requested run rather than after every session, avoiding excessive gzip
    checkpoint churn while limiting crash replay to at most the current month.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.partition_store = FeaturePartitionStore(settings)
        self.checkpoints = FeatureStateCheckpointStore()
        self.paths = self.partition_store.paths
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        self.feature_names = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]

    def _validate_tier(self, timeframe: Timeframe, *, allow_candidate: bool) -> None:
        tier = ACTIVE_FEATURE_PERSISTENCE_POLICY.tier_for(timeframe)
        if tier == "permanent":
            return
        if tier == "benchmark_candidate" and allow_candidate:
            return
        raise ValueError(
            f"historical feature persistence is not enabled for {timeframe.value}; tier={tier}"
        )

    def _load_source(self, timeframe: Timeframe, trading_date: date) -> pd.DataFrame:
        source = self.partition_store.source_path(timeframe, trading_date)
        if not source.is_file():
            raise FileNotFoundError(f"feature source partition is missing: {source}")
        con = connect_utc(":memory:")
        try:
            if timeframe == Timeframe.DAY_1:
                select_columns = "symbol, timestamp_utc, high, low, close, volume"
                order_columns = "symbol, timestamp_utc"
            else:
                select_columns = "symbol, timestamp_utc, session_segment, high, low, close, volume"
                order_columns = "symbol, session_segment, timestamp_utc"
            return con.execute(
                f"""
                SELECT {select_columns}
                FROM read_parquet({sql_string(source)})
                ORDER BY {order_columns}
                """
            ).fetch_df()
        finally:
            con.close()

    @staticmethod
    def _update_engine(
        engine: IncrementalFeatureEngine,
        bars: pd.DataFrame,
        feature_names: list[str],
    ) -> pd.DataFrame:
        has_segment = "session_segment" in bars.columns
        records: list[dict[str, object]] = []
        for row in bars.itertuples(index=False):
            symbol = str(row.symbol)
            segment = str(row.session_segment) if has_segment else None
            state_key = feature_stream_key(symbol, segment)
            values = engine.update(
                symbol=symbol,
                state_key=state_key,
                timestamp_utc=row.timestamp_utc,
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
            record: dict[str, object] = {
                "symbol": symbol,
                "timestamp_utc": row.timestamp_utc,
            }
            if has_segment:
                record["session_segment"] = segment
            for name in feature_names:
                record[name] = values[name]
            records.append(record)
        columns = ["symbol", "timestamp_utc"]
        if has_segment:
            columns.append("session_segment")
        columns.extend(feature_names)
        return pd.DataFrame.from_records(records, columns=columns)

    def _is_last_exchange_session_of_month(self, trading_date: date) -> bool:
        future = self.calendar.sessions_in_range(
            trading_date + timedelta(days=1),
            trading_date + timedelta(days=10),
        )
        return not future or future[0].month != trading_date.month

    def _write_state_checkpoint(
        self,
        engine: IncrementalFeatureEngine,
        *,
        timeframe: Timeframe,
        trading_date: date,
        write_monthly_anchor: bool,
    ) -> str:
        current = self.paths.feature_current_state_file(timeframe)
        fingerprint = self.checkpoints.write(
            current,
            engine,
            timeframe=timeframe,
            as_of_date=trading_date.isoformat(),
        )
        if write_monthly_anchor:
            monthly = self.paths.feature_monthly_state_file(timeframe, trading_date)
            monthly_fingerprint = self.checkpoints.write(
                monthly,
                engine,
                timeframe=timeframe,
                as_of_date=trading_date.isoformat(),
            )
            if monthly_fingerprint != fingerprint:
                raise RuntimeError("monthly feature-state anchor fingerprint mismatch")
        return fingerprint

    def materialize_session(
        self,
        engine: IncrementalFeatureEngine,
        *,
        timeframe: Timeframe,
        trading_date: date,
        input_as_of: str,
    ) -> FeatureSessionMaterializationResult:
        input_state_fingerprint = feature_state_fingerprint(
            engine,
            timeframe=timeframe,
            as_of_date=input_as_of,
        )
        bars = self._load_source(timeframe, trading_date)
        features = self._update_engine(engine, bars, self.feature_names)
        output_state_fingerprint = feature_state_fingerprint(
            engine,
            timeframe=timeframe,
            as_of_date=trading_date.isoformat(),
        )
        manifest: FeaturePartitionManifest = self.partition_store.write(
            features,
            timeframe=timeframe,
            trading_date=trading_date,
            input_state_fingerprint=input_state_fingerprint,
            output_state_fingerprint=output_state_fingerprint,
        )
        return FeatureSessionMaterializationResult(
            timeframe=timeframe,
            trading_date=trading_date,
            row_count=manifest.row_count,
            symbol_count=manifest.symbol_count,
            feature_path=Path(manifest.feature_path),
            input_state_fingerprint=input_state_fingerprint,
            output_state_fingerprint=output_state_fingerprint,
        )

    def _persist_anchor_if_needed(
        self,
        engine: IncrementalFeatureEngine,
        *,
        timeframe: Timeframe,
        trading_date: date,
        output_state_fingerprint: str,
        is_final_session: bool,
    ) -> date | None:
        month_end = self._is_last_exchange_session_of_month(trading_date)
        if not month_end and not is_final_session:
            return None
        checkpoint_fingerprint = self._write_state_checkpoint(
            engine,
            timeframe=timeframe,
            trading_date=trading_date,
            write_monthly_anchor=month_end,
        )
        if checkpoint_fingerprint != output_state_fingerprint:
            raise RuntimeError("persisted feature-state checkpoint fingerprint mismatch")
        return trading_date

    def _load_current(
        self,
        timeframe: Timeframe,
    ) -> tuple[IncrementalFeatureEngine, date | None]:
        path = self.paths.feature_current_state_file(timeframe)
        if not path.is_file():
            return IncrementalFeatureEngine(), None
        engine, payload = self.checkpoints.read(path, expected_timeframe=timeframe)
        raw_as_of = payload.get("as_of_date")
        if not raw_as_of:
            raise ValueError("feature current-state checkpoint is missing as_of_date")
        return engine, date.fromisoformat(str(raw_as_of))

    def _monthly_anchors(self, timeframe: Timeframe) -> list[tuple[date, Path]]:
        current = self.paths.feature_current_state_file(timeframe)
        root = current.parent / "monthly"
        anchors: list[tuple[date, Path]] = []
        if not root.exists():
            return anchors
        for path in root.glob("*/*.json.gz"):
            try:
                anchor_date = date.fromisoformat(path.name.removesuffix(".json.gz"))
            except ValueError:
                continue
            anchors.append((anchor_date, path))
        anchors.sort(key=lambda item: item[0])
        return anchors

    def latest_anchor_before(
        self,
        timeframe: Timeframe,
        trading_date: date,
    ) -> tuple[date, Path] | None:
        eligible = [item for item in self._monthly_anchors(timeframe) if item[0] < trading_date]
        return eligible[-1] if eligible else None

    def stale_source_sessions(
        self,
        *,
        timeframe: Timeframe,
        start: date,
        end: date,
    ) -> tuple[date, ...]:
        stale: list[date] = []
        for trading_date in self.calendar.sessions_in_range(start, end):
            source = self.partition_store.source_path(timeframe, trading_date)
            if not source.is_file():
                stale.append(trading_date)
                continue
            try:
                manifest = self.partition_store.read_manifest(timeframe, trading_date)
            except (ValueError, TypeError):
                stale.append(trading_date)
                continue
            if manifest is None or manifest.source_sha256 != sha256_file(source):
                stale.append(trading_date)
        return tuple(stale)

    def replay_from_correction(
        self,
        *,
        timeframe: Timeframe,
        corrected_date: date,
        end: date,
        history_start: date,
        allow_candidate: bool = False,
        progress: FeatureProgressCallback | None = None,
    ) -> FeatureRangeMaterializationResult:
        if end < corrected_date:
            raise ValueError("replay end precedes corrected session")
        if corrected_date < history_start:
            raise ValueError("corrected session precedes feature history origin")
        self._validate_tier(timeframe, allow_candidate=allow_candidate)

        anchor = self.latest_anchor_before(timeframe, corrected_date)
        if anchor is None:
            engine = IncrementalFeatureEngine()
            replay_start = history_start
            input_as_of = "genesis"
        else:
            anchor_date, anchor_path = anchor
            engine, payload = self.checkpoints.read(anchor_path, expected_timeframe=timeframe)
            if date.fromisoformat(str(payload["as_of_date"])) != anchor_date:
                raise ValueError("monthly feature-state anchor date mismatch")
            replay_start = anchor_date + timedelta(days=1)
            input_as_of = anchor_date.isoformat()

        sessions = self.calendar.sessions_in_range(replay_start, end)
        rows_processed = 0
        effective_start: date | None = None
        effective_end: date | None = None
        checkpoint_as_of: date | None = anchor[0] if anchor is not None else None
        total = len(sessions)
        for index, trading_date in enumerate(sessions, start=1):
            result = self.materialize_session(
                engine,
                timeframe=timeframe,
                trading_date=trading_date,
                input_as_of=input_as_of,
            )
            rows_processed += result.row_count
            effective_start = effective_start or trading_date
            effective_end = trading_date
            input_as_of = trading_date.isoformat()
            persisted = self._persist_anchor_if_needed(
                engine,
                timeframe=timeframe,
                trading_date=trading_date,
                output_state_fingerprint=result.output_state_fingerprint,
                is_final_session=index == total,
            )
            checkpoint_as_of = persisted or checkpoint_as_of
            if progress is not None:
                progress(result, index, total)

        return FeatureRangeMaterializationResult(
            timeframe=timeframe,
            requested_start=corrected_date,
            requested_end=end,
            effective_start=effective_start,
            effective_end=effective_end,
            sessions_processed=len(sessions),
            rows_processed=rows_processed,
            checkpoint_as_of=checkpoint_as_of,
        )

    def materialize_range(
        self,
        *,
        timeframe: Timeframe,
        start: date,
        end: date,
        bootstrap_from_empty: bool = False,
        allow_candidate: bool = False,
        progress: FeatureProgressCallback | None = None,
    ) -> FeatureRangeMaterializationResult:
        if end < start:
            raise ValueError("feature materialization end precedes start")
        self._validate_tier(timeframe, allow_candidate=allow_candidate)
        requested_sessions = self.calendar.sessions_in_range(start, end)
        if not requested_sessions:
            return FeatureRangeMaterializationResult(
                timeframe=timeframe,
                requested_start=start,
                requested_end=end,
                effective_start=None,
                effective_end=None,
                sessions_processed=0,
                rows_processed=0,
                checkpoint_as_of=None,
            )

        engine, checkpoint_date = self._load_current(timeframe)
        if checkpoint_date is None and not bootstrap_from_empty:
            raise FeatureBootstrapRequired(
                "no feature-state checkpoint exists; exact recursive history requires "
                "bootstrap_from_empty=True at the chosen ATLAS history origin"
            )

        if checkpoint_date is not None and checkpoint_date >= end:
            return FeatureRangeMaterializationResult(
                timeframe=timeframe,
                requested_start=start,
                requested_end=end,
                effective_start=None,
                effective_end=None,
                sessions_processed=0,
                rows_processed=0,
                checkpoint_as_of=checkpoint_date,
            )

        if checkpoint_date is None:
            sessions = requested_sessions
            input_as_of = "genesis"
        else:
            resume_start = checkpoint_date + timedelta(days=1)
            sessions = self.calendar.sessions_in_range(resume_start, end)
            input_as_of = checkpoint_date.isoformat()

        rows_processed = 0
        effective_start: date | None = None
        effective_end: date | None = None
        checkpoint_as_of = checkpoint_date
        total = len(sessions)
        for index, trading_date in enumerate(sessions, start=1):
            result = self.materialize_session(
                engine,
                timeframe=timeframe,
                trading_date=trading_date,
                input_as_of=input_as_of,
            )
            rows_processed += result.row_count
            effective_start = effective_start or trading_date
            effective_end = trading_date
            input_as_of = trading_date.isoformat()
            persisted = self._persist_anchor_if_needed(
                engine,
                timeframe=timeframe,
                trading_date=trading_date,
                output_state_fingerprint=result.output_state_fingerprint,
                is_final_session=index == total,
            )
            checkpoint_as_of = persisted or checkpoint_as_of
            if progress is not None:
                progress(result, index, total)

        return FeatureRangeMaterializationResult(
            timeframe=timeframe,
            requested_start=start,
            requested_end=end,
            effective_start=effective_start,
            effective_end=effective_end,
            sessions_processed=len(sessions),
            rows_processed=rows_processed,
            checkpoint_as_of=checkpoint_as_of,
        )
