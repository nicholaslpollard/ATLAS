from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.features.historical_materializer import HistoricalFeatureMaterializer
from packages.features.incremental import IncrementalFeatureEngine
from packages.features.partition_store import FeaturePartitionStore, sha256_file
from packages.features.state_checkpoint import feature_state_fingerprint


PERMANENT_FEATURE_TIMEFRAMES = (
    Timeframe.DAY_1,
    Timeframe.HOUR_4,
    Timeframe.HOUR_1,
)


@dataclass(frozen=True, slots=True)
class FeatureTimeframeAudit:
    timeframe: Timeframe
    expected_sessions: int
    manifest_sessions: int
    total_rows: int
    missing_sources: tuple[date, ...]
    missing_features: tuple[date, ...]
    missing_manifests: tuple[date, ...]
    invalid_manifests: tuple[date, ...]
    source_hash_mismatches: tuple[date, ...]
    feature_hash_mismatches: tuple[date, ...]
    state_chain_breaks: tuple[date, ...]
    checkpoint_as_of: date | None
    checkpoint_matches_tail: bool

    @property
    def passed(self) -> bool:
        return not any(
            (
                self.missing_sources,
                self.missing_features,
                self.missing_manifests,
                self.invalid_manifests,
                self.source_hash_mismatches,
                self.feature_hash_mismatches,
                self.state_chain_breaks,
            )
        ) and self.manifest_sessions == self.expected_sessions and self.checkpoint_matches_tail


@dataclass(frozen=True, slots=True)
class FeatureLakeAudit:
    start: date
    end: date
    timeframes: tuple[FeatureTimeframeAudit, ...]

    @property
    def expected_sessions(self) -> int:
        return self.timeframes[0].expected_sessions if self.timeframes else 0

    @property
    def total_rows(self) -> int:
        return sum(item.total_rows for item in self.timeframes)

    @property
    def passed(self) -> bool:
        return bool(self.timeframes) and all(item.passed for item in self.timeframes)


class FeatureLakeAuditor:
    """Audit permanent feature coverage, file integrity, and recursive-state lineage."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.store = FeaturePartitionStore(settings)
        self.materializer = HistoricalFeatureMaterializer(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)

    def audit_timeframe(
        self,
        timeframe: Timeframe,
        *,
        start: date,
        end: date,
        deep_feature_sha: bool = False,
    ) -> FeatureTimeframeAudit:
        sessions = self.calendar.sessions_in_range(start, end)
        missing_sources: list[date] = []
        missing_features: list[date] = []
        missing_manifests: list[date] = []
        invalid_manifests: list[date] = []
        source_hash_mismatches: list[date] = []
        feature_hash_mismatches: list[date] = []
        state_chain_breaks: list[date] = []
        manifest_sessions = 0
        total_rows = 0

        previous_output = feature_state_fingerprint(
            IncrementalFeatureEngine(),
            timeframe=timeframe,
            as_of_date="genesis",
        )
        tail_output: str | None = None

        for trading_date in sessions:
            source_path = self.store.source_path(timeframe, trading_date)
            feature_path = self.store.paths.feature_file(timeframe, trading_date)
            manifest_path = self.store.paths.feature_manifest_file(timeframe, trading_date)

            if not source_path.is_file():
                missing_sources.append(trading_date)
            if not feature_path.is_file():
                missing_features.append(trading_date)
            if not manifest_path.is_file():
                missing_manifests.append(trading_date)
                continue

            try:
                manifest = self.store.read_manifest(timeframe, trading_date)
            except (ValueError, TypeError, OSError):
                invalid_manifests.append(trading_date)
                continue
            if manifest is None:
                missing_manifests.append(trading_date)
                continue

            manifest_sessions += 1
            total_rows += manifest.row_count

            if manifest.input_state_fingerprint != previous_output:
                state_chain_breaks.append(trading_date)
            previous_output = manifest.output_state_fingerprint
            tail_output = manifest.output_state_fingerprint

            if source_path.is_file() and sha256_file(source_path) != manifest.source_sha256:
                source_hash_mismatches.append(trading_date)

            expected_feature = feature_path.resolve()
            try:
                manifest_feature = Path(manifest.feature_path).resolve()
            except (OSError, RuntimeError):
                manifest_feature = Path(manifest.feature_path)
            if manifest_feature != expected_feature:
                feature_hash_mismatches.append(trading_date)
            elif deep_feature_sha and feature_path.is_file():
                if sha256_file(feature_path) != manifest.feature_sha256:
                    feature_hash_mismatches.append(trading_date)

        checkpoint_as_of: date | None = None
        checkpoint_matches_tail = False
        current = self.store.paths.feature_current_state_file(timeframe)
        if current.is_file() and sessions:
            try:
                _engine, payload = self.materializer.checkpoints.read(
                    current,
                    expected_timeframe=timeframe,
                )
                raw_as_of = payload.get("as_of_date")
                if raw_as_of:
                    checkpoint_as_of = date.fromisoformat(str(raw_as_of))
                checkpoint_matches_tail = (
                    checkpoint_as_of == sessions[-1]
                    and tail_output is not None
                    and payload.get("checkpoint_fingerprint") == tail_output
                )
            except (ValueError, TypeError, OSError):
                checkpoint_matches_tail = False

        return FeatureTimeframeAudit(
            timeframe=timeframe,
            expected_sessions=len(sessions),
            manifest_sessions=manifest_sessions,
            total_rows=total_rows,
            missing_sources=tuple(missing_sources),
            missing_features=tuple(missing_features),
            missing_manifests=tuple(missing_manifests),
            invalid_manifests=tuple(invalid_manifests),
            source_hash_mismatches=tuple(source_hash_mismatches),
            feature_hash_mismatches=tuple(feature_hash_mismatches),
            state_chain_breaks=tuple(state_chain_breaks),
            checkpoint_as_of=checkpoint_as_of,
            checkpoint_matches_tail=checkpoint_matches_tail,
        )

    def audit(
        self,
        *,
        start: date,
        end: date,
        deep_feature_sha: bool = False,
    ) -> FeatureLakeAudit:
        results = tuple(
            self.audit_timeframe(
                timeframe,
                start=start,
                end=end,
                deep_feature_sha=deep_feature_sha,
            )
            for timeframe in PERMANENT_FEATURE_TIMEFRAMES
        )
        return FeatureLakeAudit(start=start, end=end, timeframes=results)
