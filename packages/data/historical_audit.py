from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import DatasetType, Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.ingestion.staging import FlatFileValidator
from packages.schemas.history import HistoricalLakeAuditReport, HistoryLayerAudit, ProviderDatasetAudit


class HistoricalLakeAuditor:
    """Audit historical source/canonical/derived coverage by exchange session."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        cfg = settings.massive.flat_files
        self.validator = FlatFileValidator(validate_gzip_crc=cfg.validate_gzip_crc, count_rows=False)

    @staticmethod
    def _bytes(paths: list[Path]) -> int:
        return sum(path.stat().st_size for path in paths if path.is_file())

    def _layer(
        self,
        name: str,
        sessions: list[date],
        path_for: Callable[[date], Path],
    ) -> HistoryLayerAudit:
        present_paths: list[Path] = []
        missing: list[date] = []
        for session in sessions:
            path = path_for(session)
            if path.is_file():
                present_paths.append(path)
            else:
                missing.append(session)
        return HistoryLayerAudit(
            name=name,
            expected_sessions=len(sessions),
            present_sessions=len(present_paths),
            missing_sessions=missing,
            bytes_on_disk=self._bytes(present_paths),
        )

    def _provider(
        self,
        dataset: DatasetType,
        sessions: list[date],
        *,
        deep_validate: bool,
    ) -> ProviderDatasetAudit:
        present_paths: list[Path] = []
        missing: list[date] = []
        invalid: list[date] = []
        expected_columns = list(self.settings.massive.flat_files.datasets[dataset.value].expected_columns)
        for session in sessions:
            path = self.paths.provider_file(dataset, session)
            if not path.is_file():
                missing.append(session)
                continue
            present_paths.append(path)
            if deep_validate:
                result = self.validator.validate(path, expected_columns=expected_columns)
                if not result.is_valid:
                    invalid.append(session)
        return ProviderDatasetAudit(
            name=dataset.value,
            dataset=dataset,
            expected_sessions=len(sessions),
            present_sessions=len(present_paths),
            missing_sessions=missing,
            invalid_sessions=invalid,
            bytes_on_disk=self._bytes(present_paths),
        )

    def audit(self, start_date: date, end_date: date, *, deep_validate: bool = False) -> HistoricalLakeAuditReport:
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        sessions = self.calendar.sessions_in_range(start_date, end_date)

        provider = {
            "1d": self._provider(DatasetType.STOCK_DAILY_AGGREGATES, sessions, deep_validate=deep_validate),
            "1m": self._provider(DatasetType.STOCK_MINUTE_AGGREGATES, sessions, deep_validate=deep_validate),
        }
        canonical = {
            "1d": self._layer("canonical_1d", sessions, lambda d: self.paths.canonical_file(Timeframe.DAY_1, d)),
            "1m": self._layer("canonical_1m", sessions, lambda d: self.paths.canonical_file(Timeframe.MINUTE_1, d)),
        }
        derived = {
            tf.value: self._layer(f"derived_{tf.value}", sessions, lambda d, tf=tf: self.paths.derived_file(tf, d))
            for tf in (Timeframe.MINUTE_15, Timeframe.HOUR_1, Timeframe.HOUR_4)
        }

        quarantine_sessions: list[date] = []
        quarantined_symbols: set[str] = set()
        for session in sessions:
            registry = self.paths.symbol_quarantine_registry(session)
            if not registry.is_file():
                continue
            try:
                payload = json.loads(registry.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            # Provider ticker case is semantically significant (for example preferred
            # share symbols containing lowercase 'p'), so audit summaries must preserve
            # the exact canonical symbol rather than case-folding quarantine entries.
            symbols = [str(s).strip() for s in payload.get("symbols", []) if str(s).strip()]
            if symbols:
                quarantine_sessions.append(session)
                quarantined_symbols.update(symbols)

        total_bytes = sum(item.bytes_on_disk for item in provider.values())
        total_bytes += sum(item.bytes_on_disk for item in canonical.values())
        total_bytes += sum(item.bytes_on_disk for item in derived.values())
        return HistoricalLakeAuditReport(
            start_date=start_date,
            end_date=end_date,
            generated_at_utc=datetime.now(UTC),
            exchange_sessions=sessions,
            provider=provider,
            canonical=canonical,
            derived=derived,
            quarantine_sessions=quarantine_sessions,
            quarantined_symbols=sorted(quarantined_symbols),
            total_bytes_on_disk=total_bytes,
        )

    @staticmethod
    def persist(report: HistoricalLakeAuditReport, path: Path) -> None:
        path = Path(path)
        atomic_write_text(path, report.model_dump_json(indent=2) + "\n")
